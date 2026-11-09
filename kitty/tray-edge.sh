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
state="${TMPDIR:-/tmp}/kitty-tray-edge-${KITTY_PID:-manual}"
conf="${KITTY_CONFIG_DIRECTORY:-$HOME/.config/kitty}/quick-access-terminal.conf"

# State is "<edge>" when docked. While maximized it is:
# "<edge> <lines> <columns> <width_px> <height_px>".
current_edge=""; saved_lines=""; saved_columns=""; saved_width_px=""; saved_height_px=""
if [ -f "$state" ]; then
    read -r current_edge saved_lines saved_columns saved_width_px saved_height_px < "$state"
fi
case "$current_edge" in
    top|bottom|left|right) ;;
    *)
        current_edge=""
        if [ -f "$conf" ]; then
            current_edge=$(awk '$1 == "edge" { print $2; exit }' "$conf")
        fi
        ;;
esac

valid_size() {
    case "$1" in
        ''|*[!0-9]*|0) return 1 ;;
        *) return 0 ;;
    esac
}

# On macOS, preserve the tray's physical thickness in pixels. Cell counts are
# not interchangeable across orientations because cells are wider than tall.
pixel_thickness() {
    [ "$(uname -s)" = "Darwin" ] || return 1
    command -v osascript >/dev/null 2>&1 || return 1

    bounds=$(osascript 2>/dev/null <<'OSA'
tell application "System Events"
    tell process "kitty-quick-access"
        if (count windows) is 0 then error "quick access panel is hidden"
        set p to position of window 1
        set s to size of window 1
        return {p, s}
    end tell
end tell
OSA
    ) || return 1

    width=""; height=""
    IFS=', ' read -r _x _y width height <<EOF
$bounds
EOF
    case "$current_edge" in
        left|right) thickness=$width ;;
        *)          thickness=$height ;;
    esac
    valid_size "$thickness" || return 1
    printf '%s\n' "$thickness"
}

if valid_size "$saved_width_px" && valid_size "$saved_height_px"; then
    case "$edge" in
        top|bottom) thickness=$saved_height_px ;;
        *)          thickness=$saved_width_px ;;
    esac
    unit=px
elif [ -n "$saved_lines" ] && [ -n "$saved_columns" ]; then
    # Old maximized state did not record pixels; fall back to cell counts.
    case "$edge" in
        top|bottom) thickness=$saved_lines ;;
        *)          thickness=$saved_columns ;;
    esac
    unit=""
else
    if thickness=$(pixel_thickness); then
        unit=px
    else
        case "$current_edge" in
            left|right) current_dimension=columns ;;
            *)          current_dimension=lines ;;
        esac
        thickness=$("$kitten_bin" @ ls | grep -o "\"$current_dimension\": [0-9]*" | head -1 | grep -o '[0-9]*$')
        unit=""
    fi
fi

case "$edge" in
    top|bottom) size="lines=${thickness:-${KITTY_TRAY_LINES:-25}}$unit" ;;
    *)          size="columns=${thickness:-${KITTY_TRAY_COLUMNS:-80}}$unit" ;;
esac

"$kitten_bin" @ resize-os-window --action=os-panel --incremental "edge=$edge" "$size"

# Persist the edge. The quick access kitten rebuilds the panel from this config
# every time it is shown, so keeping the choice only in memory resets on show.
if [ -f "$conf" ]; then
    configured_edge=$(awk '$1 == "edge" { print $2; exit }' "$conf")
    if [ "$configured_edge" != "$edge" ]; then
        tmp="$conf.tmp.$$"
        awk -v edge="$edge" '
            BEGIN { updated = 0 }
            !updated && $1 == "edge" { print "edge " edge; updated = 1; next }
            { print }
            END { if (!updated) print "edge " edge }
        ' "$conf" > "$tmp"
        mv "$tmp" "$conf"
    fi
fi

# Remember the edge so tray-resize.sh knows which dimension to grow/shrink.
echo "$edge" > "$state"
