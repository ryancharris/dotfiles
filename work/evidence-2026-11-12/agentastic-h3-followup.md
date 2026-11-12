# Agentastic H3 follow-up — 12 November 2026

**Result: configured keybinding/input behaviour remains unverified.** A representative attempt was made with pinned Agentastic.dev **0.16.2**, build **4890**, launched from its cached image. No permanent installation or agent session was created. All task-created known application data was removed afterward.

## Existing proof and remaining scope

The previous hands-on test established a login, interactive zsh, the user’s rc alias, PATH and rendered prompt. It did not exercise a configured bound key against editable terminal input. The user’s existing `.zshrc` explicitly binds the Alt-Left sequence `ESC[1;3D` to `backward-word`. Neither the binding declaration nor printing `bindkey` establishes that the application delivers the input correctly.

## Pinned release and baseline

Homebrew retained `Agentastic.dev-0.16.2.dmg` (342,890,492 bytes), SHA-256 `51c8a85dd13111585a3472580d380174ff74e91479ace2df32f071cc58e904be`. Read-only inspection of Info.plist confirmed version 0.16.2/build 4890 and bundle ID `dev.agentastic.Agentastic`.

Before launch, the app’s Application Support root, `.agentastic`, preferences plist, two known cache roots and HTTPStorages root were confirmed absent. The pre-existing protected OpenWithCodeEdit container remained present and was excluded from cleanup. No undocumented app-profile isolation switch was used; previously absent application data was temporarily recreated under the original test-and-cleanup authorization.

## Representative input attempt

A task-owned terminal was created in a disposable repository using the bundled `dev` CLI. The intended harmless test was to insert `print -r -- OLD`, deliver the configured Alt-Left input, insert `H3_`, then submit; successful word movement would produce exactly `H3_OLD`.

The `agent.send` API submitted each text call immediately despite `newline: false`. The terminal returned `OLD` before the editing step, then treated subsequent text as separate input. This attempt does **not** establish an application keybinding failure or success: the automation route could not preserve an editable line.

The terminal was then revealed through `terminal.focus` and inspected using the Orca computer-use skill. Its native terminal view was visible, but a targeted click returned no focused text receiver in the accessibility state. No blind typing or unverified key chord was counted as proof. No screenshot is retained because the shell prompt contained unrelated user/account context.

**Remaining blocker:** a verified native terminal input receiver, or a documented raw-input API that does not auto-submit. H3 keybindings remain partial/unverified; no passing claim follows from this follow-up.

## Verified cleanup

The task app PID and its descendants were stopped. A process-list recheck found **zero Agentastic processes**. All previously absent known application data roots were removed; a filesystem recheck found **zero known new roots remaining**. Task-created terminal shim/pid files were removed, and the read-only image was detached. The protected pre-existing container was left untouched, the cached download was retained, and no global startup or agent config was changed.
