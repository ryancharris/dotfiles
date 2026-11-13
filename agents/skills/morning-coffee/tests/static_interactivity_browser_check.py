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
import os
SHOTS = os.environ.get('MC_SCREENSHOTS', '')
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
            check(page.locator('#today-agenda [data-mark-key^="cal:"]').get_attribute('class').split()[-1] == 'is-done', 'calendar done persists')
            check(page.locator(REV1).get_attribute('class').split()[-1] == 'is-done', 'review done persists')
            check(page.locator('[data-mark-key^="mine:"]').get_attribute('class').split()[-1] == 'is-done', 'authored PR done persists')
            page.click(REV1 + ' [data-mark-toggle]')
            check(page.locator(REV1 + ' [data-mark-toggle]').inner_text() == 'Mark done locally',
                  'undo restores the review label')

            # Daily briefing: new-since-last-run item dismissal.
            new_row = page.locator('#new [data-mark-key]')
            check(new_row.count() == 1, 'one new item on second run')
            new_row.locator('[data-mark-toggle]').click()
            page.reload()
            check(page.locator('#new [data-mark-key]').get_attribute('class').split()[-1] == 'is-done', 'dismissed item persists')

            # Custom blocks in Today: add, overlap warning, move, delete, bounds, persistence.
            page.select_option('#block-form select[name=kind]', 'focus')
            page.fill('#block-form input[name=start]', '13:00')
            page.click('#block-form button[type=submit]')
            check(page.locator('#timeline .slot.block').count() == 1, 'focus block appears on the timeline')
            page.select_option('#block-form select[name=kind]', 'lunch')
            page.fill('#block-form input[name=start]', '13:30')
            page.click('#block-form button[type=submit]')
            check('Overlaps' in page.locator('#block-list').inner_text(), 'overlapping blocks are flagged')
            lunch_row = page.locator('#block-list .block-row').filter(has=page.locator('span.grow', has_text='Lunch ·'))
            lunch_row.locator('button[data-block-action=later]').click()
            check('13:45' in lunch_row.inner_text(), 'Later 15m moves the block')
            page.fill('#block-form input[name=start]', '18:45')
            page.click('#block-form button[type=submit]')
            check('must fit' in page.locator('#block-error').inner_text() or 'fit between' in page.locator('#block-error').inner_text(),
                  'a block outside 08:00-19:00 is refused')
            lunch_row.locator('button[data-block-action=delete]').click()
            page.reload()
            check(page.locator('#timeline .slot.block').count() == 1, 'deleted block stays deleted; focus block persists')
            check(page.locator('#timeline .slot.event').count() >= 1, 'calendar event is drawn on the timeline')

            # Presets: one click adds Lunch 30m, Dog walk 30m and Exercise 1h at the chosen start.
            page.fill('#block-form input[name=start]', '15:00')
            page.click('#block-presets button[data-preset=lunch]')
            lunch = page.locator('#block-list .block-row').filter(has=page.locator('span.grow', has_text='Lunch ·'))
            check('15:00–15:30 (30 min)' in lunch.inner_text(), 'Lunch preset adds a 30 min block at 15:00')
            page.fill('#block-form input[name=start]', '16:30')
            page.click('#block-presets button[data-preset=exercise]')
            check(page.locator('#block-list .block-row').filter(has=page.locator('span.grow', has_text='Exercise ·')).count() == 1
                  and '16:30–17:30 (60 min)' in page.locator('#block-list').inner_text(), 'Exercise preset adds a 1 hr block at 16:30')
            page.fill('#block-form input[name=start]', '17:30')
            page.click('#block-presets button[data-preset=dog-walk]')
            check('17:30–18:00 (30 min)' in page.locator('#block-list').inner_text(), 'Dog walk preset adds a 30 min block at 17:30')

            # Edit: title, start and length are all configurable on an existing block.
            row = page.locator('#block-list .block-row').filter(has=page.locator('span.grow', has_text='Lunch ·'))
            row.locator('button[data-block-action=edit]').click()
            edit = page.locator('form.block-edit')
            edit.locator('input[data-edit-title]').fill('Lunch with Sam')
            edit.locator('input[data-edit-start]').fill('12:15')
            edit.locator('select[data-edit-duration]').select_option('45')
            edit.locator('button[type=submit]').click()
            page.reload()
            check('Lunch with Sam · 12:15–13:00 (45 min)' in page.locator('#block-list').inner_text(), 'edit saves title, start and length after reload')
            check(page.locator('#timeline .slot.block', has_text='Lunch with Sam').count() == 1, 'edited block is redrawn on the timeline')
            page.locator('#block-list .block-row').filter(has=page.locator('span.grow', has_text='Lunch with Sam')).locator('button[data-block-action=edit]').click()
            page.locator('form.block-edit input[data-edit-start]').fill('18:50')
            page.locator('form.block-edit button[type=submit]').click()
            check(page.locator('form.block-edit').count() == 1 and 'fit between' in page.locator('#mc-status').inner_text(),
                  'edit past 19:00 is refused and stays in edit mode')
            page.locator('form.block-edit button[data-block-cancel]').click()
            check(page.locator('form.block-edit').count() == 0, 'cancel leaves edit mode without changes')
            page.reload()
            check('Lunch with Sam · 12:15–13:00' in page.locator('#block-list').inner_text(), 'cancelled edit leaves the saved block unchanged')

            # Timeline event toggles done from the slot too.
            before = 'is-done' in (page.locator('#timeline .slot.event').first.get_attribute('class') or '')
            page.click('#timeline .slot.event')
            page.reload()
            after = 'is-done' in (page.locator('#timeline .slot.event').first.get_attribute('class') or '')
            check(before != after, f'timeline slot done mark toggles and persists ({before} -> {after})')

            # Mobile width: no horizontal page scroll.
            page.set_viewport_size({'width': 390, 'height': 844})
            page.reload()
            overflow = page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
            check(overflow <= 0, f'no horizontal scroll at 390px (overflow {overflow}px)')
            page.screenshot(path=str(tmp / 'mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1280, 'height': 900})
            page.reload()
            page.screenshot(path=str(tmp / 'desktop.png'), full_page=True)
            if SHOTS:
                Path(SHOTS).mkdir(parents=True, exist_ok=True)
                for name in ('mobile.png', 'desktop.png'):
                    (Path(SHOTS) / name).write_bytes((tmp / name).read_bytes())

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
