#!/usr/bin/env python3
"""Save local plans, Tea block removals, review marks and to-dos. No provider calls."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import fcntl
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from day_calendar import calendar_data, plan_revision
from plan_submission import PlanError, StalePlanError, latest_plan, remove_plan_block, save_plan
from review_state import ReviewError, load_review_state, save_review_state
from calendar_state import (CalendarError, StaleCalendarError, load_calendar_state,
                            save_calendar_state, save_calendar_removal)
from todo_state import StaleTodoError, TodoError, load_todos, save_todo_action
from workspace_state import (WorkspaceError, StaleWorkspaceError, begin_refresh, load_workspace,
                             load_workspace_with_snapshot, mark_dispatch, open_workspace, public_workspace,
                             read_bridge_config, bridge_configured, suggestion_action, workspace_snapshot,
                             _safe_folder, _json, _write)


def is_tea(snapshot):
    return snapshot.get('history', {}).get('kind') == 'tea-time' or snapshot.get('report', {}).get('title', '').casefold().startswith('tea')


def session_snapshot(snapshot, root, reviews_only=False):
    """Refresh local choices when opening a saved report, never trust embedded old choices."""
    result = deepcopy(snapshot)
    if is_tea(result) and not reviews_only:
        raise PlanError('Tea scheduling is read-only. Use its local actions session or submit new plans from Coffee.')
    result.pop('submitted_plan', None)
    result.pop('calendar_confirmation', None)
    result.pop('plan_submission', None)
    result.pop('plan_removal', None)
    result.pop('review_interaction', None)
    result.pop('calendar_interaction', None)
    result.pop('todo_interaction', None)
    result.pop('workspace_interaction', None)
    result.pop('workspace', None)
    local_todos = load_todos(root, with_warnings=True, timezone_name=result['report']['timezone'])
    result['todos'] = local_todos['todos']
    result['todo_archive'] = local_todos['todo_archive']
    if local_todos['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(local_todos['warnings'])
    loaded = load_review_state(root, with_warnings=True)
    result['review_state'] = loaded['state']
    if loaded['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(loaded['warnings'])
    calendar_marks = load_calendar_state(root, result, with_warnings=True, include_removed=True)
    result['calendar_state'] = calendar_marks['state']
    result['calendar_removed'] = calendar_marks['removed']
    if calendar_marks['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(calendar_marks['warnings'])
    saved = latest_plan(root, result['report']['date'], result['report']['timezone'], with_warnings=True)
    if saved['plan'] is not None:
        result['submitted_plan'] = saved['plan']
    if saved['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(saved['warnings'])
    return result


def active_source(root, fallback, workspace=False):
    """Load the durable workspace pointer on each request, including review writes."""
    if workspace:
        state, validated_snapshot = load_workspace_with_snapshot(root)
    else:
        state, validated_snapshot = None, None
    if state is None:
        return fallback, None
    return workspace_snapshot(root, state, validated_snapshot=validated_snapshot), state


def workspace_view(root, state=None):
    state = state if state is not None else load_workspace(root)
    bridge_error = None
    try:
        config = read_bridge_config(root)
    except (WorkspaceError, OSError):
        config = {}
        bridge_error = 'Source refresh requires T3. Repair its private refresh bridge configuration before retrying.'
    result = public_workspace(state) if state is not None else {'version': 0, 'refresh': None}
    result['bridge_configured'] = bridge_configured(config)
    if config.get('thread_url'):
        result['thread_url'] = config['thread_url']
    if bridge_error:
        result['bridge_error'] = bridge_error
    return result


def interactive_snapshot(snapshot, root, endpoint, capability, workspace=False):
    source, state = active_source(root, snapshot, workspace)
    current = session_snapshot(source, root, reviews_only=is_tea(source))
    if workspace or not is_tea(source):
        current['plan_submission'] = {'endpoint': endpoint + '/submit', 'token': capability,
                                      'base_revision': plan_revision(current.get('submitted_plan'))}
    if workspace or is_tea(source):
        current['plan_removal'] = {'endpoint': endpoint + '/plan/remove', 'token': capability}
    current['calendar_interaction'] = {'endpoint': endpoint + '/calendar/done', 'token': capability}
    current['review_interaction'] = {'endpoint': endpoint + '/review', 'token': capability}
    current['todo_interaction'] = {'endpoint': endpoint + '/todo', 'token': capability}
    if state is not None:
        current['workspace'] = workspace_view(root, state)
        current['workspace_interaction'] = {
            'status_endpoint': endpoint + '/workspace/status', 'refresh_endpoint': endpoint + '/refresh',
            'start_today_endpoint': endpoint + '/start-today', 'suggestion_endpoint': endpoint + '/suggestion',
            'token': capability}
    return current


def dispatch_refresh(root, request):
    """Notify the configured local T3 thread or webhook; collection stays in T3."""
    message = 'Source refresh requires T3. Open T3 and retry when its refresh bridge is running.'
    connection = None
    success = False
    try:
        config = read_bridge_config(root)
        if config.get('local_t3'):
            local = config['local_t3']
            result = subprocess.run(
                [local['node_path'], str(Path(__file__).with_name('local_t3_refresh.js'))],
                input=json.dumps({'config': local, 'request': request, 'root': str(Path(root).resolve())}),
                capture_output=True, text=True, timeout=15)
            acknowledgement = json.loads(result.stdout) if result.returncode == 0 else None
            success = isinstance(acknowledgement, dict) and acknowledgement.get('ok') is True
        else:
            url = urlsplit(config.get('webhook_url', ''))
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError('No configured bridge.')
            connection_type = http.client.HTTPSConnection if url.scheme == 'https' else http.client.HTTPConnection
            connection = connection_type(url.hostname, url.port, timeout=10)
            payload = {key: request[key] for key in ('id', 'action', 'date', 'timezone')}
            payload['request_id'] = payload.pop('id')
            payload['refresh_id'] = payload['request_id']
            connection.request('POST', (url.path or '/') + ('?' + url.query if url.query else ''),
                               json.dumps(payload), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            # No redirects or response bodies: configured private targets cannot leak via a redirect.
            success = 200 <= response.status < 300
    except (OSError, ValueError, http.client.HTTPException, subprocess.SubprocessError):
        pass
    finally:
        if connection is not None:
            connection.close()
    try:
        mark_dispatch(root, request['id'], success, error=None if success else message)
    except WorkspaceError:
        # A completion or newer request may have overtaken this bounded dispatch.
        pass


def handler_for(snapshot, root, capability, workspace=False):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def allowed(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            strict = self.path in ('/calendar/done', '/calendar/remove', '/plan/remove', '/refresh', '/start-today', '/suggestion')
            return (self.headers.get('Host') == host and
                    self.headers.get('Origin') in ('null', 'http://' + host) and
                    self.path in ('/submit', '/review', '/todo', '/calendar/done', '/calendar/remove', '/plan/remove', '/refresh', '/start-today', '/suggestion') and
                    (not strict or self.headers.get('Origin') == 'http://' + host))

        def status_allowed(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            return (self.headers.get('Host') == host and self.headers.get('Origin') in (None, 'http://' + host) and
                    hmac.compare_digest(self.headers.get('X-Brief-Token', ''), capability))

        def respond(self, code, value):
            body = json.dumps(value).encode()
            self.send_response(code)
            if self.allowed():
                self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
                self.send_header('Vary', 'Origin')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if not self.allowed() or self.headers.get('Access-Control-Request-Method') != 'POST':
                self.respond(403, {'error': 'Not an authorized local report request.'})
                return
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Access-Control-Allow-Methods', 'POST')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Brief-Token')
            self.send_header('Access-Control-Allow-Private-Network', 'true')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()

        def do_GET(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            if self.path == '/workspace/session':
                if not workspace or not self.status_allowed():
                    self.respond(403, {'error': 'This report is not authorized for this local session.'})
                    return
                self.respond(200, {'ok': True, 'session': {'root': str(Path(root).resolve()),
                              'pid': os.getpid(), 'workspace': True}})
                return
            if self.path == '/workspace/status':
                if not workspace:
                    self.respond(404, {'error': 'Open a workspace session to check source refresh status.'})
                    return
                if not self.status_allowed():
                    self.respond(403, {'error': 'This report is not authorized for this local session.'})
                    return
                try:
                    self.respond(200, {'ok': True, 'workspace': workspace_view(root),
                                       **load_todos(root, with_warnings=True, timezone_name=snapshot.get('report', {}).get('timezone', 'America/Toronto'))})
                except (OSError, ValueError, KeyError):
                    self.respond(500, {'error': 'Source workspace state is unavailable. Local tasks can still be saved; restore the active published snapshot or repair the preserved workspace manifest.'})
                return
            if self.headers.get('Host') != host or not hmac.compare_digest(self.path, '/report/' + capability):
                self.respond(404, {'error': 'Report not found.'})
                return
            from render_brief import render
            try:
                current = interactive_snapshot(snapshot, root, 'http://' + host, capability, workspace)
            except (OSError, ValueError, KeyError):
                self.respond(500, {'error': 'Source workspace facts are unavailable. Local tasks in the open page can still be saved; restore the active published snapshot or repair the preserved workspace manifest.'})
                return
            body = render(current, now=datetime.now(ZoneInfo(current['report']['timezone']))).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if not self.allowed() or not hmac.compare_digest(self.headers.get('X-Brief-Token', ''), capability):
                self.respond(403, {'error': 'This report is not authorized for this local session.'})
                return
            if self.path in ('/refresh', '/start-today', '/suggestion') and not workspace:
                self.respond(403, {'error': 'Open a workspace session to use source refresh and suggestions.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise PlanError('Invalid submission request.')
                request = json.loads(self.rfile.read(length))
                # Root-wide local tasks remain available when source history is damaged.
                if self.path == '/todo':
                    self.respond(200, save_todo_action(root, request, timezone_name=snapshot.get('report', {}).get('timezone', 'America/Toronto')))
                    return
                source, _ = active_source(root, snapshot, workspace)
                if self.path in ('/refresh', '/start-today'):
                    if not isinstance(request, dict) or set(request) - {'date', 'timezone'}:
                        raise WorkspaceError('Choose Refresh or Start today from this workspace.')
                    zone = source['report']['timezone']
                    day = datetime.now(ZoneInfo(zone)).date().isoformat()
                    if request.get('date', day) != day or request.get('timezone', zone) != zone:
                        raise WorkspaceError('This refresh belongs to today in the workspace timezone.')
                    started = begin_refresh(root, 'refresh' if self.path == '/refresh' else 'start_today', day, zone)
                    state = started['state']
                    if started['created']:
                        try:
                            configured = bridge_configured(read_bridge_config(root))
                        except (WorkspaceError, OSError):
                            configured = False
                        if configured:
                            threading.Thread(target=dispatch_refresh, args=(root, started['request']),
                                             name='workspace-refresh', daemon=True).start()
                        else:
                            state = mark_dispatch(root, started['request']['id'], False,
                                                  error='Source refresh requires T3. Open T3 and configure its refresh bridge.')
                    view = workspace_view(root, state)
                    self.respond(202 if started['created'] and view['refresh']['status'] in ('pending', 'running') else 200,
                                 {'ok': True, 'created': started['created'], 'workspace': view})
                    return
                if self.path == '/suggestion':
                    state = suggestion_action(root, request)
                    self.respond(200, {'ok': True, 'workspace': workspace_view(root, state), **load_todos(root, with_warnings=True, timezone_name=snapshot.get('report', {}).get('timezone', 'America/Toronto'))})
                    return
                if self.path == '/plan/remove':
                    if not workspace and not is_tea(source):
                        self.respond(403, {'error': 'Remove saved local blocks from Tea, or edit your schedule in Coffee.'})
                        return
                    record = remove_plan_block(root, source, request)
                    self.respond(200, {'ok': True, 'message': 'Plan block removed locally.',
                                       'submitted_at': record['submitted_at'], 'blocks': record['blocks']})
                    return
                if self.path == '/calendar/done':
                    current = session_snapshot(source, root, reviews_only=is_tea(source))
                    record = save_calendar_state(root, current, request)
                    self.respond(200, {'ok': True, 'record': record})
                    return
                if self.path == '/calendar/remove':
                    record = save_calendar_removal(root, source, request)
                    self.respond(200, {'ok': True, 'record': record})
                    return
                if self.path == '/review':
                    record = save_review_state(root, source, request)
                    self.respond(200, {'ok': True, 'record': record, 'message': 'Review mark saved locally.'})
                    return
                if is_tea(source) and not workspace:
                    self.respond(403, {'error': 'Submit new plans from Coffee. Tea can only remove saved local blocks.'})
                    return
                record = save_plan(root, source, request, require_revision=workspace)
                ends = {block['kind']: block['end_at'] for block in calendar_data(dict(source, submitted_plan=record), read_only=True)['submitted_blocks']}
                self.respond(200, {'ok': True, 'message': 'Plan saved locally. Today shows your latest submitted blocks.',
                                   'submitted_at': record['submitted_at'], 'blocks': record['blocks'], 'end_times': ends,
                                   'revision': plan_revision(record), 'path': record['path']})
            except (StalePlanError, StaleWorkspaceError, StaleTodoError, StaleCalendarError) as error:
                self.respond(409, {'error': str(error)})
            except (ValueError, TypeError, KeyError) as error:
                self.respond(400, {'error': str(error) if isinstance(error, (PlanError, ReviewError, TodoError, WorkspaceError, CalendarError)) else 'Invalid submission request.'})
            except OSError:
                self.respond(500, {'error': 'The local change could not be saved. Check the report directory permissions.'})
    return Handler


@contextmanager
def workspace_session_lock(root):
    """Serialize discovery and launch without blocking the child's workspace lock."""
    folder = _safe_folder(root, True)
    fd = os.open(folder / '.session.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield folder
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def report_target(info):
    target = urlsplit(info['url'])
    match = re.fullmatch(r'/report/([A-Za-z0-9_-]{32,})', target.path)
    if (target.scheme != 'http' or target.hostname != '127.0.0.1' or not target.port or
            target.username or target.password or target.query or target.fragment or not match):
        raise PlanError('Resume requires private loopback session metadata.')
    return target, match[1]


def discover_workspace_session(root, registry):
    """Return a verified live session or metadata safe to resume after a refused connection."""
    if not registry.exists():
        return None, False
    info = _json(registry)
    if not isinstance(info, dict) or info.get('root') != str(root) or info.get('workspace') is not True:
        return None, False
    try:
        target, token = report_target(info)
    except (ValueError, KeyError, TypeError):
        return None, False
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=2)
    try:
        connection.request('GET', '/workspace/session', headers={'X-Brief-Token': token})
        response = connection.getresponse()
        body = response.read(8192)
        if response.status != 200:
            return None, False
        result = json.loads(body)
        if not isinstance(result, dict) or not isinstance(result.get('session'), dict):
            return None, False
        identity = result['session']
        if (result.get('ok') is True and identity.get('root') == str(root) and
                identity.get('workspace') is True and identity.get('pid') == info.get('pid')):
            return info, True
        return None, False
    except ConnectionRefusedError:
        return info, False
    except (ValueError, http.client.HTTPException):
        return None, False
    except OSError as exc:
        # A timeout is not proof that a detached service has stopped.
        raise PlanError('The existing workspace service could not be checked. Retry before starting another session.') from exc
    finally:
        connection.close()


