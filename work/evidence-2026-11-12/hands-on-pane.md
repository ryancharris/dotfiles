> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Pane hands-on acceptance test (2026-11-12)

- App: Pane by Dcouple Inc (greenfield-inc/Pane), AGPL-3.0, Electron 43.8.3
- Installed version: 2.4.217 (CFBundleShortVersionString), bundle id com.dcouple.pane, notarized Developer ID (team FBM5YSF467)
- Install: official DMG `Pane-2.4.217-macOS-arm64.dmg` (sha256 489a9329...e3b9, matches the GitHub release digest), copied to /Applications
- Isolation: launched as `Pane --pane-dir=/private/tmp/pnd` with `DO_NOT_TRACK=1 RUNPANE_TELEMETRY_DISABLED=1`; CDP on `--remote-debugging-port=9333` for screenshots and UI control. `screencapture` and `orca computer` both lacked macOS permissions in this session, so all GUI evidence comes through CDP `Page.captureScreenshot`.
- Screenshots: `<scratch>/pane-shots/` (also at /private/tmp/pane-shots/)

## Telemetry
- PostHog product analytics are on by default. On a fresh install, before any settings UI is reachable, the renderer sends `analytics_default_enabled` and `app_first_opened` with identity attached (config showed `distinctId: email:<user's git email>`). You cannot opt out in the UI before those events fire.
- Mitigation used: I pre-seeded `/private/tmp/pnd/config.json` with `analytics.posthogHost = http://127.0.0.1:9`, so those events went to a dead local port. The `--pane-dir` override plus `DO_NOT_TRACK=1` also turns off the install heartbeat (per docs/ANALYTICS_INVARIANTS.md and main/src/services/analyticsManager.ts).
- Then Settings > Privacy > Product analytics was switched OFF (`analytics.enabled=false`; 08-privacy-off.png, 09.png).
- Other outbound traffic still seen in logs: the update check and an OpenRouter model-price fetch ("Updated 360 model prices from OpenRouter").

## Grade table
| Test | Grade | Evidence |
|---|---|---|
| E-term | proven | `runpane panes create --tool-command zsh`. The panel ran the H3 probe commands and printed output (16-shell-term.png). The parent process is `/bin/zsh -i`, spawned by Pane. |
| E-chat | proven | Turned on Settings > AI & Agents > Chat tabs, then `runpane panels create --agent claude --chat` with the prompt "Reply with exactly: PANE_CHAT_OK". The native chat view rendered `PANE_CHAT_OK` (17-chat-claude.png; model Sonnet 5.5 via ACP adapter claude-agent-acp). Chat tabs were OFF by default in this install (`chatTabsEnabled:false`), even though docs say they are on for fresh installs. |
| E-orch | proven (with caveat) | Created Session `orch-test` (agent claude) and asked it to delegate. The orchestrator ran `runpane panes create --name child-ok --agent claude`. The child replied CHILD_OK and ran `runpane report --state done`. The Session activity log shows "Associated Pane child-ok" and "Worker reported done" (15:15:19Z). The parent replied "PARENT_GOT CHILD_OK / Worker report (state done ...): summary CHILD_OK" (18-orch-session.png). Caveat: the parent sat in a blocking `runpane watch --until-event` for about 8 minutes. Its final reply landed around the time I sent one "status check?" nudge, and that submit returned ok:false, so I cannot prove the parent finished without the nudge. |
| E-keys | proven | Settings > AI & Agents > Chat tab sign-in > Anthropic API key: saved `sk-test-INVALID-0000`. Pane stores it in safeStorage/keychain, not config.json (grep found 0 hits) and passes it as ANTHROPIC_API_KEY. A new Claude chat tab returned "Invalid API key · Fix external API key / Stopped by an error" (19-fake-key-401.png), so the request was routed to Anthropic and rejected. Key removed afterwards. Pane only offers Anthropic and OpenAI keys for its chat tabs; it has no OpenRouter or Google agent key (OpenRouter is for voice only). |
| H1 | proven | The "+" Add-tool menu lists "Claude" / "Codex" (chat) alongside "Claude Code in Terminal", "Codex in Terminal", "Cursor/OpenCode in Terminal", "Terminal", "Browser" (21-add-tool-menu.png). Pane codex-test held a Codex terminal-TUI tab and a Claude chat tab side by side (17-chat-claude.png). |
| H2 | proven | No Pane account or login at any point. Agents used the existing Claude Code and Codex logins. |
| H3 | proven (with caveat) | `MARK_SHELL=/bin/zsh` matches `dscl UserShell: /bin/zsh`. The rc alias is present (`gs='git switch'`, from ~/.zshrc:42), and the starship prompt rendered. PATH has `/Users/USER/.local/bin` (pos 1) and `/opt/homebrew/bin`, `/opt/homebrew/sbin`. The shell is interactive, not login (`[[ -o login ]]` → no; parent `/bin/zsh -i`), so ~/.zprofile is not sourced directly. Caveat: Pane was launched from an agent shell, not from Finder, so some of PATH is inherited (a codex bootstrap path shows up). Log lines "[ShellPath] Using cached PATH" show Pane builds its own shell PATH. |
| H4 | proven | Claude: `claude auth status` reports `authMethod: claude.ai`, `orgName: [redacted organization] Enterprise`, `subscriptionType: enterprise`. Pane pane claude-edit (Claude Code TUI) completed the task and printed `PANE_OK` (10-claude-pane.png), and the Claude chat tab also worked on the same login. Codex: `codex login status` reports "Logged in using ChatGPT", and the id_token plan claim is `ent26`. Pane pane codex-test (Codex TUI, GPT-6.1-Sol) printed `PANE_OK`. |
| H5 | proven | From a fresh install to a working agent with no config files: launch, then "Which agent do you use?" → Claude Code (1), "Bring your 15 sessions into Pane?" → Not now (2), "Open your project" → pick/skip repo (3). Pane then auto-starts an Onboarding Session running `claude --dangerously-skip-permissions`. Claude's own folder-trust and Bypass-Permissions dialogs make 2 more confirmations. Total: 3 Pane clicks + 2 agent dialogs, 0 settings. A chat GUI needs 1 extra toggle (Chat tabs). Note that the defaults are permissive: permission prompts are off (`defaultPermissionMode: ignore`), login autostart is on, and user-level MCP/skill/AGENTS.md writes are on. |
| H6 | proven | Claude edited hello.py in worktree `claude-edit`. The Changes panel shows "hello.py +2 -1 M", and the diff view opens in Unified/Split with Python syntax highlighting (12-diff.png: `def`/`greet` colored, strings green/blue, red/green line backgrounds). |

