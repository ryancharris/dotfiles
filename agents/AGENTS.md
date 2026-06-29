# Agent Instructions

Shared conventions for all AI coding agents working in this repository.

`install.sh` symlinks this file to `~/.claude/CLAUDE.md`, `~/.gemini/GEMINI.md`, and
`~/.config/opencode/AGENTS.md` — one source of truth for all agents. Claude-specific
overrides (permissions, personal context) belong in `~/.claude/CLAUDE.local.md`, which
is gitignored and not shared.

## General
- Use helpful visuals and diagrams where appropriate, especially for networking issues
- When work touches networking (protocols, traffic routing, DNS, load balancing, firewalls, CNI, service meshes, etc.), explain the relevant concept briefly — assume the reader is a platform engineer who is new to networking
- When compacting, always preserve the commit message format rules and PR body template
- Consult in-repo documentation and official public docs before assuming behavior or making recommendations; don't rely on training-data intuition when a source of truth exists
- Be evidence-based: cite the file path, doc URL, or test output that supports each assertion — don't state conclusions without showing the reasoning
- For non-trivial changes, prefer end-to-end and integration tests over unit tests alone; consider contract tests and smoke tests to verify real behavior across system boundaries

## Commits

1. Follow [Conventional Commits](https://www.conventionalcommits.org/):

- **Format:** `<type>[optional scope]: <description>`
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`
- Scope should reflect the tool or component (e.g. `gh-dash`, `install`, `zsh`, `kitty`)
- Description is lowercase, imperative mood, no trailing period
- Subject line ≤ 72 characters
- Breaking changes: append `!` after type/scope and add a `BREAKING CHANGE:` footer

2. NEVER add yourself to 'Co-Authored-By' for any commit

## Pull Requests

- Title: short (≤ 70 chars), imperative mood, describes the change
- PRs must come from a feature branch — NEVER open a PR from `main`
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

## Slash Commands

Agent-specific slash commands are defined in `agents/commands/`:

| Command | Description |
|---|---|
| `/quick-commit` | Stage all changes and create a Conventional Commit (no push) |
| `/commit-and-push` | Stage all changes, commit, and push to remote |
| `/create-pr` | Push branch and open a ready-for-review GitHub PR |
| `/create-draft-pr` | Push branch and open a draft GitHub PR |

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
