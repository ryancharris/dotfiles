---
name: morning-coffee
description: Generate a static morning report with today's calendar, local to-do list, pull requests, on-call alert and newly surfaced work. Use for morning check-ins, daily planning or an engineering overview.
---

# Morning Coffee

One static `report.html` per run. No server, no history archive. All provider access is read-only.

State lives in `${MORNING_COFFEE_DIR:-~/daily-briefs/coffee}`:

| File | Purpose |
|---|---|
| `tasks.md` | Your to-do list. Edit it directly: `- [ ] task` / `- [x] done` |
| `previous.json` | Last run's snapshot, kept only to find what is new |
| `report.html` | Latest report |

## Run

1. **Collect** (read-only) into one snapshot dict. Schema below.
   - **Required:** GitHub (`gh api user --jq .login`; use `gh api -X GET search/issues`, not `gh search prs`), Calendar, incident.io. If a required source fails, name it, stop and ask; do not publish a silent partial report.
   - **Optional:** Slack (public channels only) and Notion. If a connector is missing or unauthenticated, skip it, record `status: "skipped"`, and continue. Never block on OAuth for these.
2. **Render:** `python3 scripts/morning_coffee.py --dir "$DIR" snapshot.json` writes `report.html`, rotates `previous.json`, and prints the "New since last run" count.
3. **Open** `report.html` in the default browser (`open "$DIR/report.html"`).

## Sources

- **GitHub:** only `dbt-labs/*` and the user's own repos. Reviews waiting = `is:pr is:open user-review-requested:@me -author:$login draft:false` (plus `org:dbt-labs` and `user:$login` scopes, run separately). Mine = `is:pr is:open author:$login`, drafts included. De-duplicate by URL.
- **Calendar:** there is no Calendar MCP. Read today's primary calendar with the `orca-computer-use` skill in Firefox (`org.mozilla.firefox`), the window titled "... - Calendar - ...". Never read other Firefox windows. View only: never create, edit, RSVP or delete. Read only the user's own calendar: exclude the Transport PTO calendar (all-day `... - PTO` entries). Skip declined or cancelled events and events titled `daycare dropoff` or `family time`. Mark tentative and free events. If Calendar is signed out, stop and tell the user to sign in.
- **incident.io:** schedule `Transport On-Call` only (ignore `Transport Team`). Record the user's current and next shift as offset-aware `start`/`end`. List open incidents with severity.
- **Slack / Notion (optional):** items that need the user, e.g. direct mentions and RFCs awaiting their review. Each needs a stable `id` and a `url`.

## Snapshot schema

```json
{
  "date": "2026-11-13", "timezone": "America/Toronto", "collected_at": "ISO-8601 with offset",
  "sources": {"github": {"status": "complete|partial|unavailable|skipped", "note": ""}},
  "calendar": [{"id": "", "title": "", "start": "ISO or YYYY-MM-DD", "end": "", "all_day": false,
                "tentative": false, "free": false, "url": "", "join_url": ""}],
  "reviews":  [{"url": "", "title": "", "repo": "", "author": "", "updated_at": "", "request": "Direct|Team"}],
  "authored": [{"url": "", "title": "", "repo": "", "updated_at": "", "draft": false, "state": "e.g. CI failing"}],
  "oncall":   {"current_shift": {"start": "", "end": ""}, "next_shift": {"start": "", "end": ""}},
  "incidents": [{"id": "", "title": "", "url": "", "severity": ""}],
  "slack": [{"id": "", "title": "", "url": ""}],
  "notion": [{"id": "", "title": "", "url": ""}]
}
```

## What the report shows

Today (calendar, 24-hour HH:MM), To do (from `tasks.md`), Pull requests (Reviews waiting oldest first, My open PRs), an on-call alert only during a shift or within 24 hours before it starts, and **New since last run**: items whose identity or `state` was not in `previous.json`. On the first run everything is new, so the list is hidden.

**Today** draws a 08:00–19:00 timeline with calendar events and your own blocks (focus, exercise, dog walk, lunch, learning or custom). Blocks can be moved in 15-minute steps, resized, deleted, and are flagged when they overlap an event or another block. Blocks must fit inside the window.

**Interactive in the browser, no server.** Todos can be checked, added and deleted; Today events, review and authored PRs take a done mark; new items can be dismissed. Done marks and dismissals are saved in the browser's localStorage per report date. Todo changes are saved there too and override `tasks.md` in that browser. **Download tasks.md** exports them. Replace `tasks.md` with the download to keep changes for the next run. Browser storage is per browser profile and is not shared between machines. A source that was skipped or unavailable is named in one coverage line.

Escape all provider text. Keep raw responses and screenshots out of the repo and the report.
