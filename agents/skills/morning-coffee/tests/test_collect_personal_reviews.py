"""Exercise the CLI against a fake gh, including pagination and failure retention."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_state import save_review_state, verified_re_request

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_personal_reviews.py"


def review(state="APPROVED", stamp="2026-10-19T12:00:00Z", number=1):
    return {"id": number, "user": {"login": "Tester"}, "state": state,
            "submitted_at": stamp, "html_url": "https://github.com/dbt-labs/example/pull/2#review",
            "commit_id": "abc", "body": "large private review body" * 100}


class CollectorCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        gh = self.root / "gh"
        gh.write_text(
            "#!" + sys.executable + "\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "assert sys.argv[1:7] == ['api', '--method', 'GET', '--paginate', '--slurp', sys.argv[6]]\n"
            "with open(os.environ['CALLS'], 'a') as f: f.write(sys.argv[-1] + '\\n')\n"
            "entry=json.loads(Path(os.environ['DATA']).read_text())[sys.argv[-1]]\n"
            "print(json.dumps(entry.get('pages', [])))\n"
            "sys.exit(entry.get('exit', 0))\n",
            encoding="utf-8",
        )
        gh.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        CALLS=str(self.root / "calls"), DATA=str(self.root / "data.json"))

    def tearDown(self):
        self.temp.cleanup()

    def run_collector(self, candidates, data, *extra):
        input_path = self.root / "candidates.json"
        input_path.write_text(json.dumps(candidates), encoding="utf-8")
        (self.root / "data.json").write_text(json.dumps(data), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(input_path), "--login", "tester",
             "--team", "transport", "--output-dir", str(self.root / "evidence"), *extra],
            text=True, capture_output=True, env=self.env,
        )

    def test_paginated_policy_and_lazy_requests(self):
        data = {}
        def add(n, resource, pages=None, exit=0):
            noun = "issues" if resource == "timeline" else "pulls"
            data[f"repos/dbt-labs/example/{noun}/{n}/{resource}?per_page=100"] = {
                "pages": pages, "exit": exit,
            }
        # No personal review: do not ask for current targets or a timeline.
        add(1, "reviews", [[{"id": 9, "user": {"login": "someone"}, "state": "APPROVED"}]])
        # COMMENTED after APPROVED does not clear it; second-page targets/events matter.
        add(2, "reviews", [[review()], [review("COMMENTED", "2026-10-19T14:00:00Z", 2)]])
        add(2, "requested_reviewers", [{"users": [], "teams": []},
                                     {"users": [{"login": "TESTER"}], "teams": []}])
        add(2, "timeline", [[], [{"id": 5, "event": "review_requested",
                                "created_at": "2026-10-19T13:00:00Z",
                                "requested_reviewer": {"login": "tester"}}]])
        # Missing target evidence retains the candidate and skips the unusable timeline.
        add(3, "reviews", [[review()]])
        add(3, "requested_reviewers", exit=1)
        # New commits or an old request do not invalidate a personal approval.
        add(4, "reviews", [[review()]])
        add(4, "requested_reviewers", [{"users": [{"login": "tester"}], "teams": []}])
        add(4, "timeline", [[{"id": 1, "event": "review_requested",
                             "created_at": "2026-10-18T12:00:00Z",
                             "requested_reviewer": {"login": "tester"}}]])
        # A newer CHANGES_REQUESTED exits without any target request.
        add(5, "reviews", [[review(), review("CHANGES_REQUESTED", "2026-10-19T14:00:00Z", 2)]])
        # A failed history remains unknown, with no extra lookups.
        add(6, "reviews", exit=1)
        urls = [f"https://github.com/dbt-labs/example/pull/{n}" for n in range(1, 7)]
        result = self.run_collector(urls + [{"url": urls[0] + "/"}], data, "--workers", "4")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["candidateCount"], 6)
        self.assertEqual(summary["apiInvocations"], 11)
        self.assertEqual(summary["excludedCount"], 1)
        self.assertEqual(summary["reRequestedCount"], 1)
        self.assertEqual(summary["unknownCount"], 2)
        rows = {row["url"].split("/")[-1]: row["personalReview"] for row in summary["items"]}
        self.assertFalse(rows["1"]["excluded"])
        self.assertTrue(rows["2"]["reRequested"])
        self.assertEqual(rows["3"]["coverage"], "incomplete")
        self.assertTrue(rows["4"]["excluded"])
        self.assertEqual(rows["5"]["state"], "CHANGES_REQUESTED")
        self.assertEqual(rows["6"]["state"], "UNKNOWN")
        calls = (self.root / "calls").read_text().splitlines()
        self.assertEqual(len(calls), 11)
        self.assertFalse(any("/3/timeline" in call for call in calls))
        self.assertNotIn("large private review body", result.stdout)
        self.assertIn("large private review body",
                      (self.root / "evidence/dbt-labs/example/2/reviews.json").read_text())
        self.assertEqual(datetime.fromisoformat(summary["checked_at"]).utcoffset().total_seconds(), 0)
        self.assertEqual((self.root / "evidence").stat().st_mode & 0o777, 0o700)

    def test_team_rerequest_requires_a_current_relevant_target(self):
        stem = "repos/dbt-labs/example/"
        data = {
            stem + "pulls/1/reviews?per_page=100": {"pages": [[review()]]},
            stem + "pulls/1/requested_reviewers?per_page=100": {
                "pages": [{"users": [], "teams": [{"id": 10, "slug": "transport"}]}]},
            stem + "issues/1/timeline?per_page=100": {"pages": [[{
                "id": 1, "event": "review_requested", "created_at": "2026-10-19T13:00:00Z",
                "requested_reviewer": {"id": 10, "slug": "transport"}}]]},
        }
        result = self.run_collector(["https://github.com/dbt-labs/example/pull/1"], data)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["reRequestedCount"], 1)

    def test_local_done_without_personal_approval_gets_targeted_verified_re_request(self):
        url = "https://github.com/dbt-labs/example/pull/1"
        state_root = self.root / "local-state"
        done_at = "2026-10-19T12:00:00+00:00"
        save_review_state(state_root, {"reviews": {"items": [{"url": url}]}},
                          {"kind": "pr", "url": url, "done": True}, datetime.fromisoformat(done_at))
        data = {
            "repos/dbt-labs/example/pulls/1/reviews?per_page=100": {
                "pages": [[{"id": 9, "user": {"login": "someone-else"}, "state": "APPROVED"}]]},
            "repos/dbt-labs/example/pulls/1/requested_reviewers?per_page=100": {
                "pages": [{"users": [{"login": "TESTER"}], "teams": []}]},
            "repos/dbt-labs/example/issues/1/timeline?per_page=100": {"pages": [[{
                "id": 55, "event": "review_requested", "created_at": "2026-10-19T13:00:00Z",
                "requested_reviewer": {"login": "tester"}}]]},
            "repos/dbt-labs/example/pulls/2/reviews?per_page=100": {
                "pages": [[{"id": 10, "user": {"login": "someone-else"}, "state": "APPROVED"}]]},
        }
        result = self.run_collector(
            [url, "https://github.com/dbt-labs/example/pull/2"], data,
            "--local-state-root", str(state_root), "--workers", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["apiInvocations"], 4)
        self.assertEqual(summary["localReRequestCount"], 1)
        self.assertEqual(summary["reRequestedCount"], 0)
        first, second = summary["items"]
        self.assertEqual(first["personalReview"]["state"], "NONE")
        self.assertEqual(first["localReRequest"], {
            "verified": True, "event_id": "55", "requested_at": "2026-10-19T13:00:00+00:00",
            "url": url, "target": {"type": "user", "login": "tester"}, "current": True,
        })
        accepted = verified_re_request("pr", first, {"review_identity": {"github_login": "tester"}})
        self.assertEqual(accepted["event_id"], "55")
        self.assertEqual(accepted["url"], url)
        self.assertNotIn("localReRequest", second)
        calls = (self.root / "calls").read_text().splitlines()
        self.assertEqual(len(calls), 4)
        self.assertFalse(any("/2/requested_reviewers" in call or "/2/timeline" in call for call in calls))

    def test_local_done_event_must_be_later_and_current_relevant_team(self):
        urls = [f"https://github.com/dbt-labs/example/pull/{n}" for n in (1, 2, 3)]
        state_root = self.root / "local-state"
        for url in urls:
            save_review_state(state_root, {"reviews": {"items": [{"url": url}]}},
                              {"kind": "pr", "url": url, "done": True},
                              datetime.fromisoformat("2026-10-19T12:00:00+00:00"))
        data = {}
        for index, url in enumerate(urls, 1):
            stem = f"repos/dbt-labs/example/"
            data[stem + f"pulls/{index}/reviews?per_page=100"] = {
                "pages": [[{"id": index, "user": {"login": "other"}, "state": "APPROVED"}]]}
            data[stem + f"pulls/{index}/requested_reviewers?per_page=100"] = {
                "pages": [{"users": [], "teams": [{"id": 10, "slug": "transport"},
                                                    {"id": 11, "slug": "unrelated"}]}]}
            data[stem + f"issues/{index}/timeline?per_page=100"] = {"pages": [[{
                "id": index, "event": "review_requested",
                "created_at": "2026-10-19T11:00:00Z" if index == 1 else "2026-10-19T13:00:00Z",
                "requested_team": ({"id": 11, "slug": "unrelated"} if index == 2 else
                                   {"id": 10, "slug": "transport"})}]]}
        result = self.run_collector(urls, data, "--local-state-root", str(state_root), "--team", "transport")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["localReRequestCount"], 1)
        self.assertNotIn("localReRequest", summary["items"][0])
        self.assertNotIn("localReRequest", summary["items"][1])
        self.assertEqual(summary["items"][2]["localReRequest"]["target"], {
            "type": "team", "slug": "transport", "id": 10, "name": None})

    def test_partial_or_malformed_pages_never_exclude(self):
        data = {
            "repos/dbt-labs/example/pulls/1/reviews?per_page=100": {"pages": [[review()]]},
            "repos/dbt-labs/example/pulls/1/requested_reviewers?per_page=100": {
                "pages": [{"users": [], "teams": []}]},
            "repos/dbt-labs/example/issues/1/timeline?per_page=100": {"pages": [[], {}]},
        }
        result = self.run_collector(["https://github.com/dbt-labs/example/pull/1"], data)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["excludedCount"], 0)
        self.assertEqual(summary["unknownCount"], 1)

    def test_owner_boundary_validated_before_any_provider_call(self):
        result = self.run_collector(["https://github.com/outsider/example/pull/1"], {})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "calls").exists())
        self.assertFalse((self.root / "evidence").exists())

    def test_deleted_reviewer_and_personal_owner(self):
        result = self.run_collector(["https://github.com/tester/example/pull/1"], {
            "repos/tester/example/pulls/1/reviews?per_page=100": {
                "pages": [[{"id": 1, "user": None, "state": "APPROVED"}]]},
        })
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["apiInvocations"], 1)
        self.assertEqual(summary["items"][0]["personalReview"]["state"], "NONE")

    def test_empty_queue(self):
        result = self.run_collector([], {})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["candidateCount"], 0)


if __name__ == "__main__":
    unittest.main()
