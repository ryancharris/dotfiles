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