## Extras
- Config file: yes, `<PANE_DIR>/config.json` (default `~/.pane/config.json`; here `/private/tmp/pnd/config.json`). Pane watches it for outside edits. The DB is `sessions.db`. Per-repo `pane.json` / `conductor.json` hold scripts (docs/CONFIG_FILES.md). API keys are not stored in config (safeStorage).
- Linux build: yes per release/README (AppImage + .deb, x64/arm64). Not tested.
- Integrated browser: present ("Browser" in the Add-tool menu; a "Dev server on :51955 – Open preview" prompt appeared). Not exercised.
- CLI: `runpane` 2.4.217 bundled at `<PANE_DIR>/bin/runpane`. It talks to a unix socket (`/tmp/pane-daemon-501-*/daemon.sock`) and has a full agent-facing command contract (`runpane agent-context`).

## Side effects outside the isolated profile (important)
On first launch, with no prompt, Pane wrote to the user's **global** agent configs. These are default-ON settings:
- `~/.claude.json` mcpServers.pane
- `~/.codex/config.toml` `[mcp_servers.pane]` (symlinked into ~/dotfiles)
- `~/.cursor/mcp.json`
- `~/.codex/AGENTS.md` (pane-notify block)
- skills `pane` and `pane-manage-and-message-agents` in ~/dotfiles/agents/skills (through the ~/.claude/skills and ~/.agents/skills symlinks), ~/.codex/skills and ~/.cursor/skills

`--pane-dir` does not isolate these writes; it only points them at /private/tmp/pnd. Other agent sessions on the machine (a Ghostex tester's claude, and the user's Codex app-server daemon) picked up the pane MCP server immediately and spawned Pane helper processes.

At the end I switched off "Register Pane tools", "Install Pane skill for agents" and Approvals. Pane then removed its MCP entries and skills itself (diff-verified). What remains: `~/.cursor/mcp.json` = `{"mcpServers":{}}` and a 0-byte `~/.codex/AGENTS.md`. Details are in artifacts-pane.txt.

## Shutdown
Pane was quit with AppleScript. One Pane-binary MCP process (pid 45978) is still running. The user's Codex app-server daemon started it, not me, so I left it alone.
