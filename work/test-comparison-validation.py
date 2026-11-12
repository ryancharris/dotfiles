"""Regression: a partial hard gate cannot be labelled a pass."""
import json, shutil, subprocess, tempfile
from pathlib import Path
source=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='ade-negative-') as folder:
 root=Path(folder)
 shutil.copy2(source/'validate-comparison.py',root/'validate-comparison.py')
 manifest=json.loads((source/'comparison-grades.json').read_text())
 manifest['apps']['Paseo']['status']='passed'
 manifest['apps']['Paseo']['grades']['h3_terminal_setup']['grade']='partial'
 (root/'comparison-grades.json').write_text(json.dumps(manifest))
 run=subprocess.run(['python3',str(root/'validate-comparison.py')],capture_output=True,text=True,timeout=45)
 assert run.returncode!=0 and 'passing app has an incomplete hard or entry gate' in run.stderr,run.stderr
 print('PASS: validator rejects a claimed passing app with a partial hard requirement')
