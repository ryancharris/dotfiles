"""Private, reversible local review marks. Provider approval state stays untouched."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit, urlunsplit


class ReviewError(ValueError):
    pass


def canonical_url(value):
    """Identify a source without transient query, fragment, or trailing slash."""
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ReviewError('A review needs a valid source URL.')
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('invalid source')
        port = parsed.port
        host = parsed.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        if port is not None and port != (443 if parsed.scheme == 'https' else 80):
            host += ':' + str(port)
        path = parsed.path.rstrip('/')
        if parsed.hostname.lower() == 'github.com':
            path = path.lower()
        return urlunsplit((parsed.scheme.lower(), host, path, '', ''))
    except ValueError as error:
        raise ReviewError('A review needs a valid source URL.') from error


def review_key(kind, url):
    if kind not in ('pr', 'rfc'):
        raise ReviewError('Choose a PR or RFC review.')
    return kind + '|' + canonical_url(url)


def _identities(snapshot):
    result = set()
    for kind, section in (('pr', 'reviews'), ('rfc', 'rfcs')):
        for row in (snapshot.get(section) or {}).get('items', []):
            try:
                result.add(review_key(kind, row.get('url')))
            except (ReviewError, AttributeError):
                continue
    return result


def save_review_state(root, snapshot, request, now=None):
    """Append a mark only for a source identity present in this local report."""
    if not isinstance(request, dict) or set(request) != {'kind', 'url', 'done'} or type(request['done']) is not bool:
        raise ReviewError('Send a review kind, source URL, and true or false done state.')
    key = review_key(request['kind'], request['url'])
    if key not in _identities(snapshot):
        raise ReviewError('This review is not listed in this report.')
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ReviewError('Review time must include a timezone.')
    record = {'version': 1, 'kind': request['kind'], 'url': canonical_url(request['url']),
              'done': request['done'], 'updated_at': instant.isoformat()}
    with _locked_store(root) as folder:
        _append_record(folder, record)
    return record


@contextmanager
def _locked_store(root):
    folder = Path(root) / 'review-state'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    fd = os.open(folder / '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield folder
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _append_record(folder, record):
    instant = datetime.fromisoformat(record['updated_at'].replace('Z', '+00:00'))
    name = instant.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + secrets.token_hex(6) + '.json'
    target, temporary = folder / name, folder / ('.' + name + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _read_review_state(folder):
    result, warnings = {}, []
    for path in sorted(folder.glob('*.json')):
        try:
            record = json.loads(path.read_text())
            if record.get('version') != 1 or type(record.get('done')) is not bool:
                raise ReviewError('Invalid review metadata.')
            stamp = datetime.fromisoformat(record['updated_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ReviewError('Invalid review timestamp.')
            key = review_key(record['kind'], record['url'])
            normalized = {field: record[field] for field in ('version', 'kind', 'url', 'done', 'updated_at')}
            normalized['url'] = canonical_url(record['url'])
            if key not in result or stamp >= datetime.fromisoformat(result[key]['updated_at'].replace('Z', '+00:00')):
                result[key] = normalized
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            warnings.append('An unreadable local review mark was skipped: ' + path.name)
    return result, warnings


def load_review_state(root, with_warnings=False):
    """Read latest valid marks across days, keyed by review_key(kind, source URL)."""
    folder = Path(root) / 'review-state'
    if not folder.exists():
        result, warnings = {}, []
    else:
        with _locked_store(root) as folder:
            result, warnings = _read_review_state(folder)
    return {'state': result, 'warnings': warnings} if with_warnings else result


def _timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return stamp if stamp.tzinfo is not None and stamp.utcoffset() is not None else None
    except ValueError:
        return None


def _event_id(value):
    if isinstance(value, str):
        return bool(value.strip())
    return type(value) is int and value > 0


def _target_matches(kind, row, target, snapshot):
    if not isinstance(target, dict):
        return False
    identity = snapshot.get('review_identity') or {}
    personal = row.get('personalReview') or {}
    if not isinstance(identity, dict):
        identity = {}
    if not isinstance(personal, dict):
        personal = {}
    if kind == 'pr' and target.get('type') == 'user':
        if set(target) != {'type', 'login'}:
            return False
        login = target.get('login')
        current = personal.get('userLogin') or identity.get('github_login')
        return (isinstance(login, str) and isinstance(current, str) and
                bool(login.strip()) and login.casefold() == current.casefold())
    if kind == 'pr' and target.get('type') == 'team':
        if set(target) != {'type', 'slug', 'id', 'name'} or (target.get('name') is not None and not isinstance(target.get('name'), str)):
            return False
        slug, team_id = target.get('slug'), target.get('id')
        if not isinstance(slug, str) or not slug.strip() or not _event_id(team_id):
            return False
        configured = identity.get('github_teams', [])
        teams = list(configured) if isinstance(configured, list) else []
        row_teams = row.get('teams', [])
        if isinstance(row_teams, list):
            teams.extend(team for team in row_teams if isinstance(team, dict) and team.get('verified') is True)
        for team in teams:
            if isinstance(team, str):
                if team.casefold() == slug.casefold():
                    return True
            elif isinstance(team, dict):
                known_slug, known_id = team.get('slug'), team.get('id')
                if (isinstance(known_slug, str) and known_slug.casefold() == slug.casefold() and
                        (known_id is None or str(known_id) == str(team_id))):
                    return True
                if (known_id is not None and str(known_id) == str(team_id) and
                        (known_slug is None or (isinstance(known_slug, str) and known_slug.casefold() == slug.casefold()))):
                    return True
        return False
    if kind == 'rfc' and target.get('type') == 'user':
        if set(target) != {'type', 'id'}:
            return False
        notion_id, current = target.get('id'), identity.get('notion_user_id')
        return isinstance(notion_id, str) and bool(notion_id.strip()) and isinstance(current, str) and notion_id == current
    if kind == 'rfc' and target.get('type') == 'stakeholder_response':
        if (set(target) != {'type', 'response_id', 'respondents', 'verified'} or
                target.get('verified') is not True or not _event_id(target.get('response_id')) or
                not isinstance(target.get('respondents'), list)):
            return False
        current = identity.get('notion_user_id')
        return (isinstance(current, str) and bool(current.strip()) and
                all(isinstance(person, dict) and set(person) == {'type', 'id'} and person.get('type') == 'user'
                    and isinstance(person.get('id'), str) for person in target['respondents']) and
                any(person['id'] == current for person in target['respondents']))
    return False


def _verified_event(kind, row, snapshot):
    url = row.get('url')
    try:
        parsed = urlsplit(url) if isinstance(url, str) else None
        if parsed is None or parsed.scheme.lower() != 'https' or not parsed.hostname:
            return None
        canonical = canonical_url(url)
        if kind == 'pr' and (parsed.hostname.lower() != 'github.com' or
                             not re.fullmatch(r'/[\w.-]+/[\w.-]+/pull/[1-9]\d*/?', parsed.path, re.IGNORECASE)):
            return None
        local = row.get('localReRequest')
        if isinstance(local, dict):
            if (set(local) != {'verified', 'event_id', 'requested_at', 'url', 'target', 'current'} or
                    local.get('verified') is not True or local.get('current') is not True or
                    not _event_id(local.get('event_id')) or
                    not isinstance(local.get('url'), str) or
                    canonical_url(local['url']) != canonical):
                return None
            requested_at = _timestamp(local.get('requested_at'))
            target = local.get('target')
            evidence_id = local.get('event_id')
        else:
            personal = row.get('personalReview') or {}
            if not isinstance(personal, dict):
                return None
            evidence = personal.get('reRequestEvidence')
            if (personal.get('reRequested') is not True or personal.get('coverage') != 'complete' or
                    personal.get('timelineCoverage') != 'complete' or not isinstance(evidence, dict)):
                return None
            evidence_id = evidence.get('id') if _event_id(evidence.get('id')) else evidence.get('nodeId')
            if not _event_id(evidence_id):
                return None
            requested_at = _timestamp(evidence.get('createdAt'))
            target = evidence.get('target')
        if requested_at is None or not _target_matches(kind, row, target, snapshot):
            return None
        return {'kind': kind, 'url': canonical, 'event_id': str(evidence_id),
                'requested_at': requested_at, 'target': target}
    except (ReviewError, TypeError, ValueError):
        return None


def verified_re_request(kind, row, snapshot):
    """Return verified event provenance for a PR/RFC row, without reading or writing marks."""
    if kind not in ('pr', 'rfc') or not isinstance(row, dict) or not isinstance(snapshot, dict):
        return None
    return _verified_event(kind, row, snapshot)


def apply_verified_re_requests(root, snapshot, now=None):
    """Append local reopen marks only for verified later requests to the current reviewer."""
    if not isinstance(snapshot, dict):
        return {'changed': 0, 'warnings': ['The review snapshot could not be read.']}
    instant = now or datetime.now(timezone.utc)
    if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
        raise ReviewError('Review time must include a timezone.')
    changed = 0
    try:
        with _locked_store(root) as folder:
            state, warnings = _read_review_state(folder)
            if warnings:
                return {'changed': 0, 'warnings': warnings}
            candidates = []
            for kind, section in (('pr', 'reviews'), ('rfc', 'rfcs')):
                section_data = snapshot.get(section)
                rows = section_data.get('items', []) if isinstance(section_data, dict) else []
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    event = verified_re_request(kind, row, snapshot)
                    if event is None or event['requested_at'] > instant:
                        continue
                    key = review_key(kind, event['url'])
                    marked = state.get(key)
                    if not marked or marked['done'] is not True:
                        continue
                    updated = _timestamp(marked['updated_at'])
                    if updated is None or event['requested_at'] <= updated:
                        continue
                    candidates.append((key, event))
            for key, event in candidates:
                # Re-read after each append so duplicate rows/events in a snapshot are idempotent.
                state, warnings = _read_review_state(folder)
                if warnings:
                    return {'changed': changed, 'warnings': warnings}
                marked = state.get(key)
                if not marked or marked['done'] is not True:
                    continue
                updated = _timestamp(marked['updated_at'])
                if updated is None or event['requested_at'] <= updated:
                    continue
                record = {'version': 1, 'kind': event['kind'], 'url': event['url'],
                          'done': False, 'updated_at': instant.isoformat()}
                _append_record(folder, record)
                state[key] = record
                changed += 1
            return {'changed': changed, 'warnings': []}
    except OSError as error:
        return {'changed': changed, 'warnings': ['Local review marks could not be updated: ' + str(error)]}
