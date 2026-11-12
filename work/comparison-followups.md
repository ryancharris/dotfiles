# Comparison follow-ups — 12 November 2026

## Latest continuation status

- Both report views and the shareable PNG are rebuilt. See `README-ade-comparison.md` for their roles.
- Ranked recommendations (both picks): 1 Paseo, 2 Sheprd (Provisional), 3 Agentastic (Provisional). Paseo is the only full validated pass. Sheprd startup/input/chat/delegation now pass with pre-started core 0.1.18; Agentastic startup forwarding and actual native key editing pass. Both remain provisional pending successful authenticated API-key requests. No partial hard gate is counted as a pass.
- Latest user correction: retain the requested top-three recommendations with visible caveats and remove the yellow internal work-status strip from the card.
- The audit corrected inconsistent TUI/GUI criteria: launch-time choice counts, conversation conversion is optional. T3/OpenChamber remain unverified on the raw-TUI test, not failed for lacking conversion. OpenChamber's Enterprise terminal route counts consistently with Sheprd's.
- Retained test records and the new shell/input checks live in `evidence-2026-11-12/`; the manifest is authoritative over historical grades.
- Browser checks passed at 390/768/1400 px, all 128 grades per view and 64 selector pairs; the card is 4:5. The validator rejects a pass over an incomplete hard requirement.
- Original cleanup has documented protected/uncertain leftovers. Old benchmark and six-app checklists below are history, not active completion requirements.

## Revised brief — 12 November 2026 (criteria settled; execution authorized 12 November)

Agreed decisions (Q1–Q10, R1–R13):
- Picks: personal (heavy dotfiles, Enterprise accounts) and general (minimal dotfiles). Card: two top-3 lists over one shared grid; 2-slide carousel if the grid exceeds ~8 apps.
- Entry (ADE): integrated terminal; native chat interface; orchestration where a parent delegates to and collects from child agents; bring-your-own API keys for API-based providers, including OpenRouter-style gateways and the major labs (OpenAI, Anthropic, Google); macOS; downloadable today (no waitlist or beta-access request); release within ~90 days.
- Hard, both picks: per-pane/session TUI-or-GUI choice (kept hard even if none pass); no separate product login; respects the user's terminal configuration (login shell, startup files, env/PATH/aliases/prompt, keybindings; not emulator appearance), tested with the configured shell, not only zsh.
- Hard, both picks: integrated diff/review (promoted from extra credit, user 12 Nov). Hard, general only: good out-of-box defaults.
- Enterprise OpenAI and Anthropic: hard for the personal pick; extra credit for the general pick (user 12 Nov: not everyone has Enterprise accounts).
- Extra credit (tie-break only, never summed): Enterprise accounts (general only); settings in config files rather than the UI (less UI-only config = more credit; replaces the dropped 5-value cap); open source; the free tier covers the core workflow, with no core feature behind a paywall or upsell prompt; Linux (general); integrated browser (general only). Mobile and inline comments optional, no credit.
- Added 12 Nov after testing: hard requirement H7, both picks: does not modify other tools' configs (Claude Code, Codex, Cursor, OpenCode, shell rc) without consent; agent-CLI trust prompts don't count against the app. Provider keys passed through a hosted CLI count for entry, with the route noted. T3 Code tested on 0.1.5 (current 0.1.9): note the version on the card, do not upgrade. Pane residue ~/.codex/AGENTS.md and ~/.cursor/mcp.json did not exist before: delete at cleanup. Prove the diff for Agentastic, Ghostex and Sheprd once Screen Recording is granted.
- Config-consent audit, 12 Nov (scratchpad h7-config-consent.md): Orca FAIL (Claude/Codex/Gemini/Cursor/Hermes status hooks on by default, no prompt); Pane FAIL; Ghostex unclear, leaning fail; Paseo qualified pass (wizard toggles already on, plus a Skip button); Agentastic, Sheprd, T3 Code, OpenChamber pass. Decided (recommendations adopted after restart): a visible wizard step with toggles already on and a Skip button counts as consent, so Paseo passes; Ghostex graded fail. Orca hooks removed with `orca agent hooks off` (12 Nov; status still reports enabled, so re-check after the next Orca launch). Screen Recording was granted to Orca; the archived Agentastic and Sheprd diff proofs completed.
- Evidence: documentation counts for screening and ranking; every hard requirement of each app in either top 3 is tested hands-on before publishing, and a contradiction changes the grade and reruns the ranking. Grid keeps Proven vs Supported.
- Candidates: current six plus screen survivors; Sheprd and Herdr separate; Conductor stays excluded (beta access request); one extra screening pass over ~9 named unscreened tools; hands-on test at most 8.

