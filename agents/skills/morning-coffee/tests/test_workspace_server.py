"""Real local HTTP requests exercise durable source refresh and live workspace swaps."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for, dispatch_refresh
from plan_submission import latest_plan, save_plan
from day_calendar import plan_revision
from report_history import publish
from todo_state import load_todos
from workspace_state import complete_refresh, load_workspace, open_workspace
import workspace_state
from test_report_history import ReportSurface, snapshot


class WorkspaceServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        self.data = self.source('09:00')
        self.first = publish(self.root, self.data, 'morning-coffee')
        open_workspace(self.root, self.first['snapshot'])
        self.token = 'private-test-workspace-capability-' + 'x' * 32
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.data, self.root, self.token, workspace=True))
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def source(self, at):
        data = snapshot(at, day=self.day)
        data['availability'] = {'status': 'complete', 'checked_at': data['collected_at'],
            'coverage': 'Synthetic primary calendar', 'window_start': '09:00', 'window_end': '17:00',
            'coverage_start': self.day + 'T00:00:00-04:00', 'coverage_end': self.day + 'T23:59:00-04:00', 'busy': []}
        data['work_suggestions'] = [{'id': 'work:new', 'title': 'Investigate a new source item',
                                    'action': 'Check the source', 'source_url': 'https://example.com/new-work',
                                    'project_tags': ['Transport']}]
        return data

    def call(self, path='/workspace/status', body=None, method=None, **updates):
        method = method or ('POST' if body is not None else 'GET')
        headers = {'X-Brief-Token': self.token}
        if method == 'POST':
            headers.update(Origin=self.origin, **{'Content-Type': 'application/json'})
        headers.update(updates)
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None, headers)
            response = connection.getresponse()
            result = response.read().decode()
            return response.status, json.loads(result) if 'application/json' in response.getheader('Content-Type', '') else result
        finally:
            connection.close()

    def status(self):
        code, body = self.call()
        self.assertEqual(code, 200)
        return body['workspace']

    def configure(self, url, **extra):
        path = self.root / 'workspace' / 'config.json'
        path.write_text(json.dumps({'webhook_url': url, **extra}))
        path.chmod(0o600)

    def wait_for(self, status):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            current = self.status()
            if current['refresh'] and current['refresh']['status'] == status:
                return current
            time.sleep(0.02)
        self.fail('Workspace never reached ' + status)

    def test_missing_source_or_corrupt_manifest_does_not_block_root_tasks(self):
        Path(self.first['snapshot']).unlink()
        code, saved = self.call('/todo', {'action': 'add', 'title': 'Local work survives missing source', 'project_tags': ['Transport']})
        self.assertEqual(code, 200)
        task_id = saved['item']['id']
        code, status = self.call()
        self.assertEqual(code, 500)
        self.assertIn('Local tasks can still be saved', status['error'])
        manifest = self.root / 'workspace/state.json'
        manifest.write_text('{synthetic-corruption')
        code, saved = self.call('/todo', {'action': 'complete', 'id': task_id})
        self.assertEqual(code, 200)
        self.assertEqual(saved['item']['status'], 'completed')
        self.assertEqual(saved['item']['project_tags'], ['Transport'])
        self.assertEqual(manifest.read_text(), '{synthetic-corruption')
        code, status = self.call()
        self.assertEqual(code, 500)
        self.assertIn('Source workspace state is unavailable', status['error'])

    def test_session_discovery_identity_is_authenticated_and_bound_to_root(self):
        code, body = self.call('/workspace/session')
        self.assertEqual(code, 200)
        self.assertEqual(body['session'], {'root': str(self.root.resolve()), 'pid': os.getpid(), 'workspace': True})
        for headers in ({'X-Brief-Token': ''}, {'Origin': 'https://evil.example'}, {'Host': 'evil.example'}):
            self.assertEqual(self.call('/workspace/session', **headers)[0], 403)

    def test_private_status_authentication_and_missing_bridge_preserve_sources(self):
        first = Path(self.first['snapshot']).read_bytes()
        state = self.status()
        self.assertFalse(state['bridge_configured'])
        version = state['version']
        self.assertEqual(self.status()['version'], version, 'polling must not start or repeat source collection')
        self.assertNotIn('active_snapshot', state)
        self.assertIsNone(state['refresh'])
        for headers in ({'X-Brief-Token': ''}, {'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'Origin': 'null'}):
            self.assertEqual(self.call(**headers)[0], 403)
        for headers in ({'X-Brief-Token': 'wrong'}, {'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'Origin': 'null'}):
            self.assertEqual(self.call('/refresh', {}, **headers)[0], 403)
        self.assertEqual(self.call('/refresh', {'webhook_url': 'https://evil.example'})[0], 400)
        self.assertIsNone(self.status()['refresh'])
        status, result = self.call('/refresh', {})
        self.assertEqual(status, 200)
        self.assertTrue(result['created'])
        self.assertEqual(result['workspace']['refresh']['status'], 'failed')
        self.assertEqual(Path(self.first['snapshot']).read_bytes(), first)
        self.assertEqual(load_workspace(self.root)['active_snapshot'], str(Path(self.first['snapshot']).relative_to(self.root)))
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Local work while T3 is unavailable'})[0], 200)
        page = self.call('/report/' + self.token)[1]
        self.assertIn('Fixture stand-up', page)
        self.assertIn('Local work while T3 is unavailable', page)

    def test_report_reuses_the_snapshot_validated_with_workspace_state(self):
        original = workspace_state.published_snapshot
        with patch('workspace_state.published_snapshot', wraps=original) as validate_snapshot:
            code, page = self.call('/report/' + self.token)
        self.assertEqual(code, 200)
        self.assertIn('Fixture stand-up', page)
        self.assertEqual(validate_snapshot.call_count, 1, 'workspace load and report rendering share one validated snapshot')

        Path(self.first['snapshot']).unlink()
        code, result = self.call('/report/' + self.token)
        self.assertEqual(code, 500)
        self.assertIn('Source workspace facts are unavailable', result['error'])

    def test_async_fixed_bridge_dedupes_tabs_and_keeps_local_saves_responsive(self):
        entered, release = threading.Event(), threading.Event()
        received = []

        class Bridge(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                entered.set()
                release.wait(5)
                self.send_response(204)
                self.end_headers()

        bridge = ThreadingHTTPServer(('127.0.0.1', 0), Bridge)
        worker = threading.Thread(target=bridge.serve_forever, daemon=True)
        worker.start()
        self.configure('http://127.0.0.1:' + str(bridge.server_port) + '/hook?secret=private-bridge-secret',
                       thread_url='t3-thread://verified-task-binding')
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.call('/refresh', {}), range(2)))
            self.assertEqual(sum(body['created'] for _, body in responses), 1)
            ids = {body['workspace']['refresh']['id'] for _, body in responses}
            self.assertEqual(len(ids), 1)
            self.assertTrue(entered.wait(1))
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]['request_id'], ids.pop())
            self.assertEqual(received[0]['refresh_id'], received[0]['request_id'])
            self.assertEqual(set(received[0]), {'request_id', 'refresh_id', 'action', 'date', 'timezone'})
            # The bridge is still blocked; these requests must finish without it.
            status, task = self.call('/todo', {'action': 'add', 'title': 'Keep working', 'project_tags': ['Transport']})
            self.assertEqual(status, 200)
            self.assertEqual(task['item']['project_tags'], ['Transport'])
            self.assertEqual(self.status()['refresh']['status'], 'pending')
            self.assertTrue(self.status()['bridge_configured'])
            self.assertEqual(self.status()['thread_url'], 't3-thread://verified-task-binding')
            self.assertNotIn('private-bridge-secret', json.dumps(self.status()))
            self.assertNotIn('private-bridge-secret', self.call('/report/' + self.token)[1])
            release.set()
            self.wait_for('running')
            self.assertEqual(len(received), 1)
        finally:
            release.set()
            bridge.shutdown()
            bridge.server_close()
            worker.join()

    def test_offline_bridge_fails_request_without_replacing_facts_or_blocking_tasks(self):
        bridge = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        port = bridge.server_port
        bridge.server_close()
        self.configure('http://127.0.0.1:' + str(port) + '/private-hook')
        active = load_workspace(self.root)['active_snapshot']
        self.assertEqual(self.call('/start-today', {})[0], 202)
        failed = self.wait_for('failed')
        self.assertIn('error', failed['refresh'])
        self.assertEqual(load_workspace(self.root)['active_snapshot'], active)
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Offline task'})[0], 200)
        self.assertEqual(load_todos(self.root)[0]['title'], 'Offline task')

    def test_malformed_bridge_config_does_not_block_render_or_local_saves(self):
        path = self.root / 'workspace' / 'config.json'
        path.write_text('{broken private config')
        path.chmod(0o600)
        self.assertFalse(self.status()['bridge_configured'])
        self.assertIn('configuration', self.status()['bridge_error'])
        self.assertEqual(self.call('/refresh', {})[1]['workspace']['refresh']['status'], 'failed')
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Still editable'})[0], 200)
        self.assertEqual(self.call('/review', {'kind': 'pr', 'url': self.data['reviews']['items'][0]['url'], 'done': True})[0], 200)
        self.assertEqual(self.call('/report/' + self.token)[0], 200)
        self.assertEqual(path.read_text(), '{broken private config')

    def test_live_priority_refresh_and_task_completion_use_the_same_report_session(self):
        archive_before = Path(self.first['snapshot']).read_bytes()
        legacy_before = load_workspace(self.root)['selected_priorities']
        fresh = self.source('11:00')
        prototype = fresh['priorities'][0]
        fresh['priorities'] = [dict(prototype, id='fresh:' + str(index),
            title='Ranked recommendation ' + str(index),
            context='Needed before synthetic handoff ' + str(index)) for index in range(4)]
        published = publish(self.root, fresh, 'refresh')
        complete_refresh(self.root, published['snapshot'])
        status, markup = self.call('/report/' + self.token)
        self.assertEqual(status, 200)
        page = ReportSurface(markup)
        priorities = page.by_id['daily-priorities']
        titles = [page.visible_text(node) for node in page.elements(priorities) if node['tag'] == 'h4']
        self.assertEqual(titles, [row['title'] for row in fresh['priorities']])
        self.assertIn('Recommended priorities', page.visible_text(priorities))
        self.assertNotIn('chosen priorit', page.visible_text(priorities))
        chosen = next(row for row in self.status()['suggestions'] if row['id'] == 'fresh:0')
        status, _ = self.call('/suggestion', {'action': 'accept', 'id': chosen['id'],
                                             'fingerprint': chosen['fingerprint']})
        self.assertEqual(status, 200)
        task_id = load_workspace(self.root)['accepted']['fresh:0']['task_id']
        accepted_page = ReportSurface(self.call('/report/' + self.token)[1])
        self.assertIn('Ranked recommendation 0', accepted_page.visible_text(accepted_page.by_id['daily-priorities']))
        self.assertIn('Ranked recommendation 0', accepted_page.visible_text(accepted_page.by_id['todos']))
        before_completion = self.status()
        self.assertEqual(self.call('/todo', {'action': 'complete', 'id': task_id})[0], 200)
        after_completion = self.status()
        self.assertEqual(after_completion['version'], before_completion['version'])
        self.assertNotEqual(after_completion['local_revision'], before_completion['local_revision'])
        completed_page = ReportSurface(self.call('/report/' + self.token)[1])
        self.assertNotIn('Ranked recommendation 0', completed_page.visible_text(completed_page.by_id['daily-priorities']))
        self.assertEqual(load_workspace(self.root)['selected_priorities'], legacy_before)
        self.assertEqual(Path(self.first['snapshot']).read_bytes(), archive_before)

    def test_active_snapshot_swap_uses_current_review_scope_and_preserves_local_plan_and_tasks(self):
        old_url = self.data['reviews']['items'][0]['url']
        self.assertEqual(self.call('/review', {'kind': 'pr', 'url': old_url, 'done': True})[0], 200)
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Persistent task', 'project_tags': ['Networking']})[0], 200)
        chosen = [{'kind': 'dog_walk', 'start': 1200, 'minutes': 30}]
        saved = save_plan(self.root, self.data, {'date': self.day, 'timezone': 'America/Toronto', 'blocks': chosen})
        fresh = self.source('12:00')
        fresh['agenda']['events'][0]['title'] = 'Refreshed source meeting'
        fresh['reviews']['items'][0].update(url='https://github.com/dbt-labs/fixture/pull/999', number=999, title='New live review')
        second = publish(self.root, fresh, 'morning-coffee')
        complete_refresh(self.root, second['snapshot'])
        code, html = self.call('/report/' + self.token)
        self.assertEqual(code, 200)
        page = ReportSurface(html)
        self.assertIn('Refreshed source meeting', page.visible_text())
        self.assertIn('Persistent task', page.visible_text())
        self.assertIn('20:00–20:30', page.visible_text(page.by_id['today']))
        self.assertIn('Networking', html)
        self.assertEqual(self.call('/review', {'kind': 'pr', 'url': old_url, 'done': False})[0], 400)
        new_url = fresh['reviews']['items'][0]['url']
        self.assertEqual(self.call('/review', {'kind': 'pr', 'url': new_url, 'done': True})[0], 200)
        request = {'date': self.day, 'timezone': 'America/Toronto', 'revision': plan_revision(saved), 'block': chosen[0]}
        self.assertEqual(self.call('/plan/remove', request)[0], 200, 'Coffee supports the same narrow saved-block removal')
        self.assertEqual(latest_plan(self.root, self.day, 'America/Toronto')['blocks'], [])
        self.assertEqual(self.status()['version'], 2)

    def test_known_suggestions_only_and_accepted_task_keeps_project_tags(self):
        fingerprint = self.status()['suggestions'][0]['fingerprint']
        self.assertEqual(self.call('/suggestion', {'action': 'accept', 'id': 'unknown', 'fingerprint': fingerprint})[0], 409)
        self.assertEqual(self.call('/suggestion', {'action': 'accept', 'id': 'work:new', 'fingerprint': fingerprint}, Origin='https://evil.example')[0], 403)
        status, result = self.call('/suggestion', {'action': 'accept', 'id': 'work:new', 'fingerprint': fingerprint})
        self.assertEqual(status, 200)
        self.assertEqual(result['todos'][0]['title'], 'Investigate a new source item')
        self.assertEqual(result['todos'][0]['project_tags'], ['Transport'])
        self.assertEqual(result['workspace']['suggestions'], [])
        self.assertEqual(self.call('/suggestion', {'action': 'accept', 'id': 'work:new', 'fingerprint': fingerprint})[0], 200)
        self.assertEqual(len(load_todos(self.root)), 1)

    def test_stale_suggestion_material_returns_conflict_without_accepting_unseen_work(self):
        fingerprint = self.status()['suggestions'][0]['fingerprint']
        fresh = self.source('10:00')
        fresh['work_suggestions'][0].update(material_key='new-event', title='Unseen changed work')
        complete_refresh(self.root, publish(self.root, fresh, 'refresh')['snapshot'])
        for action in ('accept', 'dismiss'):
            code, result = self.call('/suggestion', {'action': action, 'id': 'work:new', 'fingerprint': fingerprint})
            self.assertEqual(code, 409)
            self.assertIn('changed', result['error'])
        self.assertEqual(load_todos(self.root), [])
        self.assertEqual(self.status()['suggestions'][0]['item']['title'], 'Unseen changed work')

    def test_workspace_plan_submit_requires_revision_and_rejects_stale_tabs_after_removal(self):
        request = {'date': self.day, 'timezone': 'America/Toronto',
                   'blocks': [{'kind': 'dog_walk', 'start': 780, 'minutes': 30}]}
        self.assertEqual(self.call('/submit', request)[0], 409)
        request['base_revision'] = None
        code, first = self.call('/submit', request)
        self.assertEqual(code, 200)
        self.assertEqual(self.call('/submit', request)[0], 409)
        stale = dict(request, base_revision=first['revision'])
        code, _ = self.call('/plan/remove', {'date': self.day, 'timezone': request['timezone'],
            'revision': first['revision'], 'block': request['blocks'][0]})
        self.assertEqual(code, 200)
        self.assertEqual(self.call('/submit', stale)[0], 409)
        self.assertEqual(latest_plan(self.root, self.day, request['timezone'])['blocks'], [])
        request['base_revision'] = plan_revision(latest_plan(self.root, self.day, request['timezone']))
        self.assertEqual(self.call('/submit', request)[0], 200)

    def test_detached_workspace_migrates_tea_source_and_keeps_url_across_source_replacement(self):
        tea = publish(self.root, self.source('12:00'), 'tea-time')
        complete_refresh(self.root, tea['snapshot'])
        with tempfile.TemporaryDirectory() as session:
            output = Path(session) / 'workspace.html'
            launched = subprocess.run([sys.executable, str(SKILL / 'scripts/local_plan_server.py'), '--snapshot', tea['snapshot'],
                '--root', str(self.root), '--output', str(output), '--workspace', '--background'],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(launched.returncode, 0, launched.stderr)
            from urllib.parse import urlsplit
            info = json.loads(output.with_suffix('.session.json').read_text())
            target = urlsplit(info['url'])
            token = target.path.rsplit('/', 1)[-1]
            try:
                def call(path, body=None):
                    headers = {'X-Brief-Token': token}
                    if body is not None:
                        headers.update(Origin='http://' + target.netloc, **{'Content-Type': 'application/json'})
                    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
                    try:
                        connection.request('POST' if body is not None else 'GET', path,
                                           json.dumps(body) if body is not None else None, headers)
                        response = connection.getresponse()
                        result = response.read().decode()
                        return response.status, result
                    finally:
                        connection.close()
                status, body = call('/workspace/status')
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)['workspace']['version'], 2)
                request = {'date': self.day, 'timezone': 'America/Toronto', 'base_revision': None, 'blocks': [{'kind': 'dog_walk', 'start': 1200, 'minutes': 30}]}
                self.assertEqual(call('/submit', request)[0], 200, 'Unified Coffee can edit a plan from an archived Tea source')
                saved = latest_plan(self.root, self.day, 'America/Toronto')
                self.assertEqual(call('/plan/remove', dict(date=self.day, timezone='America/Toronto', revision=plan_revision(saved), block=request['blocks'][0]))[0], 200)
                self.assertEqual(latest_plan(self.root, self.day, 'America/Toronto')['blocks'], [])
                new = self.source('15:00')
                new['agenda']['events'][0]['title'] = 'Latest workspace event'
                published = publish(self.root, new, 'morning-coffee')
                complete_refresh(self.root, published['snapshot'])
                status, body = call(target.path)
                self.assertEqual(status, 200)
                self.assertIn('Latest workspace event', body)
                self.assertEqual(json.loads(call('/workspace/status')[1])['workspace']['version'], 3)
            finally:
                os.kill(info['pid'], signal.SIGTERM)
                deadline = time.monotonic() + 3
                while output.with_suffix('.session.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)


    def local_bridge(self):
        local = {'cli_path': '/synthetic/t3', 'node_path': '/synthetic/node',
                 'runtime_path': '/synthetic/userdata/server-runtime.json',
                 'thread_id': '12345678-1234-4123-8123-123456789abc'}
        workspace_state.configure_bridge(self.root, {'local_t3': local})
        return local


    def app_bridge(self):
        import socket
        temporary = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(temporary.cleanup)
        folder = Path(temporary.name)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(folder / 'app.sock'))
        (folder / 'app.sock').chmod(0o600)
        listener.listen(4)
        self.addCleanup(listener.close)
        cli = folder / 'codex'
        cli.write_text('#!' + sys.executable + '\n' + """
