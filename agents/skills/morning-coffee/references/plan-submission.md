# Submit a local day plan

Coffee’s **Review & submit plan** shows the exact chosen date, timezone and block times. **Submit plan** writes an immutable local JSON record. Moving blocks or opening the review saves nothing. Users can adjust and resubmit throughout the day; the newest valid submission is authoritative for their chosen plan. An empty submission clears the chosen plan. These are preferences, never evidence that exercise, focus, lunch or a walk was completed.

Use the same report-root precedence as daily history: `--root`, `ENGINEERING_BRIEFS_DIR`, configured `report_dir`, then `$HOME/daily-briefs`. Submissions live at `<root>/<timezone>/<date>/submitted-plans/<timestamp>-<id>.json`, with private files and directory permissions. Tea reads the latest submission for its local day/timezone and shows it separately from actual calendar events. Fresh calendar collisions should be flagged without silently moving the user’s choices.

Start a submission-enabled Coffee report with:

```sh
python3 "$morning_skill/scripts/local_plan_server.py" \
  --snapshot "/absolute/path/to/todays/coffee/snapshot.json" \
  --output "/tmp/coffee-plan.html"
```

Keep the command running and open the resulting file. The server binds only `127.0.0.1`, uses a random port and private session capability, validates the Host and local-file Origin, and accepts authenticated JSON POSTs only. It makes no external requests, uses no OAuth credentials, and never changes Google Calendar. It validates selected blocks against each other, scheduling windows and every known calendar interval in the Coffee snapshot, including free/transparent events. The report displays the snapshot’s calendar-check time; regenerate Coffee when fresher availability is needed.

Use a new output path; immutable report HTML must not be overwritten. This temporary HTML contains a session capability, so keep it private and out of saved report history. Ctrl-C closes the server and removes the session HTML, while submitted plan records remain. The browser may require local-network access to reach the local bridge; a failed request must show a save failure rather than claim success.

`plan_submission.latest_plan(root, day, timezone, with_warnings=True)` returns `{plan, warnings}`. Invalid newer files are skipped with warnings, and the latest valid JSON is read. When no valid file exists, the plan is `None`. The default API returns the plan or `None` and raises `PlanError` when every existing submission is unreadable.
