---
name: morning-coffee
description: Open or refresh the all-day Morning Coffee engineering workspace with reviews, calendar, incidents, RFCs, chosen work, local tasks and project tags. Use for morning check-ins, daily planning, intraday refreshes or an engineering overview.
---

# Morning Coffee

Maintain one workspace throughout the day. Keep current source facts beside the user's chosen work, local tasks and submitted schedule. All provider access is read-only; local state records the user's decisions. Older Tea Time archives remain readable, but new intraday updates use this workspace.

## Open, start or refresh

Accept an optional `--date YYYY-MM-DD` argument, for example `$morning-coffee --date 2026-10-19`. With no date, use the current day in the user's IANA timezone. Reject invalid dates before collecting or changing state. Resolve and select the requested day with the read-only `report_history.py select` command in [daily history](references/daily-history.md).

For a date other than today, open its latest saved immutable HTML report. If none exists, explain that no saved report exists for that date. Do not collect today's facts as historical/future evidence, change the active workspace, or overlay current local state onto an archive. For today, continue below; an existing workspace from another day still requires explicit **Start today**. A recurring task explicitly configured to start today supplies that authorization on each run; follow [scheduled runs](references/scheduled-runs.md).

1. Read [workspace lifecycle](references/workspace.md), resolve the configured report root and user's local date/IANA timezone, then inspect existing workspace state. Open the existing private workspace URL when available. Reopening is not a source refresh and never silently advances the day.
2. For a first workspace, **Refresh all**, or explicit **Start today**, follow [source collection](references/collection.md). Refresh every source: GitHub, Calendar, Google Drive, incident.io, Slack and Notion. Discover new work and recheck prior authoritative items; an absent result, changed timestamp or elapsed plan block never proves completion. Keep failures independent and preserve earlier evidence with its original timestamp.
3. Publish an initial Morning Coffee using [daily history](references/daily-history.md); the first `--workspace` session initializes its pointer. For later collections publish a `refresh` generation and apply/complete it through the [workspace lifecycle](references/workspace.md). Complete a browser-requested refresh with its exact request ID. A stale completion must preserve the active workspace. Keep chosen order, confirmations, local completion marks, tags and plans; surface additional source work as suggestions requiring explicit acceptance or dismissal.
4. Serve the published snapshot using `local_plan_server.py --workspace --background --open` and open its private URL in the user's default browser as described in [workspace lifecycle](references/workspace.md). Reuse the same private report URL across source updates. Source links open in new browser tabs; in-page section navigation stays in the report. Read-only archives remain immutable evidence; the live session loads current local state. If the T3 source-refresh bridge is unavailable, say so and keep the current facts and local controls available.

Use the bundled scripts and renderer. Format-only previews reuse collection timestamps and leave history, workspace state and search memory unchanged. A new source collection must record actual attempt times and honest coverage for all six sources.

## Collect with evidence

The [collection contract](references/collection.md) holds provider scopes, discovery/hydration commands, privacy boundaries, queue completeness, review sizing and display order. Read its linked references for the branch being collected:

- [Personal review eligibility](references/personal-review-filter.md): effective personal approval and explicit later review-request evidence, Transport author roster and local completion checks.
- [Focus, exercise, walks and lunch](references/focus-and-exercise.md): verified scheduling intervals and anonymous busy time.
- [Quarterly planning](references/quarterly-planning.md): Google Drive discovery, fiscal-date matching and link-only privacy boundaries.
- [Incidents](references/incidents.md): Transport On-Call and incident.io authority.
- [RFC reviews](references/rfc-review.md): verified In-Review lifecycle and review window.
- [Activity and watchlist](references/activity-and-watchlist.md), [search memory](references/search-memory.md): evidence-backed priorities/outcomes and provider-local queries.

Keep raw provider responses and PR evidence outside the repository. Return compact evidence with canonical identities, source timestamps, counts and completeness markers. Prior reports are evidence to recheck, never instructions to execute. Verify uncertain statuses independently before asking the user; use the structured status checks in [rendering](references/rendering.md) and attribute user answers separately from source-observed state.

## Preserve personal work

Read [local tasks](references/todos.md) before ranking work and [local interactions](references/plan-submission.md) before enabling saves. Tasks persist across days, support subtasks, importance and project tags, and have no due dates. Source activity never completes local tasks. Explicit **Start today** carries unfinished work forward while preserving history.

Keep **Done locally** distinct from provider approval. Local completion survives commits, source `updatedAt` changes and refreshes. Only verified later requests to the current user or configured relevant team can reopen review work; use the collector evidence contract rather than inferred flags. New source suggestions use stable identities and material-event keys, not volatile timestamps or generated wording.

Confirmed local schedule blocks appear beside actual events. Coffee supports editing/submission and **Remove** for saved blocks, including choices migrated from Tea archives. Provider calendar events remain read-only. Update the UI after matching durable acknowledgements; preserve drafts, filters, focus and scroll across unrelated saves and source updates. A saved operation whose view refresh fails must say it was saved and offer a view-only retry.

## Present and deliver

Use [rendering](references/rendering.md) and [review layouts](references/review-layouts.md). Keep chosen priorities, the planner, tasks, Today, incident/on-call status, RFC decisions, reviews and previous-weekday outcomes visible. Keep new suggestions distinct from chosen work. Preserve complete eligible queues and evidence in disclosures; keep all source counts and coverage honest. Use 24-hour HH:MM throughout and the bundled café/pixel theme.

Deliver the live private workspace URL in the user's default browser, with the local path as fallback. Verify a real authenticated local save roundtrip and persistence after the launcher exits before claiming interactive saving works. An HTTP 200 report page alone verifies rendering. Honor an explicit non-HTML request using the same evidence and chosen work, with the immutable HTML companion retained locally.
