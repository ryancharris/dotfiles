"""Browser check for the static report's browser-held interactivity.

Needs Playwright and Google Chrome:  pip install playwright
Run: python3 tests/static_interactivity_browser_check.py
Renders two runs into a temp dir, then drives the report in Chrome and
asserts that todos, done marks and dismissals persist across reloads.
"""
import json, subprocess, sys, tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TZ = '-05:00'


def snapshot(reviews):
    return {'date': '2026-11-13', 'timezone': 'America/Toronto', 'collected_at': f'2026-11-13T09:00:00{TZ}',
            'sources': {'github': {'status': 'complete'}}, 'oncall': {}, 'incidents': [], 'slack': [], 'notion': [],
            'authored': [{'url': 'https://github.com/ryancharris/y/pull/2', 'title': 'Mine', 'repo': 'ryancharris/y',
                          'state': 'CI passing', 'draft': False, 'updated_at': '2026-11-12T00:00:00Z'}],
            'calendar': [{'id': 'e1', 'title': 'Team sync', 'start': f'2026-11-13T11:30:00{TZ}',
                          'end': f'2026-11-13T12:30:00{TZ}', 'url': 'https://calendar.google.com/x'}],
            'reviews': reviews}


def pr(n):
    return {'url': f'https://github.com/dbt-labs/x/pull/{n}', 'title': f'PR {n}', 'repo': 'dbt-labs/x', 'author': 'a',
            'updated_at': f'2026-11-1{n}T00:00:00Z', 'request': 'Direct'}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print('ok -', msg)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'tasks.md').write_text('- [ ] ship release\n- [x] reply to Sam\n')
        script = ROOT / 'scripts/morning_coffee.py'
        for n, reviews in ((1, [pr(1)]), (2, [pr(1), pr(2)])):
            snap = tmp / f's{n}.json'
            snap.write_text(json.dumps(snapshot(reviews)))
            subprocess.run([sys.executable, str(script), '--dir', str(tmp), str(snap)], check=True, capture_output=True)
        report = (tmp / 'report.html').resolve().as_uri()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME, headless=True)
            page = browser.new_page(accept_downloads=True)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(report)
            page.evaluate('localStorage.clear()')
            page.reload()

            # Todos: seeded from tasks.md, toggle, add, delete, persist.
            check(page.locator('#todo li').count() == 2, 'todos seeded from tasks.md')
            page.locator('#todo li').nth(0).locator('input[type=checkbox]').check()
            page.fill('#todo-add input[name=text]', 'write notes')
            page.click('#todo-add button[type=submit]')
            page.locator('#todo li').nth(1).locator('button[data-todo-delete]').click()
            page.reload()
            texts = page.locator('#todo li').all_inner_texts()
            check(any('write notes' in t for t in texts) and any('ship release' in t for t in texts),
                  f'added task and kept seeded task after reload: {texts}')
            check(not any('reply to Sam' in t for t in texts), 'deleted task stays deleted after reload')
            check(page.locator('#todo li input[type=checkbox]').nth(0).is_checked(), 'checked todo persists')

            # Done marks on calendar, PR review and authored PR rows.
            page.click('[data-mark-key^="cal:"] [data-mark-toggle]')
            REV1 = '[data-mark-key="rev:https://github.com/dbt-labs/x/pull/1"]'
            page.click(REV1 + ' [data-mark-toggle]')
            page.click('[data-mark-key^="mine:"] [data-mark-toggle]')
            page.reload()
            check(page.locator('[data-mark-key^="cal:"]').get_attribute('class') == 'is-done', 'calendar done persists')
            check(page.locator(REV1).get_attribute('class') == 'is-done', 'review done persists')
            check(page.locator('[data-mark-key^="mine:"]').get_attribute('class') == 'is-done', 'authored PR done persists')
            page.click(REV1 + ' [data-mark-toggle]')
            check(page.locator(REV1 + ' [data-mark-toggle]').inner_text() == 'Mark done locally',
                  'undo restores the review label')

            # Daily briefing: new-since-last-run item dismissal.
            new_row = page.locator('#new [data-mark-key]')
            check(new_row.count() == 1, 'one new item on second run')
            new_row.locator('[data-mark-toggle]').click()
            page.reload()
            check(page.locator('#new [data-mark-key]').get_attribute('class') == 'is-done', 'dismissed item persists')

            # Export downloads a tasks.md that the next run can read.
            with page.expect_download() as info:
                page.click('#todo-export')
            export = Path(info.value.path()).read_text()
            check('- [x] ship release' in export and '- [ ] write notes' in export and 'reply to Sam' not in export,
                  f'export matches todo state: {export!r}')

            check(not errors, f'no page errors: {errors}')
            browser.close()
    print('all static interactivity checks passed')


if __name__ == '__main__':
    main()
