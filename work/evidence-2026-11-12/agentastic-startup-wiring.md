# Agentastic actual shell/startup forwarding — 12 November 2026

**The default new terminal uses the configured `/bin/zsh` and forwards the user's login startup files.** This closes the ZDOTDIR-shim consistency check accompanying the earlier actual mapped-key test. It is based on the observed application process tree, runtime loader flags, actual generated shim contents and the pinned bundle's primary code—not an inherited `$SHELL` value.

Pinned release: Agentastic.dev **0.16.2**, build **4890**, from the same cached DMG SHA-256 recorded in `agentastic-validation-h3.md`. A fresh task-owned app (PID 38757) created a new default terminal with `dev newtab`; no startup configuration or undocumented setting was changed.

## Executable and runtime receipts

`agentastic-startup-wiring.json` retains the observed process tree:

```text
Agentastic.dev (38757) → /usr/bin/login (38955) → /bin/zsh (38959)
```

The independent macOS UserShell record is `/bin/zsh`, matching the actual child executable. The same terminal returned exact boolean markers for login, interactive, the actual user startup root, readable generated `.zprofile` and `.zshrc`, and active shell integration injection. All six were true. The user's `.zprofile` and `.zshrc` are both present and readable; absent optional startup files are recorded as absent rather than claimed executed.

## Actual generated loader wiring

The running app shell supplied its actual `AG_ZDOTDIR` loader directory. All four actual generated files were read and compared byte-for-byte with the corresponding resources in pinned 0.16.2. Every comparison passed, with both hashes retained in the JSON receipt. Small relevant excerpts are retained in `agentastic-startup-loader-excerpts.txt`; exact bundle resource names, original line ranges and full-resource hashes are in `agentastic-startup-bundle-sources.json`. Full resource copies are retained locally outside the repository.

- `.zprofile`: for a login shell with a readable user `.zprofile`, saves the generated ZDOTDIR, changes ZDOTDIR to `USER_ZDOTDIR`, **sources `$USER_ZDOTDIR/.zprofile`**, then restores the generated ZDOTDIR.
- `.zshrc`: with injection active, changes ZDOTDIR to the user root and **sources `$USER_ZDOTDIR/.zshrc`**. Its history-file handling also respects the user's startup file.
- `.zshenv`: forwards a readable user `.zshenv`, with a recursion guard and support for user ZDOTDIR changes. The user has no `.zshenv` here, so none is claimed executed.
- `.zlogin`: restores user ZDOTDIR and forwards a readable user `.zlogin` for login shells.

The actual shell is login zsh, the runtime user root is correct, the generated `.zprofile` is the exact pinned forwarding code, and its user-file existence/readability conditions are true. This establishes the loader path through the user's `.zprofile`, beyond merely observing `login=true`. No private startup contents or environment values were retained. This is primary loader wiring plus actual runtime-condition proof, not an execution trace of every statement inside the user's rc files.

`agentastic-startup-probe.py` retains the shell receipt command and collection procedure used interactively; the combined replay source was not rerun as one unit. The earlier `agentastic-validation-*` artifacts remain the separate actual native key-event proof.

## Cleanup

The app and both shell-process descendants were stopped, the cached image was detached, and the fixture plus temporary receipt files were removed. `agentastic-startup-cleanup.json` records zero Agentastic processes and zero known new application data roots.

Inspection also identified the generated temporary `ryan-codeedit-zsh` directory left from the original authorized Agentastic test. Its creation timestamp was 12 Nov 10:07:59, the original app baseline contained neither CodeEdit nor Agentastic, and its contents matched the pinned Agentastic resources. That attributable test shim was removed too. The pre-existing protected OpenWithCodeEdit container was preserved. No global shell/agent configuration or normal CLI transcript was restored or removed.
