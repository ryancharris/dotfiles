# Agent environment comparison

Eight ADEs tested on one macOS host on 12 November 2026 against the criteria in `comparison-followups.md`. The personal pick uses heavy dotfiles and Enterprise accounts; the general pick assumes minimal dotfiles. The top three are ranked recommendations; a validated pass requires every applicable entry and hard requirement to be proven. Partial evidence is not an observed failure.

Recommendations for both picks: **1. Paseo, 2. Sheprd (Provisional), 3. Agentastic (Provisional)**. Paseo is the only validated pass, using a saved login-shell profile. Sheprd and Agentastic startup/input gaps have now been closed on documented setups; successful authenticated API-key inference remains unverified for Sheprd and Agentastic. The two recommendation lists are identical; their provisional labels keep incomplete tests distinct from demonstrated product failures.

| Tested | Version | Result |
|---|---|---|
| Paseo | 0.15.4 | Ranked 1; validated pass on the saved login-shell profile. |
| Sheprd | 20261109.1 | Ranked 2, **Provisional**: startup/input/chat/delegation passed with pre-started core 0.1.18 and a saved login-shell setting; authenticated API-key response pending. |
| Agentastic | 0.16.2 | Ranked 3, **Provisional**: default startup forwarding and native key editing passed; authenticated API-key response pending. |
| Orca | 1.4.255 | Fails H7: writes Claude, Codex, Gemini, Cursor and Hermes status hooks, on by default, with no prompt. |
| Pane | 2.4.217 | Fails H7: writes MCP servers, skills and an AGENTS.md block into other agents' global configs on first launch, with no prompt. |
| Ghostex | 11.5.0 | Fails H7: wrote the ghostex-coordinator skill into ~/.claude/skills without a prompt. |
| T3 Code | 0.1.5 tested; 0.1.9 current | Not yet qualified: raw-agent launch choice, full terminal setup and authenticated API-key response remain unverified. |
| OpenChamber | 2.7.0 | Not yet qualified: raw OpenCode TUI choice, configured input and authenticated API-key response remain unverified. |

## Specific licenses

These identify the first-party project license, not every bundled dependency. The report tables link each label to its primary source, and the social card shows the compact label below each ADE name.

