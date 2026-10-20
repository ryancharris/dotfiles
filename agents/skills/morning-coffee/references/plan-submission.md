# Local review marks and day plans

PR and RFC rows offer **Mark done locally** and **Undo local done**. A successful save changes the personal **Done locally** state; source approvals, review readiness, eligibility and full queue counts stay source-derived. PR **Review progress** defaults to **To review**, with **All** and **Done locally** available so completed personal work remains discoverable. Marks are keyed by review kind and canonical source URL in the configured report root. They persist across report generations, local days and noisy source `updatedAt` changes until the user undoes them.

Coffee’s local session enables review marks and day-plan submission. Tea can enable review marks and to-do actions in a live session while its calendar and submitted schedule stay read-only. Read-only archived reports retain the marks known at publication and expose the local-session instructions; current local state takes precedence when a session opens. Group source-approved or locally done RFCs inside a collapsed Approved or done toggle, and leave pending RFCs visible. Move RFCs only after a successful save; undo restores a pending RFC unless it remains source-approved. Update controls and labels only after the server confirms a save. A failed request leaves the previous confirmed state and reports the failure.

All displayed save/check times use 24-hour HH:MM in the report’s IANA timezone. Root-wide review marks retain offset-aware timestamps; local display does not change stored instants.

## Submit a day plan

Coffee’s **Review & submit plan** shows the exact chosen date, timezone and block times. **Submit plan** writes an immutable local JSON record. Moving blocks or opening the review saves nothing. Users can adjust and resubmit throughout the day; the newest valid submission is authoritative for their chosen plan. An empty submission clears the chosen plan and its Today rows. After a successful save, hide the drag-and-drop planner and expose Edit schedule in Today; restore it only on that action. Cancel editing restores the last confirmed choices and hides the planner without changing Today or writing a submission. Update Today only after the save succeeds, using the confirmed response; opening the review or editing unsaved choices does not change Today. These are preferences, never evidence that exercise, focus, lunch or a walk was completed.

Use the same report-root precedence as daily history: `--root`, `ENGINEERING_BRIEFS_DIR`, configured `report_dir`, then `$HOME/daily-briefs`. Submissions live at `<root>/<timezone>/<date>/submitted-plans/<timestamp>-<id>.json`, with private files and directory permissions. Coffee and Tea read the latest submission for their local day/timezone and show it in Today, clearly labelled as a local chosen plan alongside actual calendar events. All visible clock values use 24-hour HH:MM. Fresh calendar collisions should be flagged without silently moving the user’s choices.

Start a submission-enabled Coffee report with:

```sh
python3 "$morning_skill/scripts/local_plan_server.py" \
  --snapshot "/absolute/path/to/todays/coffee/snapshot.json" \
  --output "/tmp/coffee-plan.html" --background --open
```

The command exits only after the detached server responds successfully. Open the private loopback URL it returns; `--open` does this automatically. The live page reloads the latest local review marks and submitted plan on every browser reload. The temporary HTML remains an opaque-origin fallback, but its embedded state is fixed at session creation. The server binds only `127.0.0.1`, uses a random port and private session capability, validates the Host and either the exact loopback Origin or local-file null Origin, and accepts authenticated JSON POSTs only. It makes no external requests, uses no OAuth credentials, and never changes Google Calendar. It validates selected blocks against each other, scheduling windows and every known calendar interval in the Coffee snapshot, including free/transparent events. The report displays the snapshot’s calendar-check time; regenerate Coffee when fresher availability is needed.

## Enable Tea review marks

Start Tea with the same configured report root as publication:

```sh
python3 "$morning_skill/scripts/local_plan_server.py" \
  --snapshot "/absolute/path/to/todays/tea/snapshot.json" \
  --output "/tmp/tea-reviews.html" --background --open
```

Open the private loopback report URL. Automatic Tea mode accepts personal PR/RFC marks and to-do actions and leaves plan submission disabled. Opening any session reloads the newest local review state, including undo actions saved after the archived snapshot. The server restricts review requests to PR/RFC identities present in that snapshot; use a fresh brief to add newly discovered reviews.

Use a new output path; immutable report HTML must not be overwritten. This temporary HTML contains a session capability, so keep it private and out of saved report history. The command prints its PID and a stop command. Stopping it removes the temporary HTML and private `.session.json` connection metadata; persisted plans and review marks remain. The private `.log` file records startup failures. Omit `--background` for a foreground session that closes with Ctrl-C. An agent tool session is temporary, so interactive report delivery uses the detached mode and verifies a save after the launcher exits. The browser may require local-network access to reach the local bridge; a failed request must show a save failure rather than claim success. Session capabilities are stripped before archiving a report.

`plan_submission.latest_plan(root, day, timezone, with_warnings=True)` returns `{plan, warnings}`. Invalid newer files are skipped with warnings, and the latest valid JSON is read. When no valid file exists, the plan is `None`. The default API returns the plan or `None` and raises `PlanError` when every existing submission is unreadable.

For a local code upgrade, preserve the current live report URL with `--resume-session /path/to/private-connection-metadata.json`. Keep a private copy of its metadata before stopping its printed PID, then launch the updated server with a new output path and the same snapshot/root. The URL and capability remain valid for existing browser tabs; latest local state is reloaded.
