import json, subprocess, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import morning_coffee as mc

TZ = '-05:00'


def snap(**kw):
    base = {'date': '2026-11-13', 'timezone': 'America/Toronto', 'collected_at': f'2026-11-13T09:00:00{TZ}',
            'sources': {'github': {'status': 'complete'}, 'slack': {'status': 'skipped', 'note': 'not connected'}},
            'calendar': [], 'reviews': [], 'authored': [], 'incidents': [], 'slack': [], 'notion': [],
            'oncall': {}}
    base.update(kw)
    return base


def pr(n, **kw):
    return {'url': f'https://github.com/dbt-labs/x/pull/{n}', 'title': f'PR {n}', 'repo': 'dbt-labs/x',
            'author': 'a', 'updated_at': f'2026-11-0{n}T00:00:00Z', 'request': 'Direct', **kw}


class Tasks(unittest.TestCase):
    def test_parses_checklist_only(self):
        t = mc.parse_tasks('# h\n- [ ] one\n- [x] two\n- [X] three\n- plain\n-[ ] bad\n  - [ ] nested')
        self.assertEqual(t, [(False, 'one'), (True, 'two'), (True, 'three'), (False, 'nested')])


class Diff(unittest.TestCase):
    def test_first_run_has_no_diff(self):
        self.assertEqual(mc.new_items(None, snap(reviews=[pr(1)])), [])

    def test_new_and_unchanged(self):
        prev = snap(reviews=[pr(1)])
        cur = snap(reviews=[pr(1), pr(2)])
        self.assertEqual([i['title'] for _, i in mc.new_items(prev, cur)], ['PR 2'])

    def test_state_change_resurfaces_authored_pr(self):
        a = {'url': 'https://github.com/dbt-labs/x/pull/9', 'title': 'mine', 'state': 'CI passing'}
        got = mc.new_items(snap(authored=[a]), snap(authored=[{**a, 'state': 'CI failing'}]))
        self.assertEqual(len(got), 1)

    def test_timestamp_noise_is_not_new(self):
        self.assertEqual(mc.new_items(snap(reviews=[pr(1)]), snap(reviews=[pr(1, updated_at='2026-11-12T00:00:00Z')])), [])


class OnCall(unittest.TestCase):
    def shift(self, s, e):
        return {'next_shift': {'start': f'{s}{TZ}', 'end': f'{e}{TZ}'}}

    def now(self, t):
        return datetime.fromisoformat(f'{t}{TZ}')

    def test_inside_shift(self):
        r = mc.oncall_alert({'current_shift': {'start': f'2026-11-13T08:00:00{TZ}', 'end': f'2026-11-13T17:00:00{TZ}'}}, self.now('2026-11-13T09:00:00'))
        self.assertEqual(r[0], 'On call now')

    def test_within_24h_before(self):
        r = mc.oncall_alert(self.shift('2026-11-14T08:00:00', '2026-11-15T08:00:00'), self.now('2026-11-13T09:00:00'))
        self.assertEqual(r[0], 'On call soon')

    def test_further_out_or_over_is_hidden(self):
        self.assertIsNone(mc.oncall_alert(self.shift('2026-11-20T08:00:00', '2026-11-21T08:00:00'), self.now('2026-11-13T09:00:00')))
        self.assertIsNone(mc.oncall_alert({}, self.now('2026-11-13T09:00:00')))


class Render(unittest.TestCase):
    def test_sections_order_and_escaping(self):
        s = snap(calendar=[
            {'id': '2', 'title': '<b>Sync</b>', 'start': f'2026-11-13T11:30:00{TZ}', 'end': f'2026-11-13T12:30:00{TZ}', 'tentative': True},
            {'id': '1', 'title': 'PTO', 'all_day': True, 'start': '2026-11-13', 'end': '2026-11-14'}],
            reviews=[pr(3), pr(1)], authored=[{'url': 'javascript:alert(1)', 'title': 'x', 'state': 'ok'}])
        h = mc.render(s, None, '- [ ] ship\n- [x] done')
        self.assertLess(h.index('PTO'), h.index('11:30–12:30'))
        self.assertIn('&lt;b&gt;Sync&lt;/b&gt;', h)
        self.assertNotIn('<b>Sync</b>', h)
        self.assertNotIn('href="javascript', h)
        self.assertLess(h.index('PR 1'), h.index('PR 3'))   # oldest first
        self.assertIn('☐ ship', h); self.assertIn('☑ done', h)
        self.assertNotIn('id=new', h)                        # hidden on first run
        self.assertIn('Coverage limits: slack: skipped — not connected', h)

    def test_new_section_on_second_run(self):
        h = mc.render(snap(reviews=[pr(1), pr(2)]), snap(reviews=[pr(1)]), '')
        self.assertIn('New since last run (1)', h)


