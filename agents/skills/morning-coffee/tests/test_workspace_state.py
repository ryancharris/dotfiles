"""Durable workspace scenarios; fixtures contain no live source information."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import workspace_state as workspace
from todo_state import load_todos, save_todo_action
from review_state import save_review_state, load_review_state, review_key

NOW = datetime(2026, 10, 20, 13, tzinfo=timezone.utc)
ZONE = 'America/Toronto'


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.counter = 0

    def snapshot(self, hour=9, day='2026-10-20', priorities=None, suggestions=None, stamp=None, **extra):
        self.counter += 1
        stamp = stamp or f'{day}T{hour:02}:00:00-04:00'
        data = {'collected_at': stamp, 'report': {'date': day, 'timezone': ZONE},
                'history': {'kind': 'morning-coffee', 'created_at': stamp},
                'priorities': priorities if priorities is not None else [self.item('first'), self.item('second')],
                'work_suggestions': suggestions or [], **extra}
        folder = self.root / 'America__Toronto' / day / f'morning-coffee-{self.counter}'
        folder.mkdir(parents=True)
        path = folder / 'snapshot.json'
        path.write_text(json.dumps(data))
        (folder / 'report.html').write_text('<html>synthetic published fixture</html>')
        return path

    def item(self, key, **extra):
        return {'id': key, 'title': 'Synthetic ' + key, 'url': 'https://example.com/' + key, 'status': 'open', **extra}

    def open(self, **kwargs):
        return workspace.open_workspace(self.root, self.snapshot(**kwargs), now=NOW)

    def refresh(self, path, **kwargs):
        return workspace.complete_refresh(self.root, path, now=NOW + timedelta(minutes=1), **kwargs)

    def choose(self, action, key):
        state = workspace.load_workspace(self.root, now=NOW)
        row = next((row for row in state['suggestions'] if row['id'] == key), None)
        fingerprint = row['fingerprint'] if row else state['accepted'].get(key, {}).get('fingerprint', '0' * 64)
        return workspace.suggestion_action(self.root, {'action': action, 'id': key, 'fingerprint': fingerprint}, now=NOW)

    def test_open_read_never_rolls_over_or_imports_new_snapshot(self):
        initial = self.open()
        newer = self.snapshot(10, day='2026-10-21')
        read = workspace.open_workspace(self.root, newer, now=NOW + timedelta(days=1))
        self.assertEqual(read, initial)
        self.assertEqual(workspace.load_workspace(self.root, now=NOW + timedelta(days=2))['date'], '2026-10-20')

    def test_concurrent_tabs_start_one_request_across_dates_actions(self):
        self.open()
        def begin(index):
            return workspace.begin_refresh(self.root, 'start_today' if index % 2 else 'refresh', '2026-10-21' if index % 2 else '2026-10-20', ZONE, now=NOW)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(begin, range(20)))
        self.assertEqual(sum(result['created'] for result in results), 1)
        self.assertEqual(len({result['request']['id'] for result in results}), 1)

    def test_stale_completion_preserves_pointer_and_failure_is_actionable(self):
        initial = self.open()
        request = workspace.begin_refresh(self.root, 'refresh', initial['date'], ZONE, now=NOW)['request']
        state = workspace.mark_dispatch(self.root, request['id'], False, error='https://secret.example/token', now=NOW)
        self.assertEqual(state['active_snapshot'], initial['active_snapshot'])
        self.assertIn('T3', state['refresh']['error'])
        self.assertNotIn('secret', json.dumps(state))
        with self.assertRaises(workspace.WorkspaceError):
            self.refresh(self.snapshot(10), request_id=request['id'])
        next_request = workspace.begin_refresh(self.root, 'refresh', initial['date'], ZONE, now=NOW)['request']
        with self.assertRaises(workspace.WorkspaceError):
            self.refresh(self.snapshot(11), request_id=request['id'])
        self.assertNotEqual(next_request['id'], request['id'])

    def test_timeout_unsticks_request_and_retains_last_good_facts(self):
        initial = self.open()
        workspace.begin_refresh(self.root, 'refresh', initial['date'], ZONE, now=NOW)
        state = workspace.load_workspace(self.root, now=NOW + timedelta(minutes=16))
        self.assertEqual(state['refresh']['status'], 'failed')
        self.assertIn('timed out', state['refresh']['error'])
        self.assertEqual(state['active_snapshot'], initial['active_snapshot'])
        with self.assertRaises(workspace.WorkspaceError):
            self.refresh(self.snapshot(10), request_id=state['refresh']['id'])

    def test_callback_completion_requires_post_request_collection_but_manual_apply_does_not(self):
        initial = self.open()
        earlier = self.snapshot(stamp='2026-10-20T09:30:00-04:00')
        requested_at = NOW + timedelta(hours=1)
        request = workspace.begin_refresh(self.root, 'refresh', initial['date'], ZONE, now=requested_at)['request']
        before = (self.root / 'workspace/state.json').read_bytes()
        with self.assertRaisesRegex(workspace.WorkspaceError, 'predates'):
            workspace.complete_refresh(self.root, earlier, request['id'], now=requested_at + timedelta(minutes=1))
        self.assertEqual((self.root / 'workspace/state.json').read_bytes(), before)
        fresh = self.snapshot(stamp='2026-10-20T10:00:00-04:00')
        state = workspace.complete_refresh(self.root, fresh, request['id'], now=requested_at + timedelta(minutes=2))
        self.assertEqual(state['refresh']['status'], 'completed')
        manual = self.snapshot(stamp='2026-10-20T10:01:00-04:00')
        state = workspace.complete_refresh(self.root, manual, now=requested_at + timedelta(hours=1))
        self.assertEqual(state['active_snapshot'], manual.relative_to(self.root).as_posix())

    def test_explicit_start_today_and_new_day_unfinished_work(self):
        local = save_todo_action(self.root, {'action': 'add', 'title': 'Local carry', 'project_tags': ['Transport']}, now=NOW)['item']
        self.open()
        self.refresh(self.snapshot(10, priorities=[self.item('second', status='completed')]))
        with self.assertRaises(workspace.WorkspaceError):
            workspace.begin_refresh(self.root, 'refresh', '2026-10-21', ZONE, now=NOW)
        request = workspace.begin_refresh(self.root, 'start_today', '2026-10-21', ZONE, now=NOW)['request']
        state = self.refresh(self.snapshot(9, day='2026-10-21', priorities=[self.item('new')]), request_id=request['id'])
        self.assertEqual(state['date'], '2026-10-21')
        self.assertEqual([row['id'] for row in state['selected_priorities']], ['first'])
        self.assertEqual([row['id'] for row in state['suggestions']], ['new'])
        self.assertEqual(load_todos(self.root)[0]['id'], local['id'])
        self.assertEqual(load_todos(self.root)[0]['project_tags'], ['Transport'])

    def test_chosen_order_stable_facts_update_missing_is_not_done(self):
        self.open(priorities=[self.item('first', user_confirmed=True), self.item('second')])
        state = self.refresh(self.snapshot(10, priorities=[self.item('second', title='Updated source'), self.item('first', user_confirmed=False), self.item('third')]))
        self.assertEqual([row['id'] for row in state['selected_priorities']], ['first', 'second'])
        self.assertTrue(state['selected_priorities'][0]['item']['user_confirmed'])
        self.assertEqual(state['selected_priorities'][1]['item']['title'], 'Updated source')
        self.assertEqual([row['id'] for row in state['suggestions']], ['third'])
        state = self.refresh(self.snapshot(11, priorities=[]))
        self.assertFalse(any(row['completed'] for row in state['selected_priorities']))
        self.assertEqual(len(workspace.workspace_snapshot(self.root, state)['priorities']), 2)

    def test_verified_resolution_completes_but_unverified_does_not(self):
        self.open()
        state = self.refresh(self.snapshot(10, priorities=[self.item('first', status='completed', verified=False)], resolutions=[{'section': 'priorities', 'id': 'second', 'verified': True, 'outcome': 'resolved'}]))
        self.assertFalse(state['selected_priorities'][0]['completed'])
        self.assertTrue(state['selected_priorities'][1]['completed'])
        state = self.refresh(self.snapshot(11))
        self.assertTrue(state['selected_priorities'][1]['completed'])

    def test_dismiss_noise_stays_hidden_material_change_resurfaces(self):
        self.open(suggestions=[self.item('suggestion', material_key='source-head-1')])
        self.choose('dismiss', 'suggestion')
        state = self.refresh(self.snapshot(10, suggestions=[self.item('suggestion', material_key='source-head-1', title='Different prose', checked_at='later', updatedAt='later')]))
        self.assertEqual(state['suggestions'], [])
        state = self.refresh(self.snapshot(11, suggestions=[self.item('suggestion', material_key='source-head-2')]))
        self.assertEqual([row['id'] for row in state['suggestions']], ['suggestion'])
        self.choose('dismiss', 'suggestion')
        state = self.refresh(self.snapshot(12, suggestions=[self.item('suggestion', material_key='source-head-1')]))
        self.assertEqual(state['suggestions'], [])

    def test_fallback_fingerprint_ignores_prose_timestamps(self):
        item = self.item('suggestion')
        noisy = dict(item, title='Rephrased', action='New wording', checked_at='today', updatedAt='today')
        self.assertEqual(workspace.material_fingerprint(item), workspace.material_fingerprint(noisy))
        self.assertNotEqual(workspace.material_fingerprint(item), workspace.material_fingerprint(dict(item, status='blocked')))

    def test_suggestion_actions_bind_material_version_and_delayed_retries_are_idempotent(self):
        initial = self.open(priorities=[], suggestions=[self.item('suggestion', material_key='event-1')])
        old = initial['suggestions'][0]['fingerprint']
        state = self.refresh(self.snapshot(10, priorities=[], suggestions=[self.item('suggestion', material_key='event-2')]))
        current = state['suggestions'][0]['fingerprint']
        before = (self.root / 'workspace/state.json').read_bytes()
        for action in ('accept', 'dismiss'):
            with self.subTest(action=action), self.assertRaises(workspace.StaleWorkspaceError):
                workspace.suggestion_action(self.root, {'action': action, 'id': 'suggestion', 'fingerprint': old}, now=NOW)
        self.assertEqual((self.root / 'workspace/state.json').read_bytes(), before)
        self.assertEqual(load_todos(self.root), [])
        accept = {'action': 'accept', 'id': 'suggestion', 'fingerprint': current}
        workspace.suggestion_action(self.root, accept, now=NOW)
        state = self.refresh(self.snapshot(11, priorities=[], suggestions=[self.item('suggestion', material_key='event-3')]))
        before = (self.root / 'workspace/state.json').read_bytes()
        workspace.suggestion_action(self.root, accept, now=NOW)
        self.assertEqual((self.root / 'workspace/state.json').read_bytes(), before)
        self.assertEqual(len(load_todos(self.root)), 1)
        dismiss = {'action': 'dismiss', 'id': 'suggestion', 'fingerprint': state['suggestions'][0]['fingerprint']}
        workspace.suggestion_action(self.root, dismiss, now=NOW)
        self.refresh(self.snapshot(12, priorities=[], suggestions=[self.item('suggestion', material_key='event-4')]))
        before = (self.root / 'workspace/state.json').read_bytes()
        state = workspace.suggestion_action(self.root, dismiss, now=NOW)
        self.assertEqual((self.root / 'workspace/state.json').read_bytes(), before)
        self.assertEqual(state['suggestions'][0]['item']['material_key'], 'event-4')

    def test_accept_once_creates_root_task_and_local_completion_wins(self):
        self.open(suggestions=[self.item('suggestion', project_tags=['Transport'])])
        accepted = self.choose('accept', 'suggestion')
        task_id = accepted['accepted']['suggestion']['task_id']
        self.choose('accept', 'suggestion')
        save_todo_action(self.root, {'action': 'complete', 'id': task_id}, now=NOW)
        state = self.refresh(self.snapshot(10, suggestions=[self.item('suggestion', status='open', title='New generated prose', checked_at='later')]))
        self.assertEqual(state['suggestions'], [])
        self.assertEqual(len(load_todos(self.root)), 1)
        self.assertEqual(load_todos(self.root)[0]['status'], 'completed')
        self.assertEqual(load_todos(self.root)[0]['project_tags'], ['Transport'])
        state = self.refresh(self.snapshot(11, suggestions=[self.item('suggestion', material_key='verified-new-request')]))
        self.assertEqual([row['id'] for row in state['suggestions']], ['suggestion'])
        accepted = self.choose('accept', 'suggestion')
        self.assertEqual(len(accepted['accepted']['suggestion']['previous_versions']), 1)
        self.assertEqual(len(load_todos(self.root)), 2)
        self.assertEqual(next(row for row in load_todos(self.root) if row['id'] == task_id)['status'], 'completed')
        with self.assertRaises(workspace.WorkspaceError):
            self.choose('accept', 'unknown')

    def test_user_answers_carried_by_identity_and_timestamp(self):
        answer = {'section': 'priorities', 'id': 'first', 'answered_at': NOW.isoformat(), 'outcome': 'completed'}
        self.open(user_answers=[answer])
        state = self.refresh(self.snapshot(10, user_answers=[dict(answer, answered_at=(NOW - timedelta(days=1)).isoformat(), outcome='open')]))
        self.assertTrue(state['selected_priorities'][0]['completed'])
        self.assertEqual(workspace.workspace_snapshot(self.root, state)['user_answers'], [answer])

    def test_atomic_replace_failure_preserves_valid_file(self):
        self.open()
        path = self.root / 'workspace/state.json'
        before = path.read_bytes()
        with patch.object(workspace.os, 'replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                workspace.begin_refresh(self.root, 'refresh', '2026-10-20', ZONE, now=NOW)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob('*.tmp')), [])
        self.assertIsNone(workspace.load_workspace(self.root, now=NOW)['refresh'])

    def test_corrupt_manifest_is_preserved_never_reset(self):
        self.open()
        path = self.root / 'workspace/state.json'
        path.write_text('{broken')
        with self.assertRaisesRegex(workspace.WorkspaceError, 'preserved'):
            workspace.open_workspace(self.root, self.snapshot(10), now=NOW)
        self.assertEqual(path.read_text(), '{broken')
        with self.assertRaises(workspace.WorkspaceError):
            workspace.begin_refresh(self.root, 'refresh', '2026-10-20', ZONE, now=NOW)
        self.assertEqual(path.read_text(), '{broken')

    def test_root_path_validation_and_private_file_modes(self):
        path = self.snapshot()
        workspace.open_workspace(self.root, path, now=NOW)
        for candidate in [path.parent / '..' / path.parent.name / 'snapshot.json', self.root / '../outside/snapshot.json']:
            with self.assertRaises(workspace.WorkspaceError):
                workspace.published_snapshot(self.root, candidate)
        linked = self.root / 'America__Toronto/2026-10-20/linked'
        linked.symlink_to(path.parent, target_is_directory=True)
        with self.assertRaises(workspace.WorkspaceError):
            workspace.published_snapshot(self.root, linked / 'snapshot.json')
        self.assertEqual((self.root / 'workspace').stat().st_mode & 0o777, 0o700)
        for filename in ['state.json', '.lock']:
            self.assertEqual((self.root / 'workspace' / filename).stat().st_mode & 0o777, 0o600)
        data = json.loads(path.read_text())
        data['report']['date'] = '2026-10-21'
        path.write_text(json.dumps(data))
        with self.assertRaises(workspace.WorkspaceError):
            workspace.load_workspace(self.root, now=NOW)

    def test_completed_review_stays_hidden_for_commits_but_verified_request_surfaces(self):
        url = 'https://github.com/example/synthetic/pull/42'
        item = self.item('pr-work', source_kind='pr', source_url=url, material_key='head-1')
        path = self.snapshot(suggestions=[item], reviews={'items': [{'url': url}]})
        source = json.loads(path.read_text())
        workspace.open_workspace(self.root, path, now=NOW)
        save_review_state(self.root, source, {'kind': 'pr', 'url': url, 'done': True}, now=NOW - timedelta(hours=1))
        row = {'url': url, 'headRefOid': 'head-2', 'status': 'OPEN', 'updatedAt': NOW.isoformat()}
        state = self.refresh(self.snapshot(10, suggestions=[dict(item, material_key='head-2')], reviews={'items': [row]}))
        self.assertEqual(state['suggestions'], [])
        self.assertTrue(load_review_state(self.root)[review_key('pr', url)]['done'])
        row['localReRequest'] = {'verified': True, 'event_id': 'synthetic-event-42', 'requested_at': (NOW - timedelta(minutes=30)).isoformat(),
                                 'url': url, 'target': {'type': 'user', 'login': 'synthetic-user'}, 'current': True}
        state = self.refresh(self.snapshot(11, suggestions=[dict(item, material_key='review-request-synthetic-event-42')],
                                            reviews={'items': [row]}, review_identity={'github_login': 'synthetic-user'}))
        self.assertEqual([row['id'] for row in state['suggestions']], ['pr-work'])
        self.assertFalse(load_review_state(self.root)[review_key('pr', url)]['done'])

    def test_already_completed_initial_work_cannot_resurface_from_stale_source_facts(self):
        answer = {'section': 'priorities', 'id': 'finished', 'source': 'user', 'status': 'completed',
                  'answer': 'Completed', 'answered_at': NOW.isoformat(), 'scope': 'Owners and targets agreed'}
        initial = self.open(priorities=[self.item('finished', status='completed')], user_answers=[answer])
        self.assertEqual(initial['selected_priorities'], [])
        state = self.refresh(self.snapshot(10, priorities=[self.item('finished', status='open')]))
        self.assertEqual(state['suggestions'], [])
        self.assertEqual(state['user_answers'], [answer])
        request = workspace.begin_refresh(self.root, 'start_today', '2026-10-21', ZONE, now=NOW)['request']
        state = self.refresh(self.snapshot(9, day='2026-10-21', priorities=[self.item('finished', status='open')]), request_id=request['id'])
        self.assertEqual(state['suggestions'], [])

    def test_explicit_verified_resolution_retires_absent_suggestion(self):
        self.open(priorities=[], suggestions=[self.item('proposed'), self.item('uncertain')])
        state = self.refresh(self.snapshot(10, priorities=[], resolutions=[
            {'section': 'priorities', 'id': 'proposed', 'verified': True, 'outcome': 'completed'},
            {'section': 'priorities', 'id': 'uncertain', 'verified': False, 'outcome': 'completed'}]))
        self.assertEqual([row['id'] for row in state['suggestions']], ['uncertain'])

    def test_completed_source_priority_overrides_stale_open_proposal(self):
        self.open(priorities=[], suggestions=[self.item('proposed')])
        state = self.refresh(self.snapshot(10, priorities=[self.item('proposed', status='completed')],
                                            suggestions=[self.item('proposed', status='open')]))
        self.assertEqual(state['suggestions'], [])

    def test_accept_retry_recovers_one_committed_task_without_reopening_user_choice(self):
        self.open(priorities=[], suggestions=[self.item('proposed', project_tags=['Transport'])])
        for archive_task in (False, True):
            with self.subTest(archive_task=archive_task):
                # First simulate interruption between the task and manifest commits.
                with patch.object(workspace, '_write', side_effect=OSError('synthetic manifest save failure')):
                    with self.assertRaises(OSError):
                        self.choose('accept', 'proposed')
                tasks = load_todos(self.root, with_warnings=True)
                self.assertEqual(len(tasks['todos']) + len(tasks['todo_archive']), 1)
                task = (tasks['todos'] + tasks['todo_archive'])[0]
                if archive_task:
                    save_todo_action(self.root, {'action': 'remove', 'id': task['id']}, now=NOW)
                else:
                    save_todo_action(self.root, {'action': 'complete', 'id': task['id']}, now=NOW)
                state = self.choose('accept', 'proposed')
                tasks = load_todos(self.root, with_warnings=True)
                self.assertEqual(len(tasks['todos']) + len(tasks['todo_archive']), 1)
                self.assertEqual(state['accepted']['proposed']['task_id'], task['id'])
                if archive_task:
                    self.assertEqual(tasks['todos'], [])
                    self.assertEqual(tasks['todo_archive'][0]['project_tags'], ['Transport'])
                else:
                    self.assertEqual(tasks['todos'][0]['status'], 'completed')
                    # Simulate the same interrupted operation again before its acknowledgement.
                    state_file = self.root / 'workspace/state.json'
                    raw = json.loads(state_file.read_text())
                    record = raw['accepted'].pop('proposed')
                    raw['suggestions'] = [{'id': 'proposed', 'fingerprint': record['fingerprint'], 'item': self.item('proposed', project_tags=['Transport'])}]
                    state_file.write_text(json.dumps(raw))

    def test_private_bridge_config_never_in_public_state(self):
        state = self.open()
        path = self.root / 'workspace/config.json'
        config = {'webhook_url': 'https://example.com/private-secret', 'thread_url': 't3-thread://thread-123', 'timeout_seconds': 300, 'scheduled_task_id': 'private-task-123'}
        path.write_text(json.dumps(config))
        path.chmod(0o600)
        self.assertEqual(workspace.read_bridge_config(self.root), config)
        self.assertNotIn('private-secret', json.dumps(workspace.public_workspace(state)))
        self.assertNotIn('active_snapshot', workspace.public_workspace(state))
        path.chmod(0o644)
        with self.assertRaises(workspace.WorkspaceError):
            workspace.read_bridge_config(self.root)
        path.chmod(0o600)
        path.write_text('{broken')
        with self.assertRaises(workspace.WorkspaceError):
            workspace.read_bridge_config(self.root)
        self.assertEqual(path.read_text(), '{broken')

    def test_configure_private_atomic_and_cli_inspection(self):
        self.open()
        config = {'webhook_url': 'https://example.com/private-secret'}
        result = workspace.configure_bridge(self.root, config)
        self.assertEqual(result, {'ok': True, 'bridge_configured': True})
        path = self.root / 'workspace/config.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        script = Path(workspace.__file__)
        for arguments in [['--root', str(self.root), 'inspect'], ['inspect', '--root', str(self.root)]]:
            inspected = subprocess.run([sys.executable, str(script), *arguments], check=True, capture_output=True, text=True)
            self.assertIn('active_snapshot', json.loads(inspected.stdout))
            self.assertNotIn('private-secret', inspected.stdout)
        path.write_text('{broken')
        with self.assertRaises(workspace.WorkspaceError):
            workspace.configure_bridge(self.root, config)
        self.assertEqual(path.read_text(), '{broken')

    def test_invalid_bridge_cannot_block_local_state_or_timeout(self):
        state = self.open()
        request = workspace.begin_refresh(self.root, 'refresh', state['date'], ZONE, now=NOW)['request']
        path = self.root / 'workspace/config.json'
        path.write_text('{broken')
        path.chmod(0o600)
        state = workspace.load_workspace(self.root, now=NOW + timedelta(minutes=16))
        self.assertEqual(state['refresh']['status'], 'failed')
        self.assertEqual(path.read_text(), '{broken')

    def test_manual_publication_cannot_race_pending_or_cross_day(self):
        initial = self.open()
        request = workspace.begin_refresh(self.root, 'refresh', initial['date'], ZONE, now=NOW)['request']
        with self.assertRaises(workspace.WorkspaceError):
            self.refresh(self.snapshot(10))
        with self.assertRaises(workspace.WorkspaceError):
            self.refresh(self.snapshot(9, day='2026-10-21'), request_id=request['id'])
        self.assertEqual(workspace.load_workspace(self.root, now=NOW)['active_snapshot'], initial['active_snapshot'])
        result = self.refresh(self.snapshot(11), request_id=request['id'])
        self.assertEqual(result['refresh']['status'], 'completed')
        # A late dispatch acknowledgement cannot reopen a completed request.
        result = workspace.mark_dispatch(self.root, request['id'], True, now=NOW)
        self.assertEqual(result['refresh']['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
