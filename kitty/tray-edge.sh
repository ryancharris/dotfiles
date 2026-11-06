#!/bin/sh
# Move the quick access tray to an edge of the screen.
# Usage (mapped to keys via remote_control_script in quick-access-terminal.conf):
#   tray-edge.sh top|right|bottom|left
set -e

edge="$1"
case "$edge" in
    top|bottom|left|right) ;;
    *)
        echo "usage: $(basename "$0") top|right|bottom|left" >&2
        exit 2
        ;;
esac

kitten_bin="${KITTY_KITTEN_BIN:-/opt/homebrew/bin/kitten}"

# Horizontal edges are sized in lines, vertical edges in columns.
# Keep these in sync with `lines`/`columns` in quick-access-terminal.conf.
case "$edge" in
    top|bottom) size="lines=${KITTY_TRAY_LINES:-25}" ;;
    *)          size="columns=${KITTY_TRAY_COLUMNS:-80}" ;;
esac

"$kitten_bin" @ resize-os-window --action=os-panel --incremental "edge=$edge" "$size"

# Remember the edge so tray-resize.sh knows which dimension to grow/shrink.
echo "$edge" > "${TMPDIR:-/tmp}/kitty-tray-edge-${KITTY_PID:-manual}"
