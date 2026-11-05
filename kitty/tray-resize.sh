#!/bin/sh
# Resize the quick access tray relative to its current height.
# Usage (mapped to keys via remote_control_script in quick-access-terminal.conf):
#   tray-resize.sh 5   # grow by 5 lines
#   tray-resize.sh -5  # shrink by 5 lines
set -e

delta="$1"
kitten_bin="${KITTY_KITTEN_BIN:-/opt/homebrew/bin/kitten}"

rows=$("$kitten_bin" @ ls | grep -o '"lines": [0-9]*' | head -1 | grep -o '[0-9]*')
[ -n "$rows" ] || exit 1

new_rows=$((rows + delta))
[ "$new_rows" -lt 5 ] && new_rows=5
[ "$new_rows" -gt 60 ] && new_rows=60

"$kitten_bin" @ resize-os-window --action=os-panel --incremental "lines=$new_rows"
