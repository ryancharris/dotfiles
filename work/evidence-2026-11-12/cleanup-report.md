> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# Post-test cleanup report (12 Nov 2026)

Baseline: `install-baseline/` (12 Nov 09:58:22). Work files: `cleanup/` (snapshot and diff scripts, `pre/` and `post/` snapshots, `removed.log`, backups).

## 1. Processes
No test-app processes were running: Ghostex, gxserver, Pane, OpenChamber, Agentastic, Sheprd and herdr-gpui all returned no `pgrep` match. The Pane MCP child (pid 45978) had already exited. The only process left was the user's opencode service (pid 59163, started 4 Nov), which was left running. Nothing needed to be killed.

## 2. Removed

**Ghostex**
- I unloaded both LaunchAgents with `launchctl bootout` (`com.madda.ghostex.gxserver` and `-login-recovery`). `brew uninstall --cask ghostex` then deleted their plists.
- The cask uninstall also removed `/Applications/Ghostex.app` and the `/opt/homebrew/bin/ghostex` link. The Caskroom entry is gone.
- Also removed:
  - `/opt/homebrew/bin/gx`
  - `~/.config/ghostex`, `~/.local/state/ghostex`, `~/.local/share/ghostex`, `~/.cache/ghostex`
  - `~/Library/Preferences/com.madda.ghostex.host.plist`
  - `~/Library/Caches/com.madda.ghostex.host.editor` and `~/Library/WebKit/com.madda.ghostex.host.editor`
  - `~/Library/Caches/org.sparkle-project.DownloaderService`. It was absent from the baseline and was created at 10:01 by Ghostex's updater.
  - `~/dotfiles/agents/skills/ghostex-coordinator`

**Pane**
- Removed `/Applications/Pane.app`, `~/Library/Application Support/Pane` and `~/Library/Preferences/com.dcouple.pane.plist`.
- Removed the daemon socket directory `/private/tmp/pane-daemon-501-a8d5ca4319ecbcc8`.
- Deleted the Keychain item "Pane Safe Storage".
- The Pane skills in `~/.codex/skills`, `~/.cursor/skills` and dotfiles were already gone (Pane removed them itself). I verified they are absent.
- The login item was switched off during testing, and no LaunchAgent exists for it.

**OpenChamber**
- Removed `/Applications/OpenChamber.app`, `~/Library/Application Support/OpenChamber`, `~/Library/Preferences/dev.openchamber.desktop.plist`, `~/Library/Logs/OpenChamber` and `~/.config/openchamber`.

**Agentastic**
- Ran `brew uninstall --cask agentasticai/tap/dev`, which removed `/Applications/Agentastic.dev.app`.
- Ran `brew untap agentasticai/tap`.
- Brew trust entry: `brew trust --json=v1` and `~/.homebrew/trust.json` contain no agentastic entry. The file was last written at 11:14, so the entry was already gone. Every remaining trust entry is a pre-existing one.
- Removed the downloaded CLI `/usr/local/bin/dev` (`AGENTASTIC_DEV_CLI v1`, 10:05). The runtime `agentastic` binary lived inside App Support and was removed with it.
- Also removed:
  - `~/.agentastic`
  - `~/Library/Application Support/Agentastic.dev` (615 MB)
  - `~/Library/Preferences/dev.agentastic.Agentastic.plist`
  - `~/Library/Caches/Agentastic.dev` and `~/Library/Caches/dev.agentastic.Agentastic`
  - `~/Library/HTTPStorages/dev.agentastic.Agentastic`
  - Both `~/Library/Application Scripts/dev.agentastic.Agentastic.*` folders
  - `$TMPDIR/agentastic-terminal-pids` and `$TMPDIR/codeedit-it2-shim`
  - `/private/tmp/claude-501/prompt.txt`

**Sheprd**
- Removed `/private/tmp/shp-app`, `~/Library/Caches/so.pen.herdr-gpui` and `~/Library/WebKit/so.pen.herdr-gpui`.

**LaunchServices**
- Unregistered 8 stale `lsregister` records for the deleted bundles. No records remain for them.

**Agent configs**
- `~/.codex/AGENTS.md` (0 bytes) and `~/.cursor/mcp.json` (`{"mcpServers": {}}`) were removed.
- `~/dotfiles/agents/codex/config.toml`: deleted 4 blocks, `[projects."/private/tmp/gxt"]`, `pane-repo`, `t3q/repo` and `orca-h6`. The `/private/var/folders/.../ade-comparison-78a3o_cj` block was kept because the directory was created on 11 Nov, so it predates the baseline. The edited file parses as valid TOML, and it has no `pane` or `ghostex` entries.
  - `git -C ~/dotfiles diff agents/codex/config.toml` was **empty both before and after**, because the file is marked skip-worktree (`git ls-files -v` shows `S`). The real change is below (pre-cleanup copy: `cleanup/codex-config.toml.pre-cleanup`):
    ```
    197,208d196
    <
    < [projects."/private/tmp/gxt"]
    < trust_level = "trusted"
    <
    < [projects."/private/tmp/pane-repo"]
    < trust_level = "trusted"
    <
    < [projects."/private/tmp/t3q/repo"]
    < trust_level = "trusted"
    <
    < [projects."/private/tmp/orca-h6"]
    < trust_level = "trusted"
    ```