- [x] Extra screening pass (JetBrains Air, AionUi, Happy, Waku, alas, supacode, Berd, Traycer, Solo).
- [x] Paper-screen all candidates against entry and hard tiers; proposed shortlist of 8 (Orca, Paseo, Sheprd, T3 Code, Ghostex, Pane, OpenChamber, Agentastic). Herdr out (no native chat). Synthesis: scratchpad paper-screen-synthesis.md. cmux out (user 12 Nov: a feature behind an experimental flag does not count as native chat). Installs approved; remove every app not installed before testing (baseline: scratchpad install-baseline/, taken 12 Nov; Sheprd is not currently installed, so it is removed too).
- [x] Re-grade the current six under the new tiers (paper/evidence; scratchpad regrade-six.json).
- [x] Hands-on test all 8 shortlisted apps (12 Nov). Matrix: scratchpad hands-on-matrix.md; per-app hands-on-*.md, artifacts-*.txt, screenshots.
- [x] Removed test apps, taps, LaunchAgents and removable data absent from the baseline, with protected/uncertain leftovers documented; verified by re-diffing against the baseline (scratchpad cleanup-report.md). Left for the user: Agentastic Containers/Group Containers (need Full Disk Access), dotfiles .bak files (probably from `orca agent hooks off`), ~/.factory/settings.json (writer unknown).
  - Also remove app-installed skills written into ~/dotfiles/agents/skills/ during testing (ghostex-coordinator, pane, pane-manage-and-message-agents, plus any later ones newer than the 12 Nov 09:58 baseline), /opt/homebrew/bin/gx, Ghostex LaunchAgents, and Codex `[projects."/private/tmp/..."]` trust entries for test fixtures in agents/codex/config.toml. Keep pre-baseline entries. Agentastic: untap agentasticai/tap and revert its `brew trust` entry; remove the downloaded `agentastic` agent CLI. Pane: confirm with user, then remove the 0-byte ~/.codex/AGENTS.md and the `{"mcpServers":{}}` ~/.cursor/mcp.json (both written 12 Nov 10:27–10:28 by Pane; whether they existed before is unknown). Remove Pane skills in ~/.codex/skills and ~/.cursor/skills, plus Pane/Ghostex/OpenChamber test-fixture project entries in ~/.claude.json and the Codex config.
- [ ] Final top-three qualification (current blocker: authenticated API-key replies for Sheprd/Agentastic; see `evidence-2026-11-12/top-three-validation.md`). Historical note: the continuation audit reopened H3. Paseo passed on a saved alternate login-shell profile; Sheprd startup and Agentastic input remain unverified. The original three-pass claim is superseded; the three recommendations remain ranked with explicit provisional labels.
- [x] Rebuilt both reports and the 4:5 social card; validated against the manifest. The card retains three ranked recommendations with exact H3 caveats; only Paseo is shown as a validated pass.

## Historical gap/unknown audit — superseded scope

Scope: all 12 fields initially graded Gap or Unknown; `gap-audit-inventory.json` records every original item. Partial/Supported fields are context, not silently claimed as fully qualified. No resource benchmarking is part of this audit.

