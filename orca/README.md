# orca

[Orca](https://github.com/stablyai/orca) has no config file. Settings live in a
SQLite store inside `~/Library/Application Support/orca/profiles/<id>/`, owned
by the running app (revisions, content hashes, an authority file). Writing to it
from outside is unsafe, so this directory records **desired state** and checks
for drift instead of symlinking.

| File | Purpose |
|------|---------|
| `settings.json` | Only settings that differ from Orca's built-in defaults |
| `check.py` | Diffs `settings.json` against live settings (reads a DB copy) |
| `apply.sh` | Installs plugins and repos via the `orca` CLI, then runs `check.py` |

Settings themselves are applied by hand in Orca → Settings; `check.py` tells you
which keys are off. `claudeCodeThemeSync` is `false` on purpose: when `true`,
Orca writes `theme: custom:orca` into `~/.claude/settings.json`, which is a
symlink into this repo.

## Known conflict: agent status hooks

Orca injects its own hook entries into `~/.claude/settings.json`,
`~/.codex/hooks.json` and `~/.gemini/settings.json`. All three are symlinks into
`agents/`, so those hooks land in tracked files and show up as a dirty tree.
They are machine-specific (absolute `~/.orca` paths), so do not commit them.
Turning off `agentStatusHooksEnabled` stops it at the cost of Orca's agent
status indicators.

## Regenerating `settings.json`

Defaults come from `out/shared/default-global-settings.js` inside
`/Applications/Orca.app/Contents/Resources/app.asar`. Diff live settings
against that to find new deliberate changes.