| ADE | Verified published license |
|---|---|
| Paseo | [Apache-2.0](https://github.com/getpaseo/paseo/blob/1c00b365c9e0b74c1580eba33d905d693125ae21/LICENSE) |
| Sheprd | [Apache-2.0](https://github.com/sheprd-labs/sheprd/blob/98916c392b8408a946d0bd3b4f00b425cfd84b8f/LICENSE) |
| Agentastic | [MIT (vendor notice)](https://www.agentastic.dev/legal/license) |
| Orca | [MIT](https://github.com/stablyai/orca/blob/084ce0eebbdda3f665251984804f2238be666296/LICENSE) |
| Pane | [AGPL-3.0-or-later + terms](https://github.com/greenfield-inc/Pane/blob/4cece4fc5bd4ffd6d3454d5a171e19e6c5676eeb/LICENSE) |
| Ghostex | [MIT](https://github.com/maddada/Ghostex/blob/80f0b7f3d824bb0dcce92afb89244ab8480600d9/LICENSE) |
| T3 Code | [MIT](https://github.com/pingdotgg/t3code/blob/6d450a4284852af137b2f3407fddd89eb76e7644/LICENSE) |
| OpenChamber | [MIT](https://github.com/openchamber/openchamber/blob/651a0564880633fbcdc2ac3f84d08e42c7748a64/LICENSE) |

Pane's AGPLv3-or-later grant also includes visible Dcouple UI-attribution and name/logo non-endorsement terms; the compact card says “AGPLv3+ · terms”. Agentastic publishes an MIT notice and separately calls its app closed source; that notice is not pinned to the exact tested 0.16.2 binary. Its source-availability grade therefore remains separate from its license label. All other license links are pinned to the tested release's source commit. Binary/service and third-party scope is retained in [the top-three license audit](evidence-2026-11-12/licenses-top-three.json) and [the other-five audit](evidence-2026-11-12/licenses-other-five.json).

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

## Runtime validation status

**Incomplete: Sheprd and Agentastic need successful authenticated API-key requests.** No valid disposable key was available; a local secret-file path or environment-variable name was requested. The earlier invalid-key 401s confirm transport, not an assistant response. This distinction now applies consistently to all eight apps.

[Actual runtime evidence](evidence-2026-11-12/top-three-validation.md) records the fresh Paseo child/result test, Sheprd source-traced startup and native parent/child run, and Agentastic native input edit with controls and process/loader receipts. App-created test resources were cleaned up. Linux builds and other docs-only extras remain labelled separately.

Sheprd's validated setup needs an already running **herdr-core 0.1.18** plus `shell = ["/bin/zsh", "-l"]` in its core config. Its bundled 0.1.13 did not honor that setting in the tested route. See the [exact dependency and limits](evidence-2026-11-12/sheprd-validation-notes.md). Agentastic's default login startup and native input now pass; no user startup file was changed.

## Read the grades

**Proven** establishes only the route and test scope in its note. **Supported** is source/docs evidence without runtime proof. **Partial** establishes only part of the requirement. **Gap** is an observed miss; **Unknown** means missing evidence. Grades are never summed. One hard gap fails a pick; incomplete hard evidence leaves it unqualified. Extras inform recommendation order without turning incomplete hard evidence into a validated pass.

A launch-time TUI/GUI choice counts; converting an existing conversation is not required. Provider keys and Enterprise accounts may run through a hosted CLI, with that route stated. The configured shell executable and login-mode startup are separate checks; a non-login shell is not automatically a failure, but named aliases alone do not prove every startup file or input binding. Terminal claims are limited to this host's configured zsh and the representative input tested.

## Regenerate and validate

From the repository root on macOS with Google Chrome installed:

```sh
python3 work/generate-comparison.py
python3 work/validate-comparison.py
python3 work/test-comparison-validation.py
python3 work/validate-top-three-evidence.py
```

The browser validator uses disposable Chrome state. It checks all 128 grades in each view, identical table contents, both audience lists, the legend and requirements disclosure at 390/768/1400 px, all 64 selector pairs, show-all and no page overflow. Narrow tables scroll intentionally.

It also checks that a qualified app has every entry/hard gate proven, then verifies the card's 64 chips against the manifest, exact 1080×1350 layout, text at least 24 px, ranking and counts. It refreshes the PNG and validation JSON. Its browser `passed` flag is separate from `runtime_qualification_complete`, which remains false while API tests are pending. Regression checks reject a claimed pass over a partial hard gate, a missing third recommendation, a failed app in the ranking, and treating API-key wiring as authenticated inference.

The runtime receipt checker exits **2** while required API-key replies are missing; exit 0 means the selected critical runtime/identity/API receipts pass, alongside the linked manual per-gate review; it is not an automated verification of every screenshot or extra-credit claim. The prepared BYOK runner has not made inference requests without a valid key.

## Paseo profile used for H3

The tested alternate profile lives in Paseo's daemon `config.json`; select it for a new terminal. On this host the configured shell is `/bin/zsh`:

```json
{"daemon":{"terminalProfiles":[{"id":"login-shell","name":"Login shell","command":"/bin/zsh","args":["-l"]}]}}
```

Merge the profile into existing configuration; the test did not replace the live config. The default remains non-login. [The follow-up](evidence-2026-11-12/paseo-h3-followup.md) distinguishes first-party terminal API input from desktop key-event translation.

## Cleanup

The prior session removed apps and integration artifacts absent from its baseline. Protected Agentastic Containers/Group Containers, uncertain `.bak` files and `~/.factory/settings.json` remain documented in the retained cleanup report. Continuation checks record their own process/data cleanup separately; baseline apps remain installed.
