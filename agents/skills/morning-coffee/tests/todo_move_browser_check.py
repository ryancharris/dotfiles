"""Exercise task moves in installed Chrome; all saves use an isolated synthetic root.

Run: uv run --with playwright --python 3.12 tests/todo_move_browser_check.py
CHROME_PATH may override the installed Chrome executable. No providers are accessed.
"""
from datetime import datetime
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, expect

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from local_plan_server import handler_for
from report_history import publish
from todo_state import load_todos, save_todo_action
from workspace_state import open_workspace
from test_report_history import snapshot


def main():
    with tempfile.TemporaryDirectory(prefix='coffee-todo-move-browser-') as temporary:
        root = Path(temporary)
        day = datetime.now(ZoneInfo('America/Toronto')).date().isoformat()
        data = snapshot('09:00', day=day)
        published = publish(root, data, 'morning-coffee')
        open_workspace(root, published['snapshot'])
        ids = {}
        for number, (title, parent) in enumerate([
            ('Alpha task', None), ('Alpha child', 'Alpha task'),
            ('Bravo task', None), ('Charlie task', None), ('Delta task', None),
        ], 1):
            request = {'action': 'add', 'title': title}
            if parent:request['parent_id'] = ids[parent]
            ids[title] = save_todo_action(root, request, task_id=f'{number:032x}')['item']['id']
        token = 'synthetic-todo-move-' + 'x' * 40
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(data, root, token, workspace=True))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(executable_path=os.environ.get(
                    'CHROME_PATH', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'), headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1100})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                url = f'http://127.0.0.1:{server.server_port}/report/{token}'
                page.goto(url)
                todos = page.locator('#todos')
                todos.scroll_into_view_if_needed()

                def row(title):
                    return todos.locator(f'[data-todo-id="{ids[title]}"]')

                def tree():
                    return todos.locator('.todo-row').evaluate_all('''nodes=>nodes.map(node=>[
                        node.dataset.todoId,
                        node.parentElement.closest('[data-todo-id]')?.dataset.todoId||null
                    ])''')

                def persisted():
                    return [[item['id'], item['parent_id']] for item in load_todos(root)]

                def expect_tree(expected):
                    try:
                        page.wait_for_function('expected=>JSON.stringify(Array.from(document.querySelectorAll("#todos .todo-row")).map(node=>[node.dataset.todoId,node.parentElement.closest("[data-todo-id]")?.dataset.todoId||null]))===JSON.stringify(expected)', arg=expected, timeout=8000)
                    except Exception:
                        page.screenshot(path='/tmp/coffee-todo-move-failure.png', full_page=True)
                        print('Actual tree:', tree(), 'Expected:', expected, 'Task status:', todos.locator('.todo-status').inner_text(), 'Move status:', todos.locator('.todo-move-status').inner_text(), flush=True)
                        raise
                    assert persisted() == expected, (persisted(), expected)

                # Actual pointer-driven drag/drop; no fabricated drag events.
                def drag(source, target, placement):
                    handle = row(source).locator(':scope > .todo-entry .todo-drag-handle')
                    entry = row(target).locator(':scope > .todo-entry')
                    handle.scroll_into_view_if_needed()
                    entry.evaluate("node=>node.scrollIntoView({block:'center',behavior:'instant'})")
                    start, end = handle.bounding_box(), entry.bounding_box()
                    assert start and end
                    fraction = {'before': .08, 'inside': .5, 'after': .92, 'before-gap': 0}[placement]
                    page.mouse.move(start['x'] + start['width']/2, start['y'] + start['height']/2)
                    page.mouse.down()
                    page.mouse.move(start['x'] + start['width']/2 + 12, start['y'] + start['height']/2, steps=4)
                    page.mouse.move(end['x'] + min(120, end['width']/2), end['y'] + end['height']*fraction - (6 if placement=='before-gap' else 0), steps=18)
                    if placement=='before-gap':page.screenshot(path='/tmp/coffee-todo-move-drop-cue.png')
                    page.mouse.up()

                def named_tree(*entries):
                    return [[ids[entry[0]], ids[entry[1]] if entry[1] else None] for entry in entries]

                def root_drag(source):
                    handle = row(source).locator(':scope > .todo-entry .todo-drag-handle')
                    handle.scroll_into_view_if_needed()
                    box = handle.bounding_box()
                    page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                    page.mouse.down()
                    page.mouse.move(box['x'] + box['width']/2 + 12, box['y'] + box['height']/2, steps=4)
                    target = todos.locator('[data-todo-root-drop]')
                    expect(target).to_be_visible()
                    target.scroll_into_view_if_needed()
                    end = target.bounding_box()
                    page.mouse.move(end['x'] + end['width']/2, end['y'] + end['height']/2, steps=18)
                    page.mouse.up()

                def keyboard_move(source, target, placement='inside'):
                    handle = row(source).locator(':scope > .todo-entry .todo-drag-handle')
                    handle.focus()
                    page.keyboard.press('Enter')
                    form = row(source).locator(f'[data-todo-move="{ids[source]}"]')
                    expect(form).to_be_visible()
                    form.locator('[name=target_id]').select_option(ids[target] if target else '')
                    if target:form.locator('[name=placement]').select_option(placement)
                    form.get_by_role('button', name='Move task', exact=True).focus()
                    page.keyboard.press('Enter')

                assert tree() == persisted()
                draft = todos.locator('.todo-add [name=title]')
                draft.fill('Unsaved new task draft')
                row('Delta task').locator(':scope > .todo-entry .todo-more > summary').click()
                row('Delta task').get_by_role('button', name='Edit task', exact=True).click()
                edit = row('Delta task').locator('.todo-edit-form [name=title]')
                edit.fill('Unsaved Delta edit')
                # Escape must cancel an active drag without any durable write.
                state_file = root / 'todos' / 'state.json'
                before_cancel = state_file.read_bytes()
                handle = row('Charlie task').locator(':scope > .todo-entry .todo-drag-handle')
                handle.scroll_into_view_if_needed()
                box = handle.bounding_box()
                page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
                page.mouse.down()
                page.mouse.move(box['x'] + box['width']/2 + 20, box['y'] + box['height']/2, steps=5)
                page.keyboard.press('Escape')
                page.mouse.up()
                assert state_file.read_bytes() == before_cancel
                # Drop into actual row padding above the entry, between task rows.
                drag('Charlie task', 'Alpha task', 'before-gap')
                expected = named_tree(('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Bravo task', None), ('Delta task', None))
                expect_tree(expected)
                expect(draft).to_have_value('Unsaved new task draft')
                expect(edit).to_have_value('Unsaved Delta edit')

                drag('Bravo task', 'Alpha task', 'inside')
                expected = named_tree(('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Bravo task', 'Alpha task'), ('Delta task', None))
                expect_tree(expected)
                # Dragging a parent into its descendant must never mutate the tree.
                before = persisted()
                drag('Alpha task', 'Alpha child', 'inside')
                page.wait_for_timeout(150)
                assert tree() == before and persisted() == before
                handle = row('Alpha task').locator(':scope > .todo-entry .todo-drag-handle')
                handle.focus()
                page.keyboard.press('Enter')
                form = row('Alpha task').locator(f'[data-todo-move="{ids['Alpha task']}"]')
                options = form.locator('[name=target_id] option').evaluate_all('nodes=>nodes.map(n=>n.value)')
                assert ids['Alpha task'] not in options and ids['Alpha child'] not in options and ids['Bravo task'] not in options, options
                form.locator('[data-todo-dismiss-move]').click()

                # A before-parent drop unnests without losing the parent's other child.
                drag('Bravo task', 'Alpha task', 'before')
                expected = named_tree(('Charlie task', None), ('Bravo task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Delta task', None))
                expect_tree(expected)
                page.route('**/todo', lambda route: route.fulfill(status=500, json={'ok': False, 'error': 'Synthetic move save failure'}))
                drag('Charlie task', 'Delta task', 'inside')
                expect(todos.locator('.todo-status')).to_contain_text('not confirmed')
                assert tree() == expected and persisted() == expected
                expect(draft).to_have_value('Unsaved new task draft')
                expect(edit).to_have_value('Unsaved Delta edit')
                page.unroute('**/todo')

                root_drag('Bravo task')
                expected = named_tree(('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Delta task', None), ('Bravo task', None))
                expect_tree(expected)
                keyboard_move('Bravo task', 'Alpha task')
                expected = named_tree(('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Bravo task', 'Alpha task'), ('Delta task', None))
                expect_tree(expected)
                expect(draft).to_have_value('Unsaved new task draft')
                expect(edit).to_have_value('Unsaved Delta edit')
                todos.screenshot(path='/tmp/coffee-todo-move-desktop.png')
                page.reload()
                expect_tree(expected)

                # Descendant rejection also holds at the authoritative HTTP boundary.
                config = todos.locator('#todo-config').evaluate('node=>JSON.parse(node.textContent)')
                response = page.request.post(config['endpoint'], headers={'X-Brief-Token': config['token'], 'Origin': f'http://127.0.0.1:{server.server_port}'}, data={
                    'action': 'move', 'id': ids['Alpha task'], 'target_id': ids['Alpha child'],
                    'placement': 'inside', 'base_order': expected})
                assert response.status == 400, response.text()
                assert persisted() == expected
                stale = list(reversed(expected))
                response = page.request.post(config['endpoint'], headers={'X-Brief-Token': config['token'], 'Origin': f'http://127.0.0.1:{server.server_port}'}, data={
                    'action': 'move', 'id': ids['Delta task'], 'target_id': ids['Charlie task'],
                    'placement': 'before', 'base_order': stale})
                assert response.status == 409, response.text()
                assert persisted() == expected

                page.set_viewport_size({'width': 390, 'height': 1200})
                keyboard_move('Bravo task', None)
                expected = named_tree(('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Delta task', None), ('Bravo task', None))
                expect_tree(expected)
                drag('Delta task', 'Charlie task', 'before')
                expected = named_tree(('Delta task', None), ('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'), ('Bravo task', None))
                expect_tree(expected)
                drag('Alpha task', 'Bravo task', 'after')
                expected = named_tree(('Delta task', None), ('Charlie task', None), ('Bravo task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'))
                expect_tree(expected)
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Task movement UI must fit a narrow viewport.'
                page.reload()
                expect_tree(expected)
                assert not errors, errors
                page.close()
                # Trusted touch input in a touch-capable mobile browser context.
                touch_context = browser.new_context(viewport={'width': 390, 'height': 1200}, has_touch=True, is_mobile=True)
                touch_page = touch_context.new_page()
                touch_page.on('pageerror', lambda error: errors.append(str(error)))
                touch_page.goto(url)
                source = touch_page.locator(f'[data-todo-id="{ids['Bravo task']}"] > .todo-entry .todo-drag-handle')
                target = touch_page.locator(f'[data-todo-id="{ids['Delta task']}"] > .todo-entry')
                source.scroll_into_view_if_needed()
                target.evaluate("node=>node.scrollIntoView({block:'center',behavior:'instant'})")
                start, end = source.bounding_box(), target.bounding_box()
                assert start and end
                cdp = touch_context.new_cdp_session(touch_page)
                sx, sy = start['x'] + start['width']/2, start['y'] + start['height']/2
                ex, ey = end['x'] + min(100, end['width']/2), end['y'] + end['height']/2
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': sx, 'y': sy}]})
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': sx + 12, 'y': sy}]})
                for step in range(1, 13):
                    cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': sx + (ex-sx)*step/12, 'y': sy + (ey-sy)*step/12}]})
                cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                expected = named_tree(('Delta task', None), ('Bravo task', 'Delta task'), ('Charlie task', None), ('Alpha task', None), ('Alpha child', 'Alpha task'))
                touch_page.wait_for_function('expected=>JSON.stringify(Array.from(document.querySelectorAll("#todos .todo-row")).map(node=>[node.dataset.todoId,node.parentElement.closest("[data-todo-id]")?.dataset.todoId||null]))===JSON.stringify(expected)', arg=expected)
                assert persisted() == expected
                assert touch_page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                touch_page.locator('#todos').screenshot(path='/tmp/coffee-todo-move-mobile.png')
                touch_page.reload()
                touch_page.wait_for_function('expected=>JSON.stringify(Array.from(document.querySelectorAll("#todos .todo-row")).map(node=>[node.dataset.todoId,node.parentElement.closest("[data-todo-id]")?.dataset.todoId||null]))===JSON.stringify(expected)', arg=expected)
                assert not errors, errors
                touch_context.close()
                browser.close()
        finally:
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
    print('Synthetic task move browser checks passed.')


if __name__ == '__main__':main()
