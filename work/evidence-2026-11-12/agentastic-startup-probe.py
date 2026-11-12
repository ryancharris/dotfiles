"""Reproduce the startup wiring receipt in an owned Agentastic terminal.

The shell command and collection were executed interactively during validation;
this combined replay source was retained afterward, not rerun as a single unit.
Usage: python3 agentastic-startup-probe.py APP_PID TERMINAL_ID
"""
import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

app_pid, terminal_id = sys.argv[1:]
assert app_pid.isdecimal()
socket_path = Path.home() / ".agentastic/sockets" / f"agentastic-{app_pid}.sock"


def rpc(method, params):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(str(socket_path))
        connection.sendall((json.dumps({"id": str(uuid.uuid4()), "method": method,
                                        "params": params}) + "\n").encode())
        data = b""
        while b"\n" not in data:
            data += connection.recv(65536)
    response = json.loads(data.split(b"\n")[0])
    if not response.get("ok"):
        raise RuntimeError(response.get("error"))
    return response["result"]


receipt = Path(tempfile.gettempdir()) / f"agentastic-startup-{app_pid}.txt"
command = (
    f'print -r -- "$AG_ZDOTDIR" > {receipt}; '
    '[[ -o login ]] && print AS_LOGIN_TRUE; '
    '[[ -o interactive ]] && print AS_INTERACTIVE_TRUE; '
    '[[ "$USER_ZDOTDIR" == /Users/ryan ]] && print AS_USER_ROOT_TRUE; '
    '[[ -r "$AG_ZDOTDIR/.zprofile" ]] && print AS_PROFILE_SHIM_TRUE; '
    '[[ -r "$AG_ZDOTDIR/.zshrc" ]] && print AS_RC_SHIM_TRUE; '
    '[[ -n "$AG_INJECTION" ]] && print AS_INJECTION_TRUE'
)
rpc("agent.send", {"terminal_id": terminal_id, "text": command,
                   "newline": True, "also_inbox": False})
for _ in range(50):
    if receipt.exists():
        break
    time.sleep(0.1)
else:
    raise RuntimeError("No startup path receipt; do not infer a pass")
root = Path(receipt.read_text().strip())
hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
          for name in [".zshenv", ".zprofile", ".zshrc", ".zlogin"]}
lines = rpc("terminal.tail", {"terminal_id": terminal_id, "lines": 30})["lines"]
markers = ["AS_LOGIN_TRUE", "AS_INTERACTIVE_TRUE", "AS_USER_ROOT_TRUE",
           "AS_PROFILE_SHIM_TRUE", "AS_RC_SHIM_TRUE", "AS_INJECTION_TRUE"]
print(json.dumps({"markers": {name: any(line.strip() == name for line in lines)
                                     for name in markers},
                  "actual_generated_shim_sha256": hashes}, indent=2))
# Actual executable evidence must separately use the app's descendant process
# tree and the configured UserShell record; inherited $SHELL is insufficient.
receipt.unlink()
