"""Synthetic regressions for source recommendations versus persistent local work."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from test_report_history import ReportSurface, snapshot
from local_plan_server import interactive_snapshot
from render_brief import render
from report_history import publish
from review_state import load_review_state, save_review_state
from todo_state import load_todos, save_todo_action
import workspace_state as workspace


ZONE = 'America/Toronto'


def content_text(node):
    """Include evidence kept in an accessible, initially closed disclosure."""
    return node if isinstance(node, str) else ' '.join(content_text(child) for child in node['children'])


class PriorityRecommendationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime.now(timezone.utc)
        self.day = self.now.astimezone(ZoneInfo(ZONE)).date().isoformat()
        self.counter = 0

    def item(self, key, **extra):
        row = dict(deepcopy(snapshot()['priorities'][0]), id=key,
                   title='Synthetic priority ' + key, url='https://example.com/' + key,
                   status='open')
        row.update(extra)
        return row

    def source(self, rows, hour=9, day=None, **extra):
        data = snapshot(f'{hour:02}:00', day=day or self.day)
        data.update(priorities=deepcopy(rows), **extra)
        return data

    def save(self, data):
        self.counter += 1
        data = deepcopy(data)
        data['history'] = {'kind': 'morning-coffee', 'created_at': data['collected_at']}
        folder = self.root / 'America__Toronto' / data['report']['date'] / f'morning-coffee-{self.counter}'
        folder.mkdir(parents=True)
        path = folder / 'snapshot.json'
        path.write_text(json.dumps(data))
        (folder / 'report.html').write_text('<html>Synthetic archive</html>')
        return path

    def open(self, rows, **extra):
        return workspace.open_workspace(self.root, self.save(self.source(rows, **extra)), now=self.now)

    def refresh(self, rows, hour=10, **extra):
        return workspace.complete_refresh(self.root, self.save(self.source(rows, hour, **extra)), now=self.now)

    def live(self):
        data = interactive_snapshot({}, self.root, 'http://127.0.0.1:12345', 'synthetic-token', workspace=True)
        return data, ReportSurface(render(data))

    def displayed_titles(self, page):
        return [page.visible_text(node) for node in page.elements(page.by_id['daily-priorities'])
                if node['tag'] == 'h4']

    def accept(self, key):
        state = workspace.load_workspace(self.root, now=self.now)
        suggestion = next(row for row in state['suggestions'] if row['id'] == key)
        return workspace.suggestion_action(self.root, {'action': 'accept', 'id': key,
            'fingerprint': suggestion['fingerprint']}, now=self.now)

    def test_same_day_refresh_uses_fresh_ranked_four_and_preserves_legacy_work(self):
        legacy = self.item('legacy', user_confirmed=True)
        answer = {'section': 'priorities', 'id': 'legacy', 'answered_at': self.now.isoformat(),
                  'outcome': 'open', 'answer': 'Still working on it'}
        initial = self.open([legacy], user_answers=[answer])
        task = save_todo_action(self.root, {'action': 'add', 'title': 'My own commitment',
            'project_tags': ['Transport'], 'important': True}, now=self.now)['item']
        before_tasks = deepcopy(load_todos(self.root, now=self.now))
        ranked = [self.item(key) for key in ('urgent', 'review', 'rfc', 'planning', 'overflow')]
        state = self.refresh(ranked)
        data, page = self.live()
        self.assertEqual([row['id'] for row in data['priorities']], [row['id'] for row in ranked[:4]])
        self.assertEqual(self.displayed_titles(page), [row['title'] for row in ranked[:4]])
        self.assertEqual(state['selected_priorities'], initial['selected_priorities'])
        self.assertEqual(state['user_answers'], [answer])
        self.assertEqual(load_todos(self.root, now=self.now), before_tasks)
        todo_text = content_text(page.by_id['todos'])
        self.assertIn(legacy['title'], todo_text)
        self.assertIn(task['title'], todo_text)
        self.assertNotIn(legacy['title'], page.visible_text(page.by_id['daily-priorities']))

    def test_start_today_adopts_new_ranking_and_carries_unfinished_local_work(self):
        initial = self.open([self.item('legacy')])
        task = save_todo_action(self.root, {'action': 'add', 'title': 'Carry this task'}, now=self.now)['item']
        tomorrow = (self.now.astimezone(ZoneInfo(ZONE)).date() + timedelta(days=1)).isoformat()
        # Request and collection times are explicit so this scenario works at any clock hour.
        requested = datetime.fromisoformat(tomorrow + 'T08:59:00-04:00')
        request = workspace.begin_refresh(self.root, 'start_today', tomorrow, ZONE, now=requested)['request']
        ranked = [self.item('tomorrow-first'), self.item('still-important')]
        path = self.save(self.source(ranked, day=tomorrow))
        state = workspace.complete_refresh(self.root, path, request['id'], now=requested + timedelta(minutes=2))
        data, page = self.live()
        self.assertEqual(state['date'], tomorrow)
        self.assertEqual(self.displayed_titles(page), [row['title'] for row in ranked])
        self.assertEqual(state['selected_priorities'], initial['selected_priorities'])
        self.assertEqual(load_todos(self.root, now=self.now)[0]['id'], task['id'])
        self.assertEqual(data['priorities'], ranked)

    def test_same_item_can_stay_recommended_with_updated_rationale_without_new_task(self):
        row = self.item('ongoing', context='A release is waiting for this check today.')
        self.open([row])
        refreshed = dict(row, context='The release is still waiting; check again before the 15:00 handoff.')
        self.refresh([refreshed])
        data, page = self.live()
        self.assertEqual([item['id'] for item in data['priorities']], ['ongoing'])
        self.assertIn('Why today', page.visible_text(page.by_id['daily-priorities']))
        self.assertIn(refreshed['context'], page.visible_text(page.by_id['daily-priorities']))
        self.assertEqual(load_todos(self.root, now=self.now), [])

    def test_accepted_task_stays_recommended_until_local_completion_even_without_refresh(self):
        row = self.item('accepted', project_tags=['Transport'])
        self.open([], work_suggestions=[row])
        state = self.accept('accepted')
        task_id = state['accepted']['accepted']['task_id']
        self.refresh([row])
        self.assertEqual([item['id'] for item in self.live()[0]['priorities']], ['accepted'])
        self.assertEqual(len(load_todos(self.root, now=self.now)), 1)
        save_todo_action(self.root, {'action': 'complete', 'id': task_id}, now=self.now)
        self.assertEqual(self.live()[0]['priorities'], [])
        self.refresh([dict(row, checked_at=self.now.isoformat(), context='New wording is not new work.')], hour=11)
        self.assertEqual(self.live()[0]['priorities'], [])
        self.assertEqual(load_todos(self.root, now=self.now)[0]['status'], 'completed')

    def test_expired_task_archive_keeps_recorded_completion_but_allows_new_material(self):
        row = self.item('accepted', material_key='first-event')
        self.open([], work_suggestions=[row])
        task_id = self.accept('accepted')['accepted']['accepted']['task_id']
        self.refresh([row])
        save_todo_action(self.root, {'action': 'complete', 'id': task_id}, now=self.now)
        save_todo_action(self.root, {'action': 'remove', 'id': task_id}, now=self.now)
        self.assertEqual(self.live()[0]['priorities'], [])
        load_todos(self.root, now=self.now + timedelta(days=9))
        self.assertEqual(self.live()[0]['priorities'], [])
        self.refresh([dict(row, material_key='new-verified-event')], hour=11)
        self.assertEqual([item['id'] for item in self.live()[0]['priorities']], ['accepted'])

    def test_reopened_task_overrides_older_recorded_completion(self):
        row = self.item('accepted')
        self.open([], work_suggestions=[row])
        task_id = self.accept('accepted')['accepted']['accepted']['task_id']
        self.refresh([row])
        save_todo_action(self.root, {'action': 'complete', 'id': task_id}, now=self.now)
        self.assertEqual(self.live()[0]['priorities'], [])
        save_todo_action(self.root, {'action': 'reopen', 'id': task_id}, now=self.now)
        self.assertEqual([item['id'] for item in self.live()[0]['priorities']], ['accepted'])

    def test_expired_cancelled_task_stays_suppressed(self):
        row = self.item('accepted')
        self.open([], work_suggestions=[row])
        task_id = self.accept('accepted')['accepted']['accepted']['task_id']
        self.refresh([row])
        save_todo_action(self.root, {'action': 'cancel', 'id': task_id}, now=self.now)
        save_todo_action(self.root, {'action': 'remove', 'id': task_id}, now=self.now)
        load_todos(self.root, now=self.now + timedelta(days=9))
        self.assertEqual(self.live()[0]['priorities'], [])

    def test_local_review_completion_and_user_answers_override_stale_recommendations(self):
        review_url = snapshot()['reviews']['items'][0]['url']
        review = self.item('review-work', source_kind='pr', source_url=review_url)
        answered = self.item('answered')
        answer = {'section': 'priorities', 'id': 'answered', 'outcome': 'completed',
                  'answered_at': self.now.isoformat()}
        self.open([review, answered], user_answers=[answer])
        save_review_state(self.root, self.source([review]), {'kind': 'pr', 'url': review_url, 'done': True}, now=self.now)
        before_marks = deepcopy(load_review_state(self.root))
        old_answer = dict(answer, outcome='open', answered_at=(self.now - timedelta(days=1)).isoformat())
        self.refresh([review, answered, self.item('fresh')], user_answers=[old_answer])
        data, _ = self.live()
        self.assertEqual([row['id'] for row in data['priorities']], ['fresh'])
        self.assertEqual(data['user_answers'], [answer])
        self.assertEqual(load_review_state(self.root), before_marks)

    def test_verified_completion_and_duplicates_do_not_consume_the_four_slots(self):
        self.open([])
        ranked = [self.item('finished', status='completed'), self.item('resolved'),
                  self.item('one'), self.item('one'), self.item('two'), self.item('three'), self.item('four')]
        self.refresh(ranked, resolutions=[{'section': 'priorities', 'id': 'resolved',
            'verified': True, 'outcome': 'resolved'}])
        self.assertEqual([row['id'] for row in self.live()[0]['priorities']], ['one', 'two', 'three', 'four'])

    def test_absence_does_not_complete_legacy_work_or_local_tasks(self):
        initial = self.open([self.item('missing')])
        task = save_todo_action(self.root, {'action': 'add', 'title': 'Still mine'}, now=self.now)['item']
        state = self.refresh([])
        data, page = self.live()
        self.assertEqual(data['priorities'], [])
        self.assertEqual(state['selected_priorities'], initial['selected_priorities'])
        self.assertIn('No recommended priorities.', page.visible_text(page.by_id['daily-priorities']))
        self.assertIn('Synthetic priority missing', content_text(page.by_id['todos']))
        self.assertEqual(load_todos(self.root, now=self.now), [task])

    def test_old_source_completion_alone_does_not_override_fresh_open_evidence(self):
        row = self.item('rechecked')
        self.open([row])
        self.refresh([dict(row, status='completed')])
        self.assertEqual(self.live()[0]['priorities'], [])
        state = self.refresh([dict(row, context='A new authoritative check finds outstanding work.')], hour=11)
        self.assertTrue(state['selected_priorities'][0]['completed'], 'Preserve historical state as recorded')
        self.assertEqual([item['id'] for item in self.live()[0]['priorities']], ['rechecked'])

    def test_partial_collection_preserves_old_evidence_time_and_reports_incomplete_coverage(self):
        old = self.item('earlier', context='Earlier source fact still needs verification.')
        morning = self.source([old])
        first = publish(self.root, morning, 'morning-coffee')
        workspace.open_workspace(self.root, first['snapshot'], now=self.now)
        archive_before = Path(first['snapshot']).read_bytes()
        fresh = self.source([self.item('fresh')], hour=11)
        fresh['sources']['github'].update(status='unavailable', note='Synthetic GitHub lookup failed.')
        result = publish(self.root, fresh, 'refresh')
        workspace.complete_refresh(self.root, result['snapshot'], now=self.now)
        data, page = self.live()
        self.assertEqual([row['id'] for row in data['priorities']], ['fresh', 'earlier'])
        retained = data['priorities'][1]
        self.assertEqual(retained['_retained_at'], morning['collected_at'])
        self.assertEqual(data['sources']['github']['checked_at'], fresh['collected_at'])
        self.assertEqual(data['sources']['github']['status'], 'unavailable')
        self.assertIn('Earlier evidence', page.visible_text(page.by_id['daily-priorities']))
        self.assertIn('5/6 complete', page.visible_text(page.by_id['source-freshness']))
        self.assertIn('Synthetic GitHub lookup failed.', content_text(page.by_id['source-freshness']))
        self.assertEqual(Path(first['snapshot']).read_bytes(), archive_before)
        # A second failed attempt cannot relabel the old fact with the last attempt time.
        later = self.source([self.item('fresh')], hour=12)
        later['sources']['github'].update(status='unavailable', note='Still unavailable.')
        result = publish(self.root, later, 'refresh')
        workspace.complete_refresh(self.root, result['snapshot'], now=self.now)
        data, _ = self.live()
        self.assertEqual(next(row for row in data['priorities'] if row['id'] == 'earlier')['_retained_at'],
                         morning['collected_at'])

    def test_check_time_never_becomes_a_source_change_time(self):
        changed = (self.now - timedelta(days=2)).isoformat()
        checked = self.now.isoformat()
        row = self.item('steady', changed_at=changed, checked_at=checked)
        self.open([row])
        data, page = self.live()
        text = content_text(page.by_id['daily-priorities'])
        changed_label = datetime.fromisoformat(changed).astimezone(ZoneInfo(ZONE)).strftime('%Y-%m-%d %H:%M %Z')
        checked_label = datetime.fromisoformat(checked).astimezone(ZoneInfo(ZONE)).strftime('%Y-%m-%d %H:%M %Z')
        self.assertIn('Last checked ' + checked_label, text)
        self.assertIn('Source changed ' + changed_label, text)
        self.assertNotIn('Source changed ' + checked_label, text)
        del row['changed_at']
        self.refresh([row])
        data, page = self.live()
        self.assertIn('Last checked ' + checked_label, content_text(page.by_id['daily-priorities']))
        self.assertNotIn('Source changed', content_text(page.by_id['daily-priorities']))
        self.assertNotIn('changed_at', data['priorities'][0])

    def test_dismissal_and_acceptance_remain_durable_across_recommendation_refresh(self):
        accepted, dismissed = self.item('accepted'), self.item('dismissed')
        self.open([], work_suggestions=[accepted, dismissed])
        self.accept('accepted')
        state = workspace.load_workspace(self.root, now=self.now)
        row = next(row for row in state['suggestions'] if row['id'] == 'dismissed')
        before = workspace.suggestion_action(self.root, {'action': 'dismiss', 'id': row['id'],
            'fingerprint': row['fingerprint']}, now=self.now)
        tasks_before = deepcopy(load_todos(self.root, now=self.now))
        after = self.refresh([dismissed, accepted, self.item('new')])
        self.assertEqual(after['accepted'], before['accepted'])
        self.assertEqual(after['dismissed'], before['dismissed'])
        self.assertEqual(load_todos(self.root, now=self.now), tasks_before)
        self.assertEqual([row['id'] for row in self.live()[0]['priorities']], ['accepted', 'new'])


if __name__ == '__main__':
    unittest.main()
