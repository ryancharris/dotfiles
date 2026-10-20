"""Private, reversible local review marks. Provider approval state stays untouched."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
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
    folder = Path(root) / 'review-state'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
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
    return record


def load_review_state(root, with_warnings=False):
    """Read latest valid marks across days, keyed by review_key(kind, source URL)."""
    result, warnings = {}, []
    for path in sorted((Path(root) / 'review-state').glob('*.json')):
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
    return {'state': result, 'warnings': warnings} if with_warnings else result
