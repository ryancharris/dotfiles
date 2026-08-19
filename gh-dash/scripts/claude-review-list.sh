#!/usr/bin/env bash
# Check in on, resume, or dismiss headless PR reviews started by claude-review.sh.
set -euo pipefail

review_dir="${TMPDIR:-/tmp}/claude-reviews"
mkdir -p "$review_dir"
self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

status_of() {
  local base="$1" status
  status="$(cat "${base}.status" 2>/dev/null || echo unknown)"
  if [[ "$status" == "running" ]]; then
    if [[ -f "${base}.pid" ]] && kill -0 "$(cat "${base}.pid")" 2>/dev/null; then
      echo running
    else
      echo interrupted
    fi
  else
    echo "$status"
  fi
}

cmd_list() {
  shopt -s nullglob
  for f in "$review_dir"/*.status; do
    base="${f%.status}"
    id="$(basename "$base")"
    if [[ -f "${base}.name" ]]; then
      name="$(cat "${base}.name")"
    else
      name="$(basename "$(cat "${base}.repo" 2>/dev/null || echo '?')") #$(cat "${base}.pr" 2>/dev/null || echo '?')"
    fi
    printf '%s\t%s\t%s\n' "$id" "$name" "$(status_of "$base")"
  done
}

render_md() {
  if command -v bat >/dev/null 2>&1; then
    bat --language=md --style=plain --color=always --paging=never "$1"
  else
    cat "$1"
  fi
}

cmd_preview() {
  local base="$review_dir/$1"
  echo "status: $(status_of "$base")"
  echo "---"
  if [[ -s "${base}.md" ]]; then
    render_md "${base}.md"
  else
    echo "(no output yet)"
  fi
}

cmd_view() {
  local base="$review_dir/$1"
  if [[ -s "${base}.md" ]]; then
    render_md "${base}.md" | less -R
  else
    printf 'no output yet (status: %s)\n\npress q to go back; ctrl-r in the picker to refresh once it finishes.\n' "$(status_of "$base")" | less -R
  fi
}

cmd_approve() {
  local id="$1" base="$review_dir/$1" repo pr comment
  repo="$(cat "${base}.repo" 2>/dev/null || echo '?')"
  pr="$(cat "${base}.pr" 2>/dev/null || echo '?')"
  comment="$(awk -F': ' '/^[[:space:]]*prApproveComment:/{print $2; exit}' "$HOME/.config/gh-dash/config.yml" 2>/dev/null || true)"
  comment="${comment%\"}"
  comment="${comment#\"}"

  local ok=0
  if [[ -n "$comment" ]]; then
    (cd "$repo" && gh pr review "$pr" --approve -b "$comment") >>"${base}.approve.log" 2>&1 || ok=1
  else
    (cd "$repo" && gh pr review "$pr" --approve) >>"${base}.approve.log" 2>&1 || ok=1
  fi

  if [[ "$ok" -eq 0 ]]; then
    cmd_dismiss "$id"
  fi
}

cmd_resume() {
  local base="$review_dir/$1"
  cd "$(cat "${base}.repo")"
  claude --resume "$(cat "${base}.session")"
}

cmd_dismiss() {
  local base="$review_dir/$1"

  if [[ -f "${base}.pid" ]]; then
    local pid
    pid="$(cat "${base}.pid")"
    kill -TERM -- "-$pid" 2>/dev/null || true
  fi

  # Only removes this review from our own tracking/picker. The underlying
  # claude session transcript is untouched and stays resumable normally
  # (cd <repo> && claude --resume) — dismiss just declutters our list.
  trash "${base}".* 2>/dev/null || rm -f "${base}".*
}

cmd_purge_stale() {
  local now cutoff
  now="$(date +%s)"
  cutoff=$((now - 48 * 3600))
  shopt -s nullglob
  for f in "$review_dir"/*.started; do
    local base id started
    base="${f%.started}"
    id="$(basename "$base")"
    started="$(cat "$f" 2>/dev/null || echo "$now")"
    if [[ "$started" -lt "$cutoff" ]]; then
      cmd_dismiss "$id"
    fi
  done
}

case "${1:-}" in
  list) cmd_list ;;
  preview) cmd_preview "$2" ;;
  view) cmd_view "$2" ;;
  resume) cmd_resume "$2" ;;
  dismiss) cmd_dismiss "$2" ;;
  approve) cmd_approve "$2" ;;
  purge) cmd_purge_stale ;;
  *)
    if ! command -v fzf >/dev/null 2>&1; then
      echo "fzf is required for the review picker (brew install fzf)" >&2
      cmd_list
      exit 1
    fi
    cmd_list | fzf \
      --delimiter='\t' --with-nth=2,3 \
      --header $'enter  view\nctrl-o resume\nctrl-a approve\nctrl-x dismiss\nctrl-r refresh\nshift-up/down scroll preview' \
      --header-border \
      --preview "'$self' preview {1}" \
      --preview-window=right:60%:wrap \
      --bind "ctrl-r:reload('$self' list)" \
      --bind "ctrl-x:execute-silent('$self' dismiss {1})+reload('$self' list)" \
      --bind "ctrl-o:become('$self' resume {1})" \
      --bind "ctrl-a:execute-silent('$self' approve {1})+reload('$self' list)" \
      --bind "enter:execute('$self' view {1})"
    ;;
esac
