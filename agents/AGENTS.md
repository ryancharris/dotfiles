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
- Use helpful visuals and diagrams where appropriate, especially for networking issues
- When work touches networking (protocols, traffic routing, DNS, load balancing, firewalls, CNI, service meshes, etc.), explain the relevant concept briefly — assume the reader is a platform engineer who is new to networking
- When compacting, always preserve the commit message format rules and PR body template
- Consult in-repo documentation and official public docs before assuming behavior or making recommendations; don't rely on training-data intuition when a source of truth exists
- EVERY claim must be validated with data or metrics. Back each assertion with a concrete observation — command output, query result, log line, metric/dashboard value, benchmark, test run, file path with line number, or doc URL. Reasoning alone is not evidence.
- Show the evidence inline: the actual command run and its output, or the query and its result. Don't summarize a result you didn't produce in this session.
- If no data exists to validate a claim, say so explicitly and label it as an assumption or hypothesis — then go get the data before acting on it
- Quantify instead of asserting: "p99 rose from 120ms to 1.4s over 6h (Datadog)" beats "latency got worse". No vague magnitudes ("much faster", "significantly", "a lot")
- Before/after claims require a measurement on both sides — never declare a fix or improvement without a post-change measurement
- For non-trivial changes, prefer end-to-end and integration tests over unit tests alone; consider contract tests and smoke tests to verify real behavior across system boundaries

## Shell

- **`timeout` does not exist on macOS** — it's GNU coreutils, not BSD. Don't use it in scripts. Use `gtimeout` only if coreutils is confirmed installed; otherwise omit the timeout entirely
- Don't suppress stderr (`2>/dev/null`) on the command whose failure you're trying to interpret. Suppress it only on calls whose failure is expected and handled
- **If a loop over remote calls fails for EVERY item, suspect the harness, not the targets.** Re-run one case with stderr visible before reporting the result. Uniform failure across heterogeneous targets is far more likely local (missing binary, bad flag, expired auth) than a genuine finding
  - Why: a loop using `timeout 45 tsh aws ...` across 6 AWS accounts died with `command not found: timeout` on every iteration; with stderr suppressed it printed "NO ALBs FOUND / ACCESS FAILED" for all 6 and read exactly like a permissions problem. It nearly shipped as "fleet unverifiable"

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
