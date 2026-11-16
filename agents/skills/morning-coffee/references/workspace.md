# Morning Coffee workspace

Each skill run collects and publishes a new report. One private browser URL shows the active report and durable local choices. The local server handles saving and completed-report updates only; all provider collection runs directly through the assistant.

Resolve `morning_skill` to this skill's absolute directory and `report_root` through [daily history](daily-history.md). Use the same root for publication, application and the live session. Private data stays outside Git.

## Inspect, generate and apply

Inspect the current validated pointer before collecting. With an existing workspace, open its active snapshot using the launch command below while generating the new report.

```sh
python3 "$morning_skill/scripts/workspace_state.py" --root "$report_root" inspect
python3 "$morning_skill/scripts/report_history.py" --root "$report_root" prepare \
  --date "$local_date" --timezone "$timezone" --kind morning-coffee
```

Pass [source preflight](source-connections.md), collect all five sources through [collection](collection.md), and publish the completed snapshot. Use the returned published snapshot path for application and launch:

```sh
python3 "$morning_skill/scripts/report_history.py" --root "$report_root" publish \
  "$snapshot_json" --kind morning-coffee
python3 "$morning_skill/scripts/workspace_state.py" --root "$report_root" apply \
  --snapshot "$published_snapshot"
python3 "$morning_skill/scripts/local_plan_server.py" \
  --root "$report_root" --snapshot "$published_snapshot" \
  --output "/tmp/morning-coffee-unique-session.html" --workspace --background --open
```

Application initializes the workspace when absent, adopts a newer completed report across local dates, and is idempotent for its active snapshot. Older reports cannot replace newer facts. Legacy refresh requests and private bridge configuration no longer participate in collection or block publication. Reopening or polling only reads the current pointer; a fresh skill run generates new source facts. Historical-date requests open archives without applying them.

A partial collection may be published with explicit failures and retained evidence at its original timestamp. Recheck earlier items from the active snapshot, including when it belongs to another day. Missing results, timestamps, commits and elapsed schedule blocks never prove completion. A collection that cannot produce a valid snapshot leaves the current pointer unchanged.

## Serve and upgrade

Use a new temporary output path. The launcher validates published snapshot/HTML pairs, discovers `workspace/session.json`, checks server root/process identity, and reuses its private URL. The detached server remains available after the launcher exits. If it stopped, the launcher resumes that URL when the port is available. A timeout alone does not prove it stopped.

For a code upgrade, save the private session metadata, stop the verified old PID, and relaunch with `--workspace --resume-session /path/to/private-copy.json`, the same root and a new output path. This preserves the URL and durable work while loading the updated server. Open the private URL in the user's default browser; deliver it directly if browser opening fails. Temporary HTML and connection metadata contain capabilities; archives strip them.

## Reconcile work without resetting choices

**Recommended priorities** reads the active snapshot's ranked `priorities`, capped at four eligible unique outcomes. New skill runs adopt the new snapshot; reopening only reads it. Legacy `selected_priorities` never override this ranking. Preserve those records, confirmations, user answers and accepted/dismissed suggestion decisions. Keep saved commitments in To do with their local order and status; surface unfinished legacy selections there separately as retained earlier priorities, since auto-seeding was not explicit acceptance and must not manufacture committed tasks.

Filter recommendations only with supported authoritative terminal status, applicable local completion or explicit user choices. Missing discovery results, absence from the ranking and generated completion criteria are not completion evidence. Verify outcomes against authoritative sources and preserve uncertain earlier work with its original timestamp. Recheck evidence before asking status questions. The [ranking contract](activity-and-watchlist.md#recommendation-ranking) defines Why today and Last checked versus meaningful change.

Actionable source work may also appear as suggestions, placed as described in the [presentation contract](rendering.md#dense-presentation-contract). **Add to today** creates one local task with its project tags; retries do not create duplicate tasks. Acceptance records a commitment, not a permanent recommendation slot; an accepted pending task can still be recommended when current evidence justifies it. **Dismiss** suppresses that material suggestion version. Use verified substantive material changes for a new suggestion; local completion and accepted/dismissed decisions survive collection noise and day changes. Locally done PR/RFC work stays suppressed until a verified later request targets the current reviewer or relevant configured team. Follow [personal review evidence](personal-review-filter.md) for strict provenance and the locally-done PR collector branch; RFC evidence requires an authoritative Notion read, never an inferred re-request flag.

Local tasks, subtasks, importance, tags and archive live across dates. New tasks default to today without a date picker; the two-tab list, day-end archiving and seven-day retention follow [local tasks](todos.md). Review marks remain personal progress, not source approvals. Plans are same-day/timezone choices, not completed activity. Both Coffee-origin and Tea-migrated saved blocks can be removed locally while actual provider events remain immutable. See [local tasks](todos.md) and [local interactions](plan-submission.md).

## Acceptance checks

Verify the delivered URL after the launcher exits and exercise authenticated local saves with durable reload. A page GET verifies rendering only. Use an isolated report root for synthetic saves, plan removal, stale-tab rejection and draft/filter preservation checks. Do not manufacture tasks or decisions in the user's live history for testing.

Apply a newly published report and confirm that the same page adopts it while preserving local work. Verify a new-day run advances the header and title, legacy in-flight requests cannot block it, and removed browser collection endpoints reject requests. Keep source coverage honest and report a saved change separately if its view fails to reload.
