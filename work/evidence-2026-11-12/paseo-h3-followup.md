# Paseo H3 follow-up — 12 November 2026

**PASS, scoped to a saved alternate login-shell profile and representative user keybindings.** This closes the previous manual `exec zsh -l` remedy with a new terminal launched directly from a persistent profile. The default terminal remains non-login; the live profile and installed app were unchanged.

## Route and setup

Used installed Paseo **0.15.4**, a new daemon home under `/private/tmp/ade-paseo-h3-20261112/home`, loopback port **6819**, and the real HOME. Its `config.json` saved `daemon.terminalProfiles` with command `/bin/zsh` and args `["-l"]`. `dscl` independently confirmed that `/bin/zsh` is the user's configured shell executable. No startup file was edited.

The daemon was launched by the installed `paseo daemon start --home` command. The shipped client SDK fetched the saved daemon configuration, resolved its profile with the shipped `resolveTerminalProfileLaunch`, and created a **new** application-managed terminal with that command and arguments. This tests the persisted profile plus first-party terminal API route; the terminal was not converted by typing `exec` after launch. A fresh workspace contained only the owned test terminal.

## Observed checks

- Interactive and login options were true; real HOME and default ZDOTDIR matched.
- Existing `gs` alias and `gro` function, seven named tools, seven tracked exported variables, tracked rc-file links, and all six detected private local declarations passed the retained checker from `../paseo-zsh-test/check.zsh`.
- Homebrew's expected prefix was present. Normal zsh login semantics apply to this new terminal; startup file reads were not instrumented, and no private values were logged.
- The user's existing `ESC [ 1 ; 3 D` and `ESC [ 1 ; 3 C` mappings resolved to `backward-word` and `forward-word`.
- Two independent harmless edit probes exercised those mappings through the real terminal input API. Backward-word inserted a marker before the final word; backward-word followed by forward-word appended a suffix after that word. Each command printed its exact expected result. A missing or incorrect mapping would produce a different result.

Only boolean/count results are retained in `paseo-h3-followup.json`. Commands began with a space under the user's existing history policy; the checker unset HISTFILE and SHARE_HISTORY before the input probes.

## Scope and cleanup

This qualifies the saved alternate profile, rather than claiming the **default** terminal is a login shell. The input tests exercise PTY input and actual shell ZLE bindings; desktop physical-key / browser-event translation was not tested. No guarantee is made for every user binding, startup side effect, or provider's noninteractive subprocess environment.

Both owned terminals from the two completed probe runs were killed; their shared test workspace was archived after each run. The isolated daemon stop returned `action: stopped`, `forced: false`; its temporary daemon home and fixture were removed. No existing daemon, terminal, provider session, global preference or app installation was targeted. One setup attempt stopped before terminal creation because of an SDK namespace mistake; the corrected run and final independent input probes succeeded. Sandboxed access hit `uv_uptime` EPERM and the recorded runtime tests used authorized host execution.
