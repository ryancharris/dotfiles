# dotfiles

## setup

- clone repository to local machine
- install cli tools and gui apps with `setup/install-brew.zsh`
- setup symlinks

## tools

### frequently used

- [ghostty](https://ghostty.org/)
- [git](https://www.git-scm.com/)
- [kitty](https://sw.kovidgoyal.net/kitty/)
- [nvim](https://neovim.io/)
- [starship](https://starship.rs/)
- [zsh](https://www.zsh.org/)

### agents

- [claude](https://claude.ai/code) — Claude Code CLI
- [gemini](https://github.com/google-gemini/gemini-cli) — Gemini CLI
- [opencode](https://opencode.ai/) — OpenCode CLI

## agent commands

Slash commands shared across agents (defined in `agents/commands/`, symlinked into each agent's config):

| Command | Description |
|---|---|
| `/quick-commit` | Stage all changes and create a Conventional Commit (no push) |
| `/commit-and-push` | Stage all changes, commit, and push to remote |
| `/review-changes` | Summarize and review uncommitted changes with suggestions |
| `/create-pr` | Push branch and open a ready-for-review GitHub PR |
| `/create-draft-pr` | Push branch and open a draft GitHub PR |

See `agents/AGENTS.md` for shared conventions (commits, PRs, code style).
