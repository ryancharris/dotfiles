# Agent Instructions

Shared conventions for all AI coding agents working in this repository.

`install.sh` symlinks this file to `~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, and
`~/.config/opencode/AGENTS.md` — one source of truth for all agents. Claude-specific
overrides (permissions, personal context) belong in `~/.claude/CLAUDE.local.md`, which
is gitignored and not shared.

**This file (`agents/AGENTS.md`) is the source of truth — always add, edit, or remove
rules here.** `~/.claude/CLAUDE.md` and the other symlink targets are just mirrors;
editing them directly edits this file too (they're the same inode), but any change
should be made with this path in mind so it's clear it belongs to the shared,
version-controlled convention set rather than a Claude-only override.

## General
- Data-driven — never assume (facts or inferred user intent). Prefer measurement over intuition/convention/training-recall; validate the approach itself, not just after-the-fact claims. Check in-repo and official docs before assuming behavior. Back every claim inline with a concrete observation (command output, query result, log line, metric, benchmark, test run, `file:line`, or doc URL) — reasoning isn't evidence, and don't summarize a result you didn't produce this session. Lacking data, go get it; if the ambiguity is user intent, ask instead of guessing
- Quantify instead of asserting: "p99 rose from 120ms to 1.4s over 6h (Datadog)" beats "latency got worse". No vague magnitudes ("much faster", "significantly", "a lot")
- Before/after claims require a measurement on both sides — never declare a fix or improvement without a post-change measurement
- For non-trivial changes, prefer end-to-end/integration tests over unit alone; consider contract and smoke tests across system boundaries
- When adding or updating a Datadog monitor, or doing incident response, backtest against the last 30 days of Datadog data before proposing a threshold or conclusion — check where the metric/log volume actually sat over that window rather than guessing a threshold. Datadog auto-downsamples 30-day windows to ~4-12h avg-aggregated buckets by default, which flattens spikes; force `.rollup(<avg|sum|min|max|count>, 3600)` (1h buckets, 720 points, well under the ~1,500-point/query cap) instead of trusting the default rollup
- Use helpful visuals and diagrams whenever/wherever possible, not just for networking
- When work touches networking (protocols, traffic routing, DNS, load balancing, firewalls, CNI, service meshes, etc.) or Terraform/IaC, explain the relevant concept briefly — the user is actively learning both and wants coaching, not just the answer. Set these explanations apart as a markdown blockquote headed `📘 Teaching: <topic>` (blockquotes render with a distinct background/border in most clients) so they're easy to spot and skip, regardless of output style
- End every response with any clarifying questions you have, if there are open ones — don't bury the question mid-response
- When compacting, always preserve the commit message format rules and PR body template

## Shell

- **`timeout` does not exist on macOS** — it's GNU coreutils, not BSD. Don't use it in scripts. Use `gtimeout` only if coreutils is confirmed installed; otherwise omit the timeout entirely
- Don't suppress stderr (`2>/dev/null`) on the command whose failure you're trying to interpret. Suppress it only on calls whose failure is expected and handled
- **If a loop over remote calls fails for EVERY item, suspect the harness, not the targets.** Re-run one case with stderr visible before reporting the result. Uniform failure across heterogeneous targets is far more likely local (missing binary, bad flag, expired auth) than a genuine finding

## Commits

1. Follow [Conventional Commits](https://www.conventionalcommits.org/):

- **Format:** `<type>[optional scope]: <description>`
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`
- Scope should reflect the tool or component (e.g. `gh-dash`, `install`, `zsh`, `kitty`)
- Description is lowercase, imperative mood, no trailing period
- Subject line ≤ 72 characters
- Breaking changes: append `!` after type/scope and add a `BREAKING CHANGE:` footer

2. NEVER add yourself to 'Co-Authored-By' for any commit

3. NEVER commit or push directly to `main`/`master` — always work on a feature branch and open a PR, even for small changes. If `HEAD` is on `main`/`master`, create and switch to a feature branch first.

## Pull Requests

- Title: short (≤ 70 chars), imperative mood, describes the change
- PRs must come from a feature branch — NEVER open a PR from `main`
- NEVER merge a PR without explicit permission from the user
- Body format:
  ```
  ## Why
  - <the problem or gap that prompted this>

  ## Effect
  - <what's observably different after this merges — behavior, not lines changed>

  ## Notes
  - <caveats, tradeoffs, follow-up work — omit if none>

  ## Validation
  - <how to verify>
  ```

## Issue Tracking

- Do not use GitHub Issues — the team doesn't use them. Surface findings, follow-up work, and decisions that
  would otherwise become a GitHub issue directly instead (PR description, Slack, or back in conversation)

## Code Style

- Prefer CLI tools over GUIs
- Favour OSS solutions
- Keep changes minimal and focused — avoid unrelated refactors
- No comments unless the logic is genuinely non-obvious
- Launch TUI apps in a new kitty tab (`kitty @ launch --type=tab`), not inside tmux

## Voice

When writing Slack messages, PR comments, or other communication sent on the user's behalf:

- Be concise where possible, but don't sacrifice detail for brevity
- Use plain language for clarity — avoid jargon unless it's the clearest way to say something
- Maintain technical expertise — write as a knowledgeable peer, not a simplified summary

## Slash Commands

Agent-specific slash commands are defined in `agents/commands/`:

| Command | Description |
|---|---|
| `/commit` | Stage all changes and create a Conventional Commit; add `push` to also push to remote |
| `/create-pr` | Push branch and open a GitHub PR; add `draft` to open it as a draft |
| `/clipboard` | Copy the latest assistant response to the system clipboard |
| `/test-coverage` | Audit test coverage for all changes on the current branch |

## Verification
- Shell config changes: verify with `source ~/.zshrc`
- Kitty config: open a new tab and confirm it loads without errors
- gh-dash changes: run `gh dash` and confirm the layout renders

## GitHub

- `gh search prs` mishandles `is:open` — use `gh pr list` with explicit filters instead
- Repeated `author:` terms don't OR together; the explicit `OR` keyword also fails — filter client-side if needed
- Always use `--force-with-lease` instead of `--force` when force pushing

## Maintenance
For each instruction, ask: "Would removing this cause Claude to make a mistake?" If not, delete it.
