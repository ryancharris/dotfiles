# Agent Instructions

Shared conventions for all AI coding agents working in this repository.

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- **Format:** `<type>[optional scope]: <description>`
- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`
- Description is lowercase, imperative mood, no trailing period
- Subject line ≤ 72 characters
- Add a body only when the intent is non-obvious (why, not what)
- Breaking changes: append `!` after type/scope and add a `BREAKING CHANGE:` footer

## Pull Requests

- Title: short (≤ 70 chars), imperative mood, describes the change
- PRs must come from a feature branch — never open a PR from `main`
- Body format:
  ```
  ## Summary
  - <what changed and why>

  ## Test plan
  - <how to verify>
  ```

## Code Style

- Prefer CLI tools over GUIs
- Favour OSS solutions
- Keep changes minimal and focused — avoid unrelated refactors
- No comments unless the logic is genuinely non-obvious

## Slash Commands

Agent-specific slash commands are defined in `agents/commands/`:

| Command | Description |
|---|---|
| `/quick-commit` | Stage all changes and create a Conventional Commit (no push) |
| `/commit-and-push` | Stage all changes, commit, and push to remote |
| `/review-changes` | Summarize and review uncommitted changes with suggestions |
| `/create-pr` | Push branch and open a ready-for-review GitHub PR |
| `/create-draft-pr` | Push branch and open a draft GitHub PR |
