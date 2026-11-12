> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Hands-on: Agentastic (Agentastic.dev) - 2026-11-12

- Installed: Agentastic.dev **0.16.2** (build 4890, bundle id `dev.agentastic.Agentastic`). The app auto-downloaded its own agent runtime, `agentastic-cli 0.22.0`.
- Install: `brew tap agentasticai/tap` -> `brew trust --cask agentasticai/tap/dev`. Homebrew refuses to load casks from untrusted taps, so this step is required. Then `brew install --cask agentasticai/tap/dev`. `brew info` confirmed that cask `dev` is "Agentastic.dev" 0.16.2 and requires macOS >= 14.
- Method: I drove everything through the bundled `dev` CLI, which talks JSON-RPC to the running app over `~/.agentastic/sockets/agentastic-<pid>.sock`.
- **GUI visual limit:** this host has not granted Screen Recording to the terminal or to Orca Computer Use. `screencapture` failed with "could not create image from display", and AX reads were not trusted. I could not take any whole-window screenshots. The integrated browser screenshot was taken through the app's own webview RPC.

## Grades
| Test | Grade | Evidence |
|---|---|---|
| E-term | **proven** | `dev newtab --worktree-path /tmp/agtest` opened a terminal. `dev send` + `dev tail` returned `TERM_OK`. |
| E-chat | **proven** (rendering not seen) | `dev agent create --agent claude --interface chat` created a native chat. Its transcript (`dev agent tail`) is `[user] Reply with exactly: AGENTASTIC_OK` / `[assistant] AGENTASTIC_OK`. Codex chat gave the same result. I could not screenshot the rendered chat view. |
| E-orch | **proven** (needed one re-instruction) | Manager agent `orchtest` (Claude, chat) spawned worker `orchtest/agtest-3`. The worker transcript says `CHILD_OK`. The manager feed recorded `agent.progress: "agtest: Replied exactly 'CHILD_OK'"`, and the manager's final report quotes it. On the first attempt the manager's `dev agent create` defaulted to the `agentastic` provider. Those two workers stalled at that CLI's "Trust this folder?" prompt, and the manager correctly escalated with `needs_user`. I closed them and mailed the manager to retry with `--agent claude`. Transcripts: `ag/orch-child.txt`, `ag/orch-manager.txt`. |
| E-keys | **proven** (env route; Provider Pass UI untested) | In the app terminal I ran `export OPENROUTER_API_KEY=sk-test-INVALID-0000`, then the bundled `agentastic exec -c model_provider="openrouter" -m openai/gpt-4o-mini`. It returned `401 Unauthorized: Invalid API key: this is not an OpenRouter API key ... url: https://openrouter.ai/api/v1/chat/completions`. The Provider Pass wallet is GUI-only, and I could not reach it without screen access. |
| H1 | **proven** | For the same app, provider and repo, I launched with `--interface chat` (native chat) and with `--interface terminal`. The terminal launch ran the raw Claude Code TUI and printed `⏺ AGENTASTIC_OK` with the `❯` prompt. The choice is made per session. I did not test switching a running session (GUI only). |
| H2 | **proven** | I created no account and saw no sign-in prompt. Claude, Codex and the Manager all worked against the existing CLI logins. `settings.json` has `reopenBehavior: "welcome"`. A 520x500 on-screen window, presumably the Welcome window, could not be inspected. |
| H3 | **proven** | `SHELL=/bin/zsh`, which matches `dscl` UserShell `/bin/zsh`. `alias gbd` returned `gbd='git branch -d'` (~/.zshrc:41). `LOGIN=yes`, `INTERACTIVE=yes`. PATH has `~/.local/bin` (position 2) and `/opt/homebrew/bin` + `/opt/homebrew/sbin`. The user's p10k-style prompt rendered. The process is `/usr/bin/login -flp USER`. It uses a ZDOTDIR shim that sources the user's .zshenv/.zshrc (`settings.json useLoginShell: true`). |
| H4 | **proven** | Claude: `claude auth status` reports `subscriptionType: "enterprise"`, `orgName: "[redacted organization] Enterprise"`. The app chat got `AGENTASTIC_OK` using that login. Codex: `codex login status` reports "Logged in using ChatGPT". The id_token claim is `chatgpt_plan_type: ent26`. The app chat got `AGENTASTIC_OK`. The app's private CODEX_HOME symlinks `auth.json` -> `~/.codex/auth.json`. |
| H5 | **proven** (good) | Steps were tap + trust + install (3 CLI commands), launch, open folder, then pick the agent and prompt. I changed no settings and wrote no config files. The app auto-discovered claude and codex and reused their logins. Rough edges: the Homebrew tap-trust step, and Manager/worker defaults can choose the `agentastic` provider, which needs a folder-trust answer and a provider credential. |
| H6 | **untested** (visual) / partial functional | A Codex chat agent edited `/tmp/agtest/hello.py`. `git diff` shows `-    return "hello " + name` / `+    return f"Hello, {name}!"`, and `dev status` reports additions. I could not take a screenshot of the in-app diff view because Screen Recording is not granted. |

