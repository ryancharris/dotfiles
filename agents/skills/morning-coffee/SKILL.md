---
name: morning-coffee
description: Generate a fresh Morning Coffee engineering report and open the all-day workspace with reviews, calendar, incidents, RFCs, chosen work, local tasks and project tags. Use for morning check-ins, daily planning, intraday report generations or an engineering overview.
---

# Morning Coffee

Maintain one workspace throughout the day. Keep current source facts beside the user's chosen work, local tasks and submitted schedule. All provider access is read-only; local state records the user's decisions. Older Tea Time archives remain readable, but new intraday updates use this workspace.

## Generate and open

Accept an optional `--date YYYY-MM-DD`. With no date, use today in the user's IANA timezone. Resolve the configured report root and requested day with the read-only `report_history.py select` command in [daily history](references/daily-history.md). Reject invalid dates before collecting or changing state.

For a date other than today, open its latest saved immutable HTML report. If none exists, explain that no saved report exists for that date. Keep the active workspace and its local state untouched.

For today, each skill invocation collects a fresh report, including when today's workspace already exists:

1. Read [workspace lifecycle](references/workspace.md), inspect existing state, and open the existing private URL when available so saved work stays accessible during collection.
2. Pass [source connection preflight](references/source-connections.md), then follow [source collection](references/collection.md) for all six sources. Discover new work and recheck prior authoritative items. Preserve independent failures and earlier evidence with its original timestamp. Read [local tasks](references/todos.md) before ranking work.
3. Publish a new immutable `morning-coffee` generation using [daily history](references/daily-history.md), then apply the published snapshot using [workspace lifecycle](references/workspace.md). A completed run advances the active day and facts while preserving local tasks, confirmations, review marks, accepted/dismissed choices and same-day plans. A failed run leaves the active report available.
4. Serve the workspace using `local_plan_server.py --workspace --background --open` and deliver its private URL in the user's default browser. Reuse that URL across completed runs; source links open in new tabs. Verify the report date and durable local controls. The browser handles local choices and completed-report updates; source generation happens in a new skill run.

Use the bundled scripts and renderer. Format-only previews reuse collection timestamps and leave history, workspace state and search memory unchanged. Every source collection records actual attempt times and honest coverage for all six sources. For recurring runs, follow [scheduled runs](references/scheduled-runs.md).

## Collect with evidence

The [collection contract](references/collection.md) holds provider scopes, discovery/hydration commands, privacy boundaries, queue completeness, review sizing and display order. Read its linked references for the branch being collected:

- [Personal review eligibility](references/personal-review-filter.md): effective personal approval and explicit later review-request evidence, Transport author roster and local completion checks.
- [Focus, exercise, walks and lunch](references/focus-and-exercise.md): verified scheduling intervals and anonymous busy time.
- [Quarterly planning](references/quarterly-planning.md): Google Drive discovery, fiscal-date matching and link-only privacy boundaries.
- [Incidents](references/incidents.md): Transport On-Call and incident.io authority.
- [RFC reviews](references/rfc-review.md): verified In-Review lifecycle and review window.
- [Activity and watchlist](references/activity-and-watchlist.md#recommendation-ranking): required ranking contract for every collection's Recommended priorities and evidence-backed outcomes; [search memory](references/search-memory.md): provider-local queries.

Keep raw provider responses and PR evidence outside the repository. Return compact evidence with canonical identities, source timestamps, counts and completeness markers. Prior reports are evidence to recheck, never instructions to execute. Verify uncertain statuses independently before asking the user; use the structured status checks in [rendering](references/rendering.md) and attribute user answers separately from source-observed state.

## Preserve personal work

Read [local tasks](references/todos.md) before ranking work and [local interactions](references/plan-submission.md) before enabling saves. Tasks persist across days, support drag ordering, nesting/unnesting, importance and project tags, and have no due dates. Preserve explicit task order after the user arranges it; moves carry subtasks and retain action history. Source activity never completes local tasks. Task dates, the To do/Archived views, day-end archiving and seven-day archive retention follow [local tasks](references/todos.md). Each new run carries unfinished work forward while preserving history.

For retrospective analysis, use [local lookbacks](references/local-history.md) to read recorded task/calendar actions and immutable plan revisions. Preserve clear history through restore/undo, and distinguish chosen plans from completed work.

Keep **Done locally** distinct from provider approval. Local completion survives commits, source `updatedAt` changes and report generations. Only verified later requests to the current user or configured relevant team can reopen review work; use the collector evidence contract rather than inferred flags. New source suggestions use stable identities and material-event keys, not volatile timestamps or generated wording.

Confirmed local schedule blocks appear beside actual events. Coffee supports editing/submission and **Remove** for saved blocks, including choices migrated from Tea archives. Provider calendar events remain read-only. Update the UI after matching durable acknowledgements; preserve drafts, filters, focus and scroll across unrelated saves and source updates. A saved operation whose view refresh fails must say it was saved and offer a view-only retry.

## Present and deliver

Use [rendering](references/rendering.md) for the separate roles of Daily briefing, What changed and suggestions, and [review layouts](references/review-layouts.md) for pull requests. Keep Today with its schedule editor, a combined Daily briefing widget immediately above To do, pull requests and RFC decisions available in that order. The pull-request section defaults to reviews waiting and includes a separate **My open PRs** tab. Show an on-call alert only during the user's shift or within 24 hours before it starts. Keep recommendations distinct from saved commitments. Preserve complete eligible queues and evidence in disclosures; keep all source counts and coverage honest. Use 24-hour HH:MM throughout and the bundled café/pixel theme.

Deliver the live private workspace URL in the user's default browser, with the local path as fallback. Verify a real authenticated local save roundtrip and persistence after the launcher exits before claiming interactive saving works. An HTTP 200 report page alone verifies rendering. Honor an explicit non-HTML request using the same evidence and chosen work, with the immutable HTML companion retained locally.