def start_background(args):
    if not args.workspace:
        return launch_background(args)
    from report_history import resolve_root
    root = resolve_root(args.root).resolve()
    with workspace_session_lock(root) as folder:
        registry = folder / 'session.json'
        info, live = discover_workspace_session(root, registry)
        if live:
            return info
        launch = argparse.Namespace(**vars(args))
        # Keep the caller's path spelling for existing plan revision compatibility.
        launch.root = str(resolve_root(args.root))
        if info is not None and not args.resume_session:
            launch.resume_session = str(registry)
        info = launch_background(launch)
        info.update(root=str(root), workspace=True)
        _write(folder, info, filename='session.json')
        return info


def launch_background(args):
    """Detach the save service from the agent's command and confirm it is reachable."""
    output = Path(args.output).expanduser().resolve()
    metadata = output.with_suffix('.session.json')
    log = output.with_suffix('.log')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if output.exists() or metadata.exists():
        raise PlanError('Use a new output path for the local session.')
    command = [sys.executable, str(Path(__file__).resolve()), '--snapshot', args.snapshot,
               '--output', str(output), '--port', str(args.port)]
    if args.root:
        command += ['--root', args.root]
    if args.resume_session:
        command += ['--resume-session', args.resume_session]
    if args.workspace:
        command += ['--workspace']
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=handle,
                                 stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    try:
        deadline = time.monotonic() + 10
        while child.poll() is None and time.monotonic() < deadline:
            try:
                info = json.loads(metadata.read_text())
                target = urlsplit(info['url'])
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=1)
                try:
                    connection.request('GET', target.path)
                    response = connection.getresponse()
                    response.read()
                    if response.status == 200:
                        return info
                finally:
                    connection.close()
            except (OSError, ValueError, http.client.HTTPException):
                pass
            time.sleep(0.05)
        raise PlanError('Local save service did not start. See ' + str(log))
    except BaseException:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)
        raise


