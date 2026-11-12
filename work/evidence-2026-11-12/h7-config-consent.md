> Historical test record, 12 November 2026. Grades below may be superseded; see [the current manifest](../comparison-grades.json). Identifying user paths and organization names are redacted.

# H7 audit: does the app modify other tools' config without consent? (2026-11-12, research only)

Consent = explicit opt-in prompt or a setting that is off by default. Writes by agent CLIs (trust entries, transcripts) are excluded.

| App | H7 | Writes into other tools' config | Consent mechanism |
|---|---|---|---|
| Orca | FAIL | Hooks into ~/.claude/settings.json (hook + statusLine wrapper), ~/.codex/hooks.json (+ trust entries in config.toml), ~/.gemini/settings.json, ~/.cursor/hooks.json, ~/.hermes/config.yaml. Scripts in ~/.orca/agent-hooks. Skills orca-cli, orca-computer-use, orchestration. | Hooks: default ON, no prompt. Skills: explicit button. Theme sync: prompt. |
| Paseo | PASS (qualified) | Skills paseo* (11 Nov 10:24:18) and ~/.local/bin/paseo symlink. No MCP, hook or rc write found. | Onboarding step "Let agents use Paseo" with visible toggles, default ON, plus Skip setup. |
| Pane | FAIL | MCP in ~/.claude.json, ~/.codex/config.toml, ~/.cursor/mcp.json; "pane-notify" block in ~/.codex/AGENTS.md; skills into ~/.claude/skills (-> dotfiles), ~/.codex/skills, ~/.cursor/skills. | Written on first launch with no prompt; settings default ON. |
| Agentastic | PASS | None. ~/.claude/settings.json, ~/.codex/config.toml and ~/.zshrc verified unchanged. Its own dirs only. | n/a |
| Ghostex | UNCLEAR (leans fail) | Skill ghostex-coordinator into ~/.claude/skills -> dotfiles (12 Nov 10:05:44). Codex config.toml rewritten 10:04:43, writer unconfirmed. | No prompt observed; written when a coordinator session was started. |
| Sheprd | PASS (limited) | None observed. ~/.claude/skills, ~/.zshrc, ~/.codex untouched. | n/a. Codex was not run; a skill-install command was not tested. |
| T3 Code | PASS | None except Codex project-trust (agent CLI). | n/a |
| OpenChamber | PASS | None. ~/.zshrc, ~/.zprofile and opencode config verified untouched. | n/a |

## Evidence

### Orca (fail)
- `orca agent hooks status` (read-only run today) prints `agentStatusHooksEnabled: true` and "installed" for claude, codex, gemini, cursor and hermes.
- The extracted app (/private/tmp/orx/.../constants-*.js) has `agentStatusHooksEnabled:!0` in the defaults. The renderer code treats the setting as `!== false`. That makes it default-on, with an opt-out toggle and `orca agent hooks off`.
- Mtimes:
  - ~/.orca/agent-hooks scripts and codex hooks.json (+ .bak): 10 Nov 12:19:59.
  - Cursor and Gemini hooks: 11 Nov 10:36:21.
  - Claude settings.json: 12 Nov 10:10.
  - `claude-statusline.installed`: 12 Nov 10:27.
- The Nov-12 Claude and statusline rewrites coincide with the tester's isolated Orca instance. It ran with the real HOME, so Orca re-applies hooks on each launch. This is not proven for each write.
- The dotfiles repo shows the hook entries as uncommitted diffs in agents/claude/settings.json, agents/codex/hooks.json and agents/gemini/settings.json. All reference .orca/agent-hooks.
- Skills (10 Nov): orca-cli 12:30:09, orca-computer-use 12:29:59, orchestration 12:24:48. They were created 5-10 minutes after the hooks, and ~/.cursor/skills/orchestration is a link to the same skill.
  - Orca's UI has explicit "Install skills" / "Install skill" buttons (FeatureWallSetupChecklist, SkillInstallDialog). The Orca docs mirror describes `orca skills install` running `npx skills`.
  - I found no automatic install-on-launch path, so this is attributed to a user click. That is inferred from timing and UI code; I did not see the click.
- Claude theme sync: ~/.orca/claude-theme-sync.json and claude/settings.json.bak (both 10 Nov 15:55:46) show the user accepted the "Match Claude Code to your Orca theme" prompt. The tester declined it today. This is a prompted opt-in.

### Paseo
- ~/.local/bin/paseo symlink (10:24:18.933), config.json (10:24:18.933) and skills/.paseo-managed-files.json (10:24:18.944) all share one timestamp on 11 Nov. That is one action: Continue on the Orchestration wizard step.
- The wizard screenshot (paseo-shots/04-orch.png) shows three default-ON toggles: Enable Paseo tools, Orchestration skills, Command line. The skills toggle has a selector icon. A "Skip setup" button is present.
- The skills were therefore installed by the app, driven by an explicit prompt. The user accepted the defaults; I can't tell from the evidence whether they changed any toggle.
- If the wizard is skipped, "Enable Paseo tools" is OFF (verified). Skills-off-on-skip was not verified.
- Paseo's MCP is injected at agent spawn (`mcp.injectIntoAgents`). ~/.claude.json mcpServers and the Codex mcp_servers have no paseo key. ~/.zshrc has no Paseo text. The PATH-in-rc helper (cli-install/shell-rc.js) did not fire because ~/.local/bin is already on PATH.
- Strict reading ("must be off by default"): FAIL. Prompt reading: PASS. I grade it pass, flagged.

### Pane (fail)
- The tester observed the writes on first launch with no prompt. Settings > AI & Agents (Register Pane tools, Install Pane skill for agents, Approvals) were default ON.
- The writes are listed above. Pane removed them itself when the toggles were turned off, and left behind a 0-byte ~/.codex/AGENTS.md and `{"mcpServers":{}}` in ~/.cursor/mcp.json.
- Other agent processes picked up the MCP entry immediately.

### Ghostex
- The skill appeared when the coordinator session started. No consent prompt was seen. The coordinator was a user-chosen feature, but the install was not offered.
- The Codex config.toml change at 10:04:43 cannot be attributed (Ghostex or the Codex CLI).
- The Claude and Codex agent prompts are injected at launch (`--append-system-prompt-file`, `-c developer_instructions`). These are not file writes.

### Others
Agentastic, Sheprd, T3 Code and OpenChamber: the tester diffed against the baseline and checked sha/mtime of the config files.
- Agentastic: checked ~/.claude/settings.json, ~/.codex/config.toml and ~/.zshrc. Its own AgentLaunch codex-home links stay in its own data dir.
- T3 Code: wrote only the Codex trust entry (an agent CLI write).
- OpenChamber: only an empty ~/.config/openchamber/managed-opencode.

## Not verified
- I did not read the web docs of Ghostex, Sheprd, T3 Code, Agentastic or OpenChamber. Those grades rest on the tester's observations from one run. Behaviour on other paths (a Sheprd skill command, Codex runs, a Ghostex upgrade) may differ.
- Orca's hook default comes from the installed 1.4.255 bundle and the CLI status, not from the Orca docs.
