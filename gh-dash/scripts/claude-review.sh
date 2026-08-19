#!/usr/bin/env bash
# Fire-and-forget PR review: runs claude headlessly in the background so
# gh-dash regains control immediately, then notifies when it's done.
# State lives in $TMPDIR/claude-reviews so claude-review-list.sh can find it.
set -euo pipefail
set -m  # give the background job its own process group so dismiss can kill it as a unit

repo_path="$1"
pr_number="$2"

review_dir="${TMPDIR:-/tmp}/claude-reviews"
mkdir -p "$review_dir"
repo_name="$(basename "$repo_path")"
id="${repo_name}-${pr_number}"
base="$review_dir/$id"
session_id="$(uuidgen)"

pr_title="$(cd "$repo_path" && gh pr view "$pr_number" --json title -q .title 2>/dev/null || true)"
session_name="${repo_name} #${pr_number}"
if [[ -n "$pr_title" ]]; then
  session_name="${session_name}: ${pr_title:0:60}"
fi

echo "$repo_path" > "${base}.repo"
echo "$pr_number" > "${base}.pr"
echo "$session_id" > "${base}.session"
echo "$session_name" > "${base}.name"
date +%s > "${base}.started"
echo running > "${base}.status"
: > "${base}.md"

(
  cd "$repo_path"
  if claude -p --session-id "$session_id" --name "$session_name" --permission-mode auto "/review $pr_number" > "${base}.md" 2>&1; then
    echo done > "${base}.status"
  else
    echo "failed:$?" > "${base}.status"
  fi
  osascript -e "display notification \"PR #$pr_number review finished\" with title \"claude review: $repo_name\"" >/dev/null 2>&1 || true
) >/dev/null 2>&1 &
disown

echo $! > "${base}.pid"
echo "review running in background -> ${base}.md"
