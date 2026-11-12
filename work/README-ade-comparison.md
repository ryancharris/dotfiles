# Agent environment comparison

Eight ADEs tested on one macOS host on 12 November 2026 against the criteria in `comparison-followups.md`. The personal pick uses heavy dotfiles and Enterprise accounts; the general pick assumes minimal dotfiles. The top three are ranked recommendations; a validated pass requires every applicable entry and hard requirement to be proven. Partial evidence is not an observed failure.

Recommendations for both picks: **1. Paseo, 2. Sheprd (Provisional), 3. Agentastic (Provisional)**. Paseo is the only validated pass, using a saved login-shell profile. Sheprd still lacks a verified persistent startup route; Agentastic still lacks an input-binding proof. The two recommendation lists are identical; their provisional labels keep incomplete tests distinct from demonstrated product failures.

| Tested | Version | Result |
|---|---|---|
| Paseo | 0.15.4 | Ranked 1; validated pass on the saved login-shell profile. |
| Sheprd | 20261109.1 | Ranked 2, **Provisional**: H3 startup-file preservation is partial. Chat also needs New Herdr 2 Terminal first when Herdr 1 is absent. |
| Agentastic | 0.16.2 | Ranked 3, **Provisional**: startup checks passed, but configured terminal input/keybinding behavior could not be validated in the follow-up. |
| Orca | 1.4.255 | Fails H7: writes Claude, Codex, Gemini, Cursor and Hermes status hooks, on by default, with no prompt. |
| Pane | 2.4.217 | Fails H7: writes MCP servers, skills and an AGENTS.md block into other agents' global configs on first launch, with no prompt. |
| Ghostex | 11.5.0 | Fails H7: wrote the ghostex-coordinator skill into ~/.claude/skills without a prompt. |
| T3 Code | 0.1.5 tested; 0.1.9 current | Not yet qualified on tested 0.1.5: an interactive raw-agent session was not exercised (H1), and default startup-file preservation remains partial (H3). |
| OpenChamber | 2.7.0 | Not yet qualified: GUI chat uses OpenCode, but a raw OpenCode TUI session was not exercised for the matching launch-time choice (H1). |

## Outputs

- `ade-comparison-social.png`: the shareable social image, **2160×2700 (4:5)**.
- `ade-comparison-card.html`: the 1080×1350 design source for that image.
- `ade-comparison-share.html`: the full report with all eight apps visible; use this to read or share the complete comparison.
- `ade-comparison-detailed.html`: the same evidence with a two-app selector; use this for side-by-side inspection.
- `comparison-grades.json`: source of truth for all 16 fields, audience scope, route limits, qualification state and ranking.
- `evidence-2026-11-12/`: sanitized historical test records and continuation checks. Original screenshots remain on the test host; raw account/config files are not published.
- `generate-comparison.py`: regenerates both reports and the card content from the manifest; card CSS is retained as the layout template.
- `comparison-validation.json`: browser validation results, including layout and hard-gate invariants.

Herdr, cmux, Conductor and 13 other tools were excluded before testing; the manifest records why. Earlier six-app probes, benchmark files, `ade-comparison.html`, `ade-social-card.html` and `concept-*.html` are local historical drafts, not current deliverables. CPU/RAM benchmarking was removed from scope.

## Read the grades

**Proven** establishes only the route and test scope in its note. **Supported** is source/docs evidence without runtime proof. **Partial** establishes only part of the requirement. **Gap** is an observed miss; **Unknown** means missing evidence. Grades are never summed. One hard gap fails a pick; incomplete hard evidence leaves it unqualified. Extras inform recommendation order without turning incomplete hard evidence into a validated pass.

A launch-time TUI/GUI choice counts; converting an existing conversation is not required. Provider keys and Enterprise accounts may run through a hosted CLI, with that route stated. The configured shell executable and login-mode startup are separate checks; a non-login shell is not automatically a failure, but named aliases alone do not prove every startup file or input binding. Terminal claims are limited to this host's configured zsh and the representative input tested.

## Regenerate and validate

From the repository root on macOS with Google Chrome installed:

```sh
python3 work/generate-comparison.py
python3 work/validate-comparison.py
python3 work/test-comparison-validation.py
```

The browser validator uses disposable Chrome state. It checks all 128 grades in each view, identical table contents, both audience lists, the legend and requirements disclosure at 390/768/1400 px, all 64 selector pairs, show-all and no page overflow. Narrow tables scroll intentionally.

It also checks that a qualified app has every entry/hard gate proven, then verifies the card's 64 chips against the manifest, exact 1080×1350 layout, text at least 24 px, ranking and counts. It refreshes the PNG and validation JSON. Regression checks reject a claimed pass over a partial hard gate, a missing third recommendation, and a failed app in the ranking.

## Paseo profile used for H3

The tested alternate profile lives in Paseo's daemon `config.json`; select it for a new terminal. On this host the configured shell is `/bin/zsh`:

```json
{"daemon":{"terminalProfiles":[{"id":"login-shell","name":"Login shell","command":"/bin/zsh","args":["-l"]}]}}
```

Merge the profile into existing configuration; the test did not replace the live config. The default remains non-login. [The follow-up](evidence-2026-11-12/paseo-h3-followup.md) distinguishes first-party terminal API input from desktop key-event translation.

## Cleanup

The prior session removed apps and integration artifacts absent from its baseline. Protected Agentastic Containers/Group Containers, uncertain `.bak` files and `~/.factory/settings.json` remain documented in the retained cleanup report. Continuation checks record their own process/data cleanup separately; baseline apps remain installed.
