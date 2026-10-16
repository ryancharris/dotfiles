#!/usr/bin/env python3
"""Create a bounded model view of saved gh pr view JSON; retain the raw file."""
import argparse
import json
import re
from pathlib import Path

FAIL = {'ACTION_REQUIRED', 'CANCELLED', 'FAILURE', 'STALE', 'STARTUP_FAILURE', 'TIMED_OUT'}
OK = {'SUCCESS', 'NEUTRAL', 'SKIPPED'}


def check_summary(checks):
    counts = dict(total=len(checks), failing=0, pending=0, completedWithoutFailure=0, unknown=0)
    for check in checks:
        kind = check.get('__typename')
        if kind == 'CheckRun':
            if check.get('status') != 'COMPLETED':
                bucket = 'pending'
            elif check.get('conclusion') in FAIL:
                bucket = 'failing'
            elif check.get('conclusion') in OK:
                bucket = 'completedWithoutFailure'
            else:
                bucket = 'unknown'
        elif kind == 'StatusContext':
            state = check.get('state')
            bucket = ('failing' if state in {'ERROR', 'FAILURE'} else
                      'pending' if state in {'EXPECTED', 'PENDING'} else
                      'completedWithoutFailure' if state == 'SUCCESS' else 'unknown')
        else:
            bucket = 'unknown'
        counts[bucket] += 1
    counts['state'] = ('FAILING' if counts['failing'] else 'PENDING' if counts['pending'] else
                       'UNKNOWN' if counts['unknown'] else 'PASSING' if counts['total'] else 'NONE')
    return counts


def compact(pr, body_limit=1200):
    keys = ('number', 'title', 'url', 'isDraft', 'baseRefName', 'mergeable',
            'mergeStateStatus', 'reviewDecision', 'additions', 'deletions',
            'changedFiles', 'updatedAt')
    result = {key: pr.get(key) for key in keys}
    author = pr.get('author') or {}
    result['author'] = author.get('login') if isinstance(author, dict) else author
    result['checkSummary'] = check_summary(pr.get('statusCheckRollup') or [])
    if 'statusCheckRollup' not in pr:
        result['checkSummary'].update(total=None, state='UNKNOWN', availability='unavailable')
    commits = pr.get('commits') or []
    explicit_count = pr.get('commitCount', pr.get('commitsTotalCount'))
    result['commitCount'] = explicit_count if explicit_count is not None else len(commits) if 'commits' in pr else None
    result['commitCountUnverified'] = explicit_count is None and ('commits' not in pr or len(commits) >= 100)
    result['commitHeadlinesSample'] = [item.get('messageHeadline', '') for item in commits[:3]]
    paths = [item.get('path', '') for item in (pr.get('files') or [])]
    result['filePathsSample'] = paths[:12]
    result['filePathsSampled'] = pr.get('changedFiles') is None or pr['changedFiles'] > len(result['filePathsSample'])
    body = pr.get('body') or ''
    result['bodyExcerpt'] = body[:body_limit]
    result['bodyExcerptTruncated'] = len(body) > body_limit
    lines = body.splitlines()
    evidence = []
    for index, line in enumerate(lines):
        if re.search(r"\b(hold|blocked|prerequisit\w*|unreviewed|fails? open|failing open)\b|don['’]t merge|do not merge", line, re.I):
            excerpt = '\n'.join(lines[max(0, index - 1):index + 3])[:600]
            if excerpt not in evidence:
                evidence.append(excerpt)
    result['constraintExcerpts'] = evidence[:6]
    result['constraintExcerptsTruncated'] = len(evidence) > 6
    observed_comments = len(pr.get('comments') or []) if 'comments' in pr else pr.get('commentCount', 0)
    if observed_comments >= 20:
        result['commentCountObserved'] = observed_comments
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_json', type=Path)
    parser.add_argument('compact_json', type=Path)
    args = parser.parse_args()
    raw = json.loads(args.raw_json.read_text())
    output = [compact(item) for item in raw] if isinstance(raw, list) else compact(raw)
    args.compact_json.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'compact_file': str(args.compact_json), 'records': len(output) if isinstance(output, list) else 1}))


if __name__ == '__main__':
    main()
