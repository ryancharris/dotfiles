> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Hands-on: Ghostex (2026-11-12)

- Installed: `brew install --cask ghostex`. brew info listed 11.4.0, but the cask fetched **11.5.0** (`CFBundleShortVersionString` = 11.5.0). arm64.
- Driven entirely by the `ghostex` CLI, which talks to gxserver on 127.0.0.1:58744. Test project: `/private/tmp/gxt`, project id P8iyu.
- **Screenshots: none.** `screencapture -x` fails with "could not create image from display", both from this shell and from inside a Ghostex terminal. `ghostex screenshot` wraps screencapture and fails the same way. `orca computer` returns permission_denied because Accessibility is not granted. Running screencapture through kitty was refused by the auto-mode classifier. So every GUI-render claim below is backed by Ghostex's chat data API, not by pixels.
- Evidence dir: `<scratch>/ghostex/`

## Grades

| Test | Grade | Evidence |
|---|---|---|
| E-term | proven | `create-session --start` started a zmx-backed terminal. `send-message` ran commands and `read-text` returned the output `TERM_OK_42`. See `ghostex/term-h3.txt`. |
| E-chat | partial | `send-session-chat-message` "Reply with exactly: GHOSTEX_OK". The chat API (`read-session-chat`, the backend of the chat GUI) returned assistant text `GHOSTEX_OK` for both Claude and Codex. See `ghostex/chat-claude.json` and `ghostex/chat-codex.txt`. The GUI render was not visually verified because screenshots were blocked. |
| E-orch | proven | `coordinator create --agent claude` with a task to start one thread replying CHILD_OK. The coordinator ran `start-thread`, and a child session "child-test" (G4t36) appeared. Ghostex delivered a "Ghostex thread report" back to the parent, which replied `PARENT_GOT CHILD_OK`. See `ghostex/coord-chat.txt` and `ghostex/child-chat.txt`. |
| E-keys | partial | Ghostex has no provider-key store: secrets are only 1Password refs and one-off secret request cards, and the only API key it stores is Linear's. Keys belong to the agent CLIs. Proof of routing: in a Ghostex terminal, `OPENROUTER_API_KEY=sk-test-INVALID-0000 pi --no-session -p --model openrouter/openai/gpt-4o-mini ...` returned an OpenRouter `401 Invalid API key`. See `ghostex/term-pi-openrouter.txt`. Ghostex launches `pi` and `opencode` as agents, but the key path is the CLI's own, not the app's. |
| H1 | proven (CLI-level) | A single Claude session (G810p) is the real `claude` TUI running in a zmx terminal (`read-text` shows the Claude Code v2.1.318 banner and prompt) and also a chat transcript (`read-session-chat`). The README documents switching chat/CLI per session with Option+G. The hotkey itself was not exercised, because there is no GUI control. |
| H2 | proven | No Ghostex account or login prompt. Claude and Codex worked on their existing logins. `ghostex accounts` only offers optional account-swap helpers. |
| H3 | proven | Inside the Ghostex terminal: `SHELL=/bin/zsh`, which matches `dscl UserShell /bin/zsh`. Login=yes and interactive=yes. The ~/.zshrc alias `gsc='git switch -c'` is present. PATH contains `/Users/USER/.local/bin` (entry 2) and `/opt/homebrew/bin` and `/opt/homebrew/sbin` (entries 5–6). The user's starship prompt rendered. |
| H4 | proven | Claude: Ghostex ran the user's `claude` CLI, whose banner reads "Sonnet 5.5 · Claude Enterprise". `claude auth status` reports subscriptionType `enterprise`, orgName "[redacted organization] Enterprise". Reply: GHOSTEX_OK. Codex: Ghostex ran `codex --no-daemon -c developer_instructions=...`; `codex login status` reports "Logged in using ChatGPT" and the auth.json plan is `ent26`. Reply: GHOSTEX_OK. |
| H5 | partial | CLI route from a fresh install to a working agent took 3 commands and 0 settings or config files: `ghostex open <repo>`, `ghostex create-agent claude --project-id …`, `send-session-chat-message`. The defaults were sane: GitHub Dark Ghostty theme, the user's login shell, existing CLI logins. The GUI first-run onboarding was never seen (`firstLaunchSetupComplete:false`), so the GUI step count is unknown. |
| H6 | partial | The agent edited `hello.py` with its Edit tool. The chat payload carries a structured `patch.hunks` diff for the tool result, which the chat GUI renders as a diff. See `ghostex/chat-claude-detail.json` and `ghostex/final-git-diff.txt`. There is no screenshot, so syntax highlighting was not verified. |

## Extras
- **Config files:** `~/.config/ghostex/ghostty/config.ghostty` (Ghostty syntax; a managed block plus the user's own lines), `~/.config/ghostex/gxserver/config.json` (listeners: local 58744, remote 58745 off, bearer auth), and `~/.config/ghostex/native-sidebar-settings.json`. Most other app state is in `~/.local/state/ghostex/gxserver/state.db` (SQLite).
- **Linux:** yes, according to the README: AppImage, deb, rpm, tar.zst and AUR. Not tested.
- **Integrated browser:** yes. The app bundles CEF ("Ghostex Helper (Renderer/GPU/Plugin)") and has `gx browser open|open-pane|mcp`. Per the README, Chromium is installed on first use. Not opened.

## Side effects to know
- Ghostex wrote the skill **`~/.claude/skills/ghostex-coordinator`** when the coordinator started. That path resolves through a symlink to `~/dotfiles/agents/skills/ghostex-coordinator`, where it is untracked.
- It installed two LaunchAgents: `com.madda.ghostex.gxserver` and `com.madda.ghostex.gxserver-login-recovery`. Both have RunAtLoad=false.
- It created a shim at `/opt/homebrew/bin/gx`.
- `~/.zshrc`, `~/.claude/settings.json`, `~/.claude/CLAUDE.md` and `~/.codex/hooks.json` are unchanged (sha checked before and after).
- `~/.codex/config.toml` was rewritten at 10:04:43, when Codex launched. It now equals dotfiles HEAD. The writer is unconfirmed; it may have been the Codex CLI.
- Claude sessions were launched with `--append-system-prompt-file ~/.local/state/ghostex/gxserver/agent-note/note.md`. Codex sessions get `developer_instructions` via `-c`.
- Shutdown: `ghostex server stop-all` killed 5 zmx sessions, then the app was quit, then the GhostexEditor daemon was killed. No Ghostex processes remain.
