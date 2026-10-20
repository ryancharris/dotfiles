"""Concise Tea questions backed by recorded, unsuccessful source checks."""
from datetime import datetime
from html import escape


def pending_checks(snapshot):
    """Only ask when an actual timestamped validation attempt is recorded."""
    pending = []
    seen = set()
    checkpoint = snapshot.get('updates', {}).get('since')
    try:
        checkpoint = datetime.fromisoformat(checkpoint.replace('Z', '+00:00')) if checkpoint else None
        if checkpoint is not None and checkpoint.utcoffset() is None:
            checkpoint = None
    except (TypeError, ValueError, AttributeError):
        checkpoint = None
    resolved = {(row.get('section'), str(row.get('id'))) for row in snapshot.get('resolutions', [])
                if row.get('verified') is True and row.get('outcome') in
                ('completed', 'resolved', 'closed', 'cancelled', 'merged', 'approved')}
    for row in snapshot.get('status_checks', []):
        if row.get('outcome') != 'uncertain' or not row.get('question'):
            continue
        attempts = []
        for attempt in row.get('attempts', []):
            try:
                stamp = datetime.fromisoformat(attempt['checked_at'].replace('Z', '+00:00'))
                valid = stamp.utcoffset() is not None and (checkpoint is None or stamp >= checkpoint)
            except (KeyError, TypeError, ValueError, AttributeError):
                valid = False
            if valid and attempt.get('source') and attempt.get('result') and attempt.get('method'):
                attempts.append(attempt)
        key = (row.get('section'), row.get('id'))
        if not attempts or not all(key) or key in seen or (key[0], str(key[1])) in resolved:
            continue
        seen.add(key)
        pending.append({**row, 'attempts': attempts})
    return pending


def render_confirmation_questions(snapshot):
    rows = pending_checks(snapshot)
    if not rows:
        return ''
    def item(row):
        attempts = row['attempts']
        return ('<li><p><b>' + escape(row.get('title') or str(row['id'])) + '</b> · '
                + escape(row['question']) + '</p><details><summary>Checks tried · '
                + str(len(attempts)) + '</summary><ul>'
                + ''.join('<li>' + escape(attempt['source'] + ' · ' + attempt['method'])
                          + ': ' + escape(attempt['result']) + ' <span class="muted">'
                          + escape(attempt['checked_at']) + '</span></li>' for attempt in attempts)
                + '</ul></details></li>')
    result = ('<section id="status-confirmation" class="status-confirmation"><h2>🍵 Quick check</h2>'
              '<p class="muted">Still unclear after source checks. Reply in chat.</p><ul>'
              + ''.join(item(row) for row in rows[:3]) + '</ul>')
    if len(rows) > 3:
        result += ('<details><summary>' + str(len(rows) - 3) + ' more questions</summary><ul>'
                   + ''.join(item(row) for row in rows[3:]) + '</ul></details>')
    return result + '</section>'
