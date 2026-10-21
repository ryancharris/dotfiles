# Scheduled Morning Coffee

A recurring task that explicitly says **Start today** authorizes daily rollover. Resolve the current date in the user's IANA timezone on every run; never copy a date from the task's creation, session title or previous snapshot. Append that local date to the new session title.

1. Read the [workspace lifecycle](workspace.md), inspect the configured root, and launch/reuse its private workspace server. Pass `--open` to open its URL immediately in the user's default browser, including when reusing an existing server.
2. If there is no workspace, collect all six sources, publish the initial `morning-coffee` snapshot, and launch/open the workspace as soon as it exists. Otherwise create the durable request:

```sh
python3 "$morning_skill/scripts/workspace_state.py" --root "$report_root" begin \
  --timezone "$timezone"
```

3. Retain the returned `request.id`, `request.date`, `request.timezone` and `request.action`. `begin` chooses same-day refresh or new-day rollover under the state lock, including after weekends or missed runs. If `created` is false, inspect the matching existing request and avoid duplicating an active collector. A conflicting request or future-dated workspace requires diagnosis; never reset it to force progress.
4. Collect directly through the assistant using the [collection contract](collection.md). This path works without a browser webhook. Recheck prior evidence and preserve independent source results; provider failures must remain visible with retained evidence's original timestamps. Publish `--kind refresh` and complete the exact request ID using the commands in [workspace lifecycle](workspace.md). If collection cannot produce a valid snapshot, fail that ID without changing the active pointer. A timed-out request needs a new `begin` and fresh collection; never relabel an old snapshot to bypass validation.
5. Verify that the same browser URL shows the completed local date in both report header and tab title, with durable local work retained. Report any unavailable sources or browser/bridge limitation honestly.

Requests default to a one-hour timeout. Existing private bridge configurations may override it; migrate a 900-second setting as described in the workspace reference. The scheduler is independent of this timeout and must have the intended local cadence and next run verified after setup. T3 and its source connections must be available when the scheduled run executes.

Use this task prompt, substituting the user's timezone:

> Run /morning-coffee. Start today in America/Toronto on every scheduled run; this explicitly authorizes daily rollover. Follow references/scheduled-runs.md in the installed skill, including workspace_state.py begin, all six source collections, and exact request-ID completion. Open/reuse the report in the user's default browser at the start using --open; source links open new tabs. Collect directly even if the browser webhook is unavailable. Preserve local work and verify the completed report's local date. Append today's local YYYY-MM-DD to the session title.