import json, sys
from pathlib import Path
Path(__file__).with_name('invocation.json').write_text(json.dumps(sys.argv[1:]))
print('Queued message 32345678-1234-4123-8123-123456789abc for thread ' + sys.argv[3] + '.')
""")
        cli.chmod(0o700)
        local = {'cli_path': str(cli), 'socket_path': str(folder / 'app.sock'),
                 'thread_id': '12345678-1234-4123-8123-123456789abc'}
        workspace_state.configure_bridge(self.root, {'local_codex_app': local,
            'webhook_url': 'https://example.invalid/never-fallback'})
        return local, folder, listener

    def test_codex_app_button_queues_once_and_adopts_exact_completion_with_local_work(self):
        local, folder, listener = self.app_bridge()
        archive = Path(self.first['snapshot']).read_bytes()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.call('/refresh', {}), range(2)))
        self.assertEqual(sum(body['created'] for _, body in responses), 1)
        state = self.wait_for('running')
        request_id = state['refresh']['id']
        invocation = json.loads((folder / 'invocation.json').read_text())
        self.assertEqual(invocation[:4], ['queue', '--thread', local['thread_id'], '--message'])
        self.assertEqual(len(invocation), 5)
        self.assertIn(request_id, invocation[4])
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Kept during app refresh'})[0], 200)
        fresh = self.source('12:00')
        checked = datetime.now(ZoneInfo('America/Toronto')).isoformat()
        fresh['collected_at'] = checked
        for source in fresh['sources'].values():
            source['checked_at'] = checked
        fresh['agenda']['events'][0]['title'] = 'Fresh app collection'
        published = publish(self.root, fresh, 'refresh')
        complete_refresh(self.root, published['snapshot'], request_id=request_id)
        self.assertEqual(self.status()['refresh']['status'], 'completed')
        page = self.call('/report/' + self.token)[1]
        self.assertIn('Fresh app collection', page)
        self.assertIn('Kept during app refresh', page)
        self.assertEqual(Path(self.first['snapshot']).read_bytes(), archive)
        public = json.dumps(self.status())
        self.assertNotIn(local['thread_id'], public)
        self.assertNotIn(local['socket_path'], public)

    def test_closed_codex_app_fails_without_webhook_fallback_and_local_saves_work(self):
        local, folder, listener = self.app_bridge()
        listener.close()
        with patch('local_plan_server.http.client.HTTPSConnection') as fallback:
            self.call('/refresh', {})
            self.wait_for('failed')
            fallback.assert_not_called()
        self.assertFalse((folder / 'invocation.json').exists())
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Kept with app closed'})[0], 200)
        self.assertIn('Kept with app closed', self.call('/report/' + self.token)[1])

    def test_local_bridge_dispatches_exact_request_without_exposing_private_config(self):
        local = self.local_bridge()
        entered, release = threading.Event(), threading.Event()
        calls = []
        def run(command, **kwargs):
            calls.append((command, json.loads(kwargs['input'])))
            entered.set()
            release.wait(3)
            return subprocess.CompletedProcess(command, 0, '{"ok":true}', '')
        try:
            with patch('local_plan_server.subprocess.run', side_effect=run):
                self.assertTrue(self.status()['bridge_configured'])
                _, result = self.call('/refresh', {})
                self.assertTrue(entered.wait(1))
                self.assertFalse(self.call('/refresh', {})[1]['created'])
                self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Work during local refresh'})[0], 200)
                release.set()
                self.wait_for('running')
        finally:
            release.set()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], [local['node_path'], str(SKILL / 'scripts/local_t3_refresh.js')])
        self.assertEqual(calls[0][1]['config'], local)
        self.assertEqual(calls[0][1]['request']['id'], result['workspace']['refresh']['id'])
        self.assertNotIn('/synthetic', self.call('/report/' + self.token)[1])
        self.assertNotIn('/synthetic', json.dumps(self.status()))


    def test_local_bridge_requires_success_ack_and_fails_safely(self):
        self.local_bridge()
        active = load_workspace(self.root)['active_snapshot']
        outcomes = [subprocess.CompletedProcess([], 1, '', 'private error'),
                    subprocess.CompletedProcess([], 0, '{"ok":false}', ''),
                    subprocess.CompletedProcess([], 0, '[]', ''),
                    subprocess.CompletedProcess([], 0, 'invalid json', ''),
                    subprocess.TimeoutExpired('synthetic-node', 15)]
        for outcome in outcomes:
            request = workspace_state.begin_refresh(self.root, 'refresh', self.day, 'America/Toronto')['request']
            with patch('local_plan_server.subprocess.run', side_effect=outcome if isinstance(outcome, Exception) else None,
                       return_value=outcome):
                dispatch_refresh(self.root, request)
            self.assertEqual(self.status()['refresh']['status'], 'failed')
            self.assertNotIn('private error', json.dumps(self.status()))
            self.assertEqual(load_workspace(self.root)['active_snapshot'], active)
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Still editable'})[0], 200)


    def codex_bridge(self, mode='complete'):
        cwd = self.root / 'collector project'
        cwd.mkdir(exist_ok=True)
        cli = cwd / 'synthetic codex'
        (self.root / 'codex-template.json').write_text(json.dumps(self.source('12:00')))
        result_path = self.root / 'codex-publication.json'
        # A real subprocess stands in for the model CLI, publishing only through
        # the same exact-ID durable API used by the actual collector.
        cli.write_text('#!' + sys.executable + '\n' + """
