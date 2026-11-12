# Sheprd H3 follow-up — 12 November 2026

**Result: Partial.** Existing pinned release 20261109.1 was reused without a download or install; its tarball SHA-256 matches the previously verified release. The test used disposable XDG directories, a separate `HC_SOCKET` and the bundled core. No provider session or baseline core was targeted.

The actual GUI fallback terminal again passed real HOME/default ZDOTDIR, the named alias and function, seven tool lookups, seven exported-variable presence checks, both startup-file symlink checks and all six detected private declarations. It was interactive zsh but non-login. These boolean/count results do not prove `.zprofile` execution, every startup side effect or all possible private declarations.

The pinned app's generated settings and first-party config interface supplied no verified persistent GUI login-shell launch choice. Its `new_core_terminal` source path constructs the default spawn with no explicit login argument. The earlier `exec zsh -l` remedy does not establish a saved default for a new GUI terminal. No standalone login-shell child was counted as a pass. Startup qualification therefore remains incomplete.

For input, the configured keymap maps Ctrl+A to beginning-of-line and Ctrl+K to kill-line. A harmless marker typed through the GUI reached the owned terminal. Background GUI modifier/Return events produced no observable change, so they are **not** claimed as a GUI keyboard pass. Sending actual Ctrl+A/Ctrl+K events through the bundled first-party core erased the marker; a subsequent harmless print command produced the expected output. This proves those shell editing bindings through the core input path, with the GUI modifier path still unverified. No foreground takeover was attempted.

Cleanup returned success for the isolated app quit and core stop, the held app process exited 0, and the task-owned profile was removed. The pre-existing verified app bundle remains in its earlier temporary location. Only [sanitized booleans/counts](sheprd-h3-followup.json) are retained; screenshots, private prompt text, raw histories and environment values are not copied here.
