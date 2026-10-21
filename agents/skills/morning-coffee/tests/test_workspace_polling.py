"""Exercise browser polling lifecycle with controlled visibility, network and timers."""
from pathlib import Path
import shutil
import subprocess
import unittest


class WorkspacePollingTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node needed for workspace polling')
    def test_polling_lifecycle(self):
        subprocess.run(['node', '--test', str(Path(__file__).with_suffix('.js'))], check=True,
                       capture_output=True, text=True)

    @unittest.skipUnless(shutil.which('node'), 'Node needed for local T3 refresh')
    def test_local_refresh_transport(self):
        subprocess.run(['node', '--test', str(Path(__file__).with_name('test_local_t3_refresh.js'))], check=True,
                       capture_output=True, text=True)