- [x] Orca highlighted diff: actual installed Monaco diff/language wiring and successful background tab-open receipt; Unknown becomes Supported. Live GUI colors remain unobserved without OS UI grants.
- [x] Herdr built-in preview: execute actual module loader/parser on a 1,601-line fixture and inspect current upstream; confirm plain text and 1,500-row cap. Gap remains a confirmed limitation. See `diff-gap-closure.md` and `herdr-diff-gap-result.json`.
- [ ] Finish cmux delegation/diff/shell evidence and record source vs real-application boundaries.
- [ ] Finish Sheprd and T3 actual file-preference/restore and shell checks.
- [ ] Finish all five Enterprise-route investigations, preserving the unresolved OpenAI identity classification and exact live tests where feasible.
- [ ] Integrate each result in both reports, retain a per-item answer/blocker, refresh the social image, independently review and validate, and update PR #106.

## Historical six-app report — superseded scope

- [x] Add a visual evidence grade to all 48 comparison fields in each view, with a five-status legend; retain the grade manifest, refresh the social image, and verify all grades, table parity, widths and selector combinations in `comparison-validation.json`.

This section supersedes earlier resource and four-app tracking below. CPU/RAM measurements and Kitty parity were dropped by the user; they are not completion requirements for this update. Existing zsh remains required. Conductor stays excluded.

- [x] Add Sheprd and T3 Code to both active HTML views, both comparison tables, the history disclosure and interactive selectors; refresh the social PNG.
- [x] Independently review current primary documentation and pinned source for each new app. See `sheprd-evidence.md` and `t3-evidence.md` for requirement-by-requirement findings, immutable citations and limits.
- [x] Confirm Sheprd is distinct from the installed official Herdr 0.1.15. Scope the historical preview limitation to that tested Herdr version.
- [x] Retain Paseo/Orca as the current evidence-based evaluation order; introduce T3 Code and Sheprd as source-reviewed challengers, without claiming live qualification.
- [x] Browser checks passed at 390, 768 and 1400px: requirements disclosure, six-app rows, all 36 selector combinations, show-all and no outer-page overflow. Both table contents match between views; see `comparison-validation.json`.

Qualification follow-ups (tracked, not claimed complete):

- [ ] Sheprd: pin a release and verify documented main-branch features exist in it; no-account startup, parent/child launch/message/result, rendered highlighted patch, actual host zsh checks, preference restore/count, OpenRouter and both Enterprise identities.
- [ ] T3 Code: qualify a current pinned build rather than installed beta 0.1.5; test no-account local UI, delegation/message/result, rendered highlighted patch, actual host zsh checks, preference restore/count, OpenRouter and both Enterprise identities. Optional Connect account is separate from local access.
- [ ] Paseo: resolve the already-working OpenAI identity's Enterprise classification. The previously passed OpenRouter and Claude Enterprise tests remain valid evidence for their recorded setup.

No new app was installed or authenticated for the six-app addition; no previous successful runtime evidence was transferred to a different app.

## Completed in this session

- [x] Audit vendor documentation for delegation, diff viewers, licenses, free/paid features, product login and possible provider routes; preserve test versus documentation distinctions. See `capability-evidence.md`.
- [x] Audit the dotfiles. Kitty parity is no longer required; existing zsh configuration remains a requirement. See `settings-evidence.md` for the earlier historical audit.
- [x] Replace the unsupported ranking with hard gates and tie-breakers; update both HTML views with matching comparison rows and the requirements-history disclosure.
- [x] Remove the non-comparable idle-memory chart; build a benchmark scaffold that cannot claim synthetic results are comparable. See `benchmark/README.md`.
- [x] Independently check the two views against the research; correct the cmux test and OpenRouter-route language. Verify both HTML files parse and their ten comparison rows match. Run four benchmark scaffold tests.

