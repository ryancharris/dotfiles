# Focus and exercise suggestions

Morning Coffee recommends **one uninterrupted hour for exercise**, **at least two contiguous hours for focus**, **a thirty-minute dog walk** and **a thirty-minute lunch**. Coffee's planner is editable; Tea's calendar shows actual events and the latest submitted plan read-only. Editing a suggestion changes the visualization; submitting the placed blocks saves a local plan through [plan submission](plan-submission.md), which Tea reads on later runs.

Collect scheduling evidence before filtering agenda titles. Use detailed records from the primary calendar and every additional calendar already known from user context; paginate completely. Include all-day busy events, accepted events and tentative events as busy. Exclude cancelled and declined events. Keep transparent/free events labelled as free in the agenda, but reserve their occupied time in this planner too: the suggested blocks must overlap no event. Events omitted from the visible agenda still constrain scheduling, but contribute only anonymous `{start, end}` intervals: preserve the title/privacy filtering rules in the agenda. Offset-free all-day dates use the report timezone and an exclusive end date.

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

Use the user's planning window or default 09:00–17:00 for focus, exercise and lunch. Dog walks can use any free time during the local day, with no afternoon restriction. Record the actual queried bounds as `coverage_start/end` so the planner can validate early/evening walks; legacy snapshots without those bounds establish only the planning window. Collect the entire local day, including anonymous intervals for filtered events. `complete` means the declared calendar scope and bounds were fully checked, not that every calendar in the account was enumerated. Label primary-only coverage. Use `partial` or `unavailable` if listing, pagination or detailed event filtering failed; withhold availability claims. An empty `busy` list is valid only after a complete check.

The history helper runs `scripts/plan_day.py` during publication. It searches for nonoverlapping 120-minute focus, 60-minute exercise, 30-minute lunch and 30-minute dog-walk slots, preferring earlier focus and midday exercise/lunch. Dog walks have no time-of-day preference beyond free time after the latest check. Suggestions begin after the later of collection and availability verification. Keep exact busy boundaries and all-day/exclusive-end events. Render times, durations, coverage, planning window and verification time. Offer longer focus when explicitly requested and supported.

When all four goals cannot fit, name unplaced goals briefly and keep them in the unplaced tray. Show the verified subset that fits; never place goals on occupied time. Incomplete availability stays explicitly unverified. Keep omitted/private event titles and aggregate meeting-load/free-time calculations out of the brief.

## Interactive day view

Render `day_calendar.py` with inline calendar assets. Existing events stay fixed; anonymous intervals reserve time without disclosing omitted titles. Users drag suggestions, enter times or use keyboard arrows, place/unplace blocks and reset. Snap to fifteen minutes, preserve durations and each type's allowed bounds. Reject overlaps with every existing event and other proposed block on all edit paths, including reset/cancel. Incomplete availability stays uncertain after local edits. Keep instructions to one line. Tea uses `render_calendar(snapshot, read_only=True)` with actual events and submitted blocks in separate labelled lanes, without editing controls. Flag any new event conflicts without moving the saved choices.
