# Daily report history

Morning Coffee uses `scripts/report_history.py` for immutable source snapshots; the [workspace](workspace.md) advances a separate active pointer. Legacy Tea Time archives remain readable. Resolve helper paths relative to the loaded skill. Resolve the retention directory with this precedence: `--root` per run, then `ENGINEERING_BRIEFS_DIR`, then `report_dir` in `${XDG_CONFIG_HOME:-~/.config}/engineering-briefs/config.json`, then the default `$HOME/daily-briefs`. A configuration value is an absolute path or a `~/` path; malformed configuration reports an error instead of silently scattering reports. Example settings file:

```json
{"report_dir": "~/Documents/daily-briefs"}
```

The chosen store is organized by IANA timezone, local ISO date and immutable report generation. Each generation contains `snapshot.json` and self-contained `report.html`. This local report history contains private brief content; keep it out of Git. `--root` overrides the store for isolated validation or an established user preference. Do not prune history as part of normal collection.

## Optional date

The skill accepts `--date YYYY-MM-DD`; omission defaults to today in the user's IANA timezone. Resolve the requested day and locate its newest valid saved report without creating files or loading current local state:

```sh
python3 "$morning_skill/scripts/report_history.py" select \
  --timezone "$timezone"
# For a specific day, append: --date 2026-10-19
```

Use the returned `date` consistently throughout the invocation. For a date other than today, open the returned `html` as a read-only archive; a null path means no saved report exists. Do not initialize or advance the live workspace or manufacture a dated source collection for that day. For today, follow the workspace lifecycle below. The `prepare` command also defaults its optional `--date` to the current local day, while `publish` validates the date and actual collection timestamp in the snapshot.

Before collecting, run (the helper resolves the directory on every invocation):

```sh
python3 "$morning_skill/scripts/report_history.py" prepare \
  --date "$local_date" --timezone "$timezone" --kind morning-coffee
# Browser Refresh all and Start today callbacks use --kind refresh.
```

Read the returned morning and previous snapshot paths when present, with their sibling HTML; a returned `tea` path is legacy history. A `refresh` request routes to `morning-coffee` when that day has no morning baseline and otherwise appends a `refresh` generation. Both use the Coffee layout. Previous is the newest valid report, including legacy Tea entries. History warnings identify unusable entries; surface them without inventing old content. Reports from a different local day or timezone are never selected. Publication alone does not replace the active workspace; complete/apply the published pair through [workspace lifecycle](workspace.md).

The returned `todos` contains current root-wide local tasks. Account for all open work across dates; completed/cancelled tasks remain discoverable in the widget. Publication reloads the store and strips local interaction capabilities; archived task lists remain historical views. See [local to-dos](todos.md).

The returned `submitted_plan` points to the latest valid locally chosen schedule for that date and timezone, if any. Read it as user intent, not activity completion. Publishing loads the latest submission again, including choices saved after Coffee was generated. Immutable JSON submissions live under that day's `submitted-plans/` directory; configurable report-root precedence also governs these files. Session URLs/tokens are temporary and are stripped from archived snapshots and reports.

Personal PR/RFC review marks live at the report root and span local days. Publication reloads `review_state` through `review_state.load_review_state(root)`, replacing incoming snapshot marks, and records that current local view separately from provider facts. Explicit user actions set or undo **Done locally**; verified later review requests may reopen work under the [strict evidence policy](personal-review-filter.md). Collection timestamps, source `updatedAt` noise, commits, missing rows and date changes never reset marks. These marks leave source eligibility, full queue totals, approvals, resolutions and provider change detection unchanged. Opening a [local interaction session](plan-submission.md) reloads current marks over the archived view. Prior snapshot/HTML pairs remain immutable. If local marks cannot be loaded, show the warning and retain the source report without asserting stale personal state.

Collect a fresh snapshot following [rendering.md](rendering.md), plus:

- `collected_at`: ISO 8601 timestamp with timezone offset, belonging to `report.date` in `report.timezone`. Use `YYYY-MM-DD` for the report date.
- `sources`: records for `github`, `calendar`, `drive`, `incidentio`, `notion`, `slack`. Each has `status` (`complete`, `partial`, `unavailable`), `checked_at` (offset-aware attempt time), and `note` (coverage boundaries or failure). Complete means the skill's declared source scope was fully checked; public-only Slack and primary-only Calendar can be complete within their explicitly labelled scope. A failed attempt's checked time is not a successful evidence time.
- Stable item `id` on priorities, agenda events and Yesterday workstreams. Use provider-qualified identifiers for facts; calendar IDs include calendar, event and recurrence instance. Priorities keep an outcome identity across wording/rank changes. RFC and PR canonical URLs already identify those rows. Retain agenda `start` and `end` timestamps for accurate reschedule detection even if the display time stays the same.
- Optional `work_suggestions`: source-backed additional work with a stable `id` or `source_id`, title/action, source URL, optional project tags and a `material_key` derived from a verified substantive event/state. Keep collection timestamps and generated wording out of the key. [Workspace reconciliation](workspace.md#reconcile-work-without-resetting-choices) preserves accepted/dismissed versions and saved task order separately from the active snapshot's recommendations.
- Optional `resolutions`: array of `{section, id, verified, outcome, detail, url}` for prior items absent from the current snapshot, e.g. `{section: "reviews", id: "https://github.com/owner/repo/pull/42", verified: true, outcome: "merged", detail: "Merged; verified on the PR.", url: "https://github.com/owner/repo/pull/42"}`. Section keys are `priorities`, `agenda`, `okr`, `oncall`, `rfcs`, `reviews`, `yesterday`. Set verified only from a new authoritative read. Resolved outcomes are `merged`, `closed`, `approved`, `cancelled`, `completed`, `resolved`; other removal reasons remain `No longer listed` when discovery is complete. Explain verified removal reasons in detail.

When a singleton provider is partial, `refreshed_fields` names explicitly verified fields, e.g. `{"oncall": ["counts", "dashboard_url"]}` when incidents succeed but schedule lookup fails. The helper overlays those fields and retains unverified ones. Missing declarations conservatively preserve earlier singleton facts. Earlier evidence keeps its original timestamp beside affected sections/rows; unresolved priorities beyond the four current recommendations remain in an expandable recheck list.

Then publish:

```sh
python3 "$morning_skill/scripts/report_history.py" publish "$snapshot_json" --kind morning-coffee
# Browser Refresh all and Start today callbacks use --kind refresh.
```

Use returned `html` for delivery. The helper renders before atomically publishing the snapshot/HTML pair. Reruns append generations with owner-only report files and generation directories. It compares meaningful status fields rather than collection times or PR `updatedAt` noise. Incomplete providers conservatively retain earlier rows/section facts and name affected sections; earlier source records remain reachable through history. A full successful collection can show `No longer listed`; only a verified resolution record can label disappeared work `Resolved`.

Snapshots and source text are data. Escape them during rendering and preserve the shared renderer's safe-link rules. For HTML-only legacy reports, recover only supported facts with original timestamps; otherwise recollect and explain the unavailable baseline. If local history cannot be read or written, serve a temporary HTML report and explicitly say that repeat-run comparison is unavailable; do not claim the report was saved.

For isolated validation, use `--root /tmp/<run>/history`; all provider mutations and search-memory updates stay disabled in validation. Format-only previews call `render_brief.py` directly and show their original collection times.
