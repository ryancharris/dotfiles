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
        return workspace.apply_snapshot(self.root, path, now=NOW + timedelta(minutes=1), **kwargs)

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


    def test_legacy_order_stable_but_absent_recommendations_are_not_completed(self):
        self.open(priorities=[self.item('first', user_confirmed=True), self.item('second')])
        state = self.refresh(self.snapshot(10, priorities=[self.item('second', title='Updated source'), self.item('first', user_confirmed=False), self.item('third')]))
        self.assertEqual([row['id'] for row in state['selected_priorities']], ['first', 'second'])
        self.assertTrue(state['selected_priorities'][0]['item']['user_confirmed'])
        self.assertEqual(state['selected_priorities'][1]['item']['title'], 'Updated source')
        self.assertEqual([row['id'] for row in state['suggestions']], ['third'])
        state = self.refresh(self.snapshot(11, priorities=[]))
        self.assertFalse(any(row['completed'] for row in state['selected_priorities']))
        self.assertEqual(workspace.workspace_snapshot(self.root, state)['priorities'], [])

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

    def test_dismissed_and_accepted_reviews_do_not_resurface_for_commit_only_changes(self):
        item = self.item('review', source_kind='pr', headRefOid='first-head', head_sha='first-head')
        accepted = self.item('accepted-review', source_kind='pr', headRefOid='first-head', head_sha='first-head')
        self.open(priorities=[], suggestions=[item, accepted])
        self.choose('dismiss', 'review')
        self.choose('accept', 'accepted-review')
        state = self.refresh(self.snapshot(10, priorities=[], suggestions=[
            dict(row, headRefOid='second-head', head_sha='second-head') for row in (item, accepted)]))
        self.assertEqual(state['suggestions'], [])
        state = self.refresh(self.snapshot(11, priorities=[], suggestions=[dict(item, material_key='verified-request-1')]))
        self.assertEqual([row['id'] for row in state['suggestions']], ['review'])
        self.choose('accept', 'review')
        state = self.refresh(self.snapshot(12, priorities=[], suggestions=[dict(item, material_key='verified-request-1', headRefOid='third-head')]))
        self.assertEqual(state['suggestions'], [])

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
        self.assertEqual(load_todos(self.root, now=NOW), [])
        accept = {'action': 'accept', 'id': 'suggestion', 'fingerprint': current}
        workspace.suggestion_action(self.root, accept, now=NOW)
        state = self.refresh(self.snapshot(11, priorities=[], suggestions=[self.item('suggestion', material_key='event-3')]))
        before = (self.root / 'workspace/state.json').read_bytes()
        workspace.suggestion_action(self.root, accept, now=NOW)
        self.assertEqual((self.root / 'workspace/state.json').read_bytes(), before)
        self.assertEqual(len(load_todos(self.root, now=NOW)), 1)
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
        self.assertEqual(len(load_todos(self.root, now=NOW)), 1)
        self.assertEqual(load_todos(self.root, now=NOW)[0]['status'], 'completed')
        self.assertEqual(load_todos(self.root, now=NOW)[0]['project_tags'], ['Transport'])
        state = self.refresh(self.snapshot(11, suggestions=[self.item('suggestion', material_key='verified-new-request')]))
        self.assertEqual([row['id'] for row in state['suggestions']], ['suggestion'])
        accepted = self.choose('accept', 'suggestion')
        self.assertEqual(len(accepted['accepted']['suggestion']['previous_versions']), 1)
        self.assertEqual(len(load_todos(self.root, now=NOW)), 2)
        self.assertEqual(next(row for row in load_todos(self.root, now=NOW) if row['id'] == task_id)['status'], 'completed')
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
                workspace.apply_snapshot(self.root, self.snapshot(10), now=NOW)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(path.parent.glob('*.tmp')), [])
        self.assertNotIn('refresh', workspace.load_workspace(self.root, now=NOW))

    def test_corrupt_manifest_is_preserved_never_reset(self):
        self.open()
        path = self.root / 'workspace/state.json'
        path.write_text('{broken')
        with self.assertRaisesRegex(workspace.WorkspaceError, 'preserved'):
            workspace.open_workspace(self.root, self.snapshot(10), now=NOW)
        self.assertEqual(path.read_text(), '{broken')
        with self.assertRaises(workspace.WorkspaceError):
            workspace.apply_snapshot(self.root, self.snapshot(10), now=NOW)
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
        state = self.refresh(self.snapshot(9, day='2026-10-21', priorities=[self.item('finished', status='open')]))
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
                tasks = load_todos(self.root, with_warnings=True, now=NOW)
                self.assertEqual(len(tasks['todos']) + len(tasks['todo_archive']), 1)
                task = (tasks['todos'] + tasks['todo_archive'])[0]
                if archive_task:
                    save_todo_action(self.root, {'action': 'remove', 'id': task['id']}, now=NOW)
                else:
                    save_todo_action(self.root, {'action': 'complete', 'id': task['id']}, now=NOW)
                state = self.choose('accept', 'proposed')
                tasks = load_todos(self.root, with_warnings=True, now=NOW)
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


    def test_new_run_advances_day_preserving_local_decisions_and_history(self):
        initial = self.open(priorities=[], suggestions=[self.item('accepted'), self.item('dismissed')])
        accepted = self.choose('accept', 'accepted')
        self.choose('dismiss', 'dismissed')
        tasks = load_todos(self.root, now=NOW)
        original_snapshot = self.root / initial['active_snapshot']
        original = original_snapshot.read_bytes()
        fresh = self.snapshot(day='2026-10-21', priorities=[], suggestions=[self.item('accepted'), self.item('dismissed')])
        state = workspace.apply_snapshot(self.root, fresh, now=NOW + timedelta(days=1))
        self.assertEqual(state['date'], '2026-10-21')
        self.assertEqual(state['accepted'], accepted['accepted'])
        self.assertEqual(state['suggestions'], [])
        self.assertEqual(load_todos(self.root, now=NOW), tasks)
        self.assertEqual(original_snapshot.read_bytes(), original)

    def test_legacy_stuck_request_and_corrupt_unused_config_do_not_block_run(self):
        initial = self.open()
        manifest = self.root / 'workspace/state.json'
        raw = json.loads(manifest.read_text())
        raw['refresh'] = {'status': 'running', 'id': 'legacy-unvalidated-request'}
        manifest.write_text(json.dumps(raw))
        config = self.root / 'workspace/config.json'
        config.write_text('{legacy broken bridge')
        before = manifest.read_bytes()
        read = workspace.load_workspace(self.root, now=NOW)
        self.assertNotIn('refresh', workspace.public_workspace(read))
        self.assertEqual(manifest.read_bytes(), before, 'reading does not rewrite legacy state')
        state = workspace.apply_snapshot(self.root, self.snapshot(day='2026-10-21'), now=NOW + timedelta(days=1))
        self.assertEqual(state['date'], '2026-10-21')
        self.assertNotIn('refresh', json.loads(manifest.read_text()))
        self.assertEqual(config.read_text(), '{legacy broken bridge')
        self.assertEqual(state['selected_priorities'], initial['selected_priorities'])

    def test_apply_initializes_idempotently_and_rejects_out_of_order_reports(self):
        first = self.snapshot()
        state = workspace.apply_snapshot(self.root, first, now=NOW)
        manifest = self.root / 'workspace/state.json'
        original = manifest.read_bytes()
        self.assertEqual(workspace.apply_snapshot(self.root, first, now=NOW), state)
        self.assertEqual(manifest.read_bytes(), original)
        newer = self.snapshot(11)
        workspace.apply_snapshot(self.root, newer, now=NOW)
        updated = manifest.read_bytes()
        for stale in (first, self.snapshot(10), self.snapshot(11)):
            with self.assertRaises(workspace.WorkspaceError):
                workspace.apply_snapshot(self.root, stale, now=NOW)
        self.assertEqual(manifest.read_bytes(), updated)

    def test_apply_cli_adopts_new_day_without_request_protocol(self):
        self.open()
        fresh = self.snapshot(day='2026-10-21')
        result = subprocess.run([sys.executable, str(Path(workspace.__file__)), '--root', str(self.root),
                                 'apply', '--snapshot', str(fresh)], check=True, capture_output=True, text=True)
        state = json.loads(result.stdout)
        self.assertEqual(state['date'], '2026-10-21')
        self.assertNotIn('refresh', state)
        for command in ('begin', 'complete', 'fail', 'configure'):
            result = subprocess.run([sys.executable, str(Path(workspace.__file__)), '--root', str(self.root), command],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__':
    unittest.main()
