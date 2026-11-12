"""Sanitized Agentastic 0.16.2 terminal probe; GUI key steps are in the report."""
import json
import re
import socket
import sys
import uuid

app_pid, terminal_id, action = sys.argv[1:]
socket_path = f"/Users/ryan/.agentastic/sockets/agentastic-{app_pid}.sock"


def rpc(method, params):
    payload = {"id": str(uuid.uuid4()), "method": method, "params": params}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(socket_path)
        connection.sendall((json.dumps(payload) + "\n").encode())
        data = b""
        while b"\n" not in data:
            data += connection.recv(65536)
    response = json.loads(data.split(b"\n")[0])
    if not response.get("ok"):
        raise RuntimeError(response.get("error"))
    return response.get("result")


if action == "init":
    # Boolean shell receipts precede a session-only neutral prompt for private screenshots.
    command = (
        "clear; [[ -o login ]] && print AGH3_LOGIN_TRUE; "
        "[[ -o interactive ]] && print AGH3_INTERACTIVE_TRUE; "
        "(( $+aliases[gbd] )) && print AGH3_RC_ALIAS_TRUE; "
        "[[ -n $PROMPT ]] && print AGH3_PROMPT_PRESENT_TRUE; "
        "[[ $(bindkey '^[[1;3D') == *backward-word* ]] && print AGH3_BINDING_TRUE; "
        "precmd_functions=(); PROMPT='AGH3> '; RPROMPT=''; "
        "print AGH3_RECEIVER_READY"
    )
    print(json.dumps(rpc("agent.send", {"terminal_id": terminal_id, "text": command,
                                      "newline": True, "also_inbox": False})))
elif action == "focus":
    print(json.dumps(rpc("terminal.focus", {"terminal_id": terminal_id, "focus": True})))
elif action == "read":
    result = rpc("terminal.tail", {"terminal_id": terminal_id, "lines": 80})
    clean = [re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line).strip()
             for line in result.get("lines", [])]
    markers = ["AGH3_LOGIN_TRUE", "AGH3_INTERACTIVE_TRUE", "AGH3_RC_ALIAS_TRUE",
               "AGH3_PROMPT_PRESENT_TRUE", "AGH3_BINDING_TRUE", "AGH3_RECEIVER_READY",
               "CONTROL_OLD", "CONTROL_NEW", "EDIT_OLD", "EDIT_NEW"]
    print(json.dumps({marker: marker in clean for marker in markers}, indent=2))
else:
    raise SystemExit("Choose init, focus or read")
