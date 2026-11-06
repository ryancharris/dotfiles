#!/usr/bin/env python3
"""Select RFC reviews and recent activity from fully paginated Notion metadata.

Provider calls stay in the assistant. This helper makes selection and publication
completeness reproducible without credentials or a second Notion integration.
"""
import argparse
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

STATUSES = {'In-Review', 'Drafting', 'Paused', 'Approved', 'Superseded', 'Obsolete', 'Withdrawn'}


def canonical_rfc_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.hostname not in ('app.notion.com', 'www.notion.so', 'notion.so'):
        raise ValueError('RFC discovery requires a canonical Notion page URL.')
    match = re.search(r'([a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})$', parsed.path)
    if not match:
        raise ValueError('RFC discovery requires a Notion page ID.')
    return 'https://app.notion.com/p/' + match[1].replace('-', '').lower()


def plain_title(value):
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, data):
            self.parts.append(data)
    parser = Text()
    parser.feed(str(value or 'Untitled RFC'))
    return ' '.join(unescape(''.join(parser.parts)).split()) or 'Untitled RFC'


def instant(value, zone):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            if len(value) != 10:
                return None
            parsed = parsed.replace(tzinfo=zone)
        return parsed
    except ValueError:
        return None


def urls(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError('RFC approval links are incomplete or malformed.')
    return list(dict.fromkeys(value))


def select(discovery, now, timezone='America/Toronto', recent_days=14):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError('RFC selection requires an offset-aware report time.')
    if type(recent_days) is not int or recent_days < 1:
        raise ValueError('The recent-activity window must be a positive number of days.')
    source = discovery.get('data_source_url')
    if not isinstance(source, str) or not source.startswith('collection://'):
        raise ValueError('Fetch the RFC data-source schema before selection.')
    rows = discovery.get('rows')
    if not isinstance(rows, list):
        raise ValueError('RFC discovery must contain paginated metadata rows.')
    zone = ZoneInfo(timezone)
    start = now - timedelta(days=recent_days)
    warnings, unique = [], {}
    if discovery.get('has_more') is not False:
        warnings.append('RFC discovery pagination is incomplete.')
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('RFC metadata rows must be objects.')
        url = canonical_rfc_url(row.get('url', ''))
        if row.get('data_source_url', source) != source:
            raise ValueError('An RFC row belongs to a different data source.')
        row = dict(row, url=url)
        if url in unique:
            if unique[url] != row:
                raise ValueError('Conflicting duplicate RFC metadata; re-fetch before selecting.')
            continue
        unique[url] = row
    expected = discovery.get('expected_count')
    if expected is not None and (type(expected) is not int or expected < len(unique)):
        raise ValueError('RFC discovery count does not match its source scope.')
    if expected is not None and expected != len(unique):
        warnings.append('RFC discovery returned fewer unique rows than its source count.')
    reviews, activity = [], []
    for url, row in unique.items():
        status = row.get('RFC Status')
        if status not in STATUSES:
            warnings.append('An RFC has an unknown lifecycle: ' + url)
            continue
        submitted = instant(row.get('date:Submitted for review:start'), zone)
        created = instant(row.get('Created time') or row.get('createdTime'), zone)
        edited = instant(row.get('Last edited time'), zone)
        # Lifecycle defines open review work. Age and missing dates cannot hide it.
        if status != 'In-Review' and not (edited and start <= edited <= now):
            continue
        if status == 'In-Review' and (submitted is None or submitted > now):
            warnings.append('Review submission date unavailable or in the future: ' + url)
        try:
            approvals = urls(row.get('Approvals ', []))
        except (ValueError, TypeError):
            approvals = None
            warnings.append('RFC approval links unavailable: ' + url)
        item = {'id': url, 'url': url, 'title': plain_title(row.get('Name')),
                'lifecycle': status, 'submitted_at': submitted.isoformat() if submitted else None,
                'updated_at': edited.isoformat() if edited else None,
                'created_at': created.isoformat() if created else None,
                'approval_urls': approvals}
        if status == 'In-Review':
            item['date_label'] = ('Submitted ' + submitted.astimezone(zone).strftime('%Y-%m-%d %H:%M')
                                  if submitted and submitted <= now else
                                  'Submission date unavailable' + (' · created ' + created.astimezone(zone).strftime('%Y-%m-%d') if created else ''))
            reviews.append(item)
        else:
            item['date_label'] = 'Updated ' + edited.astimezone(zone).strftime('%Y-%m-%d %H:%M')
            activity.append(item)
    reviews.sort(key=lambda r: (instant(r['submitted_at'], zone).timestamp() if r['submitted_at'] else float('inf'), r['url']))
    activity.sort(key=lambda r: (instant(r['updated_at'], zone).timestamp(), r['url']), reverse=True)
    manifest = {'complete': discovery.get('has_more') is False and (expected is None or expected == len(unique)) and all(row.get('RFC Status') in STATUSES for row in unique.values()),
                'data_source_url': source, 'checked_at': discovery.get('checked_at'),
                'discovered_count': len(unique), 'expected_count': expected,
                'review_urls': [r['url'] for r in reviews], 'activity_urls': [r['url'] for r in activity],
                'lifecycles': {url: row.get('RFC Status') for url, row in unique.items()}}
    return {'items': reviews, 'activity': activity, 'discovery': manifest, 'warnings': list(dict.fromkeys(warnings)),
            'window_label': 'All In-Review RFCs',
            'activity_label': 'Recent RFC activity · updated in the past ' + str(recent_days) + ' days'}


def validate_surface(rfcs):
    """Reject a publication that silently omits or misclassifies selected RFCs."""
    manifest = rfcs.get('discovery')
    if manifest is None:
        return  # Read and publish legacy snapshots with their original contract.
    if not isinstance(manifest, dict):
        raise ValueError('RFC discovery manifest must be an object.')
    found = set()
    for field, expected_key in (('items', 'review_urls'), ('activity', 'activity_urls')):
        actual = [canonical_rfc_url(row['url']) for row in rfcs.get(field, [])]
        expected = {canonical_rfc_url(url) for url in manifest[expected_key]}
        if len(actual) != len(set(actual)) or not expected.issubset(actual) or found.intersection(actual):
            raise ValueError('RFC selection is missing, duplicated or in the wrong surface; preserve every selected RFC, including failed hydration placeholders.')
        found.update(actual)
        for row in rfcs.get(field, []):
            url = canonical_rfc_url(row['url'])
            lifecycle = row.get('lifecycle')
            observed = manifest['lifecycles'].get(url)
            retained = url not in expected and row.get('_retained_at') and manifest.get('complete') is not True and observed not in STATUSES
            if not retained and (url not in expected or lifecycle != observed):
                raise ValueError('RFC lifecycle differs from the authoritative discovery manifest.')
            legacy_review = retained and field == 'items' and lifecycle is None
            if not legacy_review and (lifecycle == 'In-Review') != (field == 'items'):
                raise ValueError('Only In-Review RFCs belong in the review queue.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('discovery', type=Path)
    parser.add_argument('--at', required=True, help='Offset-aware report timestamp')
    parser.add_argument('--timezone', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = select(json.loads(args.discovery.read_text()), datetime.fromisoformat(args.at.replace('Z', '+00:00')), args.timezone)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'reviews': len(result['items']), 'activity': len(result['activity']), 'complete': result['discovery']['complete'], 'warnings': result['warnings']}))


if __name__ == '__main__':
    main()
