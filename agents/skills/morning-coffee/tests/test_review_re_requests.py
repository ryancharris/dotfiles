"""Verified later review requests may reopen only the matching local done mark."""
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review_state import apply_verified_re_requests, load_review_state, review_key, save_review_state, verified_re_request


PR = 'https://github.com/dbt-labs/example/pull/42'
RFC = 'https://www.notion.so/fixture-rfc'
DONE_AT = '2026-10-20T09:00:00+00:00'
REQUESTED_AT = '2026-10-20T10:00:00+00:00'
NOW = datetime.fromisoformat('2026-10-20T12:00:00+00:00')


def local_event(url, target=None, **changes):
    event = {'verified': True, 'event_id': 'event-42', 'requested_at': REQUESTED_AT,
             'url': url, 'target': target or {'type': 'user', 'login': 'alice'}, 'current': True}
    event.update(changes)
    return event


def snapshot(pr_rows=(), rfc_rows=(), **metadata):
    return {'reviews': {'items': list(pr_rows)}, 'rfcs': {'items': list(rfc_rows)}, **metadata}


class VerifiedReRequestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def mark_done(self, kind='pr', url=PR, when=DONE_AT):
        return save_review_state(self.root, snapshot([{'url': PR}], [{'url': RFC}]),
                                 {'kind': kind, 'url': url, 'done': True}, datetime.fromisoformat(when))

    def test_later_verified_current_user_request_reopens_once(self):
        self.mark_done()
        other_url = PR.replace('/42', '/43')
        save_review_state(self.root, snapshot([{'url': other_url}]),
                          {'kind': 'pr', 'url': other_url, 'done': True}, datetime.fromisoformat(DONE_AT))
        row = {'url': PR, 'localReRequest': local_event(PR), 'updatedAt': '2099-12-31T00:00:00Z'}
        other_row = {'url': other_url, 'updatedAt': '2099-12-31T00:00:00Z'}
        data = snapshot([row, other_row], review_identity={'github_login': 'ALICE'})
        evidence = verified_re_request('pr', row, data)
        self.assertEqual(evidence['url'], PR)
        self.assertEqual(evidence['event_id'], 'event-42')
        self.assertEqual(evidence['requested_at'], datetime.fromisoformat(REQUESTED_AT))
        first = apply_verified_re_requests(self.root, data, now=NOW)
        self.assertEqual(first, {'changed': 1, 'warnings': []})
        mark = load_review_state(self.root)[review_key('pr', PR)]
        self.assertFalse(mark['done'])
        self.assertEqual(mark['updated_at'], NOW.isoformat())
        self.assertTrue(load_review_state(self.root)[review_key('pr', other_url)]['done'])
        self.assertEqual(apply_verified_re_requests(self.root, data, now=NOW)['changed'], 0)
        self.assertEqual(len(list((self.root / 'review-state').glob('*.json'))), 3)
        save_review_state(self.root, snapshot([{'url': PR}]), {'kind': 'pr', 'url': PR, 'done': True},
                          datetime.fromisoformat('2026-10-20T13:00:00+00:00'))
        self.assertEqual(apply_verified_re_requests(self.root, data, now=NOW)['changed'], 0)

    def test_older_or_equal_event_does_not_clear_a_later_done_mark(self):
        for index, requested_at in enumerate(('2026-10-20T10:59:00+00:00', '2026-10-20T11:00:00+00:00'), 1):
            with self.subTest(requested_at=requested_at):
                root = self.root / str(index)
                done_at = '2026-10-20T11:00:00+00:00'
                save_review_state(root, snapshot([{'url': PR}]), {'kind': 'pr', 'url': PR, 'done': True},
                                  datetime.fromisoformat(done_at))
                event = local_event(PR, requested_at=requested_at)
                data = snapshot([{'url': PR, 'localReRequest': event}], review_identity={'github_login': 'alice'})
                result = apply_verified_re_requests(root, data, now=NOW)
                self.assertEqual(result['changed'], 0)
                self.assertTrue(load_review_state(root)[review_key('pr', PR)]['done'])

    def test_unverified_wrong_url_unknown_target_missing_event_and_updated_at_noise_are_ignored(self):
        cases = [
            ('unverified', local_event(PR, verified=False), {'github_login': 'alice'}),
            ('wrong URL', local_event('https://github.com/dbt-labs/example/pull/99'), {'github_login': 'alice'}),
            ('non HTTPS URL', local_event('http://github.com/dbt-labs/example/pull/42'), {'github_login': 'alice'}),
            ('unknown target', local_event(PR, {'type': 'bot', 'name': 'helper'}), {'github_login': 'alice'}),
            ('no event identity', local_event(PR, event_id=''), {'github_login': 'alice'}),
            ('wrong current user', local_event(PR, {'type': 'user', 'login': 'bob'}), {'github_login': 'alice'}),
            ('updatedAt only', None, {'github_login': 'alice'}),
        ]
        for index, (label, evidence, identity) in enumerate(cases, 1):
            with self.subTest(label=label):
                root = self.root / str(index)
                row_url = PR.replace('/42', '/' + str(index))
                save_review_state(root, snapshot([{'url': row_url}]), {'kind': 'pr', 'url': row_url, 'done': True},
                                  datetime.fromisoformat(DONE_AT))
                row = {'url': row_url, 'updatedAt': '2099-12-31T00:00:00Z'}
                if evidence is not None:
                    if label not in ('wrong URL', 'non HTTPS URL'):
                        evidence = dict(evidence, url=row_url)
                    row['localReRequest'] = evidence
                result = apply_verified_re_requests(root, snapshot([row], review_identity=identity), now=NOW)
                self.assertEqual(result['changed'], 0)
                self.assertTrue(load_review_state(root)[review_key('pr', row_url)]['done'])

    def test_only_configured_team_targets_match_and_current_team_can_reopen(self):
        other = {'type': 'team', 'slug': 'other-team', 'id': 8, 'name': 'Other'}
        current = {'type': 'team', 'slug': 'transport', 'id': 10, 'name': 'Transport'}
        for index, (target, teams, expected) in enumerate([
                (other, [{'slug': 'transport', 'id': 10}], 0),
                (current, [{'slug': 'transport', 'id': 10}], 1)], 1):
            with self.subTest(target=target):
                root = self.root / 'team' / str(index)
                row_url = PR.replace('/42', '/' + str(index))
                save_review_state(root, snapshot([{'url': row_url}]), {'kind': 'pr', 'url': row_url, 'done': True},
                                  datetime.fromisoformat(DONE_AT))
                event = local_event(row_url, target)
                result = apply_verified_re_requests(
                    root, snapshot([{'url': row_url, 'localReRequest': event}],
                                   review_identity={'github_teams': teams}), now=NOW)
                self.assertEqual(result['changed'], expected)
                self.assertEqual(load_review_state(root)[review_key('pr', row_url)]['done'], expected == 0)

    def test_personal_review_policy_evidence_requires_re_requested_and_current_user(self):
        self.mark_done()
        row = {'url': PR, 'personalReview': {
            'userLogin': 'alice', 'reRequested': True, 'coverage': 'complete', 'timelineCoverage': 'complete',
            'reRequestEvidence': {'id': 123, 'nodeId': 'event-node', 'createdAt': REQUESTED_AT,
                                  'target': {'type': 'user', 'login': 'alice'}}}}
        result = apply_verified_re_requests(self.root, snapshot([row]), now=NOW)
        self.assertEqual(result['changed'], 1)

    def test_rfc_requires_verified_notion_user_identity(self):
        self.mark_done('rfc', RFC)
        event = local_event(RFC, {'type': 'user', 'id': 'notion-user-1'})
        row = {'url': RFC, 'localReRequest': event}
        no_identity = apply_verified_re_requests(self.root, snapshot(rfc_rows=[row]), now=NOW)
        self.assertEqual(no_identity['changed'], 0)
        self.assertTrue(load_review_state(self.root)[review_key('rfc', RFC)]['done'])
        with_identity = apply_verified_re_requests(
            self.root, snapshot(rfc_rows=[row], review_identity={'notion_user_id': 'notion-user-1'}), now=NOW)
        self.assertEqual(with_identity['changed'], 1)
        self.assertFalse(load_review_state(self.root)[review_key('rfc', RFC)]['done'])

    def test_rfc_accepts_explicit_verified_stakeholder_response_for_current_notion_user(self):
        self.mark_done('rfc', RFC)
        response_target = {'type': 'stakeholder_response', 'response_id': 'response-42',
                           'verified': True, 'respondents': [{'type': 'user', 'id': 'notion-user-1'}]}
        row = {'url': RFC, 'localReRequest': local_event(RFC, response_target)}
        result = apply_verified_re_requests(
            self.root, snapshot(rfc_rows=[row], review_identity={'notion_user_id': 'notion-user-1'}), now=NOW)
        self.assertEqual(result['changed'], 1)

    def test_corrupt_store_is_preserved_and_prevents_automatic_changes(self):
        self.mark_done()
        path = self.root / 'review-state' / 'corrupt.json'
        path.write_text('{broken')
        original = path.read_bytes()
        data = snapshot([{'url': PR, 'localReRequest': local_event(PR)}], review_identity={'github_login': 'alice'})
        result = apply_verified_re_requests(self.root, data, now=NOW)
        self.assertEqual(result['changed'], 0)
        self.assertTrue(result['warnings'])
        self.assertEqual(path.read_bytes(), original)
        self.assertTrue(load_review_state(self.root)[review_key('pr', PR)]['done'])


if __name__ == '__main__':
    unittest.main()
