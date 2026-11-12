> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Paseo hands-on, round 2 (2026-11-12)

Version: Paseo desktop and CLI 0.15.4. It was already installed and was not reinstalled.
Scope: only the items that were not yet proven (E-chat, H1, H5, H6, browser extra). Everything else is carried over from the prior evidence in `work/paseo-provider-qualification.md`, `work/paseo-zsh-qualification.md`, `paseo-openrouter-result.json` and `regrade-six.md`.

## Isolation
- A second Paseo.app instance was launched with `PASEO_HOME=/private/tmp/psq` (a fresh daemon home whose config.json only sets listen to 127.0.0.1:6797), `PASEO_ELECTRON_USER_DATA_DIR=/private/tmp/psq-ud` and `PASEO_ELECTRON_FLAGS=--remote-debugging-port=9461`. All three env hooks were found in the installed `dist/main.js` and `server/paseo-home.js`.
- The user's own Paseo (port 6767, ~/.paseo, daemon pid 56423) was not touched.
- GUI was driven and captured through CDP (`Page.captureScreenshot`, `Input.*`). The window is 677x1392 because the window manager forces that size.

## Grades

| Item | Grade | Evidence |
|---|---|---|
| E-term | proven (prior) | paseo-zsh-qualification.md |
| **E-chat** | **proven** | I opened a GUI "Agent" tab, picked Claude > Haiku 5.5 and sent "Reply with exactly: PASEO_OK". The chat rendered the user bubble and the assistant reply `PASEO_OK` (shots 12, 12b). The `paseo logs` timeline shows `[User] …` then `PASEO_OK`. The extra wrap-up text after it comes from the user's own global Claude Stop hook, which shows that Paseo runs the real ~/.claude config. |
| E-orch | proven (prior) | regrade-six |
| E-keys | proven (prior) | OpenRouter via OpenCode, paseo-openrouter-result.json |
| **H1** | **proven** | The New-tab menu in one workspace offers **Agent** (GUI chat), **Terminal**, Diff and Browser. A **Terminal profiles** list (Claude Code, Codex, OpenCode, Pi) launches the raw CLI TUI (shot 07). The GUI chat tab and a raw `claude` TUI tab ran side by side in the same workspace (shot 13 shows the real Claude Code trust prompt). The choice is made per tab/session. "Import session" also pulls a terminal-started session into chat. |
| H2 | proven (prior) | Confirmed again: the fresh profile had no login or account prompt. |
| H3 | partial (prior) | interactive zsh but non-login by default; `exec zsh -l` works around it |
| H4 | proven (prior) | Claude enterprise, Codex ent26 |
| **H5** | **proven (good)** | Fresh profile, no config files, no settings changed. Launching opens a 5-step wizard (Appearance / Providers / Projects / Orchestration / Mobile). **Providers auto-detected** Claude (18 models), Codex (8), OpenCode, Pi with zero input (shot 02). Projects step offers recent Claude/Codex project dirs. Minimal path to a working agent: Skip setup (1), add project (folder picker; I used `paseo project create` because the native picker can't be automated), open workspace (1), Agent tab (1), **Select model** (3 clicks: there is no preselected default model, so this is required), type and send. That is about 7 GUI actions and 0 config edits. Caveat: when the wizard is skipped, Settings > Host > Agents shows **"Enable Paseo tools" OFF** (orchestration MCP). The wizard's Orchestration step defaults it, skills and the CLI to ON (shots 04, 19). Default Claude permission mode resolved to `auto` (`paseo inspect`). |
| **H6** | **proven** | The GUI agent edited hello.py in /private/tmp/psq-repo (git status `M hello.py`, +5 -1). A "+5 -1" pill opened the Changes panel. Clicking the file opened a Diff tab with a unified diff, red/green rows, line numbers and syntax colouring: `def`/`return` purple, function names blue, strings green (shot 16). The diff is drawn on canvas (no DOM text), so the grade rests on the screenshot. |
| Extras: config | proven (prior + now) | Daemon: `$PASEO_HOME/config.json` (default ~/.paseo/config.json). Desktop: `<userData>/desktop-settings.json` (4 keys). Renderer prefs are in localStorage. |
| Extras: Linux | docs | AppImage/DEB/RPM (paseo.sh/download) |
| **Extras: browser** | **proven present; correction** | The built-in **browser tab works out of the box** on a fresh profile: New tab > Browser loaded example.com with no config (shot 17). What is **off by default** is the agent **Browser tools** (MCP control of tabs). Settings > Host > Agents > Browser tools toggle is OFF (shot 19), matching docs (`daemon.browserTools.enabled`). Docs say both are desktop-only. So "browser off by default" is wrong for the browser itself and right for agent browser automation. |

## Screenshots
All are in `$ORIGINAL_SCRATCHPAD/paseo-shots/`:
01-launch (wizard, no login), 02-providers (auto-detect), 03-projects, 04-orch (defaults ON), 07-ws-open (Agent/Terminal/Diff/Browser + terminal profiles), 09/09b/11 model picker, 12-chat-reply and 12b-chat-thought-expanded (E-chat), 13-claude-tui-tab (raw TUI, H1), 14-edit-turn, 15-diff (changes panel), 16-diff-file (H6 highlighted diff), 17-browser, 19-settings-agents (Paseo tools/Browser tools OFF).

## Notes
- I cancelled the Claude TUI folder-trust prompt (Esc) so that nothing was written to ~/.claude.json.
- Following the user's global repo hook, the agent created branch `hello-greetings` in the disposable repo.
- Cleanup: the isolated app was quit with SIGTERM to its own pid, and its daemon stopped (`localDaemon: stopped`). No helpers remain. The artifacts are listed in artifacts-paseo.txt.
