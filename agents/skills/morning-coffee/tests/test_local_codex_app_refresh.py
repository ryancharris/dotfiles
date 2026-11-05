"""Exercise the desktop queue through real private sockets and subprocesses."""
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_codex_app_refresh import collection_prompt, dispatch_codex_app_refresh
from workspace_state import _validate_bridge_config

THREAD = '12345678-1234-4123-8123-123456789abc'
REQUEST = dict(id='22345678-1234-4123-8123-123456789abc', action='refresh',
               date='2026-11-05', timezone='America/Toronto')


class CodexAppRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/tmp')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.root / 'app.sock'))
        (self.root / 'app.sock').chmod(0o600)
        self.socket.listen(4)
        self.addCleanup(self.socket.close)
        cli = self.root / 'codex'
        cli.write_text('#!' + sys.executable + '\n' + '''
import json, sys
from pathlib import Path
Path(__file__).with_name('invocation.json').write_text(json.dumps(sys.argv[1:]))
print('Queued message 32345678-1234-4123-8123-123456789abc for thread ' + sys.argv[3] + '.')
''')
        cli.chmod(0o700)
        self.config = dict(cli_path=str(cli), socket_path=str(self.root / 'app.sock'), thread_id=THREAD)
        self.state = patch('local_codex_app_refresh.load_workspace', return_value={'refresh': dict(REQUEST, status='pending')})
        self.state.start()
        self.addCleanup(self.state.stop)

    def test_queues_fixed_prompt_without_resuming_or_starting_any_backend(self):
        self.assertTrue(dispatch_codex_app_refresh(self.root, dict(REQUEST, prompt='UNTRUSTED', root='/untrusted'), self.config))
        args = json.loads((self.root / 'invocation.json').read_text())
        self.assertEqual(args[:4], ['queue', '--thread', THREAD, '--message'])
        self.assertEqual(len(args), 5)
        self.assertIn(REQUEST['id'], args[4])
        self.assertIn(str(self.root.resolve()), args[4])
        self.assertIn('Do not begin another request', args[4])
        self.assertNotIn('UNTRUSTED', args[4])
        self.assertNotIn('/untrusted', args[4])

    def test_offline_or_unsafe_app_socket_never_queues_a_message(self):
        self.socket.close()
        with self.assertRaises(OSError):
            dispatch_codex_app_refresh(self.root, REQUEST, self.config)
        self.assertFalse((self.root / 'invocation.json').exists())
        (self.root / 'app.sock').chmod(0o666)
        self.assertFalse(dispatch_codex_app_refresh(self.root, REQUEST, self.config))
        self.assertFalse((self.root / 'invocation.json').exists())

    def test_stale_request_never_connects_or_queues(self):
        with patch('local_codex_app_refresh.load_workspace', return_value={'refresh': dict(REQUEST, status='completed')}):
            self.assertFalse(dispatch_codex_app_refresh(self.root, REQUEST, self.config))
        self.assertFalse((self.root / 'invocation.json').exists())

    def test_requires_matching_queue_acknowledgement(self):
        from subprocess import CompletedProcess
        for code, output in [(1, 'private backend failure'), (0, 'Queued.'),
                             (0, 'Queued message 32345678-1234-4123-8123-123456789abc for thread other.')]:
            with patch('local_codex_app_refresh.subprocess.run', return_value=CompletedProcess([], code, output, 'private error')):
                self.assertFalse(dispatch_codex_app_refresh(self.root, REQUEST, self.config))

    def test_config_requires_fixed_local_binding(self):
        self.assertEqual(_validate_bridge_config({'local_codex_app': self.config})['local_codex_app'], self.config)
        for patch_value in (dict(cli_path='relative'), dict(thread_id='invalid'), dict(socket_path='https://remote'), dict(command='arbitrary')):
            with self.assertRaises(ValueError):
                _validate_bridge_config({'local_codex_app': dict(self.config, **patch_value)})
        with self.assertRaises(ValueError):
            collection_prompt(self.root, dict(REQUEST, action='arbitrary'))


if __name__ == '__main__':
    unittest.main()