- [x] Validate two cmux shortcuts in a temporary configuration and run its Kitty import in dry-run mode; the latter retained a different scrollback. Register a file-backed Paseo test provider in an isolated daemon using dummy credentials. See `config-provider-test-results.md`.
- [x] Test Orca terminal API launch, follow-up and output; received `ORCA_CHILD_INITIAL_OK` and `ORCA_CHILD_FOLLOWUP_OK`. Supervised child reported `ORCA_SUPERVISED_CHILD_OK` with `worker_done` succeeded in the current workspace. Cross-worktree and cross-provider delegation remain untested.
- [x] Validate host sampling on synthetic single-process CPU and sleep workloads, a deterministic PTY terminal workload, and an xctrace Activity Monitor synthetic recording. These are not application comparisons; see `benchmark/README.md`.

## Outstanding — not completed

- [ ] Run parent-child spawn, messaging and collection for each feasible product and test highlighting using the same representative patch. Orca terminal API launch, follow-up and output passed after escalation; supervised worker reported success in the current workspace. Cross-worktree and cross-provider paths remain untested; see `orca-delegation-test.md`. cmux denied an external process access to its socket; its viewer remains untested. Conductor is excluded by user decision after a signup screen was observed; login-free access was not independently disproved. See `runtime-test-evidence.md`.
- [ ] Verify each app uses the existing zsh startup files and required shell configuration, and count independent UI-only values for relevant remaining requirements. Kitty keybinding and appearance parity are no longer required.
- [ ] Exercise an OpenRouter key and the user's OpenAI and Anthropic enterprise accounts in each usable environment, including organization-specific policies; no such account-specific requests were performed. `codex login status` reported ChatGPT login but did not establish an enterprise entitlement; Claude reported no active auth in this test process. Never store credentials in artifacts.
- [ ] Complete a true 1:1 GUI benchmark: implement and validate product adapters, same isolated machine state, fixture and actual active workloads, process-lifecycle coverage, physical-memory attribution and repetitions. Single exploratory active-terminal trials have run in Orca, Paseo and cmux; see `benchmark/orca-paseo-results.md` and `benchmark/other-results.md`. They are not isolated or comparable; host sampling now works with authorized escalation, but isolated GUI app adapters, validated process coverage and matched workloads remain unavailable. Benchmark the remaining four contenders; Conductor is excluded from further trials by user decision.
- [ ] After actual tests, determine whether any app passes every hard gate and only then rank qualified apps on the requested extra-credit criteria.
- [ ] Refresh `ade-comparison-social.png` after Conductor was excluded; the previous social image and Firefox screenshots are stale.
- [x] Inspect both views in a real browser at 390, 768 and 1400px; verify the requirements disclosure and two-app selector. Both tables have a visible horizontal-scroll cue at narrow widths. The current resource table also passed the desktop and mobile browser layout check; no outer-page overflow was observed.

- [ ] Herdr desktop is open with a visible zsh terminal, confirmed 11 November 2026. Its test terminal still needs safe automation and isolation. The earlier TUI fallback was blocked; see `benchmark/other-results.md`.

- [x] Exclude Conductor from contention and both comparison views at the user’s direction after its sign-up barrier was observed. Its login-free path was not independently disproved.

- [x] Revalidated both four-app views at 390, 768 and 1400px, tested the requirements toggle and comparison selectors, and refreshed `ade-comparison-social.png`.

## Four-app controlled benchmark — latest attempt

- [x] Built phase-aligned workload, monitor and audit tools. Sixteen tests pass; prior exploratory records lack absolute phase timestamps and cannot be retroactively aligned. See `benchmark/phase-alignment.md`.
- [ ] Provision and verify native isolation before measured trials. A separate macOS user needs an administrator password; no macOS VM manager or existing image was found. Apple Virtualization.framework reported support, but its restore-image catalog lookup failed. See `benchmark/isolation-evidence.md`.
- [ ] Validate Herdr desktop test-tab visibility and process coverage; its shared core is serving existing terminals. Do not treat shared-instance measurements as an isolated benchmark.
- [ ] Run the 12 randomized idle/active trials only after isolation, process coverage, zsh checks and visibility are verified. No phase-aligned ADE trials have run yet.

