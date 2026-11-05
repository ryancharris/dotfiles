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
| `ctrl+shift+↑` / `ctrl+shift+↓` (in tray) | Grow/shrink tray height by 5 lines |

Panel appearance lives in `quick-access-terminal.conf` (bottom edge tray, 25 lines).
Height resets to 25 lines each time the tray is re-opened; `tray-resize.sh` adjusts it live.

## macOS

| Key | Action |
|-----|--------|
| `cmd+]` | Cycle OS windows forward |
| `cmd+[` | Cycle OS windows backward |
