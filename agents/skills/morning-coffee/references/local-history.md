# Local lookbacks

Keep cleared tasks and calendar choices as evidence for later reflection. Task and calendar actions append compact timestamped metadata inside their existing state files, under the same lock and atomic replacement as the action. Restoring or undoing a clear preserves its history; unchanged retries add no event. History stays out of report and live UI projections. Saved plans remain immutable revisions, including custom focus names and removed blocks; do not copy them into another journal.

The first meaningful save upgrades a legacy task/calendar store to version 2. The first meaningful task move upgrades tasks to version 3 with explicit ordering; move events retain the prior/new parent and relative destination. Task readers accept versions 1–3 and calendar readers accept versions 1–2; older writers reject newer versions instead of dropping history or manual ordering. Restart/resume the live server after upgrading these modules. Reads and unchanged saves do not migrate stores. Never fabricate earlier transitions or completion timestamps from `updated_at`, clearing, plan submission or elapsed calendar styling.

Use the read-only exporter for lookbacks (run from the skill directory):

```sh
python3 scripts/local_history.py --root /Users/ryan/daily-briefs --from 2026-10-19 --to 2026-10-22 --timezone America/Toronto
```

Dates are inclusive local action dates. Optional `--project Transport` filters tasks by their tags at the action time and excludes plan/calendar records without tags. JSON separates recorded `events` from current/retained `facts`, with `counts`, `warnings` and `limitations`. Counts represent actions, so one clear batch counts once regardless of its task count. Current task facts have unknown action dates and remain separate even under date filtering. Plan submissions show intent; explicit calendar marks show the user's completion choices. Historical transitions before recording began remain unknown.

The exporter reads existing files without locks, migrations or creating directories. Each file is atomic, but the combined export is not a transaction across stores. Preserve immutable reports as source evidence; do not prune or compact history without a separate retention decision. At the current small data volume, compact records in existing files avoid additional database and journal overhead.
