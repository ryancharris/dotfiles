"""Exercise the delivered browser session after its launching command has exited."""
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import urlsplit

from test_report_history import ReportSurface, snapshot

SERVER = Path(__file__).resolve().parents[1] / 'scripts' / 'local_plan_server.py'


class LocalSessionTests(unittest.TestCase):
    def test_restart_keeps_existing_report_url_token_and_saved_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'snapshot.json'
            source.write_text(json.dumps(snapshot()))
            resume = folder / 'resume.json'
            pid = None
            try:
                def launch(name, reuse=False):
                    output = folder / (name + '.html')
                    command = [sys.executable, str(SERVER), '--snapshot', str(source), '--output', str(output),
                               '--root', str(folder / 'store'), '--background']
                    if reuse:
                        command += ['--resume-session', str(resume)]
                    result = subprocess.run(command, capture_output=True, text=True, timeout=20)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return json.loads(output.with_suffix('.session.json').read_text())

                initial = launch('first')
                pid = initial['pid']
                resume.write_text(json.dumps(initial))
                resume.chmod(0o600)
                target = urlsplit(initial['url'])
                capability = target.path.rsplit('/', 1)[-1]

                def post(done):
                    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
                    connection.request('POST', '/review', json.dumps({'kind': 'pr', 'url': snapshot()['reviews']['items'][0]['url'], 'done': done}),
                                       {'Origin': 'http://' + target.netloc, 'Content-Type': 'application/json', 'X-Brief-Token': capability})
                    response = connection.getresponse()
                    result = response.status, json.loads(response.read())
                    connection.close()
                    return result

                self.assertEqual(post(True)[0], 200)
                os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + 3
                while (folder / 'first.session.json').exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                replacement = launch('second', True)
                pid = replacement['pid']
                self.assertEqual(replacement['url'], initial['url'])
                connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
                connection.request('GET', target.path)
                response = connection.getresponse()
                page = response.read().decode()
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertIn('data-review-done="true"', page)
                self.assertFalse(post(False)[1]['record']['done'])
            finally:
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

    def test_detached_coffee_and_tea_save_reload_and_undo_after_launcher_exits(self):
        for tea in (False, True):
            with self.subTest(tea=tea), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                data = snapshot()
                if tea:
                    data['history'] = {'kind': 'tea-time'}
                    data['report']['title'] = 'Tea Time'
                source, output = folder / 'snapshot.json', folder / 'session.html'
                source.write_text(json.dumps(data))
                original = source.read_bytes()
                launched = subprocess.run([sys.executable, str(SERVER), '--snapshot', str(source),
                                           '--output', str(output), '--root', str(folder / 'store'),
                                           '--background'], capture_output=True, text=True, timeout=20)
                self.assertEqual(launched.returncode, 0, launched.stderr)
                metadata = output.with_suffix('.session.json')
                info = json.loads(metadata.read_text())
                target = urlsplit(info['url'])
                try:
                    self.assertEqual(os.getsid(info['pid']), info['pid'])
                    self.assertNotEqual(info['pid'], os.getpid())
                    for file in (output, metadata, output.with_suffix('.log')):
                        self.assertEqual(file.stat().st_mode & 0o777, 0o600)

                    def request(method='GET', path=None, payload=None, **headers):
                        connection = http.client.HTTPConnection(target.hostname, target.port, timeout=3)
                        try:
                            connection.request(method, path or target.path,
                                               json.dumps(payload) if payload is not None else None, headers)
                            response = connection.getresponse()
                            return response.status, response.read().decode(), dict(response.getheaders())
                        finally:
                            connection.close()

                    status, page, headers = request()
                    self.assertEqual(status, 200)
                    self.assertEqual(headers['Cache-Control'], 'no-store')
                    self.assertEqual(headers['Referrer-Policy'], 'no-referrer')
                    surface = ReportSurface(page)
                    config_node = next(n for n in surface.elements()
                                       if n['attrs'].get('class') == 'review-interaction-data')
                    config = json.loads(config_node['children'][0])
                    auth = {'Origin': 'http://' + target.netloc, 'Content-Type': 'application/json',
                            'X-Brief-Token': config['token']}
                    pr = {'kind': 'pr', 'url': data['reviews']['items'][0]['url'], 'done': True}
                    self.assertEqual(request(path='/')[0], 404)
                    self.assertEqual(request(path=target.path + '?extra=1')[0], 404)
                    self.assertEqual(request(Host='evil.example')[0], 404)
                    self.assertEqual(request('POST', '/review', pr, **dict(auth, Origin='https://evil.example'))[0], 403)
                    self.assertEqual(request('POST', '/review', pr, **dict(auth, **{'X-Brief-Token': 'wrong'}))[0], 403)
                    self.assertEqual(list((folder / 'store').rglob('*.json')), [])
                    status, body, headers = request('POST', '/review', pr, **auth)
                    self.assertEqual(status, 200)
                    self.assertEqual(headers['Access-Control-Allow-Origin'], auth['Origin'])
                    self.assertTrue(json.loads(body)['record']['done'])

                    def persisted_done():
                        surface = ReportSurface(request()[1])
                        row = next(n for n in surface.elements() if n['attrs'].get('data-review-kind') == 'pr')
                        return row['attrs']['data-review-done']

                    self.assertEqual(persisted_done(), 'true')
                    self.assertEqual(request('POST', '/review', dict(pr, done=False), **auth)[0], 200)
                    self.assertEqual(persisted_done(), 'false')
                    # The file/inline fallback still uses its opaque null origin.
                    rfc = {'kind': 'rfc', 'url': data['rfcs']['items'][0]['url'], 'done': True}
                    self.assertEqual(request('POST', '/review', rfc, **dict(auth, Origin='null'))[0], 200)
                    add = {'action': 'add', 'title': 'Shared local task', 'due_date': data['report']['date']}
                    self.assertEqual(request('POST', '/todo', add, **dict(auth, Origin='https://evil.example'))[0], 403)
                    status, body, _ = request('POST', '/todo', add, **auth)
                    self.assertEqual(status, 200)
                    task = json.loads(body)['item']
                    self.assertIn('Shared local task', request()[1])
                    for action, fields, expected in [
                        ('complete', {}, 'completed'), ('cancel', {}, 'cancelled'),
                        ('reschedule', {'due_date': '2026-10-21'}, 'pending'), ('remove', {}, 'removed')]:
                        status, body, _ = request('POST', '/todo', {'action': action, 'id': task['id'], **fields}, **auth)
                        self.assertEqual(status, 200)
                        self.assertEqual(json.loads(body)['item']['status'], expected)
                    self.assertNotIn('Shared local task', request()[1])
                    if tea:
                        self.assertEqual(request('POST', '/submit', {'blocks': []}, **auth)[0], 403)
                    self.assertEqual(source.read_bytes(), original)
                finally:
                    os.kill(info['pid'], signal.SIGTERM)
                    deadline = time.monotonic() + 3
                    while metadata.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertFalse(metadata.exists())
                    self.assertFalse(output.exists())

    def test_failed_background_start_reports_failure_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source, output = folder / 'broken.json', folder / 'session.html'
            source.write_text('{')
            launched = subprocess.run([sys.executable, str(SERVER), '--snapshot', str(source),
                                       '--output', str(output), '--background'],
                                      capture_output=True, text=True, timeout=20)
            self.assertNotEqual(launched.returncode, 0)
            self.assertIn('did not start', launched.stderr)
            self.assertEqual(source.read_text(), '{')
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.session.json').exists())


if __name__ == '__main__':
    unittest.main()
