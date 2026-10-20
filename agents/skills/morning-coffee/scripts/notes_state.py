"""Private root-wide scratchpad shared by Coffee and Tea."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from html import escape
import json
import os
from pathlib import Path
import tempfile
from time_format import local_time

MAX_NOTES = 25000


class NotesError(ValueError):
    pass


class NotesConflict(NotesError):
    pass


def empty_notes():
    return {'version': 1, 'text': '', 'revision': 0, 'updated_at': None}


def _text(value):
    if not isinstance(value, str) or len(value) > MAX_NOTES:
        raise NotesError('Notes must be plain text up to 25,000 characters.')
    if any(ord(char) < 32 and char not in '\t\n\r' for char in value):
        raise NotesError('Notes contain unsupported control characters.')
    return value


@contextmanager
def _locked(root, exclusive):
    folder = Path(root) / 'notes'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    folder.chmod(0o700)
    fd = os.open(folder / '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:
            yield folder
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _read(folder):
    path = folder / 'state.json'
    if not path.exists():
        return empty_notes()
    try:
        state = json.loads(path.read_text())
        if (not isinstance(state, dict) or state.get('version') != 1 or
                type(state.get('revision')) is not int or state['revision'] < 1):
            raise ValueError('Invalid note revision')
        _text(state.get('text'))
        stamp = datetime.fromisoformat(state['updated_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('Missing timestamp offset')
        return {key: state[key] for key in ('version', 'text', 'revision', 'updated_at')}
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as error:
        raise NotesError('Local notes could not be read. Existing notes were preserved.') from error


def load_notes(root, with_warnings=False):
    if not (Path(root) / 'notes').exists():
        state = empty_notes()
        return {'state': state, 'warnings': []} if with_warnings else state
    try:
        with _locked(root, False) as folder:
            state = _read(folder)
        warnings = []
    except (OSError, NotesError) as error:
        if not with_warnings:
            raise
        state, warnings = empty_notes(), [str(error)]
    return {'state': state, 'warnings': warnings} if with_warnings else state


def save_notes(root, request):
    if not isinstance(request, dict) or set(request) != {'text', 'revision'}:
        raise NotesError('Supply note text and its current revision.')
    text = _text(request['text'])
    if type(request['revision']) is not int or request['revision'] < 0:
        raise NotesError('Invalid note revision.')
    with _locked(root, True) as folder:
        current = _read(folder)
        if request['revision'] != current['revision']:
            raise NotesConflict('Notes changed in another page. Your draft is still here. Copy it before reloading to see the latest saved notes.')
        state = {'version': 1, 'text': text, 'revision': current['revision'] + 1,
                 'updated_at': datetime.now(timezone.utc).isoformat()}
        fd, temporary = tempfile.mkstemp(prefix='.notes-', dir=folder)
        try:
            with os.fdopen(fd, 'w') as handle:
                json.dump(state, handle, ensure_ascii=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, folder / 'state.json')
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {'ok': True, 'notes': state}


def render_notes(snapshot):
    state = snapshot.get('notes') or empty_notes()
    config = snapshot.get('notes_interaction') or {}
    zone = snapshot['report']['timezone']
    saved = state.get('updated_at')
    status = ('Saved locally at ' + local_time(saved, zone) + '.' if saved else 'Notes save locally as you type.') if config else 'Archived notes · open a live Coffee or Tea report to edit.'
    serialized = json.dumps({**config, 'notes': state, 'timezone': zone}, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return ('<section id="notes" class="local-notes"><div class="section-head"><h2>Notes</h2><p class="muted">Learnings, details &amp; things to remember · shared across days</p></div>'
            '<label for="local-notes-text">Your notes</label><textarea id="local-notes-text" rows="4" maxlength="25000" placeholder="Capture a learning, useful detail, or something to remember…" aria-describedby="local-notes-status"' + ('' if config else ' readonly') + '>' + '\n' + escape(state.get('text', '')) + '</textarea>'
            '<div class="notes-save"><p id="local-notes-status" role="status" aria-live="polite">' + escape(status) + '</p><button type="button" data-notes-retry hidden>Retry save</button></div>'
            '<script id="notes-config" type="application/json">' + serialized + '</script></section>')
