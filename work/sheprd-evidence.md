# Sheprd comparison evidence

Research date: 2026-11-11. Source inspected at commit [`30b97d174f0421307c137701ab9442b43c7a9448`](https://github.com/sheprd-labs/sheprd/commit/30b97d174f0421307c137701ab9442b43c7a9448), committed 2026-11-11T10:47:08-08:00. Public source was downloaded to `/private/tmp/sheprd-comparison-source`; no application was installed, no daemon was started, no settings were changed, and no credentials were used. These findings describe inspected **main-branch source/documentation**, not a tested release. CPU/memory and Kitty parity are excluded as requested.

## Identity

Sheprd is an independent Rust/GPUI client for Herdr terminal servers. It supports Herdr 1 and bundles a pinned herdr-core for use without a separate Herdr installation. The project explicitly disclaims affiliation with Herdr. It belongs in its own comparison column. [Project README](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/README.md)

The installed `/Applications/Herdr.app` is **official Herdr 0.1.15**, bundle ID `dev.herdr.app`, executable `Herdr` (read directly from its Info.plist). Sheprd's renamed/legacy bundles use `so.pen.herdr-gpui`; although its old Homebrew tap also installed `Herdr.app`, that basename alone does not establish identity. No `/Applications/Sheprd.app` or `sheprd` executable was found on PATH. Preserve the earlier no-syntax-highlighting/1,500-line preview observation only as a historical observation of the tested Herdr 0.1.15 build. It is not a Sheprd observation. [Sheprd signing check](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/scripts/release/sign-macos.sh#L84), [rename compatibility](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/README.md#macos)

## Requirements

| Requirement | Finding | Evidence level |
| --- | --- | --- |
| Parallel agents | Worktrees, split chats, fan-out lanes running the same prompt with chosen agents, and dispatch are documented. Closing the GUI leaves daemon sessions running. | Documented; not run locally |
| Agent-to-agent orchestration | Underlying Herdr CLI controls agents/panes. The core client implements terminal run, send and wait, plus launch/readiness/turn-completion helpers. Native chat renders Claude/Codex/OpenCode subagents and their reported work. This supplies concrete delegation primitives, but a source review does not prove a successful spawn → two-way message → returned result round trip. | Source inspected; full round trip untested |
| Modern highlighted diffs | Review tab supports unified and side-by-side layouts, word changes, file tree, search, branch/base comparisons and inline notes. Its renderer uses Syntect syntax grammars; repository tests assert syntax spans on both sides. The tests were inspected, not executed. | Source confirmed; GUI untested |
| No ADE product login | The documented first-launch path opens a local daemon/shell directly. Separate Sheprd registration is not part of that path. GitHub/GitLab integration sign-in and upstream model authentication are separate optional integrations. | Documented local path; first launch untested |
| OpenRouter API key | Sheprd runs `opencode acp`. OpenCode supports `OPENROUTER_API_KEY` and OpenRouter models. This is a **via-OpenCode route**, not evidence that Sheprd's own usage/balance integration is an inference provider. | Compatible path documented; actual request untested |
| Existing OpenAI/Anthropic enterprise accounts | Native bridges run installed `codex app-server` and Claude Code directly; each agent signs in in its own way. Documentation explicitly preserves agent environment/config and describes Claude gateways/Bedrock/Vertex and Codex custom model-provider endpoints. Existing subscription eligibility and the user's exact enterprise identities remain untested. Enterprise endpoints alone do not prove enterprise subscription access. | Documented CLI credential/config reuse; both user identities untested |
| Preserve user's zsh config | New terminals delegate shell selection to the backend. GUI launches probe the login shell's PATH and XDG config; chat docs say endpoint environment belongs in the pane host's shell startup files. This suggests the expected route but does not establish aliases, functions, exports, private local declarations or login mode for the user's actual pane. | Startup/config path documented; user's zsh untested |
| Portable configuration / ≤5 independent UI-only values | Persistent overrides are `~/.config/herdr/config-gpui.local.toml` (or XDG equivalent); shared Herdr settings are `config.toml`. Theme/font/layout/keys/chat/env/preferences have file-backed configuration and live reload. Managed `config-gpui.toml` is regenerated and must not be treated as the user override file. CLI get/set/unset/check works without the app running. No complete desired-profile audit/restore was performed; do not report a measured zero UI-only count. Remembered review/session presentation can also live in app state. | Strong file-backed design; actual ≤5 audit untested |
| Open source | Apache-2.0 license. | LICENSE inspected |
| Useful free features / paid features | Public downloads/source and the inspected local feature paths have no documented Sheprd subscription gate. No priced Sheprd tier was identified. Model providers and optional cloud services retain their own costs; do not imply free inference or cloud machines. | Source/docs inspected; no commercial guarantee inferred |

Primary evidence:

- [Worktree/fan-out behavior](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/worktrees.md), [CLI controls](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/docs/cli.md), [run/send/wait implementations](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-core-client/src/connection.rs#L205), [launch/completion helpers](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-core-client/src/agent.rs), [subagent rendering](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/docs/rich-chat.md#sub-agents-background-shells-and-monitors).
- [Review features and bounds](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/review.md), [Syntect highlighter](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-gpui/src/review/highlight.rs), [renderer assertions](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-gpui/src/review/view/tests/colours.rs). The review docs scope review to local checkouts and list manual loading for >20,000 changed lines or >4 MiB; the highlighter limits syntax coloring to 2,000 bytes of a long line. These are bounds, not evidence of a failed ordinary review.
- [First launch](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/quick-start.md#first-launch), [installation](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/install.md), [Apache-2.0 LICENSE](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/LICENSE).
- [Agent commands, native bridges and enterprise endpoints](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-acp/README.md#enterprise-endpoints), [OpenCode OpenRouter key route](https://opencode.ai/docs/providers/#gateways). A quota/balance display for OpenRouter is not an authenticated coding request.
- [Configuration paths, override merge and CLI](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/website/docs/configuration.md), [full config example including chat environment](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-gpui/config-gpui.example.toml), [login-shell launch behavior](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-gpui/README.md).

## Proposed concrete comparison text

Compact field-table row (same five-column order as existing report):

| Environment | Agents & delegation | Diff review | Portable setup | Access / catch |
| --- | --- | --- | --- | --- |
| 🐑 Sheprd | Worktree fan-out + Claude/Codex/OpenCode subagents; delegation round trip untested | Unified + side-by-side syntax-colored review in source; GUI untested | TOML preferences + keybindings; user's zsh and five-value audit untested | No local product account in documented startup; CLI credentials; OpenRouter via OpenCode untested |

Provider/config detail row:

| Environment | Product login | OpenRouter | Enterprise accounts | Zsh / UI-only cap | License / price |
| --- | --- | --- | --- | --- | --- |
| 🐑 Sheprd | Local startup requires no Sheprd account in docs; untested | OpenCode route documented; no live request | Existing CLI auth/config supported; OpenAI and Anthropic enterprise requests untested | TOML config documented; user's shell + ≤5 audit pending | Apache-2.0; no documented local subscription gate; provider/cloud costs separate |

## Ranking implication and remaining qualification

Sheprd is a strong new challenger for this user's priorities: unusually explicit portable configuration, modern source-backed diff rendering, multiple existing CLI integrations and an Apache license. Keep it separate from Herdr. It merits a hands-on evaluation; current documentary evidence cannot displace Paseo's demonstrated delegation, diff, zsh and provider results or Orca's locally demonstrated orchestration. Do not label Sheprd a qualified winner or a failed candidate from this source-only pass.

To qualify it: pin an installed release and repeat the same local no-account startup, actual zsh probe, multi-language diff fixture, parent/child spawn/message/result flow, OpenRouter request, both enterprise-account requests, and preference-file restore/count audit. Check that each cited main-branch feature exists in that release before promoting its cells to tested. No CPU/memory benchmark is part of these follow-ups.
