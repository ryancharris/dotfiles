# T3 Code qualification evidence — 11 November 2026

**Historical source review:** the current installed-0.1.5 results and their route limits are retained in [the hands-on archive](evidence-2026-11-12/hands-on-t3code.md); use `comparison-grades.json` for the current grading decision. Current-main documentation does not upgrade the tested build.

Scope: current public documentation and inspected source, not an end-to-end qualification of the user's credentials or preferences. No installation, live settings changes, authentication changes, model requests, or resource measurements were performed. The installed `/Applications/T3 Code (Beta).app` is version **0.1.5**; its capabilities must not be equated with current main. Source was cloned read-only into `/private/tmp/t3code-evidence-20261111`, commit `f31ce3eeb5f4adbfe7f961403822cf90db05808f` (11 November 2026).

## Concrete comparison cells

| Column | Proposed wording | Evidence class |
| --- | --- | --- |
| Agents & delegation | Parallel threads; child delegation, follow-up messaging and result collection implemented. | Source inspected; live flow untested |
| Highlighted diff | Syntax-highlighted split and unified diffs. | Source inspected; sample rendering untested |
| Zsh & portable config | Zsh supported; JSON settings, keybindings and themes. Device-local preferences; five-value audit pending. | Source/docs; user's zsh untested |
| Product login | Local host commands need no product sign-in. T3 Connect uses an account. | Documented; local UI untested |
| OpenRouter | Explicit Claude/OpenRouter setup with separate provider credentials and endpoint. | Documented; actual key untested here |
| Enterprise accounts | Reuses existing Claude/Codex CLI logins; work/personal separation supported. | Documented; user's enterprise accounts untested here |
| License | MIT. | License inspected |
| Free / paid | Local app free; provider charges separate. Connect account and machine limits optional. | Documented |

## Parallel agents and orchestration

Current source implements `delegate_task` to start a child with a task, optional worktree isolation, `task_status` to read its result, and `task_cancel`. The `t3_thread_send` tool supports steering a running turn, queueing, restarting, and following up on a finished child. `t3_thread_wait` waits for a run. This meets the *implementation shape* of launch → message → collect, beyond merely displaying parallel panes. Upstream integration-test source covers delegation and follow-up/result behavior; those tests were **read, not run** in this audit. [Tool definitions](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/apps/server/src/mcp/toolkits/orchestrator/tools.ts#L86), [integration test](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/apps/server/src/mcp/OrchestratorMcpToolkit.integration.test.ts#L354).

The ordinary user interface does not allow direct messages into an agent-started subagent; the docs direct the human to message its parent. This is distinct from the agent-facing tool implementation and should not be flattened into either “no messaging” or an unqualified runtime pass. [Thread UI behavior](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/thread-sidebar.md#L271).

## Diff rendering

The current web renderer uses `@pierre/diffs`, offers split/unified layouts, and passes a preferred syntax highlighter. The shared highlighter module initializes per-language lexers and theme palettes. This establishes implemented syntax highlighting, but no rendered sample was checked in the installed beta. [Diff panel](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/apps/web/src/components/DiffPanel.tsx#L1489), [highlighter](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/apps/web/src/lib/syntaxHighlighting.ts).

## Login, provider keys and enterprise accounts

The documented host `t3 thread start/send/show/list` commands use the orchestration tools **without sign-in**. Local pairing/approval and provider authentication are separate from a T3 account. Remote MCP clients may need OAuth approval; optional T3 Connect uses a T3 account. Do not reject the local app solely because Connect has sign-in, or imply Connect meets the no-account requirement. [Host commands and external-agent access](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/outside-agents.md#L150).

The OpenRouter recipe uses a separate Claude config directory, `ANTHROPIC_BASE_URL=https://openrouter.ai/api`, a sensitive auth-token variable, and an explicitly empty Anthropic API key. Custom OpenRouter model IDs can be added. This is an explicit supported route, stronger than inferring support merely from a generic terminal. Existing Claude CLI login/config is reused; separate instances can isolate work and personal credentials. No disposable key was read or used during this addition. [Claude and OpenRouter configuration](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/providers-claude.md#L123).

Codex supports an existing CLI login, with separate or shared/shadow homes for multiple accounts. The documentation establishes compatibility routes, not that either of this user's Enterprise identities can issue requests through T3 Code under their organization policies. [Codex accounts](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/providers-codex.md#L23).

## Shell and dotfiles portability

The inspected terminal manager uses the requested shell or `$SHELL`, with zsh fallbacks. Zsh starts with `-o nopromptsp`, **not `-l`**. This is compatible with interactive `.zshrc` startup, while direct `.zprofile` execution is not established. The user's aliases, functions, private local configuration, login exports and tools have not been exercised through T3 Code. [Terminal manager](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/apps/server/src/terminal/Manager.ts#L558).

Keybindings are directly editable at `~/.t3/userdata/keybindings.json`. Server settings use `~/.t3/userdata/settings.json`; theme JSON files can be exported/published under `~/.t3/userdata/themes`, with a CLI default. Appearance preferences are device/browser-local. Therefore “all settings portable” and “≤5 UI-only values” remain unproven; the actual desired nondefault values need a restore test. Kitty parity is outside scope. [Keybindings](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/keybindings.md#L93), [settings files](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/managed-policy.md#L127), [appearance/themes](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/appearance.md).

## License, price and ranking implication

MIT license. The local application is free; users pay their model providers. Optional T3 Connect is presently free for three machines per account, with higher limits through paid T3 Chat plans. This is an optional remote-service distinction, not a local ADE feature paywall. [License](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/LICENSE), [cost FAQ](https://github.com/pingdotgg/t3code/blob/f31ce3eeb5f4adbfe7f961403822cf90db05808f/docs/user/faq.md#L26).

**Recommendation:** T3 Code is a serious challenger because its current implementation covers delegation, modern diffs, explicit OpenRouter configuration and existing CLI credentials while remaining MIT/free. Do not promote it over Paseo's actual successful qualification on source claims alone. Keep Paseo first on demonstrated fit, Orca second on tested orchestration, and flag T3 Code as the next candidate to qualify rather than presenting a tested ordinal ranking for all six.

Necessary follow-ups: run a pinned current build in an isolated profile; confirm local UI with no T3 account; launch two agents, send one a follow-up and collect results; inspect a syntax-highlighted sample diff; exercise the user's zsh sentinels; restore the actual nondefault settings and count remaining UI-only values; perform separately authorized OpenRouter and both Enterprise-account requests. No CPU/RAM work is required.
