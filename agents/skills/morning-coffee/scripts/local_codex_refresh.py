"""Run a fixed source refresh in a privately bound Codex collector session."""
import json
import os
from pathlib import Path
import signal
import subprocess

from workspace_state import WorkspaceError, load_workspace, mark_dispatch


def collection_prompt(root, request):
    metadata = {key: request[key] for key in ('id', 'action', 'date', 'timezone')}
    return '\n'.join([
        'The user requested a Morning Coffee source refresh from the local dashboard.',
        'Follow the Morning Coffee skill at ' + json.dumps(str(Path(__file__).resolve().parents[1] / 'SKILL.md')) + '.',
        'Use this trusted report root: ' + json.dumps(str(Path(root).resolve())) + '.',
        'This request has already been created. Do not begin another request or redispatch it.',
        'Inspect the durable workspace. Collect only if its pending/running request exactly matches: ' + json.dumps(metadata) + '.',
        'Run source connection preflight and collect all six sources with honest coverage, preserving local choices.',
        'Publish a refresh generation and complete that exact request ID. A process exit or chat reply is not completion.',
        'If stale, do nothing. If collection fails, fail that exact request safely.',
        'Use the configured provider connections read-only. Do not change connection settings, schedules, or provider access.',
        'This is a request in the existing collector session. Do not create another chat.',
    ])


def dispatch_codex_refresh(root, request, local, timeout):
    """Monitor the collector; only its exact-ID durable completion means success."""
    process = None
    attempted = False
    try:
        state = load_workspace(root)
        current = state and state.get('refresh')
        if (not current or current['status'] != 'pending' or
                any(current[key] != request[key] for key in ('id', 'action', 'date', 'timezone'))):
            return
        attempted = True
        # No shell, arbitrary arguments, browser instructions, or approval bypass.
        command = [local['cli_path'], 'exec', '--sandbox', 'workspace-write',
                   '--cd', local['cwd'], '--add-dir', str(Path(root).resolve()),
                   'resume', local['thread_id'], '-']
        process = subprocess.Popen(command, cwd=local['cwd'], stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   text=True, start_new_session=True)
        state = mark_dispatch(root, request['id'], True)
        if state['refresh']['status'] != 'running':
            return
        process.communicate(collection_prompt(root, request), timeout=timeout)
    except (OSError, ValueError, subprocess.SubprocessError, WorkspaceError):
        pass
    finally:
        if process is not None and process.poll() is None:
            # Stop the collector and any tool children after timeout or a stale start.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if process is not None and process.stdin is not None:
            process.stdin.close()
        # Terminal completion/failure and newer requests are preserved by mark_dispatch.
        # Even exit 0 must fail if the collector never published/completed this request.
        if attempted:
            try:
                mark_dispatch(root, request['id'], False)
            except WorkspaceError:
                pass
