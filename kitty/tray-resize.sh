#!/bin/sh
# Resize the quick access tray's thickness, relative to its current size.
# Usage (mapped to keys via remote_control_script in quick-access-terminal.conf):
#   tray-resize.sh 5   # grow by 5
#   tray-resize.sh -5  # shrink by 5
# Grows/shrinks height for top/bottom trays, width for left/right trays.
set -e

delta="$1"
kitten_bin="${KITTY_KITTEN_BIN:-/opt/homebrew/bin/kitten}"
state="${TMPDIR:-/tmp}/kitty-tray-edge-${KITTY_PID:-manual}"

edge=""
if [ -f "$state" ]; then read -r edge _ < "$state"; fi
case "$edge" in
    left|right) dim=columns; min=20; max=200 ;;
    *)          dim=lines;   min=5;  max=60  ;;
esac

size=$("$kitten_bin" @ ls | grep -o "\"$dim\": [0-9]*" | head -1 | grep -o '[0-9]*$')
[ -n "$size" ] || exit 1

new_size=$((size + delta))
[ "$new_size" -lt "$min" ] && new_size=$min
[ "$new_size" -gt "$max" ] && new_size=$max

"$kitten_bin" @ resize-os-window --action=os-panel --incremental "$dim=$new_size"
