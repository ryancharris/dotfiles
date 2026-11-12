# Agentastic actual H3 validation — 12 November 2026

**Pass for the tested configured shell/input scope.** Pinned Agentastic.dev **0.16.2**, build **4890**, delivered the user's configured Alt-Left word movement to an actual newly created login zsh terminal. A discriminating live input edit returned the exact expected output. This supersedes the earlier key-input-unverified result in `agentastic-h3-followup.md`; that earlier automation attempt remains historical evidence.

## Release and startup

The cached official release DMG was mounted read-only, without permanent installation. Its SHA-256 is `51c8a85dd13111585a3472580d380174ff74e91479ace2df32f071cc58e904be`; Info.plist identifies 0.16.2/build 4890. The task-owned app PID was 21150. The app's default terminal creation route (`dev newtab`) created a new shell, with no terminal setting changes.

`agentastic-validation-startup.json` retains boolean-only receipts: login shell, interactive shell, the existing `gbd` rc alias, nonempty prompt, and the existing `ESC[1;3D` → `backward-word` binding were all true. Earlier retained hands-on evidence establishes PATH and the original rendered user prompt. For this input test only, the prompt and precmd callbacks were replaced in the disposable shell with `AGH3> ` so screenshots contain no private prompt/account context. No startup file or global configuration was edited.

## Actual input test

The bundled terminal API created and revealed terminal `2B646054-2731-4F53-A68A-CA43B58FB4B4` in a disposable repository. The visible native terminal had a cursor at the neutral prompt and returned `AGH3_RECEIVER_READY`. Foreground paste then produced an **unsent, editable command line** visible in the target window, establishing a real input receiver despite the terminal's absent accessibility text field.

The exact target process was activated by PID using System Events. An independent query of the frontmost application's Unix PID returned **21150**, matching the task terminal owner before the configured edit. Orca's foreground action receipts identify target window **96666**, foreground delivery, and the respective paste/hotkey/pressKey actions. Their own verification flags are unverified synthetic/clipboard input; the passing assertion comes from the separately observed screen changes and terminal output, not those acknowledgements.

1. Control: paste `print -r -- CONTROL_OLD`, then Return. The terminal printed the standalone line **`CONTROL_OLD`**.
2. Paste `print -r -- EDIT_OLD` without Return. The fresh screenshot showed the unsent line.
3. Send **Alt-Left** through `orca computer hotkey`. A fresh screenshot showed the block cursor on the initial `E` of `EDIT_OLD`, establishing word movement on the editable line.
4. Send **Ctrl-K** to kill the suffix. The old input disappeared; zsh displayed a gray history autosuggestion from the control command, which was not submitted.
5. Paste `EDIT_NEW`, then Return. The terminal printed the standalone line **`EDIT_NEW`**; it did not print `EDIT_OLD`.

This discriminates the mapped movement from merely typing a replacement at the end: without Alt-Left, Ctrl-K at line end would remove nothing and appending the replacement would yield `EDIT_OLDEDIT_NEW`. The observed output was exactly `EDIT_NEW`.

`agentastic-validation-input.json` retains exact marker-match results. The same terminal's output was read back through the app's own `terminal.tail` API; screenshots independently show both control and edited output. No agent/model request was used.

## Retained evidence and reproduction

- `agentastic-validation-probe.py` was actually executed for initialization, focus, and marker readback. It only exposes known markers/booleans.
- `agentastic-validation-ui-replay.py` records the exact GUI command sequence used interactively and guards the app's frontmost PID; it was not run as one unit.
- `agentastic-validation-before-edit.png`, `agentastic-validation-word-start.png`, `agentastic-validation-after-kill.png`, and `agentastic-validation-after-edit.png` preserve the relevant neutral terminal region.
- `agentastic-validation-provenance.json` records each original `orca computer` screenshot capture ID, original SHA-256 and dimensions, crop bounds, crop SHA-256, target window ID and foreground delivery. Only a crop operation was applied; screenshot content was not retouched.

## Harness limits and consent audit

Earlier CUA typing failed with `noWindowsAvailable`. Initial Orca keyboard actions also encountered target/foreground mismatch. Another test app briefly held foreground, and `open -a` created a task-owned AppTranslocation duplicate (PID 24042) rather than activating the original instance. These are recorded as automation/instance-selection conditions, not app keybinding failures. Exact-PID activation resolved them. Both task instances were cleaned up.

The config hash request arrived after launch. `agentastic-validation-config-consent.json` therefore compares only **post-launch/pre-input → post-input**. One external file, `.claude.json`, changed during concurrent tests; the writer is unresolved. No other compared external rc/agent configuration changed. No file was restored or attributed to Agentastic without evidence. This follow-up does not replace the earlier H7 baseline audit.

## Cleanup

Both task-owned Agentastic instances and their descendants were stopped. `agentastic-validation-cleanup.json` records **zero remaining Agentastic processes** and **zero known new application data roots**. All baseline-absent known app roots and task terminal shim/pid files were removed; the existing protected OpenWithCodeEdit container was preserved. The image was detached and the temporary repository/probe state was removed. No external agent configuration or normal CLI transcript was deleted or restored.
