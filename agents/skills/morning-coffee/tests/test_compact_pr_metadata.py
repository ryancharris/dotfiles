"""Readiness buckets must retain blockers and incomplete provider evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compact_pr_metadata import compact, readiness


def ready_pr():
    return {'isDraft': False, 'mergeable': 'MERGEABLE', 'mergeStateStatus': 'CLEAN',
            'reviewDecision': 'APPROVED', 'statusCheckRollup': [
                {'__typename': 'CheckRun', 'status': 'COMPLETED', 'conclusion': 'SUCCESS'}]}


class ReadinessTests(unittest.TestCase):
    def test_ready_requires_explicit_known_evidence_and_existing_checks(self):
        original = ready_pr()
        self.assertEqual(compact(original)['readiness']['status'], 'READY')
        for key in ('isDraft', 'mergeable', 'mergeStateStatus', 'reviewDecision', 'statusCheckRollup'):
            with self.subTest(missing=key):
                data = deepcopy(original)
                del data[key]
                self.assertEqual(readiness(data)['status'], 'UNKNOWN')
        for checks in ([], None, {}, 'unavailable', 1):
            self.assertEqual(readiness(dict(original, statusCheckRollup=checks))['status'], 'UNKNOWN')
            self.assertEqual(compact(dict(original, statusCheckRollup=checks))['readiness']['status'], 'UNKNOWN')
        self.assertEqual(readiness(dict(original, isDraft=0))['status'], 'UNKNOWN')
        self.assertEqual(readiness(dict(original, reviewDecision=''))['status'], 'READY')

    def test_each_authoritative_blocker_wins_over_unknown_or_running_checks(self):
        for change in ({'isDraft': True}, {'mergeable': 'CONFLICTING'},
                       {'mergeStateStatus': 'DIRTY'}, {'mergeStateStatus': 'BEHIND'},
                       {'mergeStateStatus': 'BLOCKED'}, {'mergeStateStatus': 'DRAFT'},
                       {'mergeStateStatus': 'UNSTABLE'}, {'reviewDecision': 'REVIEW_REQUIRED'},
                       {'reviewDecision': 'CHANGES_REQUESTED'}):
            with self.subTest(change=change):
                data = dict(ready_pr(), mergeable='UNKNOWN', statusCheckRollup=None)
                data.update(change)
                result = readiness(data)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertIn('CI unavailable', result['facts'])

    def test_unknown_mergeability_remains_unknown_even_with_running_checks(self):
        data = ready_pr()
        data['statusCheckRollup'][0].update(status='IN_PROGRESS', conclusion=None)
        self.assertEqual(readiness(data)['status'], 'PENDING')
        result = readiness(dict(data, mergeable='UNKNOWN', mergeStateStatus='UNKNOWN'))
        self.assertEqual(result['status'], 'UNKNOWN')
        self.assertIn('GitHub is still calculating', result['facts'])
        self.assertIn('1 pending', result['facts'])

    def test_failing_check_wins_over_pending_and_unknown_mergeability(self):
        data = ready_pr()
        data.update(mergeable='UNKNOWN', mergeStateStatus='UNKNOWN')
        data['statusCheckRollup'] = [
            {'__typename': 'StatusContext', 'state': 'FAILURE'},
            {'__typename': 'CheckRun', 'status': 'QUEUED', 'conclusion': None}]
        result = compact(data)
        self.assertEqual(result['readiness']['status'], 'BLOCKED')
        self.assertIn('1 failing', result['readiness']['facts'])
        self.assertIn('1 pending', result['readiness']['facts'])
        self.assertEqual(result['checkSummary']['state'], 'FAILING')

    def test_unknown_checks_never_become_pending_or_passing(self):
        for check in ({'__typename': 'CheckRun'},
                      {'__typename': 'CheckRun', 'status': 'NEW_STATE'},
                      {'__typename': 'CheckRun', 'status': 'COMPLETED', 'conclusion': 'NEW_CONCLUSION'},
                      {'__typename': 'StatusContext', 'state': 'NEW_STATE'},
                      {'__typename': 'UnknownNode'}, None):
            with self.subTest(check=check):
                result = compact(dict(ready_pr(), statusCheckRollup=[check]))
                self.assertEqual(result['readiness']['status'], 'UNKNOWN')
                self.assertEqual(result['checkSummary']['unknown'], 1)
                self.assertEqual(result['checkSummary']['pending'], 0)
                self.assertEqual(result['checkSummary']['completedWithoutFailure'], 0)

    def test_unknown_review_or_merge_state_never_becomes_ready(self):
        for change in ({'reviewDecision': 'NEW_DECISION'}, {'mergeStateStatus': 'HAS_HOOKS'},
                       {'mergeable': 'UNKNOWN'}, {'mergeStateStatus': 'UNKNOWN'}):
            self.assertEqual(readiness(dict(ready_pr(), **change))['status'], 'UNKNOWN')

    def test_neutral_and_skipped_checks_keep_their_exact_nonfailure_meaning(self):
        data = ready_pr()
        data['statusCheckRollup'] = [dict(data['statusCheckRollup'][0], conclusion=value)
                                   for value in ('SUCCESS', 'NEUTRAL', 'SKIPPED')]
        result = compact(data)
        self.assertEqual(result['readiness']['status'], 'READY')
        self.assertIn('3/3 completed without failure', result['readiness']['facts'])
        self.assertEqual(data['statusCheckRollup'][1]['conclusion'], 'NEUTRAL')


if __name__ == '__main__':
    unittest.main()
