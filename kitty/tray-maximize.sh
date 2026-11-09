#!/bin/sh
# Toggle the quick access tray between full screen and its docked size.
# Usage (mapped to keys via remote_control_script in quick-access-terminal.conf):
#   tray-maximize.sh
set -e

kitten_bin="${KITTY_KITTEN_BIN:-/opt/homebrew/bin/kitten}"
state="${TMPDIR:-/tmp}/kitty-tray-edge-${KITTY_PID:-manual}"

# State is "<edge>" when docked. While maximized it is:
# "<edge> <lines> <columns> <width_px> <height_px>".
# With no state (fresh panel) fall back to the configured edge.
conf="${KITTY_CONFIG_DIRECTORY:-$HOME/.config/kitty}/quick-access-terminal.conf"
edge=""; saved_lines=""; saved_columns=""
if [ -f "$state" ]; then
    read -r edge saved_lines saved_columns _width_px _height_px < "$state"
elif [ -f "$conf" ]; then
    edge=$(awk '$1 == "edge" { print $2; exit }' "$conf")
fi
[ -n "$edge" ] || edge=bottom

if [ -n "$saved_lines" ]; then
    # Maximized: go back to the docked edge at the size it had before.
    # Both dimensions are passed; kitty ignores the one that does not apply.
    "$kitten_bin" @ resize-os-window --action=os-panel --incremental \
        "edge=$edge" "lines=$saved_lines" "columns=$saved_columns"
    echo "$edge" > "$state"
else
    lines=$("$kitten_bin" @ ls | grep -o '"lines": [0-9]*' | head -1 | grep -o '[0-9]*$')
    columns=$("$kitten_bin" @ ls | grep -o '"columns": [0-9]*' | head -1 | grep -o '[0-9]*$')
    [ -n "$lines" ] && [ -n "$columns" ] || exit 1

    width_px=""; height_px=""
    if [ "$(uname -s)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then
        bounds=$(osascript 2>/dev/null <<'OSA' || true
tell application "System Events"
    tell process "kitty-quick-access"
        if (count windows) is 0 then error "quick access panel is hidden"
        set s to size of window 1
        return s
    end tell
end tell
OSA
        )
        IFS=', ' read -r width_px height_px <<EOF
$bounds
EOF
        case "$width_px" in ''|*[!0-9]*|0) width_px="" ;; esac
        case "$height_px" in ''|*[!0-9]*|0) height_px="" ;; esac
    fi

    # edge=center anchors the panel to every screen edge, i.e. full screen.
    "$kitten_bin" @ resize-os-window --action=os-panel --incremental edge=center
    echo "$edge $lines $columns $width_px $height_px" > "$state"
fi
