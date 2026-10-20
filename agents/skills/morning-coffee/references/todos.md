# Local to-do list

Both briefs load `load_todos(report_root, with_warnings=True)` into the session snapshot before rendering. Keep all returned tasks in `snapshot.todos`; overdue and due-today pending tasks are user-entered work to account for alongside source priorities. `todo_summary(snapshot)` provides those groups and upcoming tasks using the report's local date. Completed and cancelled tasks remain discoverable but are excluded from outstanding work. Source activity never implies local task completion.

The live widget saves explicit add, complete, cancel, reopen, reschedule and remove actions through the authenticated loopback `/todo` endpoint. Any task can have subtasks, with independent dates and statuses. Filters preserve ancestor context for matching subtasks. Completing or cancelling a parent changes only that task. Removing a task promotes its children to its parent, preserving their work. Rescheduling chooses a calendar date and returns that task to pending. Changes appear after a matching successful acknowledgement. Archived reports show the saved state with disabled write controls.

Store tasks at `<report_root>/todos/state.json`, across dates and report types. Each task has a locally generated ID, optional `parent_id`, title, status, due date, and creation/update timestamps. Add accepts an optional existing parent ID; flat stores load with null parents. Invalid parent links and cycles are disclosed. The lock serializes actions from concurrent Coffee and Tea sessions; atomic replacement preserves the prior file if a write fails. Files are private to the user. An unreadable store is disclosed and preserved rather than overwritten. Reopening a live report reloads the current store.

Publish archives without `todo_interaction`, which contains a short-lived local saving capability. Load the latest store for each new live session instead of trusting an archived task list. Task changes affect local planning only.

Completed tasks show a check emoji, struck-through title and gray text. Style only the completed item’s own entry so pending subtasks remain visually active.

Use the star toggle to mark a task high importance. Stars persist across both briefs and status/date changes; starred tasks sort first within the selected view. Preserve nesting: a starred descendant brings its ancestor group forward without automatically starring its parents. Older tasks default to unstarred. Apply changes only after the local store confirms the requested importance.
