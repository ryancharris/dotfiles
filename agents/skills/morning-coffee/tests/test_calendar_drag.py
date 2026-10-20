"""Run the focused pointer and keyboard interaction suite in normal discovery."""
from pathlib import Path
import shutil
import subprocess
import unittest


class CalendarDragTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for planner interaction tests')
    def test_drag_and_keyboard_interactions(self):
        result = subprocess.run(
            ['node', '--test', str(Path(__file__).with_suffix('.js'))],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
