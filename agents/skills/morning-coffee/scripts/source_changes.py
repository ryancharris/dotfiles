"""Material source comparisons, independent of collector prose and UI labels."""
from datetime import datetime
import re


PR_SECTIONS = ('reviews', 'authored_prs')


def code(value):
    return str(value or '').strip().upper()


def checks(value):
    """Ignore dictionary order and derived `state`; unknown evidence stays unknown."""
    if not isinstance(value, dict):
        return None
    keys = ('passing', 'failing', 'pending', 'total')
    if any(not isinstance(value.get(key), int) or isinstance(value[key], bool)
           or value[key] < 0 for key in keys):
        return None
    return {key: value.get(key, 0) for key in (*keys, 'unknown')}


def check_label(value):
    text = f"{value['passing']}/{value['total']} passing · {value['failing']} failing · {value['pending']} pending"
    return text + (f" · {value['unknown']} unknown" if value['unknown'] else '')


def source_fields(old, new, section):
    """Return concise provider deltas; keep the full generated-text diff in the audit."""
    result = []

    def add(label, before, after):
        if before != after:
            result.append({'label': label, 'before': before, 'after': after})

    if section in PR_SECTIONS:
        for key, label in [('reviewDecision', 'Review decision'), ('mergeStateStatus', 'Merge status')]:
            before, after = code(old.get(key)), code(new.get(key))
            # Both entering and leaving UNKNOWN are evidence availability, not
            # a verified mergeability transition. Other actual changes survive.
            if key == 'mergeStateStatus' and (not before or not after or 'UNKNOWN' in (before, after)):
                continue
            add(label, before or 'No decision', after or 'No decision')
        before, after = checks(old.get('ci')), checks(new.get('ci'))
        if before is not None and after is not None and before != after:
            add('Checks', check_label(before), check_label(after))
        if section == 'reviews':
            add('Request', code(old.get('queue')), code(new.get('queue')))
            add('Requested teams', ', '.join(sorted(set(old.get('teams', [])))),
                ', '.join(sorted(set(new.get('teams', [])))))
        else:
            add('Draft', bool(old.get('isDraft')), bool(new.get('isDraft')))
    elif section == 'priorities':
        if new.get('verified') is True:
            add('Status', code(old.get('status') or 'open').lower(), code(new.get('status') or 'open').lower())
    elif section == 'rfcs':
        add('Approved by you', bool(old.get('user_approved')), bool(new.get('user_approved')))
        before = {a['url']: a for a in old.get('approvals', []) if a.get('url')}
        for approval in new.get('approvals', []):
            prior = before.get(approval.get('url'))
            if not prior or prior.get('deleted') or approval.get('deleted'):
                continue
            a, b = code(prior.get('status')), code(approval.get('status'))
            if a in ('', 'UNAVAILABLE', 'UNKNOWN') or b in ('', 'UNAVAILABLE', 'UNKNOWN'):
                continue
            add((approval.get('scope') or 'Stakeholder') + ' review', prior['status'], approval['status'])
        # Only explicit request categories, never generated relationship prose.
        for key in ('request_label', 'relationship'):
            a, b = old.get(key), new.get(key)
            if a in ('Optional', 'Direct request', 'Request status unknown') and b in ('Optional', 'Direct request', 'Request status unknown'):
                add('Personal request', a, b)
                break
    elif section == 'oncall':
        for key, label in [('state', 'State'), ('responder', 'Responder'), ('shift', 'Shift')]:
            add(label, old.get(key, ''), new.get(key, ''))
        # Organization-wide incident counts are coverage, not user work changes.
    elif section == 'agenda':
        def stamp(value):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                return value
        # The generated time label is not independent calendar evidence.
        for key, label in [('start', 'Start'), ('end', 'End')]:
            if stamp(old.get(key)) != stamp(new.get(key)):
                add(label, old.get(key, ''), new.get(key, ''))
        for key, label in [('title', 'Title'), ('free', 'Free'), ('tentative', 'Tentative'), ('join_url', 'Call link')]:
            add(label, old.get(key, False if key in ('free', 'tentative') else ''),
                new.get(key, False if key in ('free', 'tentative') else ''))
    return result


def legacy_fields(row):
    """Read saved pre-semantic audits conservatively without reparsing source prose."""
    fields = []
    section = row.get('section')
    allowed = {
        'Daily priorities': {'Status'},
        'Reviews waiting': {'Queue', 'Teams', 'Readiness', 'Review decision', 'Merge status', 'Checks'},
        'My open PRs': {'Isdraft', 'Readiness', 'Review decision', 'Merge status', 'Checks'},
        'RFCs to review': {'Approved by you', 'Relationship'},
        'Today': {'Time', 'Free', 'Tentative', 'Call link'},
        'On call & incidents': {'State', 'Responder', 'Shift'},
    }
    for field in row.get('fields', []):
        label = field.get('label')
        if label not in allowed.get(section, set()):
            continue
        before, after = field.get('before'), field.get('after')
        if section in ('Reviews waiting', 'My open PRs'):
            if label == 'Readiness':
                # Detailed readiness is generated from other source fields. A
                # legacy bare category can still describe a verified change.
                if 'facts:' in str(before).lower() or 'facts:' in str(after).lower():
                    continue
                before = re.sub(r'^status:\s*', '', str(before), flags=re.I)
                after = re.sub(r'^status:\s*', '', str(after), flags=re.I)
            if label in ('Readiness', 'Review decision', 'Merge status', 'Queue'):
                before, after = code(before), code(after)
                if label in ('Readiness', 'Merge status') and 'UNKNOWN' in (before, after):
                    continue
            if label == 'Checks':
                def parse(value):
                    return checks({k: int(v) for k, v in re.findall(r'\b(passing|failing|pending|total|unknown):\s*(\d+)\b', str(value))})
                a, b = parse(before), parse(after)
                if a is None or b is None or a == b:
                    continue
                before, after = check_label(a), check_label(b)
        if section == 'Daily priorities':
            if row.get('verified') is not True:
                continue
            before = 'open' if code(before) in ('', 'UNAVAILABLE', 'NONE') else str(before).lower()
            after = 'open' if code(after) in ('', 'UNAVAILABLE', 'NONE') else str(after).lower()
        if section == 'RFCs to review' and label == 'Relationship':
            if before not in ('Optional', 'Direct request') or after not in ('Optional', 'Direct request'):
                continue
        if before != after:
            fields.append(dict(field, before=before, after=after))
    return fields
