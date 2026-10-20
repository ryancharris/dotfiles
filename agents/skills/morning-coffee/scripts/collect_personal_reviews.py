#!/usr/bin/env python3
"""Collect personal-review eligibility from scoped PR URLs; print compact evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

from personal_review_policy import personal_review_decision


def canonical_url(value, login):
    url = value if isinstance(value, str) else value["url"]
    parsed = urlparse(url)
    match = re.fullmatch(r"/([\w.-]+)/([\w.-]+)/pull/([1-9]\d*)/?", parsed.path)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or not match
            or parsed.query or parsed.fragment
            or match[1].casefold() not in {"dbt-labs", login.casefold()}):
        raise ValueError("Expected an allowed-owner GitHub PR URL: " + url)
    return "https://github.com/" + "/".join(match.groups()[:2]) + "/pull/" + match[3]


def fetch_pages(endpoint, destination, shape):
    """Only fully decoded, correctly shaped pages count as available evidence."""
    try:
        response = subprocess.run(
            ["gh", "api", "--method", "GET", "--paginate", "--slurp", endpoint],
            capture_output=True, text=True, timeout=120, check=False,
        )
        destination.write_text(response.stdout, encoding="utf-8")
        if response.returncode:
            destination.with_suffix(".error.txt").write_text(response.stderr, encoding="utf-8")
            return None
        pages = json.loads(response.stdout)
        if not isinstance(pages, list) or not pages:
            return None
        if shape == "array":
            if not all(isinstance(page, list) and all(isinstance(row, dict) for row in page)
                       for page in pages):
                return None
            return [row for page in pages for row in page]
        if not all(isinstance(page, dict)
                   and all(isinstance(page.get(key), list)
                           and all(isinstance(row, dict) for row in page[key])
                           for key in ("users", "teams")) for page in pages):
            return None
        return {key: [row for page in pages for row in page[key]] for key in ("users", "teams")}
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        destination.with_suffix(".error.txt").write_text(str(error), encoding="utf-8")
        return None


def compact_decision(decision):
    result = {key: value for key, value in decision.items() if key != "personalReviews"}
    latest = decision.get("latestEffectiveReview")
    if latest:
        result["latestEffectiveReview"] = {
            key: latest.get(key) for key in ("id", "state", "submitted_at", "html_url", "commit_id")
        }
    return result


def collect_one(url, login, teams, root):
    owner, repo, _, number = urlparse(url).path.strip("/").split("/")
    directory = root / owner / repo / number
    directory.mkdir(parents=True, exist_ok=False)
    pull = f"repos/{owner}/{repo}/pulls/{number}"
    calls = 1
    reviews = fetch_pages(pull + "/reviews?per_page=100", directory / "reviews.json", "array")
    decision = personal_review_decision(reviews, login, None, teams)
    # Reuse the policy's ordering rules; COMMENTED never resets an effective approval.
    if decision["state"] == "APPROVED":
        calls += 1
        targets = fetch_pages(pull + "/requested_reviewers?per_page=100",
                              directory / "targets.json", "targets")
        decision = personal_review_decision(reviews, login, targets, teams)
        if targets is not None:
            calls += 1
            timeline = fetch_pages(f"repos/{owner}/{repo}/issues/{number}/timeline?per_page=100",
                                   directory / "timeline.json", "array")
            decision = personal_review_decision(
                reviews, login, targets, teams, timeline, timeline_complete=timeline is not None,
            )
    result = {"url": url, "personalReview": compact_decision(decision), "apiInvocations": calls}
    (directory / "decision.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path, help="JSON array of PR URLs or objects with url")
    parser.add_argument("--login", required=True, help="Login verified by gh api user")
    parser.add_argument("--team", action="append", default=[], help="Configured dbt-labs team slug")
    parser.add_argument("--output-dir", required=True, type=Path, help="New private temporary directory")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    if not isinstance(candidates, list):
        parser.error("candidates must be a JSON array")
    try:
        urls = list(dict.fromkeys(canonical_url(value, args.login) for value in candidates))
    except (KeyError, TypeError, ValueError) as error:
        parser.error(str(error))
    args.output_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(
            lambda url: collect_one(url, args.login, args.team, args.output_dir), urls,
        ))
    summary = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "candidateCount": len(results),
        "excludedCount": sum(row["personalReview"]["excluded"] for row in results),
        "reRequestedCount": sum(row["personalReview"]["reRequested"] for row in results),
        "unknownCount": sum(row["personalReview"]["coverage"] != "complete" for row in results),
        "apiInvocations": sum(row["apiInvocations"] for row in results),
        "items": results,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