- `~/.claude.json`: backed up to `cleanup/claude.json.backup`, then edited with Python's json module. Five project entries were removed: `/private/tmp/agtest`, `gxt`, `orca-h6`, `pane-repo` and `pnd/sessions/legacy-pane-chat`. Project count went from 42 to 37. A check confirmed that no other top-level key changed.

**Temporary test trees in /private/tmp** (only those named in the artifacts files):
- Directories: agtest, agd-repo, gxt, ocb, ocb-repo, orp, orca-h6, orpt, orx, pane-dl, pane-docs, pnd, pane-repo, pane-shots, pane-cfgsnap, psq, psq-ud, psq-repo, shp-dl, shp-r, shp-repo, t3q (about 2.4 GB in all).
- Log and helper files: orp-launch.log, orp-launch2.log, pane-h3.txt, pnd-launch.log, pnd-launch2.log, psq-app.log.

## 3. Final baseline diff (`cleanup/final-diff.txt`)
```
+ applications.txt: .DS_Store
+ applications.txt: .localized
+ containers.txt: dev.agentastic.Agentastic.OpenWithCodeEdit
+ home.txt: .factory
+ user-applications.txt: .localized
```
Nothing that was in the baseline was removed: the diff has no `-` lines. The brew casks, formulae and taps, the LaunchAgents and the npm globals all match the baseline exactly.

## 4. Remaining items and why

| Item | Explanation |
|---|---|
| `/Applications/.DS_Store`, `/Applications/.localized`, `~/Applications/.localized` | These date from 10 Nov, 25 Mar and 19 May. They predate the baseline. The baseline listing hid them; my `/bin/ls -A` shows them. |
| `~/Library/Containers/dev.agentastic.Agentastic.OpenWithCodeEdit` | **Could not remove.** macOS protects it ("Operation not permitted"). It holds only `.com.apple.containermanagerd.metadata.plist`, and its app is gone. Removing it needs Full Disk Access for the terminal, or `containermanagerd` may reap it. |
| `~/Library/Group Containers/dev.agentastic.Agentastic.shared` | **Could not remove**, also protected. Not part of the baseline listings. Same fix as above. |
| `~/.factory/settings.json` (`{"hooks": {}}`, 10:59) | **Unsure, left in place.** It is the hooks file for Factory Droid. At 10:59 the `.bak` files under `~/dotfiles/agents/{claude,codex,gemini}` were written as well, which looks like a hook-manager sync. Kept apps (Orca, Paseo, T3) and removed apps both reference `.factory`, so I cannot attribute it. |
| `~/dotfiles/agents/claude/settings.json.bak` (born 10:10), `codex/config.toml.bak` (born 10:34) and `hooks.json.bak`, `gemini/settings.json.bak` (older), all modified 10:59 | **Unsure, left in place.** These are hook-manager backups next to the `~/.claude/settings.json` source, which must not be touched. The writer is unknown and could be one of the kept apps. |
| `/usr/local/bin/aws-vpn-client` (root, 11:13) | The AWS VPN Client re-created its own link. AWS VPN Client was installed before testing. Not test-related. |
| `~/.claude/projects/-private-tmp-*` (14 directories), `~/.claude/projects/-Users-USER/*.jsonl`, `~/.claude/sessions/*`, `~/.codex/sessions/2026/11/12/*`, `~/.codex/*.sqlite`, `~/.claude/history.jsonl`, `~/Library/Caches/claude-cli-nodejs/-private-tmp-*`, `/private/tmp/claude-501/-private-tmp-*` | Normal Claude and Codex session transcripts, history and per-project caches. Kept as instructed. |
| `~/.local/share/opencode/*` updates | From a single `opencode run` in Orca. This is runtime state of the user's existing opencode install. |
| `/private/tmp/orca-ab-*`, `/private/tmp/opencode`, `/private/tmp/.bun-501-*`, `/private/tmp/backend-debug.log`, `/private/tmp/TemporaryDirectory.*` | Today's temporary files, but not named in any artifacts file, so left per the rules. They are probably runtime temp files from Orca and opencode. |
| `/private/tmp/sheprd-*`, `cmux-gap-source-*`, `ade-*`, `adebench-*` | Earlier-round probe trees (11 Nov and before). Not in the artifacts files, so left. |
| `~/.cache/herdr-gpui`, `~/Library/Preferences/so.pen.herdr-gpui.plist` | Born 11 Nov 16:48, before the baseline (the plist is in the baseline). Kept. |
| `~/dotfiles/agents/skills/synced/...` (modified 11:07) | The folder predates the baseline (born 28 Sep). Its contents were refreshed by Claude skill sync. Kept. |
| Skills dated 10 or 11 Nov (orca-*, orchestration, paseo*) | Kept as instructed. `ghostex-coordinator` was the only skill created after the baseline. |
| Scratchpad folders (`oc-dl`, `pane-tools`, `ag/`, screenshots and others) | Test evidence inside the session scratchpad. Not system state, so left. |
