# dotfiles

Personal configuration files for macOS, managed via symlinks.

## setup

```sh
git clone https://github.com/ryancharris/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

> [!NOTE]
> Installs Homebrew (if missing), all CLI tools and GUI apps, and creates symlinks.

## tools

| Tool | Description | Keymaps |
|------|-------------|:-------:|
| [aerospace](https://nikitabobko.github.io/AeroSpace/guide) | Tiling window manager | [→](aerospace/README.md) |
| [git](https://www.git-scm.com/) | Version control | — |
| [kitty](https://sw.kovidgoyal.net/kitty/) | Terminal emulator | [→](kitty/README.md) |
| [nvim](https://neovim.io/) | Editor | [→](nvim/README.md) |
| [starship](https://starship.rs/) | Shell prompt | — |
| [zsh](https://www.zsh.org/) | Shell | [→](zsh/README.md) |

## agent commands

Slash commands shared across agents (defined in `agents/commands/`, symlinked into each agent's config).

<details>
<summary><code>/quick-commit</code></summary>
Stage all changes and create a Conventional Commit (no push)
</details>

<details>
<summary><code>/commit-and-push</code></summary>
Stage all changes, commit, and push to remote
</details>

<details>
<summary><code>/create-pr</code></summary>
Push branch and open a ready-for-review GitHub PR
</details>

<details>
<summary><code>/create-draft-pr</code></summary>
Push branch and open a draft GitHub PR
</details>

See `agents/AGENTS.md` for shared conventions (commits, PRs, code style).
