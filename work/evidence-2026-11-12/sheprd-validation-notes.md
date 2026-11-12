# Sheprd validation — configured core route

**PASS for the recorded route:** Sheprd 20261109.1 with an already installed herdr-core 0.1.18, started on a separate test socket, and a saved login-shell choice. **The bundled core 0.1.13 has an observed startup limitation.** The passing result does not describe a fresh launch using only the bundle.

## What actually passed

The pinned app connected to the owned core and created a new visible terminal tab through `sheprd run new_core_terminal`. Its own tab listing reported that tab; the owned core's terminal count increased from one to two. No shell was replaced with `exec zsh -l` after launch, and no unrelated login-shell subprocess was counted as the terminal.

In that same new terminal:

- The configured `/bin/zsh` was interactive and in login mode with startup processing enabled. Source-trace output confirmed reads of the actual `.zprofile`, `.zshrc` and `.zshrc.local`; only those match booleans are retained.
- The named alias/function, seven tools, seven exported variables and all six detected private declarations passed. The user's prompt was present before the probe replaced it with a neutral prompt for output parsing.
- The configured Ctrl+A/Ctrl+K mappings were checked, then real key events through the first-party core erased a harmless unsubmitted marker. The subsequent print command produced its expected output. This establishes the representative core input path; it does not claim physical desktop modifier-event coverage.

The app's native Claude chat attached and showed. That parent started child `t4` (`sv-child`), whose recorded parent was `t3`; the child exited 0, and the parent waited for and read its output. The child marker was observed in that output. The exact final parent marker was then verified from an **assistant-role record in this new test session**, not from a prompt echo. The user's existing Stop hook wrapped the child output in prose, so one follow-up clarified that observing the marker inside the wrapper was sufficient. One inspected permission for `herdr-core wait sv-child` was allowed once; no general Bash permission was added.

An independent [guarded startup-only rerun](sheprd-validation-startup-guards.json) retained the actual address-set delta: the app had `t1` before its new-terminal action, and that action added only `t2`. All ten guards passed, including every required startup/export/tool/private-declaration check and the actual input edit. In that same tab, a raw `claude` launch displayed the provider's TUI chrome; process metadata confirmed a Claude process with no structured/headless flags. No inference prompt was sent and no trust prompt appeared. The raw TUI was cancelled. All 13 external config/startup comparisons remained unchanged in this rerun.

The original full-run script's ownership flag was a vacuous check and its pass predicate did not cover every recorded observation. Those historical values are not used as ownership proof. The corrected script uses the real set delta and exhaustive startup/input/child guards; the separate startup-only rerun validates the corrected ownership and startup guards without repeating model calls. The full-run native-chat and child receipts remain independent actual observations.

See [the final sanitized full-run result](sheprd-validation-final.json). The [earlier bundled attempt](sheprd-validation-runtime.json) and [intermediate installed-core attempt](sheprd-validation-systemcore.json) retain their harness limitations; neither is substituted for the corrected final run.

## Required setup and version boundary

The supported core setting is saved in `~/.config/herdr-core/config.toml` (or the corresponding `XDG_CONFIG_HOME` directory):

```toml
shell = ["/bin/zsh", "-l"]
```

The validation added `"-o", "sourcetrace"` to that array to observe startup-file reads without logging their contents. It wrote this configuration only in an isolated profile. Start the installed core before Sheprd so the app joins that existing core; this test used separate `HC_SOCKET`, `HC_SESSION` and XDG directories. It did not replace the bundled executable or target the user's running daemon.

The actual tested app joined the pre-started isolated core, created its terminal and completed the native-chat/child test; those runtime receipts establish this route. Later upstream code corroborates it: [the core connector](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-gpui/src/core_terminals/hub.rs) first joins the resolved existing socket, and [the endpoint resolver](https://github.com/sheprd-labs/sheprd/blob/30b97d174f0421307c137701ab9442b43c7a9448/crates/sheprd-core-client/src/endpoint.rs) supports `HC_SOCKET` and isolated session/config roots. Commit `30b97d1` is later than the 9 November tested release and is **corroboration, not release-matched source proof**. The test explicitly pre-started the newer installed binary and does not establish automatic selection of that binary by a fresh app launch.

The [core 0.1.18 documentation](https://github.com/herdrdev/herdr-core/blob/v0.1.18/README.md#default-shell) and [configuration code](https://github.com/herdrdev/herdr-core/blob/v0.1.18/crates/herdr-core/src/config.rs) describe the saved shell argv. The [core changelog](https://github.com/herdrdev/herdr-core/blob/v0.1.20/CHANGELOG.md) places the macOS login-shell fix in 0.1.15 and configurable shell argv in 0.1.16. Runtime testing matched that boundary: the bundled 0.1.13 ignored the newer setting and its new app terminal stayed non-login; 0.1.18 honored it and source tracing established the actual startup reads.

## Reproduce and cleanup

[The self-contained probe](sheprd-validation-run.py) reuses existing app/core binaries and creates only disposable test configuration. Coordinate foreground ownership before running it because launching the native app can take focus. Inspect any native-chat permission prompts and allow only the task-owned core run/wait/read operations. Add `--startup-only` to repeat startup, input and raw-TUI checks without any model request; it writes a separate result and preserves the full-run receipts.

```sh
python3 work/evidence-2026-11-12/sheprd-validation-run.py \
  --bundle /private/tmp/sheprd-config-test-release/Sheprd.app \
  --core "$HOME/.local/bin/herdr-core"
```

No software was downloaded, installed or updated. Before the native agent started, SHA-256 comparisons showed all 13 checked agent-config/startup paths unchanged. After the native-chat/child run, `.claude.json` alone differed; only hashes were compared, so changed-field categories and the precise writer were not captured. The change occurred during the agent-CLI phase and was not attributed or reverted. No project-trust entries for the two named test roots remained. Digests, account data, private prompt text and raw transcripts are not published.

The owned app exited 0, its core stop succeeded and its temporary profile was removed. Normal agent session transcripts remain in the user's existing CLI history. The pre-existing app bundle, installed core executable and baseline daemons were left in place.
