# dotfiles

Personal configuration files for macOS, managed via symlinks.

## setup

```sh
git clone https://github.com/ryancharris/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

> [!NOTE]
> Installs Homebrew (if missing), all CLI tools and GUI apps from the [`Brewfile`](Brewfile), and creates symlinks.

## tools

| Tool | Description | Keymaps |
|------|-------------|:-------:|
| [aerospace](https://nikitabobko.github.io/AeroSpace/guide) | Tiling window manager | [→](aerospace/README.md) |
| [diffnav](https://github.com/dlvhdr/diffnav) | Diff viewer | — |
| [gh-dash](https://github.com/dlvhdr/gh-dash) | GitHub dashboard | — |
| [git](https://www.git-scm.com/) | Version control | — |
| [git-delta](https://dandavison.github.io/delta/) | Git pager | — |
| [kitty](https://sw.kovidgoyal.net/kitty/) | Terminal emulator | [→](kitty/README.md) |
| [nvim](https://neovim.io/) | Editor | [→](nvim/README.md) |
| [orca](https://github.com/stablyai/orca) | Agent workspace manager | [→](orca/README.md) |
| [starship](https://starship.rs/) | Shell prompt | — |
| [zsh](https://www.zsh.org/) | Shell | [→](zsh/README.md) |

## agents

### commands

Slash commands shared across agents (defined in `agents/commands/`, symlinked into each agent's config).

<details>
<summary><code>/commit</code></summary>
Stage all changes and create a Conventional Commit, optionally pushing to remote
</details>

<details>
<summary><code>/create-pr</code></summary>
Push branch and open a GitHub PR, ready for review or as a draft
</details>

<details>
<summary><code>/clipboard</code></summary>
Copy the latest assistant response to the system clipboard
</details>

<details>
<summary><code>/test-coverage</code></summary>
Audit test coverage for all changes on the current branch
</details>

See `agents/AGENTS.md` for shared conventions (commits, PRs, code style).

### skills

| Skill | Description |
|-------|-------------|
| [`morning-coffee`](agents/skills/morning-coffee/SKILL.md) | Read-only daily engineering brief covering PRs, reviews, agenda, on-call status, incidents, recent activity, and cross-org signals. |
