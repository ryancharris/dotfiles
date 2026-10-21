"""Keep the browser tab date consistent with an in-place source rollover."""
from pathlib import Path
import shutil
import subprocess
import unittest

SKILL = Path(__file__).resolve().parents[1]


class WorkspaceTitleTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for workspace interaction tests')
    def test_rollover_patches_header_and_browser_title_together(self):
        script = r'''
const assert = require('node:assert/strict');
const {patchWorkspace} = require(process.argv[1]+'/assets/workspace.js');
function page(date) {
  const nodes = new Map();
  const selectors=['.shop-sign','.world-status','#workspace-coverage','#what-changed','#today','#on-call','#daily-priorities','#rfcs-to-review','#reviews-waiting','#yesterday','#source-notes','#focus-exercise','.workspace-state-data'];
  const doc={
    title:'Morning Coffee · '+date,
    activeElement:null,
    defaultView:{scrollX:0,scrollY:0,scrollTo(){}},
    querySelector(selector){return nodes.get(selector)||null;},
    querySelectorAll(){return [];},
    importNode(node){return {...node};},
  };
  for(const selector of selectors)nodes.set(selector,{
    textContent:selector==='.workspace-state-data'?JSON.stringify({date}):date,
    hidden:true,
    querySelector(){return null;},
    querySelectorAll(){return [];},
    replaceWith(replacement){nodes.set(selector,replacement);},
  });
  return doc;
}
const old=page('2026-10-20'),fresh=page('2026-10-21');
patchWorkspace(old,fresh);
assert.equal(old.querySelector('.shop-sign').textContent,'2026-10-21');
assert.equal(JSON.parse(old.querySelector('.workspace-state-data').textContent).date,'2026-10-21');
assert.equal(old.title,'Morning Coffee · 2026-10-21');
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
