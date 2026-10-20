#!/usr/bin/env python3
"""Save local Coffee plans and Coffee/Tea review marks. No provider calls."""
import argparse
from copy import deepcopy
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit
from plan_submission import PlanError, latest_plan, save_plan
from review_state import ReviewError, load_review_state, save_review_state
from todo_state import TodoError, load_todos, save_todo_action


def is_tea(snapshot):
    return snapshot.get('history', {}).get('kind') == 'tea-time' or snapshot.get('report', {}).get('title', '').casefold().startswith('tea')


def session_snapshot(snapshot, root, reviews_only=False):
    """Refresh local choices when opening a saved Coffee, never trust embedded old choices."""
    result = deepcopy(snapshot)
    if is_tea(result) and not reviews_only:
        raise PlanError('Tea is read-only. Start a submission session from Coffee.')
    result.pop('submitted_plan', None)
    result.pop('calendar_confirmation', None)
    result.pop('plan_submission', None)
    result.pop('review_interaction', None)
    result.pop('todo_interaction', None)
    local_todos = load_todos(root, with_warnings=True)
    result['todos'] = local_todos['todos']
    if local_todos['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(local_todos['warnings'])
    loaded = load_review_state(root, with_warnings=True)
    result['review_state'] = loaded['state']
    if loaded['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(loaded['warnings'])
    saved = latest_plan(root, result['report']['date'], result['report']['timezone'], with_warnings=True)
    if saved['plan'] is not None:
        result['submitted_plan'] = saved['plan']
    if saved['warnings']:
        result.setdefault('history', {}).setdefault('warnings', []).extend(saved['warnings'])
    return result


def handler_for(snapshot, root, capability):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def allowed(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            return (self.headers.get('Host') == host and
                    self.headers.get('Origin') in ('null', 'http://' + host) and
                    self.path in ('/submit', '/review', '/todo'))

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
            if self.headers.get('Host') != host or not hmac.compare_digest(self.path, '/report/' + capability):
                self.respond(404, {'error': 'Report not found.'})
                return
            from render_brief import render
            current = session_snapshot(snapshot, root, reviews_only=is_tea(snapshot))
            for key in ('plan_submission', 'review_interaction', 'todo_interaction'):
                if key in snapshot:
                    current[key] = snapshot[key]
            body = render(current).encode()
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
            if self.path == '/submit' and is_tea(snapshot):
                self.respond(403, {'error': 'Tea calendar is read-only. Submit plans from Coffee.'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise PlanError('Invalid submission request.')
                request = json.loads(self.rfile.read(length))
                if self.path == '/todo':
                    self.respond(200, save_todo_action(root, request))
                    return
                if self.path == '/review':
                    record = save_review_state(root, snapshot, request)
                    self.respond(200, {'ok': True, 'record': record, 'message': 'Review mark saved locally.'})
                    return
                record = save_plan(root, snapshot, request)
                self.respond(200, {'ok': True, 'message': 'Plan saved locally. Tea will use your latest submitted blocks.',
                                   'submitted_at': record['submitted_at'], 'blocks': record['blocks'], 'path': record['path']})
            except (ValueError, TypeError, KeyError) as error:
                self.respond(400, {'error': str(error) if isinstance(error, (PlanError, ReviewError, TodoError)) else 'Invalid submission request.'})
            except OSError:
                self.respond(500, {'error': 'The local change could not be saved. Check the report directory permissions.'})
    return Handler


def start_background(args):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, help='Morning Coffee or Tea Time snapshot.json')
    parser.add_argument('--output', required=True, help='New temporary session-enabled HTML; never overwrite immutable history')
    parser.add_argument('--root', help='Report store override; otherwise use normal daily-briefs configuration')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--background', action='store_true', help='Keep saving available after the launching command exits')
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
        snapshot = session_snapshot(original, root, reviews_only=is_tea(original))
        capability = secrets.token_urlsafe(32)
        server = HTTPServer(('127.0.0.1', args.port), handler_for(snapshot, root, capability))
        endpoint = 'http://127.0.0.1:' + str(server.server_port)
        if not is_tea(snapshot):
            snapshot['plan_submission'] = {'endpoint': endpoint + '/submit', 'token': capability}
        snapshot['review_interaction'] = {'endpoint': endpoint + '/review', 'token': capability}
        snapshot['todo_interaction'] = {'endpoint': endpoint + '/todo', 'token': capability}
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