## Extras
- Config file: `~/Library/Application Support/Agentastic.dev/settings.json` (JSON, 423 lines: composer, connections/agents, terminal `useLoginShell`, etc.). The agent CLI uses `~/.agentastic/config.toml`. Repo-level `.agentastic/` is also used.
- Linux: no desktop build. The app is macOS-only; the `agentastic` CLI and `agentastic-dev-server` have Linux binaries (the formula has `on_linux` and the bundle has `ServerBinaries/*linux*`).
- Integrated browser: **present**. `dev browser open https://example.com` returned title "Example Domain". Webview screenshot: `ag/browser.png`. It bundles Chromium/CEF resources.
- Other: rich `dev` CLI (agents, terminals, manager/mail/memory, artifacts, device, computer). Quitting via AppleScript timed out, presumably on a confirmation dialog, so I stopped it with SIGTERM. A detached `agentastic-dev-server computer-host` helper outlived the app and I killed it. Claude TUI sessions warned "Transcript saving is off — inherited CLAUDE_CODE_CHILD_SESSION marker" because the app inherited the env from the tester's `open`.

## Evidence files (scratch)
- `ag/browser.png`, `ag/orch-child.txt`, `ag/orch-manager.txt`, `ag/bin/dev` (CLI wrapper)
- No GUI window screenshots (Screen Recording not granted).

## H6 visual proof (round 3)
**Grade: proven.** Agentastic.dev 0.16.2 (build 4890), already installed. Screen Recording is now granted, so `screencapture -x` works.

- Repo: disposable `/private/tmp/agd-repo` (git init, one commit with `calc.py`).
- Agent: `dev agent create --repo /private/tmp/agd-repo --agent claude --interface chat --mode local --focus --prompt "Edit calc.py ..."`. This used the existing Enterprise Claude login. Claude asked "Claude wants to use Edit calc.py" with **Allow once / Deny** buttons. I clicked Allow once through `orca computer click`; System Events `click at` did not trigger it. The chat then rendered `AGENTASTIC_OK` (`ag/h6-chat.png`). `git diff`: `-    return "hello " + name` / `+    return f"Hello, {name}!"` plus a new `def mul(a, b): return a * b` (+5 -1).
- Diff view: **View > Show Diff** opened a "master vs master" tab. It is a side-by-side A/B diff of `calc.py` with hunk header `@@ -3,7 +3,11 @@`, line numbers, red/green line shading, a `+5 -1` counter, per-hunk accept/reject icons and "Change 1 of 1" navigation. Screenshot: `ag/h6-diff.png`.
- Verified syntax highlighting with the Read tool on the screenshot. The colours are per token, not just per line. Keywords `def` and `if` are pink/magenta. The function names `greet` and `mul` and the identifier `name` are cyan/blue. String literals (`"hello "`, `f"Hello, {name}!"`, `"__main__"`) are orange/red. Operators and plain text are white. The same token colours appear on unchanged context lines (5, 9/13), so this is real Python highlighting, not +/- shading.
- The View menu also has **Run Code Review**, which I did not exercise.
- Setup friction, not a defect in H6: after the earlier session, `dev import` created a workspace with `window_count 0`, so the GUI could not show it. Neither Open Recent nor Add Repository opened a window for it. Quitting with SIGTERM and relaunching with `open -a Agentastic.dev /private/tmp/agd-repo` gave it its own window. The first agent, `E9EBE599…`, was lost in that restart and shows as `failed`. The second agent, `B9566DC6…`, did the edit. `--run-mode agentAutoApprove` was not used: it was blocked by the tester-side safety classifier.
- Other screenshots: `ag/h6-perm3.png` (permission card), `ag/h6-perm.png`/`h6-perm2.png` (full desktop, contain other apps; do not share).
- App quit afterwards with SIGTERM (AppleScript quit returned "User canceled"). The orphaned `claude --print` child from the first agent was killed. No Agentastic processes remain.