import json, os, sys, time
from pathlib import Path
sys.path.insert(0, SCRIPTS)
from workspace_state import complete_refresh, load_workspace, workspace_snapshot
from report_history import publish
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
prompt = sys.stdin.read()
root = Path(ROOT)
metadata = json.loads(next(line for line in prompt.splitlines() if 'exactly matches: ' in line).split('exactly matches: ', 1)[1][:-1])
(root / 'invocation.tmp').write_text(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), 'prompt': prompt, 'id': metadata['id'], 'pid': os.getpid()}))
(root / 'invocation.tmp').replace(root / 'invocation.json')
if MODE == 'wait':
    while not (root / 'release').exists():
        time.sleep(0.01)
if MODE in ('complete', 'wait'):
    state = load_workspace(root)
    previous = workspace_snapshot(root, state)
    collected = max(datetime.fromisoformat(state['refresh']['requested_at']), datetime.fromisoformat(previous['collected_at'])) + timedelta(microseconds=1)
    collected = collected.astimezone(ZoneInfo(metadata['timezone']))
    data = json.loads((root / 'codex-template.json').read_text())
    data['collected_at'] = collected.isoformat()
    data['report']['time'] = collected.strftime('%H:%M')
    for source in data['sources'].values():
        source['checked_at'] = collected.isoformat()
    published = publish(root, data, 'refresh')
    (root / 'codex-publication.json').write_text(json.dumps(published))
    complete_refresh(root, published['snapshot'], request_id=metadata['id'])
