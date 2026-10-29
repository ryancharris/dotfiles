# Focus and exercise suggestions

Morning Coffee recommends **one uninterrupted hour for exercise**, **two contiguous hours for focus by default**, **a thirty-minute dog walk**, **a thirty-minute lunch** and **a thirty-minute reading / learning block**. Coffee's planner starts with every optional block unplaced; users opt in by dragging or placing a block. Restore only choices from a successful prior submission. Tea's calendar shows actual events and the latest submitted plan read-only. Editing a suggestion changes the visualization; submitting the placed blocks saves a local plan through [plan submission](plan-submission.md), which Tea reads on later runs.

Collect scheduling evidence before applying the [calendar display window](collection.md#calendar-display-window) or filtering agenda titles. Use detailed records from the primary calendar and every additional calendar already known from user context; paginate completely. Include all-day busy events, accepted events and tentative events as busy. Exclude cancelled and declined events. Keep transparent/free events labelled as free in the agenda, but reserve their occupied time in this planner too: the suggested blocks must overlap no event. Events omitted from the visible agenda still constrain scheduling, but contribute only anonymous `{start, end}` intervals: preserve the title/privacy filtering rules in the agenda. Offset-free all-day dates use the report timezone and an exclusive end date.

Keep one anonymous busy interval per event, including coincident events, rather than merging them. For visible events, optionally include `event_id` matching the agenda row's stable `id`. This lets [local calendar removals](plan-submission.md#remove-a-calendar-occurrence-locally) release only that occurrence's time while retaining other events. Store source evidence unchanged; the planner applies the local choices.

Add `availability` to the compact snapshot:

```json
{
  "status": "complete",
  "checked_at": "2026-10-19T09:00:00-04:00",
  "coverage": "Primary calendar only; all detailed busy records checked",
  "window_start": "09:00",
  "window_end": "17:00",
  "coverage_start": "2026-10-19T00:00:00-04:00",
  "coverage_end": "2026-10-20T00:00:00-04:00",
  "busy": [{"start": "2026-10-19T10:00:00-04:00", "end": "2026-10-19T10:30:00-04:00"}]
}
```

Use the user's planning window or default 09:00–17:00 for focus, exercise, lunch and reading / learning. Dog walks can use any free time during the local day, with no afternoon restriction. Record the actual queried bounds as `coverage_start/end` so the planner can validate early/evening walks; legacy snapshots without those bounds establish only the planning window. Collect the entire local day, including anonymous intervals for filtered events. `complete` means the declared calendar scope and bounds were fully checked, not that every calendar in the account was enumerated. Label primary-only coverage. Use `partial` or `unavailable` if listing, pagination or detailed event filtering failed; withhold availability claims. An empty `busy` list is valid only after a complete check.

The history helper runs `scripts/plan_day.py` during publication. It searches for nonoverlapping 120-minute focus, 60-minute exercise, 30-minute lunch, 30-minute dog-walk and 30-minute reading / learning slots, preferring earlier focus and midday exercise/lunch. Dog walks have no time-of-day preference beyond free time after the latest check. Suggestions begin after the later of collection and availability verification. Keep exact busy boundaries and all-day/exclusive-end events. Render times, durations, coverage, planning window and verification time. Focus and reading / learning each have a duration control accepting 15-minute increments from 15 minutes through the checked planning-window length. Changing a placed block’s duration must preserve its start and reject calendar, plan or window conflicts; unplace it to choose a different length before finding a new time. Keep the chosen length on save, reload and edit cancellation. Focus also has an optional editable name; blank uses Focus. Preserve that label through drag, submit, reload and cancel without changing scheduling or completion identity.

When all five goals cannot fit, name unplaced goals briefly and keep them in the unplaced tray. Offer the verified subset that fits as unplaced choices; place a goal only after the user opts in, and never on occupied time. Incomplete availability stays explicitly unverified. Keep omitted/private event titles and aggregate meeting-load/free-time calculations out of the brief.

## Interactive day view

Render `day_calendar.py` with inline calendar assets. Coffee’s visible calendar spans 08:30–17:00; full-day evidence and valid saved choices remain available to validation. Show Today as the default read view and put the planner inside the same widget as its edit view. Show it through Today’s Edit schedule and return to Today after submission (including an empty plan). In the editor, use one shared calendar column for existing events and placed blocks. Cancel editing hides it and restores the last confirmed choices without saving; unsaved edits and failed saves stay visible. Existing events stay fixed; anonymous intervals reserve time without disclosing omitted titles. Users drag unplaced choices onto the calendar, move placed blocks, enter HH:MM times or use keyboard arrows, place/unplace blocks and reset. Preview a drag without changing the chosen plan; commit only a valid drop and restore the prior state on cancel or invalid drop. Fresh-plan reset leaves all optional blocks unplaced. Snap starts to fifteen minutes, use the chosen focus duration and preserve each type's allowed bounds. Reject overlaps with every existing event and other proposed block on all edit paths, including reset/cancel. Incomplete availability stays uncertain after local edits. Keep instructions to one line. Tea uses `render_calendar(snapshot, read_only=True)` with actual events and submitted blocks in separate labelled lanes, without editing controls. Flag any new event conflicts without moving the saved choices.

Use 24-hour HH:MM for every time label and input in Coffee and Tea. After a successful local submission, include the saved choices in Today immediately and on subsequent renders, clearly labelled as local plan blocks. Unsubmitted edits and failed saves leave Today unchanged; an empty successful submission clears the saved-plan rows. Keep saved choices separate from actual provider events and retain conflict labels after a calendar refresh.

Keep block controls in aligned full-width rows: block label, start time and placement/removal share the same columns. Group Focus duration and optional name beneath its main row; group Reading / learning duration beneath its row. The `learning` kind remains distinct from `focus` through saving, completion and removal. Stack labels above controls on narrow screens while preserving the same field/action alignment.
