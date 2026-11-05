"""Queue a fixed refresh request in the open Codex app's existing collector chat.

The CLI's queue command stores input for the app to consume. Deliberately omit
--resume: the desktop app owns the writer and starts the turn itself.
"""
from datetime import date
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
from uuid import UUID
from zoneinfo import ZoneInfo

from workspace_state import load_workspace


def collection_prompt(root, request):
    metadata = {key: request[key] for key in ('id', 'action', 'date', 'timezone')}
    UUID(metadata['id'])
    if metadata['action'] not in ('refresh', 'start_today'):
        raise ValueError('Invalid refresh action.')
    if date.fromisoformat(metadata['date']).isoformat() != metadata['date']:
        raise ValueError('Invalid refresh date.')
    ZoneInfo(metadata['timezone'])
    skill = Path(__file__).resolve().parents[1] / 'SKILL.md'
    return '\n'.join([
        'A user explicitly requested a Morning Coffee source refresh from the local dashboard.',
        'Follow the installed Morning Coffee skill at ' + json.dumps(str(skill)) + ' and its workspace/source collection workflow.',
        'Use the report root resolved by the trusted local launcher: ' + json.dumps(str(Path(root).resolve())) + '.',
        'Inspect the durable workspace first. Proceed only if its current pending/running request exactly matches: ' + json.dumps(metadata) + '.',
        'Collect all six sources with honest coverage, preserve local choices, publish a refresh and complete that exact request ID. If stale, do nothing. If collection fails, fail that exact ID safely.',
        'Handle this existing browser request directly. Do not begin another request, create another chat, or change schedules, connection settings, or provider access.',
    ])


def dispatch_codex_app_refresh(root, request, config):
    """Return a queue acknowledgement, never launch an agent or app backend."""
    current = load_workspace(root).get('refresh') or {}
    if current.get('id') != request['id'] or current.get('status') not in ('pending', 'running'):
        return False
    prompt = collection_prompt(root, request)
    target = Path(config['socket_path'])
    info, parent = target.lstat(), target.parent.stat()
    uid = os.getuid()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != uid or parent.st_uid != uid
            or info.st_mode & 0o077 or parent.st_mode & 0o022):
        return False
    # The app's private IPC listener establishes liveness. The CLI queue command
    # alone would also succeed with the app closed, leaving input unconsumed.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        connection.connect(str(target))
    result = subprocess.run([
        config['cli_path'], 'queue', '--thread', config['thread_id'], '--message', prompt,
    ], capture_output=True, text=True, timeout=12)
    acknowledgement = r'Queued message [0-9a-f-]{36} for thread ' + re.escape(config['thread_id']) + r'\.'
    return result.returncode == 0 and re.fullmatch(acknowledgement, result.stdout.strip()) is not None