- [x] A temporary Herdr core terminal passed interactive/login zsh, gs alias, gro function and brew checks. Desktop visibility was not confirmed and its core daemon was shared; no isolated GUI measurement resulted. See `benchmark/herdr-readiness.md`.

- [x] Confirmed interactive/login zsh plus alias, function and Homebrew checks in a temporary Herdr core terminal; it was removed and did not appear in desktop GUI. See `benchmark/herdr-readiness.md`.
- [x] Refreshed the social image after the Herdr evidence update and checked both views at 390, 768 and 1400 px with working controls.

## Offline VM trial attempt

- [x] Created task-owned offline macOS VM and staged four app bundles, tracked zsh startup and non-secret dependencies. No host account or group was changed; guest SIP is disabled in the downloaded prebuilt image. Host credentials and private local zsh config were not shared.
- [x] Orca VM diagnostic v2 completed 480/480 parser acknowledgements at natural 99×56; one frame was visually observed. Raw result: `benchmark/guest-share/results/orca-preflight-diagnostic-v2`. This is non-comparable: process coverage and equal viewports not established, one trial only. It is not comparable to prior host v1 measurements.
- [x] Resumed after the prior VM-control interruption: Orca stopped and fresh Herdr and Paseo diagnostics completed; the later status and remaining work are recorded below.
- [x] Replaced the earlier host samples with clearly labelled VM diagnostics; see current status below.

## Offline VM diagnostics — continuation

- [x] Task-owned Orca, Herdr and Paseo guests each completed one v2 terminal diagnostic. Matching 480/480 parser acknowledgements, 748,320 bytes, payload SHA-256 `3ddf4a73d77fd12c2d7b112f245fc36e728dda8c82c332a879f896f7b8f36b54`, and matching recomputed active audit fields verified. Viewports: Orca 99×56, Herdr 120×37, Paseo 124×52.
- [x] Both comparison views show the new guest diagnostics rather than the earlier host samples, with explicit non-comparability and zsh caveats.
- [x] The temporary cmux guest was stopped; isolated `tart list` confirms all task-owned VMs currently stopped.
- [ ] cmux diagnostic: unified CUA native pipe startup failed, and the outside guest CLI was rejected by cmux's socket (`only processes started inside cmux can connect`). No socket security bypass was attempted. Computer-use availability and a legitimate in-app control path are required to continue.
- [ ] Strict repeated four-app 1:1 test: establish equal visible viewports, validate complete process/lifecycle coverage and memory attribution, address omitted private zsh state, and run independent fresh repeated trials. Paseo painting was not verified during workload; single Orca and Herdr frames were observed.
- [x] Refreshed social PNG and browser-validated both updated views at 390, 768 and 1400 pixels; disclosure and comparison selectors passed.

## Paseo winner qualification

- [x] Real Claude Enterprise request through Paseo passed; real existing OpenAI account request passed. Both test agents and dedicated workspace archived. See `paseo-provider-qualification.md`.
- [x] Actual host Paseo terminal passed named zsh aliases/functions, tools, exports and detected private local declarations; default non-login shell and explicit working login remedy recorded. See `paseo-zsh-qualification.md`.
- [x] Current renderer and desktop preferences match defaults: 0 non-default independent UI values for current setup. Four test desktop values restored in isolated profiles. General future renderer preference export remains unproven. See `paseo-config-qualification.md`.
- [x] User supplied a disposable key; a real request through isolated Paseo/OpenCode/OpenRouter passed. Actual assistant response verified; daemon/helpers stopped and key-bearing-file scan returned zero. See `paseo-openrouter-result.json`.
- [ ] Confirm the intended OpenAI enterprise profile: working current account is classified `ent26`, not safely mapped to explicit Enterprise. User clarification requested.
- [x] Updated both report views to replace the generic warning with these two remaining checks; refreshed social PNG and checked layout/controls at 390, 768 and 1400 pixels.

- [x] Paseo report now has one remaining qualification check: intended OpenAI Enterprise identity classification.
