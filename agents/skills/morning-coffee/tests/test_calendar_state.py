"""Calendar completion identity, persistence and concurrency using isolated roots."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calendar_state import CalendarError, calendar_key, load_calendar_state, save_calendar_state


def snapshot():
    return {'report': {'date': '2026-10-21', 'timezone': 'America/Toronto'},
            'agenda': {'events': [{'id': 'recurring-event', 'title': 'Meeting', 'start': '2026-10-21T15:00:00-04:00'}]},
            'submitted_plan': {'blocks': [{'kind': 'focus', 'start': 540, 'minutes': 45}]}}


class CalendarStateTests(unittest.TestCase):
    def test_private_persistence_idempotence_and_explicit_undo(self):
        source = snapshot()
        key = calendar_key(source, source['agenda']['events'][0])
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(load_calendar_state(root, source), {})
            self.assertFalse((Path(root) / 'workspace').exists(), 'empty read creates no state')
            for done in (True, True, False, False):
                self.assertEqual(save_calendar_state(root, source, {'key': key, 'done': done}), {'key': key, 'done': done})
                self.assertEqual(load_calendar_state(root, source), {key: done})
            folder = Path(root) / 'workspace'
            paths = list(folder.glob('calendar-*.json'))
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual(load_calendar_state(root, source, with_warnings=True), {'state': {key: False}, 'warnings': []})

    def test_source_identity_precedence_and_day_timezone_isolation(self):
        source = snapshot()
        event = source['agenda']['events'][0]
        key = calendar_key(source, event)
        changed = dict(event, title='Renamed', start='2026-10-21T16:00:00-04:00', updatedAt='later', url='https://calendar.example/new')
        self.assertEqual(key, calendar_key(source, changed))
        url_event = {'url': 'https://calendar.example/item', 'title': 'Original', 'start': '09:00'}
        self.assertEqual(calendar_key(source, url_event), calendar_key(source, dict(url_event, title='Renamed', start='10:00')))
        fallback = {'title': 'Meeting', 'start': '09:00'}
        self.assertNotEqual(calendar_key(source, fallback), calendar_key(source, dict(fallback, start='10:00')))
        with tempfile.TemporaryDirectory() as root:
            save_calendar_state(root, source, {'key': key, 'done': True})
            for report in ({'date': '2026-10-22', 'timezone': 'America/Toronto'}, {'date': '2026-10-21', 'timezone': 'UTC'}):
                other = dict(source, report=report)
                self.assertNotEqual(key, calendar_key(other, event))
                self.assertEqual(load_calendar_state(root, other), {})
                with self.assertRaises(CalendarError):
                    save_calendar_state(root, other, {'key': key, 'done': True})
            source['agenda']['events'][0] = changed
            self.assertEqual(load_calendar_state(root, source), {key: True})

    def test_local_identity_exact_saved_block_and_namespace(self):
        source = snapshot()
        block = source['submitted_plan']['blocks'][0]
        key = calendar_key(source, block, local=True)
        for changed in (dict(block, start=555), dict(block, minutes=60), dict(block, kind='lunch')):
            self.assertNotEqual(key, calendar_key(source, changed, local=True))
        self.assertNotEqual(key, calendar_key(source, {'id': key}))
        with tempfile.TemporaryDirectory() as root:
            save_calendar_state(root, source, {'key': key, 'done': False})
            self.assertEqual(load_calendar_state(root, source), {key: False})
            source['submitted_plan']['blocks'] = [dict(block, minutes=60)]
            with self.assertRaises(CalendarError):
                save_calendar_state(root, source, {'key': key, 'done': True})

    def test_invalid_requests_and_scope_never_write(self):
        source = snapshot()
        key = calendar_key(source, source['agenda']['events'][0])
        with tempfile.TemporaryDirectory() as root:
            for request in ({'key': key, 'done': 1}, {'key': key, 'done': 'true'}, {'key': key},
                            {'key': key, 'done': True, 'extra': 1}, {'key': '0' * 64, 'done': True},
                            {'key': [], 'done': True}, None):
                with self.subTest(request=request), self.assertRaises(CalendarError):
                    save_calendar_state(root, source, request)
            self.assertFalse((Path(root) / 'workspace').exists())
            for report in ({'date': 'bad', 'timezone': 'UTC'}, {'date': '2026-10-21', 'timezone': 'Unknown/Bad'}):
                with self.assertRaises(CalendarError):
                    calendar_key(dict(source, report=report), {})

    def test_corruption_preserved_and_write_refused(self):
        source = snapshot()
        key = calendar_key(source, source['agenda']['events'][0])
        with tempfile.TemporaryDirectory() as root:
            save_calendar_state(root, source, {'key': key, 'done': True})
            path = next((Path(root) / 'workspace').glob('calendar-*.json'))
            valid = json.loads(path.read_text())
            for content in ('{', json.dumps(dict(valid, state={key: 1})), json.dumps(dict(valid, date='2026-10-22'))):
                path.write_text(content)
                loaded = load_calendar_state(root, source, with_warnings=True)
                self.assertEqual(loaded['state'], {})
                self.assertEqual(len(loaded['warnings']), 1)
                with self.assertRaises(CalendarError):
                    load_calendar_state(root, source)
                with self.assertRaises(CalendarError):
                    save_calendar_state(root, source, {'key': key, 'done': False})
                self.assertEqual(path.read_text(), content)

    def test_concurrent_saves_retain_all_marks_and_failed_replace_preserves_state(self):
        source = snapshot()
        source['agenda']['events'] = [{'id': str(index)} for index in range(32)]
        requests = [{'key': calendar_key(source, event), 'done': True} for event in source['agenda']['events']]
        with tempfile.TemporaryDirectory() as root:
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda request: save_calendar_state(root, source, request), requests))
            expected = {request['key']: True for request in requests}
            self.assertEqual(load_calendar_state(root, source), expected)
            with patch('workspace_state.os.replace', side_effect=OSError('simulated disk failure')):
                with self.assertRaises(OSError):
                    save_calendar_state(root, source, dict(requests[0], done=False))
            self.assertEqual(load_calendar_state(root, source), expected)
            self.assertEqual(list((Path(root) / 'workspace').glob('*.tmp')), [])


if __name__ == '__main__':
    unittest.main()
