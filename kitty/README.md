# kitty

Custom keybindings defined in `kitty.conf`. Main modifier is `cmd`.

## Config

| Key | Action |
|-----|--------|
| `cmd+shift+r` | Reload config |

## Windows

| Key | Action |
|-----|--------|
| `cmd+enter` | New window |
| `cmd+shift+h` | New horizontal split |
| `cmd+shift+v` | New vertical split |
| `cmd+h` | Focus window left |
| `cmd+l` | Focus window right |
| `cmd+k` | Focus window up |
| `cmd+j` | Focus window down |
| `cmd+r` | Start resizing window |

## Tabs

| Key | Action |
|-----|--------|
| `cmd+t` | New tab |
| `cmd+w` | Close tab |
| `cmd+1` … `cmd+9` | Go to tab 1–9 |
| `cmd+0` | Go to tab 0 |
| `cmd+shift+.` | Move tab forward |
| `cmd+shift+,` | Move tab backward |
| `cmd+shift+d` | Detach tab |

## Layouts

| Key | Action |
|-----|--------|
| `cmd+shift+f` | Stack layout |
| `cmd+shift+g` | Splits layout |

## Quick access terminal

Global toggle (works from any app), configured in AeroSpace:

| Key | Action |
|-----|--------|
| `alt+t` | Show/hide the kitty quick access tray |
| `ctrl+shift+h` (in tray) | Dock tray to the **left** edge |
| `ctrl+shift+j` (in tray) | Dock tray to the **bottom** edge |
| `ctrl+shift+k` (in tray) | Dock tray to the **top** edge |
| `ctrl+shift+l` (in tray) | Dock tray to the **right** edge |
| `ctrl+shift+m` (in tray) | Toggle full screen and back to the docked size |
| `ctrl+shift+↑` / `ctrl+shift+↓` (in tray) | Grow/shrink tray thickness by 5 |

Docking uses vim-style directions (`h`/`j`/`k`/`l` = left/down/up/right), matching
`cmd+hjkl` window focus and AeroSpace's `alt+hjkl`.

Panel appearance lives in `quick-access-terminal.conf` (bottom edge tray, 25 lines,
80 columns when docked vertically). `tray-edge.sh` docks it live, `tray-resize.sh`
changes the thickness live — height for top/bottom, width for left/right —
and `tray-maximize.sh` fills the screen (kitty's `edge center`) then restores the
previous edge and size.

Edge and size reset to the config values each time the tray is re-opened, and
keybinding changes need a tray restart (quit the `kitty-quick-access` process,
then `alt+t`) because the keymaps are applied when the panel is created.

## macOS

| Key | Action |
|-----|--------|
| `cmd+]` | Cycle OS windows forward |
| `cmd+[` | Cycle OS windows backward |