def stop_service(*_):
    raise KeyboardInterrupt


def session_identity(args):
    """Reuse a private report URL during a local code upgrade."""
    if not args.resume_session:
        return secrets.token_urlsafe(32), args.port
    info = json.loads(Path(args.resume_session).expanduser().read_text())
    target, token = report_target(info)
    if args.port not in (0, target.port):
        raise PlanError('Resume requires private loopback session metadata.')
    return token, target.port


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, help='Morning Coffee or Tea Time snapshot.json')
    parser.add_argument('--output', required=True, help='New temporary session-enabled HTML; never overwrite immutable history')
    parser.add_argument('--root', help='Report store override; otherwise use normal daily-briefs configuration')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--resume-session', help='Private connection metadata for restarting at the same report URL')
    parser.add_argument('--background', action='store_true', help='Keep saving available after the launching command exits')
    parser.add_argument('--workspace', action='store_true', help='Serve the durable all-day workspace from a published snapshot inside the report root')
    parser.add_argument('--open', action='store_true', help='Open the live report in the default browser')
    args = parser.parse_args()
    try:
        if args.background:
            info = start_background(args)
            print('Local save service running in background (PID ' + str(info['pid']) + ').')
            print('Open the private session report: ' + info['url'])
            print('Stop service: kill ' + str(info['pid']))
            if args.open:
                import webbrowser
                webbrowser.open(info['url'])
            return
        from report_history import resolve_root
        from render_brief import render
        source, output = Path(args.snapshot).expanduser().resolve(), Path(args.output).expanduser().resolve()
        if output == source or output == source.with_name('report.html'):
            raise PlanError('Use a new temporary HTML path; history files must not be replaced.')
        root = resolve_root(args.root)
        original = json.loads(source.read_text())
        if args.workspace:
            open_workspace(root, source)
        capability, port = session_identity(args)
        server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(original, root, capability, args.workspace))
        endpoint = 'http://127.0.0.1:' + str(server.server_port)
        snapshot = interactive_snapshot(original, root, endpoint, capability, args.workspace)
        output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        metadata = output.with_suffix('.session.json')
        if metadata.exists():
            raise PlanError('Use a new output path for the local session.')
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        info = {'pid': os.getpid(), 'url': endpoint + '/report/' + capability, 'html': str(output)}
        previous_term = signal.signal(signal.SIGTERM, stop_service)
        metadata_created = False
        try:
            with os.fdopen(fd, 'w') as handle:
                handle.write(render(snapshot))
            with os.fdopen(os.open(metadata, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
                metadata_created = True
                json.dump(info, handle)
            print('Open the private session report: ' + info['url'], flush=True)
            print('Keep this terminal running, or use --background. Ctrl-C closes this session.', flush=True)
            if args.open:
                import webbrowser
                webbrowser.open(info['url'])
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            output.unlink(missing_ok=True)
            if metadata_created:
                metadata.unlink(missing_ok=True)
            signal.signal(signal.SIGTERM, previous_term)
        print('Session closed. Submitted plans remain in ' + str(root))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
