"""Reproduce the observed harmless GUI edit after probe.py init/focus.

This replay source records the exact command sequence used interactively; it was
not run as one unit. Pass the current task-owned app PID and terminal window ID.
"""
import json
import subprocess
import sys

pid, window_id = sys.argv[1:]
assert pid.isdecimal() and window_id.isdecimal()


def guarded_action(verb, flag, value):
    subprocess.check_call([
        "osascript", "-e", 'tell application "System Events" to set frontmost of '
        f'first application process whose unix id is {pid} to true'
    ])
    frontmost = subprocess.check_output([
        "osascript", "-e", 'tell application "System Events" to get unix id of '
        'first application process whose frontmost is true'
    ], text=True).strip()
    if frontmost != pid:
        raise RuntimeError("Stop: target app is not independently verified frontmost")
    raw = subprocess.check_output([
        "orca", "computer", verb, "--app", f"pid:{pid}", "--window-id", window_id,
        flag, value, "--restore-window", "--json"
    ], text=True)
    result = json.loads(raw[raw.index("{"):])
    if not result.get("ok"):
        raise RuntimeError(result.get("error"))
    print(json.dumps(result))
    # Inspect the fresh screenshot after each step. A provider acknowledgement
    # alone is unverified; terminal marker readback is the success assertion.


guarded_action("paste-text", "--text", "print -r -- CONTROL_OLD")
guarded_action("press-key", "--key", "Return")
guarded_action("paste-text", "--text", "print -r -- EDIT_OLD")
guarded_action("hotkey", "--key", "Alt+Left")
guarded_action("hotkey", "--key", "Ctrl+K")
guarded_action("paste-text", "--text", "EDIT_NEW")
guarded_action("press-key", "--key", "Return")
