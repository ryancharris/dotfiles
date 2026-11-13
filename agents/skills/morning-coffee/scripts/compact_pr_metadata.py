#!/usr/bin/env python3
"""Create a bounded model view of saved gh pr view JSON; retain the raw file."""
import argparse
import json
import re
from pathlib import Path

FAIL = {'ACTION_REQUIRED', 'CANCELLED', 'FAILURE', 'STALE', 'STARTUP_FAILURE', 'TIMED_OUT'}
OK = {'SUCCESS', 'NEUTRAL', 'SKIPPED'}
RUNNING = {'IN_PROGRESS', 'PENDING', 'QUEUED', 'REQUESTED', 'WAITING'}


def check_summary(checks):
    counts = dict(total=len(checks), failing=0, pending=0, completedWithoutFailure=0, unknown=0)
    for check in checks:
        if not isinstance(check, dict):
            counts['unknown'] += 1
            continue
        kind = check.get('__typename')
        if kind == 'CheckRun':
            if check.get('status') in RUNNING:
                bucket = 'pending'
            elif check.get('status') != 'COMPLETED':
                bucket = 'unknown'
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


def readiness(pr, summary=None):
    """Bucket verified merge evidence without turning missing facts into success."""
    if summary is None:
        source_checks = pr.get('statusCheckRollup')
        summary = check_summary(source_checks if isinstance(source_checks, list) else [])
        if not isinstance(pr.get('statusCheckRollup'), list):
            summary.update(total=None, state='UNKNOWN', availability='unavailable')
    mergeable = pr.get('mergeable')
    merge_state = pr.get('mergeStateStatus')
    review = pr.get('reviewDecision')
    blockers = []
    if pr.get('isDraft') is True:
        blockers.append('draft')
    if mergeable == 'CONFLICTING' or merge_state == 'DIRTY':
        blockers.append('merge conflicts')
    if merge_state in {'BEHIND', 'BLOCKED', 'DRAFT', 'UNSTABLE'}:
        blockers.append({'BEHIND': 'behind base', 'BLOCKED': 'branch requirements blocked',
                         'DRAFT': 'draft', 'UNSTABLE': 'unstable checks'}[merge_state])
    if review in {'REVIEW_REQUIRED', 'CHANGES_REQUESTED'}:
        blockers.append('review required' if review == 'REVIEW_REQUIRED' else 'changes requested')
    if summary['failing']:
        blockers.append(f"{summary['failing']} failing checks")
    facts = [f"mergeability {mergeable or 'unavailable'}",
             f"merge state {merge_state or 'unavailable'}",
             f"review {review if review else 'no decision' if review == '' else 'unavailable'}"]
    if mergeable == 'UNKNOWN':
        facts[0] += ' — GitHub is still calculating'
    if pr.get('isDraft') is True:
        facts.append('draft')
    elif pr.get('isDraft') is not False:
        facts.append('draft status unavailable')
    total = summary['total']
    if total is None:
        facts.append('CI unavailable')
    elif not total:
        facts.append('CI: no checks reported')
    else:
        facts.append(f"CI {summary['completedWithoutFailure']}/{total} completed without failure; "
                     f"{summary['failing']} failing; {summary['pending']} pending; {summary['unknown']} unknown")
    unknown = (not isinstance(pr.get('isDraft'), bool) or
               mergeable not in {'MERGEABLE', 'CONFLICTING'} or
               merge_state not in {'CLEAN', 'BEHIND', 'BLOCKED', 'DRAFT', 'DIRTY', 'UNSTABLE'} or
               review not in {'', 'APPROVED', 'REVIEW_REQUIRED', 'CHANGES_REQUESTED'} or
               not total or summary['unknown'] > 0 or summary.get('availability') == 'unavailable')
    status = ('BLOCKED' if blockers else 'UNKNOWN' if unknown else
              'PENDING' if summary['pending'] else 'READY')
    if blockers:
        facts.insert(0, ', '.join(dict.fromkeys(blockers)))
    return {'status': status, 'facts': '; '.join(facts)}


def compact(pr, body_limit=1200):
    keys = ('number', 'title', 'url', 'isDraft', 'baseRefName', 'mergeable',
            'mergeStateStatus', 'reviewDecision', 'additions', 'deletions',
            'changedFiles', 'updatedAt')
    result = {key: pr.get(key) for key in keys}
    author = pr.get('author') or {}
    result['author'] = author.get('login') if isinstance(author, dict) else author
    source_checks = pr.get('statusCheckRollup')
    result['checkSummary'] = check_summary(source_checks if isinstance(source_checks, list) else [])
    if not isinstance(pr.get('statusCheckRollup'), list):
        result['checkSummary'].update(total=None, state='UNKNOWN', availability='unavailable')
    result['readiness'] = readiness(pr, result['checkSummary'])
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
