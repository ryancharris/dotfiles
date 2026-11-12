"""Regressions: keep three recommendations without inventing qualification."""
import copy, json, shutil, subprocess, tempfile
from pathlib import Path

source = Path(__file__).resolve().parent
baseline = json.loads((source / 'comparison-grades.json').read_text())

def false_pass(manifest):
    manifest['apps']['Paseo']['status'] = 'passed'
    manifest['apps']['Paseo']['grades']['h3_terminal_setup']['grade'] = 'partial'

def missing_pick(manifest):
    manifest['ranking']['personal'] = ['Paseo', 'Sheprd']

def failed_pick(manifest):
    manifest['ranking']['personal'] = ['Paseo', 'Sheprd', 'Orca']

cases = [
    (false_pass, 'passing app has an incomplete hard or entry gate'),
    (missing_pick, 'exactly three recommendations are required'),
    (failed_pick, 'failed app cannot be recommended'),
]
for mutate, expected in cases:
    with tempfile.TemporaryDirectory(prefix='ade-negative-') as folder:
        root = Path(folder)
        shutil.copy2(source / 'validate-comparison.py', root / 'validate-comparison.py')
        manifest = copy.deepcopy(baseline)
        mutate(manifest)
        (root / 'comparison-grades.json').write_text(json.dumps(manifest))
        run = subprocess.run(['python3', str(root / 'validate-comparison.py')], capture_output=True, text=True, timeout=45)
        assert run.returncode != 0 and expected in run.stderr, run.stderr
        print('PASS: rejects ' + mutate.__name__)
