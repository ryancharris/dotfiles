"""Authored open PRs remain distinct from review requests and survive refreshes."""
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from render_brief import render
from report_history import changes, reconcile
from test_report_history import ReportSurface, snapshot


SKILL = Path(__file__).resolve().parents[1]


def with_authored():
    data = snapshot()
    row = deepcopy(data['reviews']['items'][0])
    for field in ('queue', 'teams', 'authorOnTransport'):
        row.pop(field, None)
    row.update(url='https://github.com/dbt-labs/example-fixture/pull/77', number=77,
               title='Synthetic authored draft', isDraft=True,
               updatedAt='2026-10-19T13:00:00-04:00')
    data['authored_prs'] = {
        'collected_label': '09:00 EDT',
        'coverage': 'Synthetic authored coverage.',
        'scopes': [{'label': 'Authored scope', 'url': 'https://github.com/pulls?q=author%3Afixture'}],
        'items': [row],
    }
    return data


class AuthoredPrTests(unittest.TestCase):
    def test_renderer_has_accessible_distinct_tabs_and_no_local_done_for_authored(self):
        page = render(with_authored())
        surface = ReportSurface(page)
        section = surface.by_id['reviews-waiting']
        tabs = [node for node in surface.elements(section) if node['attrs'].get('role') == 'tab']
        self.assertEqual([' '.join(surface.visible_text(node).split()) for node in tabs], ['Reviews waiting 1', 'My open PRs 1'])
        self.assertEqual([node['attrs']['aria-selected'] for node in tabs], ['true', 'false'])
        self.assertEqual([node['attrs']['aria-controls'] for node in tabs], ['pr-panel-reviews', 'pr-panel-authored'])
        authored = surface.by_id['pr-panel-authored']
        self.assertIn('Synthetic authored draft', surface.visible_text(authored))
        self.assertIn('DRAFT', surface.visible_text(authored))
        self.assertFalse(any('data-local-review' in node['attrs'] for node in surface.elements(authored)))
        self.assertNotIn('Review progress', surface.visible_text(authored))
        self.assertNotIn('hidden', authored['attrs'])

    def test_incomplete_github_refresh_retains_authored_rows_and_reports_changes(self):
        previous = with_authored()
        current = with_authored()
        current['collected_at'] = '2026-10-19T14:00:00-04:00'
        current['sources']['github']['status'] = 'partial'
        current['authored_prs']['items'] = []
        retained = reconcile(current, previous)
        self.assertEqual([row['number'] for row in retained['authored_prs']['items']], [77])
        self.assertIn('My open PRs', retained['stale_sections'])

        missing = with_authored()
        missing['collected_at'] = current['collected_at']
        missing['sources']['github']['status'] = 'partial'
        missing.pop('authored_prs')
        retained_missing = reconcile(missing, previous)
        self.assertEqual([row['number'] for row in retained_missing['authored_prs']['items']], [77])
        self.assertEqual(retained_missing['authored_prs']['scopes'], previous['authored_prs']['scopes'])

        updated = with_authored()
        updated['authored_prs']['items'][0]['isDraft'] = False
        updates = changes(updated, previous)
        authored = [row for row in updates if row['section'] == 'My open PRs']
        self.assertEqual(len(authored), 1)
        self.assertEqual(authored[0]['status'], 'Updated')

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for tab keyboard tests')
    def test_tabs_support_click_arrows_home_and_end(self):
        script = r'''
const assert=require('node:assert/strict');
global.window={location:{hash:''},addEventListener(){}};
const {mount}=require(process.argv[1]+'/assets/brief.js');
class Element {
  constructor(id=''){this.id=id;this.attrs={};this.listeners={};this.hidden=false;this.tabIndex=0;}
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
  fire(type,event={}){for(const fn of this.listeners[type]||[])fn({preventDefault(){event.prevented=true;},...event});}
  setAttribute(name,value){this.attrs[name]=String(value);}
  getAttribute(name){return this.attrs[name];}
  focus(){this.focused=true;}
  closest(){return section;}
}
const section=new Element('reviews-waiting'),tabs=[new Element('pr-tab-reviews'),new Element('pr-tab-authored')];
tabs[0].attrs={role:'tab','aria-controls':'pr-panel-reviews','aria-selected':'true'};
tabs[1].attrs={role:'tab','aria-controls':'pr-panel-authored','aria-selected':'false'};
const panels={'pr-panel-reviews':new Element(),'pr-panel-authored':new Element()};
const tablist=new Element();tablist.querySelectorAll=()=>tabs;
const doc={briefHashMounted:false,getElementById:id=>panels[id],querySelectorAll:q=>q==='.pr-tabs'?[tablist]:[]};
mount(doc);
assert.equal(tablist.hidden,false);assert.equal(panels['pr-panel-reviews'].hidden,false);assert.equal(panels['pr-panel-authored'].hidden,true);
tabs[1].fire('click');assert.equal(tabs[1].attrs['aria-selected'],'true');assert.equal(panels['pr-panel-authored'].hidden,false);
tabs[1].fire('keydown',{key:'ArrowLeft'});assert.equal(tabs[0].attrs['aria-selected'],'true');assert.equal(tabs[0].focused,true);
tabs[0].fire('keydown',{key:'End'});assert.equal(tabs[1].attrs['aria-selected'],'true');
tabs[1].fire('keydown',{key:'Home'});assert.equal(tabs[0].attrs['aria-selected'],'true');
assert.equal(section.getPrTabState(),'pr-tab-reviews');section.restorePrTabState('pr-tab-authored');assert.equal(section.getPrTabState(),'pr-tab-authored');
'''
        result = subprocess.run(['node', '-e', script, str(SKILL)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