if MODE == 'fail':
    sys.stderr.write('private backend error token')
    sys.exit(1)
""".replace('SCRIPTS', repr(str(SKILL / 'scripts'))).replace('ROOT', repr(str(self.root))).replace('MODE', repr(mode)))
        cli.chmod(0o700)
        local = {'cli_path': str(cli), 'cwd': str(cwd), 'thread_id': '12345678-1234-4123-8123-123456789abc'}
        workspace_state.configure_bridge(self.root, {'local_codex': local})
        return local, result_path

    def test_codex_button_reruns_collector_and_reuses_report_with_local_choices(self):
        local, fresh = self.codex_bridge('wait')
        archive = Path(self.first['snapshot']).read_bytes()
        self.assertTrue(self.status()['bridge_configured'])
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(pool.map(lambda _: self.call('/refresh', {}), range(2)))
            self.assertEqual(sum(body['created'] for _, body in responses), 1)
            request_id = responses[0][1]['workspace']['refresh']['id']
            self.wait_for('running')
            self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Keep this commitment'})[0], 200)
            deadline = time.monotonic() + 3
            while not (self.root / 'invocation.json').exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            invocation = json.loads((self.root / 'invocation.json').read_text())
            self.assertEqual(invocation['id'], request_id)
            self.assertEqual(invocation['cwd'], str(Path(local['cwd']).resolve()))
            self.assertEqual(invocation['args'], ['exec', '--sandbox', 'workspace-write', '--cd', local['cwd'],
                '--add-dir', str(self.root.resolve()), 'resume', local['thread_id'], '-'])
            self.assertIn('Do not begin another request', invocation['prompt'])
        finally:
            (self.root / 'release').touch()
        self.wait_for('completed')
        fresh = json.loads(fresh.read_text())
        self.assertEqual(load_workspace(self.root)['active_snapshot'], str(Path(fresh['snapshot']).relative_to(self.root)))
        self.assertEqual(Path(self.first['snapshot']).read_bytes(), archive)
        page = self.call('/report/' + self.token)[1]
        self.assertIn('Keep this commitment', page)
        self.assertNotIn(local['thread_id'], page)
        self.assertNotIn(local['cli_path'], json.dumps(self.status()))

    def test_codex_exit_without_durable_completion_fails_even_with_exit_zero(self):
        active = load_workspace(self.root)['active_snapshot']
        for mode in ('fail', 'no-completion'):
            self.codex_bridge(mode)
            self.call('/refresh', {})
            self.wait_for('failed')
            self.assertNotIn('private backend', json.dumps(self.status()))
            self.assertEqual(load_workspace(self.root)['active_snapshot'], active)

    def test_codex_missing_executable_fails_without_blocking_local_work(self):
        local, _ = self.codex_bridge()
        Path(local['cli_path']).unlink()
        self.call('/refresh', {})
        self.wait_for('failed')
        self.assertEqual(self.call('/todo', {'action': 'add', 'title': 'Still editable'})[0], 200)

    def test_codex_timeout_kills_collector_and_preserves_snapshot(self):
        from local_codex_refresh import dispatch_codex_refresh
        local, _ = self.codex_bridge('wait')
        active = load_workspace(self.root)['active_snapshot']
        request = workspace_state.begin_refresh(self.root, 'refresh', self.day, 'America/Toronto')['request']
        dispatch_codex_refresh(self.root, request, local, 1.5)
        self.assertEqual(self.status()['refresh']['status'], 'failed')
        self.assertEqual(load_workspace(self.root)['active_snapshot'], active)
        invocation = json.loads((self.root / 'invocation.json').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(invocation['pid'], 0)

    def test_codex_stale_metadata_and_duplicate_dispatch_do_not_spawn(self):
        from local_codex_refresh import dispatch_codex_refresh
        local, _ = self.codex_bridge()
        request = workspace_state.begin_refresh(self.root, 'refresh', self.day, 'America/Toronto')['request']
        for key, value in [('id', '87654321-1234-4123-8123-123456789abc'), ('action', 'start_today'),
                           ('date', '2000-01-01'), ('timezone', 'UTC')]:
            dispatch_codex_refresh(self.root, dict(request, **{key: value}), local, 1)
        workspace_state.mark_dispatch(self.root, request['id'], True)
        dispatch_codex_refresh(self.root, request, local, 1)
        self.assertFalse((self.root / 'invocation.json').exists())
        self.assertEqual(self.status()['refresh']['status'], 'running')


    def test_codex_precedence_does_not_fall_through_on_collector_failure(self):
        local, _ = self.codex_bridge('fail')
        workspace_state.configure_bridge(self.root, {'local_codex': local,
            'local_t3': {'cli_path': '/synthetic/t3', 'node_path': '/synthetic/node',
                         'runtime_path': '/synthetic/runtime.json', 'thread_id': local['thread_id']},
            'webhook_url': 'http://127.0.0.1:1/should-not-be-called'})
        request = workspace_state.begin_refresh(self.root, 'refresh', self.day, 'America/Toronto')['request']
        with patch('local_plan_server.subprocess.run') as t3, patch('local_plan_server.http.client.HTTPConnection') as webhook:
            dispatch_refresh(self.root, request)
        self.assertEqual(self.status()['refresh']['status'], 'failed')
        t3.assert_not_called()
        webhook.assert_not_called()


if __name__ == '__main__':
    unittest.main()
