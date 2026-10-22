# Local review progress and day plans

Enable the unified Morning Coffee session through [workspace lifecycle](workspace.md) with `local_plan_server.py --workspace --background --open`, which opens its URL in the user's default browser. Use the same configured report root as publication. The private live URL reloads the active source snapshot plus current local tasks, review marks and same-day/timezone plan. Archives preserve historical state and strip session capabilities. All provider events and approval records remain read-only.

Use 24-hour HH:MM for local save/check times in the report's IANA timezone. Stored timestamps remain offset-aware instants. Update controls, labels and lists only after a matching successful acknowledgement; a failed save retains the previous confirmed view and drafts.

## Personal review progress

PR/RFC rows offer **Mark done locally** and **Undo local done**. Marks are keyed by kind and canonical source URL in the report root and persist across source refreshes, local dates and timestamp noise. They record personal progress separately from provider approvals, eligibility, readiness and full queue counts. Verified later review requests may reopen work under the [strict source-evidence policy](personal-review-filter.md); commits and `updatedAt` alone never do.

PR **Review progress** defaults to **To review**, with **All** and **Done locally** keeping marked rows discoverable. Pending RFCs stay visible; source-approved or locally done RFCs remain in the collapsed Approved or done group. Undo restores a pending RFC unless the source still approves it. Restrict save identities to the current active snapshot, including newly collected reviews after a workspace source update.

## Calendar completion

**Done** and **Undo done** let the user strike through calendar events and saved local plan blocks at any time, in Today and the calendar widget. Store the explicit choice locally by report date/timezone and source identity (or exact saved block); retain it across reloads and source refreshes. An explicit not-done choice overrides automatic elapsed-time styling. With no explicit choice, ended items retain their automatic strike-through. Completion changes display only: calendar events remain read-only and every occupied interval still constrains scheduling. Apply a mark only after a matching durable acknowledgement, preserve the previous mark on failure, and keep archives immutable without save capabilities.

## Submit and edit a day plan

Optional blocks start unplaced. **Review & submit plan** shows the exact date, timezone and selected block times. **Submit plan** appends an immutable private local record. Dragging, entering times or opening the review writes nothing. Users can resubmit throughout the day; the latest valid record is authoritative. An empty submission clears the saved choices and their Today rows. Focus blocks accept an optional editable `name` (trimmed, at most 120 characters, no control characters); blank uses Focus. Preserve it through submission, reload, editing and removal acknowledgements. The name is a label, so renaming preserves the block's calendar completion identity. A chosen block is user intent, never evidence that focus, exercise, lunch or a walk happened.

After an acknowledged save, collapse the planner and expose **Edit schedule** in Today. Editing leaves Today on its last confirmed choices. **Cancel editing** restores those confirmed choices and collapses the planner without writing. Keep the fixed calendar lane immutable and reject overlaps with all known intervals, including transparent/free events. Validate the chosen focus duration, fixed durations for other blocks, quarter-hour starts and the checked scheduling windows; show the source calendar-check timestamp. Request source Refresh for fresher availability.

Submissions live under `<root>/<timezone with / replaced by __>/<date>/submitted-plans/<timestamp>-<id>.json`, with private files/directories. Coffee-origin choices and choices migrated from Tea archives use the same latest-plan reader. Show confirmed local choices beside actual events in Today and the calendar using the block name and local editing controls; omit the repeated Local chosen plan text. Flag fresh conflicts without silently moving or dropping a choice.

## Remove a saved block

Expose **Remove** on each saved local block in the unified workspace. It removes that choice from the latest same-day/timezone plan and appends an immutable version, preserving all remaining blocks and every earlier record. The final removal saves an empty plan. Removal changes a preference; it neither completes a task nor changes a provider event. Restore or adjust choices with Edit schedule and resubmit.

The dedicated `/plan/remove` request carries only date/timezone, the saved revision and the exact local block kind/start/duration. It requires the private token, exact loopback Host and exact loopback Origin. It rejects stale versions, actual calendar event identities and arbitrary replacement plans. Coffee submits and removals share a per-day lock so an old tab cannot overwrite a newer choice.

POST and view-refresh requests have ten-second abort deadlines. The client verifies that acknowledgement blocks exactly equal the previous saved plan minus the selected block, including cardinality. Only then refresh the calendar, Today and affected agenda indicators; preserve unrelated task/tag/subtask drafts, filters, focus and scroll. A save failure retains the confirmed DOM. If persistence succeeds but fresh HTML cannot load, explicitly say the block was removed locally, keep stale mutation controls locked and offer **Refresh saved plan** to retry only the read.

## Session lifecycle and verification

Use a new temporary output path and keep it private. The launcher returns after the detached server responds, printing its private URL, PID and stop command. Stopping removes the temporary HTML and `.session.json` metadata; persisted local state remains. The private `.log` records startup failures. For upgrades preserve the URL with the resume workflow in [workspace lifecycle](workspace.md). Open the loopback URL: file-origin fallbacks have fixed embedded state and cannot perform exact-origin workspace actions.

The server binds `127.0.0.1`, validates Host/origin and requires authenticated JSON for mutations. Local actions use no provider credentials. Only an explicit source-refresh action may notify the fixed configured T3 webhook; source collection itself stays in T3 under the skill's read-only scopes. Missing or offline T3 must not disable local task, review or plan saving.

Verify a real authenticated save and durable reload after the launcher exits. An HTTP 200 report GET is rendering proof only. Exercise stale identity rejection and failed saves; confirm unrelated draft editors survive acknowledged plan and source updates. Do not assert that saving works until the delivered session roundtrip succeeds.

`plan_submission.latest_plan(root, day, timezone, with_warnings=True)` returns `{plan, warnings}`. Unreadable newer records are skipped with warnings. With no valid file the plan is `None`; the default API raises `PlanError` when all existing submissions are unreadable. Preserve damaged records and disclose recovery warnings.

Legacy sessions without `--workspace` remain available for historical report compatibility: Coffee permits plan editing, Tea permits narrow saved-block removal, and both support local tasks and review marks. New delivery uses the unified workspace rather than generating a separate Tea report.
