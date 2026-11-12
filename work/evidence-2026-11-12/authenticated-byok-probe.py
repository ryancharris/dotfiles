"""Prepared OpenCode 2.2.5/OpenRouter probe; --execute and an inherited key are required.

Run inside the ADE-owned terminal whose route is being qualified. This script
does not establish the hosting app identity; retain that terminal's launch receipt.
No raw model output, credentials, or credential-bearing config is retained.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile


DENY = [{"action": "*", "resource": "*", "effect": "deny"}]


def probe_config(model):
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": model,
        "update": "disable",
        "snapshots": False,
        "compaction": {"auto": False},
        "default_agent": "byok-probe",
        "permissions": DENY,
        "agents": {
            "byok-probe": {
                "description": "One response connectivity probe without tools",
                "mode": "primary",
                "system": "Return only the exact marker supplied in the user prompt.",
                "permissions": DENY,
                "steps": 1,
            },
            "title": {"disabled": True},
            "summary": {"disabled": True},
        },
        "providers": {
            "openrouter": {"settings": {"apiKey": "{env:OPENROUTER_API_KEY}"}}
        },
    }


def parse_response(stdout, marker):
    """Read the pinned CLI's completed assistant-text events, never arbitrary strings."""
    texts, seen_parts, sessions, messages, types = [], set(), set(), set(), {}
    tool_events = error_events = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if not isinstance(kind, str):
            continue
        types[kind] = types.get(kind, 0) + 1
        tool_events += kind == "tool_use"
        error_events += kind == "error"
        part = event.get("part")
        if kind != "text" or not isinstance(part, dict):
            continue
        if part.get("type") != "text" or part.get("synthetic"):
            continue
        if not isinstance(part.get("text"), str):
            continue
        if not part.get("messageID") or not part.get("id"):
            continue
        if not isinstance(part.get("time"), dict) or not part["time"].get("end"):
            continue
        if not event.get("sessionID"):
            continue
        if part["id"] in seen_parts:
            continue
        seen_parts.add(part["id"])
        sessions.add(event["sessionID"])
        messages.add(part["messageID"])
        texts.append(part["text"])
    matched = (
        bool(types.get("step_start"))
        and len(sessions) == len(messages) == 1
        and "".join(texts).strip() == marker
    )
    return {
        "event_counts": types,
        "completed_assistant_text_parts": len(texts),
        "assistant_response_matches": bool(matched),
        "tool_events": tool_events,
        "error_events": error_events,
        "step_finish_observed": bool(types.get("step_finish")),
    }


def terminate_owned_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marker", required=True)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--app-route", required=True,
                        help="Caller label; the separate ADE terminal receipt establishes context")
    parser.add_argument("--opencode", default="opencode")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{7,95}", args.marker):
        parser.error("marker must be 8-96 uppercase letters, digits or underscores")
    if not re.fullmatch(r"openrouter/[A-Za-z0-9._:/#-]+", args.model):
        parser.error("model must explicitly select the openrouter provider")
    result = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "claimed_app_route": args.app_route,
        "app_route_requires_separate_terminal_receipt": True,
        "model": args.model,
        "marker": args.marker,
        "executed": False,
        "passed": False,
        "key_source": "inherited OPENROUTER_API_KEY only",
        "key_in_arguments_or_config": False,
        "tools_policy": "V2 global and selected-agent deny-all; selected agent steps=1",
        "raw_output_retained": False,
    }
    key = os.environ.get("OPENROUTER_API_KEY", "")
    result["key_present"] = bool(key)
    if not args.execute:
        result["outcome"] = "prepared_only_not_executed"
    elif not key:
        result["outcome"] = "missing_inherited_key"
    else:
        with tempfile.TemporaryDirectory(prefix="ade-byok-", dir="/private/tmp") as folder:
            root = Path(folder)
            child_env = dict(os.environ)
            # Do not attach to an existing server or inherit per-run OpenCode overrides.
            for name in list(child_env):
                if name.startswith("OPENCODE_"):
                    child_env.pop(name)
            for name in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
                         "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
                         "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "OPENROUTER_BASE_URL"]:
                child_env.pop(name, None)
            for name, leaf in [("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                               ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state")]:
                path = root / leaf
                path.mkdir()
                child_env[name] = str(path)
            config_dir = root / "config" / "opencode"
            config_dir.mkdir()
            (config_dir / "opencode.json").write_text(json.dumps(probe_config(args.model)))
            fixture = root / "fixture"
            fixture.mkdir()
            process = None
            try:
                version = subprocess.run([args.opencode, "--version"], cwd=fixture,
                                         env=child_env, capture_output=True, timeout=15)
                result["installed_version_matches_recipe"] = bool(
                    re.search(rb"\b(?:v)?2\.2\.5\b", version.stdout)
                ) and version.returncode == 0
                if not result["installed_version_matches_recipe"]:
                    result["outcome"] = "unsupported_cli_version"
                else:
                    command = [args.opencode, "--standalone", "run", "--format", "json",
                               "--agent", "byok-probe", "--model", args.model,
                               "Reply with exactly: " + args.marker]
                    process = subprocess.Popen(command, cwd=fixture, env=child_env,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               start_new_session=True)
                    result["executed"] = True
                    stdout, stderr = process.communicate(timeout=args.timeout)
                    result["exit_code"] = process.returncode
                    result["key_in_captured_output"] = key.encode() in stdout + stderr
                    result.update(parse_response(stdout, args.marker))
                    result["passed"] = (
                        process.returncode == 0 and result["assistant_response_matches"]
                        and result["tool_events"] == result["error_events"] == 0
                        and not result["key_in_captured_output"]
                    )
                    result["outcome"] = "authenticated_reply_observed" if result["passed"] else "not_qualified"
                    if result["passed"]:
                        result["actual_assistant_response"] = args.marker
            except subprocess.TimeoutExpired:
                result["outcome"] = "timeout_not_qualified"
            except OSError:
                result["outcome"] = "local_execution_error_not_qualified"
            finally:
                if process is not None:
                    terminate_owned_group(process)
                result["key_bearing_temporary_file_count_before_cleanup"] = sum(
                    key.encode() in p.read_bytes()
                    for p in root.rglob("*") if p.is_file() and not p.is_symlink()
                )
        result["temporary_profile_removed"] = not root.exists()
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "executed": result["executed"],
                      "outcome": result["outcome"], "result": str(args.result)}))
    return 0 if result["passed"] or not args.execute else 1


if __name__ == "__main__":
    raise SystemExit(main())
