> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Orca hands-on (round 2, gap items only) — 2026-11-12

- **Installed version:** Orca 1.4.255 (`orca --version`, Info.plist). Latest upstream is 1.4.257; the updater found it but did not install it. It was already installed, so nothing was installed.
- **Isolation:** I launched a second instance, `ORCA_USER_DATA_PATH=/private/tmp/orp /Applications/Orca.app/Contents/MacOS/Orca --user-data-dir=/private/tmp/orp --remote-debugging-port=9477`. The single-instance lock is per profile (from app.asar `launch-user-data-path.js`). The `orca` CLI with the same `ORCA_USER_DATA_PATH` targeted only this runtime (runtimeId d8ad77cb…, not the user's 8600d970…). The user's running Orca (pid 23362) was untouched. Its status was still `ready` at the end.
- **Screenshots:** taken from the real window through CDP `Page.captureScreenshot`. A 1500×950 viewport override was applied per capture because the window was 677 px wide.
- **HOME:** unchanged, so the real ~/.zshrc and the existing Claude/Codex logins were used read-only.

## Grade table (this round)

| Item | Grade | Evidence |
|---|---|---|
| E-chat | **proven** | `orca agent launch --agent claude --surface chat --prompt "Reply with exactly: ORCA_OK"` returned `outcome.kind=structured`. The native chat rendered the user bubble and the reply `ORCA_OK` (Claude Sonnet 5.5) (07). Codex native chat rendered `ORCA_CODEX_OK` (GPT‑6.1‑Sol) (15). |
| H1 | **proven** | Settings → Chat UI has a per-agent Chat/CLI toggle for Claude, Codex, Grok, OpenCode(2), Pi, OMP and Antigravity (13). I set Codex to Chat and left Claude on CLI. Launches without `--surface` then gave Codex `structured` ("default … in your settings") and Claude `terminal` ("user_default"). This is persisted as `nativeChatProviders={"codex":true}` in profile-state.db. Switching works both ways. The chat tab's right-click "Continue with Terminal Agent" opened a raw Claude Code v2.1.318 TUI with the chat's context (09). The CLI tab's right-click "Continue in Chat UI" opened a native chat with the CLI transcript (12). The session panel also offers "Resume in Worktree" / "Resume in New Terminal" (12). The 1.4.255 labels differ from the docs' "Resume in New CLI / New Native Chat". The source also has "Resume in New Chat". |
| H3 | **proven** (closes the prior partial) | A new Orca terminal in /private/tmp/orca-h6 ran with the user's real rc files: `SHELL=/bin/zsh` (matches `dscl … UserShell: /bin/zsh`), LOGIN=yes, INTERACTIVE=yes. Alias `gsc` from ~/.zshrc line 43 was present. PATH contained ~/.local/bin and /opt/homebrew/bin. `brew` resolved, ZSH 5.9, and the user's custom prompt rendered. Agents also honored the user's ~/.claude Stop hooks (the hook text appears in the chat). |
| H5 | **proven** | Fresh profile: no login. The wizard took 3 "Continue" clicks: (1) Chat UI vs Terminal, default **Terminal**; (2) default agent, Claude auto-detected from 8 found CLIs, **Yolo mode ON by default**; (3) theme. Orca then finished onboarding, auto-launched Claude in `~`, and asked "Trust ~ for agents?". So there were 4 interactions and 0 settings or config files before a working agent. The wizard says "1 of 4", but a 4th step was not observed. Recorded defaults: `agentDefaultSurface=terminal`, `agentPermissionDefault=full-access`, `nativeChatPermissionMode=full-access`, `defaultTuiAgent=claude`, `diffDefaultView=inline`. The agent CLIs must already be installed and signed in. |
| H6 | **proven** | The Claude chat edited calc.py (`git diff`: +6 −1). `orca file diff calc.py --focus` opened a Monaco inline diff with real syntax colors (18). The DOM showed 5 token colors: keywords rgb(86,156,214), strings rgb(206,145,120), brackets rgb(255,215,0), and others, on top of add/remove shading. The chat's own "1 changed file" turn diff is shaded but not syntax-colored (17). |
| E-keys | **partial** | The fake key `sk-test-INVALID-0000` went through the environment to Pi in an Orca terminal. `pi --no-session -p --model openrouter/openai/gpt-4o-mini …` returned `401 {"message":"Invalid API key: this is not an OpenRouter API key…"}`, so the request reached OpenRouter. Orca itself has no API-key entry for OpenRouter, OpenAI, Anthropic or Google. AI Provider Accounts only manages CLI logins plus an "OpenCode Go API key" (19). Chat env takes variable *names* only. `opencode run` with OPENROUTER_API_KEY failed with "Model unavailable" (OpenCode 2.2.5 listed no openrouter/openai providers). |
| H4 (bonus) | proven, now also in native chat | Claude chat/CLI header showed "Claude Enterprise". `claude auth status` gave subscriptionType=enterprise. The Codex chat used the existing ChatGPT login (prior evidence: plan ent26). |
| H2 (re-observed) | proven | No Orca account at first launch. The status bar showed "Sign-in expired" for an optional Orca account, which did not block anything. |
| X-config | partial | Settings are kept in SQLite `profiles/local-default/profile-state.db` (domain `settings`, JSON payload). There is no user-editable settings file; keybindings are in `~/.orca/keybindings.json`. |
| X-browser | proven | `orca tab create --url https://example.com` gave title "Example Domain", rendered in an in-app browser tab with a grab/annotate toolbar (20). |
| X-linux | supported (docs, not tested) | AppImage and AUR (six-docs-gaps.md, stablyai/orca README). |

Not retested (already proven earlier): E-term, E-orch.

## Screenshots (`<scratch>/orca-shots/`)
01 first launch · 02 agent pick + Yolo default · 03 theme · 04 trust/onboarding completed · 07 Claude native chat · 08 chat tab menu · 09 chat→CLI TUI · 11/12 CLI→Chat · 13 per-agent Chat/CLI settings · 15 Codex chat · 16/17 edit + turn diff · 18 Monaco highlighted diff · 19 provider accounts · 20 browser

## Side effects (see artifacts-orca.txt)
- "Trust repository" for /private/tmp/orca-h6 wrote a Codex `[projects]` trusted entry and a ~/.claude.json project trust.
- Session transcripts were written under ~/.claude/projects and ~/.codex/sessions.
- I declined the Claude theme sync and the trust for `~`.
