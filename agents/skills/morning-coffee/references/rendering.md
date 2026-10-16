# Rendering a Morning Coffee snapshot

Collect and normalize source facts once, then render through the bundled helper:

```sh
python3 scripts/render_brief.py /tmp/snapshot.json /tmp/morning-coffee.html
```

The helper uses only Python's standard library. It reads sibling `assets/brief.css` and `assets/brief.js`, then inlines both into the output. It does not call providers, update memory, or open a browser. The resulting report makes no network calls during rendering. Links remain ordinary user-initiated navigation. Keep the snapshot and output temporary; never commit real report data with the helper.

The root JSON object has `schema_version: 1` and these fields. Strings are plain source text, never HTML:

- `report`: `title`, `page_title`, `eyebrow`, local `date`, `time`, IANA `timezone`, optional `preview_label`, and `footer`.
- `coverage`: one compact string for the coverage banner, or an empty string when no notice is needed.
- `priorities`: array of `{title, context, action, done, evidence}`. Evidence is `{paragraphs: [string], links: [{label, url}]}`.
- `okr`: optional `{label, url, period}` with the verified current-quarter link.
- `agenda`: `{coverage, events}`. Every event has `{time, title, url, join_url, join_label}`; optional `free` and `tentative` booleans add explicit labels. Retain all in-scope events.
- `oncall`: `{schedule, state, responder, shift_label, shift, dashboard_url, counts, note}`. Counts is `{active: integer, triage: integer}` from verified incident data. Omit unsupported counts rather than guessing.
- `rfcs`: `{window_label, database_url, coverage_label, coverage, items}`. An item has `{id, title, url, author, submitted_local, request_emoji, request_label, user_approved, approval_status, summary, relationship, next_action, approval_url}`. Only the collector decides inclusion in the exact In-Review / rolling-14-day window, and only verified user approval sets `user_approved: true`.
- `reviews`: `{collected_label, scopes: [{label, url}], items}`. Items are the complete, deduplicated eligible queue in canonical oldest-first order, after excluding personal approvals without an explicit re-request. Each has `{repository, number, url, title, queue, teams, author, readiness, reviewDecision, mergeStateStatus, ci, effort, updatedAt, summary, changedFiles, commitCount, additions, deletions}`. `authorOnTransport` is true/false for complete roster coverage and null when membership is unknown. `authorRoster` is `{status, note}` with status complete/partial/unavailable, and `personalReview` reports excludedCount, reRequestedCount and unknownCount. Default Authors is Transport team only for a complete roster; otherwise Everyone with a coverage note. `queue` is `direct` or `team`; direct takes precedence over overlaps. `author` is `{login}` or null; `readiness` is `{status, facts}`; `ci` is `{passing, failing, pending, total}` with optional `unknown`; an unavailable total is null; `effort` is `{size, label, inputs, driver}`. Size is S/M/L. Missing or invalid update timestamps render as unavailable. Do not retain full commits, files, raw bodies, or checks in this rendering snapshot. Derive and copy source fields programmatically; author only the concise recommendation/summary text instead of reproducing bulk JSON through the model.
- `yesterday`: `{date, coverage, items: [{title, content}]}` using the same evidence shape as priorities.

The section navigator, readiness/effort distributions, and request totals derive from snapshot rows. They summarize the full retained queue, independent of the Authors default; while the table defaults to ten rows. Filters, adjustable 10/25/50/All pagination, and clear controls operate on the existing DOM; no additional fetching or re-ranking occurs. Every PR is included in the HTML, and all remain visible if JavaScript is unavailable.

# Dense presentation contract

Order: Daily priorities, OKRs, Today, On call & incidents, RFCs to review, Reviews waiting, Yesterday. Today and On call remain separate full-width rows. No Across the org section.

Use aligned ledgers for priorities, RFCs, and PRs, with readable typography, moderate row spacing, hairlines, and broad use of available width. The bundled theme uses a warm Gruvbox-inspired dark background, cream text, tan secondary labels and a muted amber accent. Essential metadata remains comfortably readable; do not shrink it to achieve density. Show data-grounded readiness and size distributions, count navigation, and review-size glyphs. Use muted semantic accents with readable labels and reserve a tinted interruption for coverage. Keep contrast and keyboard focus clear on the dark surfaces. No decorative image assets are needed.

Keep each priority's action and completion checkpoint visible. Keep PR title, author, Direct/Team source, team tags, readiness, CI counts, and numeric size inputs visible. Put full PR TL;DR, effort driver, precise readiness facts, and timestamp inside a semantic `details` disclosure. Priority, RFC, and Yesterday evidence may also use disclosures. Never remove facts to achieve density.

The single responsive breakpoint is 760px. Wide ledgers span the full reading width; narrow layouts stack fields with no fixed minimum column widths. Explicit table roles preserve row/column semantics when CSS changes table display. Label size shorthand (`f` files, `c` commits), approval checkmarks, and request emojis. Distribution counts must also be readable as text and accessible labels.