class Grouping(unittest.TestCase):
    def test_reviews_group_by_repo_with_request_icons(self):
        a = {**pr(1), 'repo': 'dbt-labs/a', 'request': 'Direct'}
        b = {**pr(2), 'repo': 'dbt-labs/b', 'request': 'Team'}
        c = {**pr(3), 'repo': 'dbt-labs/a', 'request': 'Team'}
        h = mc.render(snap(reviews=[b, a, c]), None, '')
        self.assertEqual(h.count('class="repo-group"'), 3)   # a(direct), then b and a(team) in other requests
        self.assertLess(h.index('dbt-labs/a'), h.index('dbt-labs/b'))   # busiest repo first
        self.assertIn('👤 Direct', h); self.assertIn('👥 Team', h)
        self.assertLess(h.index('PR 1'), h.index('PR 3'))                # oldest first inside a group

    def test_team_badge_names_every_matching_team(self):
        h = mc.render(snap(reviews=[{**pr(4), 'request': 'Team', 'teams': ['transport', 'ops-platform']}]), None, '')
        self.assertIn('req-team', h); self.assertIn('transport, ops-platform', h)

    def test_sections_order_transport_then_direct_then_other(self):
        t = {**pr(1), 'transport': True, 'request': 'Team', 'teams': ['transport']}
        d = {**pr(2), 'request': 'Direct'}
        o = {**pr(3), 'request': 'Team', 'teams': ['ops-platform']}
        h = mc.render(snap(reviews=[o, d, t]), None, '')
        self.assertLess(h.index('Transport team authors'), h.index('Direct requests'))
        self.assertLess(h.index('Direct requests'), h.index('Other team requests'))
        self.assertLess(h.index('PR 1'), h.index('PR 2'))
        self.assertLess(h.index('PR 2'), h.index('PR 3'))

    def test_drafts_are_filtered_from_both_lists(self):
        h = mc.render(snap(reviews=[{**pr(4), 'draft': True}], authored=[{'url': 'https://github.com/x/y/pull/9', 'title': 'Draft mine', 'draft': True, 'state': 'Draft'}]), None, '')
        self.assertNotIn('PR 4', h); self.assertNotIn('Draft mine', h)

    def test_line_counts_and_tldr_shown_or_marked_unavailable(self):
        h = mc.render(snap(reviews=[{**pr(5), 'request': 'Direct', 'additions': 39, 'deletions': 134, 'tldr': 'Removes old okta entries.'},
                                    {**pr(6), 'request': 'Direct'}]), None, '')
        self.assertIn('+39', h); self.assertIn('−134', h); self.assertIn('Removes old okta entries.', h)
        self.assertIn('+? −?', h); self.assertIn('TL;DR unavailable from PR metadata.', h)
        self.assertNotIn('Review effort', h); self.assertNotIn('mergeable', h.lower())

    def test_unknown_request_is_labelled_not_guessed(self):
        self.assertIn('❔', mc._request_badge(None))


class Seed(unittest.TestCase):
    def test_timed_events_carry_minutes_and_all_day_do_not(self):
        s = snap(calendar=[
            {'id': '1', 'title': 'Sync', 'start': f'2026-11-13T11:30:00{TZ}', 'end': f'2026-11-13T12:30:00{TZ}'},
            {'id': '2', 'title': 'PTO', 'all_day': True, 'start': '2026-11-13', 'end': '2026-11-14'}])
        h = mc.render(s, None, '')
        seed = json.loads(h.split('id="mc-seed" type="application/json">')[1].split('</script>')[0].replace('\\u003c', '<'))
        timed = [e for e in seed['events'] if not e['all_day']][0]
        self.assertEqual((timed['start_min'], timed['end_min']), (690, 750))
        self.assertEqual(seed['window'], [480, 1140])
        self.assertNotIn('start_min', [e for e in seed['events'] if e['all_day']][0])

    def test_script_cannot_close_itself_from_event_titles(self):
        s = snap(calendar=[{'id': '1', 'title': '</script><img src=x onerror=alert(1)>',
                            'start': f'2026-11-13T11:30:00{TZ}', 'end': f'2026-11-13T12:30:00{TZ}'}])
        h = mc.render(s, None, '')
        self.assertNotIn('</script><img', h)
        self.assertEqual(h.count('</script>'), 2)   # seed + script only

class Cli(unittest.TestCase):
    def test_end_to_end_two_runs(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); f = d / 's.json'; out = d / 'state'
            run = lambda: subprocess.run([sys.executable, str(ROOT / 'scripts/morning_coffee.py'), '--dir', str(out), str(f)],
                                         capture_output=True, text=True, check=True).stdout
            f.write_text(json.dumps(snap(reviews=[pr(1)])))
            self.assertIn('new: 0', run())
            (out / 'tasks.md').write_text('- [ ] keep me')
            f.write_text(json.dumps(snap(reviews=[pr(1), pr(2)])))
            self.assertIn('new: 1', run())
            html = (out / 'report.html').read_text()
            self.assertIn('keep me', html); self.assertIn('PR 2', html)


if __name__ == '__main__':
    unittest.main()
