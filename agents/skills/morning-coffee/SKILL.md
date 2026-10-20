---
name: morning-coffee
description: Prepare a single-pane daily engineering overview with reviews, calendar, Transport planning, incidents, RFCs, priorities and an interactive day planner for focus, exercise, dog walks and lunch. Read sources and save submitted day plans locally for Tea Time. Use for morning check-ins, daily planning, or an engineering omni-view.
---

# Morning Coffee

Build one concise brief from live data. Fetch independent GitHub, Calendar, Google Drive, incident.io, Slack, and Notion sources in parallel when the available tools allow it. All provider access is read-only. Local writes are search metadata, dated reports, user-submitted day plans and personal review marks.

## Daily history and Tea Time

Read [references/daily-history.md](references/daily-history.md) before collection. Prepare today's history with `--kind morning-coffee`, collect fresh sources, then publish the snapshot and HTML through the shared history helper. Use the user's local day and timezone. An explicit Morning Coffee invocation always produces Morning Coffee, including reruns. [Tea Time](../tea-time/SKILL.md) uses this same collection contract to refresh today's brief; if no Morning Coffee exists, it creates and serves Morning Coffee first.

For interactive Coffee delivery, read [local review marks and day plans](references/plan-submission.md), start its local save session from the published snapshot, and use its detached `--background --open` mode so browser saves remain available after the agent turn ends. No OAuth setup is needed. The immutable report stays in daily history; submitted plans and review marks are retained separately in the same configured store. If local saving cannot be enabled, disclose that limitation and serve the ordinary report. A successful plan submit records the chosen schedule; **Mark done locally** records personal PR/RFC review progress separately from source approvals. Session opening reloads current local marks over archived snapshot state.

## Local to-dos

Read [local to-dos](references/todos.md) before ranking work. The history prepare result includes current tasks; account for pending overdue and due-today items alongside source priorities, labelled as user-entered work. Keep future, completed and cancelled tasks discoverable in the shared nested widget; parent and child tasks retain independent dates and statuses. Explicit widget actions update the local store for both briefs; source activity never completes a task automatically.

## Collect once, render from compact evidence

Keep full provider responses and raw PR hydration in a temporary run directory. Return one compact representation to the model: prefer structured content, otherwise parse the relevant text once. Show counts, candidate identities, concise evidence and completeness metadata rather than full response envelopes, duplicated representations or repeated passing-check arrays. Project results inside the orchestration call before returning them to the model; preserve pagination/cap markers and source failures in that projection. When discovering tools, inspect matching names first, then only the selected read operations’ declarations. Reuse saved evidence for targeted reads instead of printing a larger raw envelope after truncation.

For format-only preview iterations, reuse the dated temporary snapshot and display its collection times; do not present it as a fresh collection. Recollect live data for a new dated brief or an explicit refresh. Preview runs leave search memory and installed files unchanged. Generate HTML with the bundled renderer rather than rewriting its CSS, scripts and markup each run.

## Establish context

- Use the user's current local date and timezone for the report.
- Resolve the GitHub login with `gh api user --jq .login`; do not hardcode it. Use this API call as the capability check rather than relying on the aggregate exit status of `gh auth status`.
- Limit every GitHub queue to repositories owned by `dbt-labs` or by the authenticated `$login`. Exclude every other repository owner, even when the user authored the PR or was requested for review.
- If `gh-dash/config.yml` exists, use it only to discover `dbt-labs` team review scopes. Ignore unrelated organizations and PR sections.
- Label each source failure in its own section and continue with the other source. Never replace missing live data with examples or guesses.

## GitHub

If `gh api user --jq .login` fails, show `GitHub unavailable — fix or unset an invalid GH_TOKEN/GITHUB_TOKEN, or run gh auth login -h github.com` and continue with the calendar. Do not let a broken account on another host disable a working GitHub account.

Avoid `gh search prs`; its handling of `is:open` is unreliable in this environment. Discover direct review requests through the GitHub Search API. Run separate queries for the two allowed, disjoint owner scopes; the REST endpoint rejects combining these qualifiers with `OR`:

```sh
query="is:pr is:open org:dbt-labs user-review-requested:@me -author:$login draft:false"
gh api --paginate --slurp -X GET search/issues \
  -f q="$query" -f per_page=100

query="is:pr is:open user:$login user-review-requested:@me -author:$login draft:false"
gh api --paginate --slurp -X GET search/issues \
  -f q="$query" -f per_page=100
```

For each configured `dbt-labs` team, query only `org:dbt-labs team-review-requested:dbt-labs/TEAM -author:$login draft:false`. Never query team queues in personal repositories. Do not fetch a separate authored-open-PR queue.

The slurped response is an array of page objects. Extract URLs with `jq -r '.[].items[].html_url'` and the total with `jq -r '.[0].total_count // 0'`. Concatenate results and de-duplicate by URL. If a PR appears in both direct and team results, render it once and classify its request type as Direct. If it appears in several team results, render it once and retain every matching team label. Compare each query's total with its returned URL count; mark the relevant section incomplete if they differ because GitHub search returns at most 1,000 results.

Apply the personal-approval eligibility rules in [references/personal-review-filter.md](references/personal-review-filter.md), then retain every eligible, successfully hydrated, non-draft result for display. Merge direct and team requests into one filterable table. Preserve request-type provenance and every matching team label. Search pagination limits and hydration failures still require honest incompleteness notices; table filtering never changes the fetched totals. Retain exact scoped GitHub query links as source references and recovery links for incomplete results.

Hydrate each candidate separately, with roughly 6–8 calls in flight. Resolve helper paths from this skill directory and save raw JSON outside the skill/repository. Use the compact helper for the model-facing view:

```sh
gh pr view "$url" \
  --json number,title,url,author,isDraft,body,files,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,additions,deletions,changedFiles,commits,updatedAt \
  > "$raw_json"
python3 "$skill_dir/scripts/compact_pr_metadata.py" "$raw_json" "$compact_json"
```

The helper aggregates every returned check exactly and exposes bounded body/path/commit evidence with truncation flags. Keep raw evidence for targeted reads when a neutral summary, hold, or dependency is unclear. A sampled path list cannot establish that tests, migrations or components are absent; use exact changedFiles for effort. If commitCountUnverified is true, resolve the exact PR commit total before displaying sizing inputs. Collect personal review evidence with `scripts/collect_personal_reviews.py` as described in the personal-review reference; it fetches current targets and timelines only for effective personal approvals. Fetch other comments or reviews only when they materially affect effort or clarify an action.

If hydration fails, retry the PR with minimal identity, readiness, CI and size metadata, then retrieve missing exact sizing inputs separately. Mark a candidate failed only when the minimal retry also fails; disclose unavailable rich evidence rather than inventing a summary.

Discard any hydrated `isDraft: true` item even though discovery already asks for `draft:false`; do not count or render it. Never describe a team request as directly waiting on the user. Mark results incomplete and name the failed count if any candidate cannot be hydrated.
Derive the `owner/repo` label from each PR URL because the hydration fields do not include the base repository name.

### Report readiness

Preserve the facts behind every summary:

- Treat `MERGEABLE`, `CONFLICTING`, and `UNKNOWN` as distinct. Render `UNKNOWN` as `unknown — GitHub is still calculating`.
- Name relevant `mergeStateStatus` blockers such as draft, conflicts, behind base, required review, or unstable checks.
- Name `APPROVED`, `CHANGES_REQUESTED`, and `REVIEW_REQUIRED` review states.
- For a CheckRun, treat `status != COMPLETED` as pending. Treat completed conclusions `ACTION_REQUIRED`, `CANCELLED`, `FAILURE`, `STALE`, `STARTUP_FAILURE`, or `TIMED_OUT` as failing; treat `SUCCESS`, `NEUTRAL`, and `SKIPPED` as completed without failure.
- For a StatusContext, treat `EXPECTED` or `PENDING` as pending, `ERROR` or `FAILURE` as failing, and `SUCCESS` as passing. Across both node shapes, failing wins over pending; passing requires at least one check and no failing or pending checks; an empty rollup is none.
- Unrecognized check types, states or completed conclusions remain unknown; report uncertainty rather than counting them as passing.
- Do not flatten readiness to a yes/no when the evidence is mixed. Prefer summaries such as `blocked — mergeable; review required; CI 18/18 passing`.

### Summarize review work

For every rendered direct or team review item, include all three:

- `Author:` the GitHub login from the hydrated `author.login` field, rendered as `@login`. If GitHub does not return a login, render `Author unavailable`; never infer it from commits, branch names, or prose.
- `TL;DR:` one or two neutral sentences explaining what changes and why, based on the PR title, body, changed-file paths, and commit metadata. Do not invent motivation or behavior. If those fields do not establish a useful summary, say `TL;DR unavailable from PR metadata.`
- `Review effort:` `Low (S)`, `Medium (M)`, or `High (L)`, followed by a compact evidence-based explanation. This is review surface, not elapsed-time or completion-time guidance.

Calculate `LOC = additions + deletions` and `C = commit count`:

- `S`: at most 5 files, 200 LOC, and 3 commits.
- `M`: at most 15 files, 800 LOC, and 8 commits.
- `L`: exceeds any M ceiling.

Always display the inputs beside the label, for example `Medium (M) — 9 files, +318/-74, 4 commits`. Explain the main review drivers that are directly observable, such as a localized file set, cross-component breadth, tests, migrations, schemas, generated files, or dependency changes. Do not infer risk from the author or title alone, and do not adjust the S/M/L size class subjectively. Show comment or prior-review counts only when their volume materially increases expected review effort.

## Google Calendar

Read [references/focus-and-exercise.md](references/focus-and-exercise.md) before collecting scheduling evidence. Suggest one hour of exercise, at least two contiguous hours of focus, a thirty-minute dog walk and a thirty-minute lunch. Dog walks can use any verified free time during the local day. The user can submit their chosen blocks to the local daily report store; read [plan submission](references/plan-submission.md) to enable the local save button. Tea reads the latest submitted plan for that local date and timezone. Calendar events remain unchanged.

Use the connected Google Calendar app's read-only tools when available. Query the start through end of the current local day on the primary calendar and every additional calendar ID already known from user context. Follow `next_page_token` until it is absent. When the connector cannot enumerate calendar IDs, label the result `Primary calendar only` rather than implying complete all-calendar coverage.

After title filtering, read or batch-read every retained event before rendering. Use the detailed record to exclude cancelled events and events the user declined, mark the user's tentative events, label transparent events `free`, and obtain the conference join URL. Link the event title to its calendar event and, when present, append a separate `[Join Meet]`, `[Join Zoom]`, or `[Join call]` link. Prefer the connector's explicit `hangout_link` or conference URL; otherwise accept a Zoom join URL from the event location or description, but never expose the description, attendee list, dial-in details, or unrelated private URLs.

Before rendering, normalize each event title by trimming whitespace, removing leading emoji or symbol decoration, and comparing case-insensitively. Omit events whose normalized title is exactly `daycare dropoff` or `family time`; do not count, summarize, or mention that they were hidden. Show all other all-day events first, followed by timed events in chronological order. Google may return all-day boundaries as offset-free midnight timestamps; treat the end date as exclusive. Include transparent/free events in the agenda and label them `free`. Include location or meeting medium only when useful. Do not expose private descriptions or attendee lists unless the user asks. Use anonymous occupied intervals, including transparent/free events, for the nonoverlapping focus/exercise/walk suggestions defined in the scheduling reference. Keep booked-time totals, meeting-load calculations, free-time totals, overlap summaries and back-to-back summaries out of the brief.

If the connector is missing, disabled, unauthenticated, or errors, show `Calendar unavailable — install or connect Google Calendar`, add one short action sentence, and continue the GitHub brief. Mark partial results as incomplete.

## On call and incidents

Read [references/incidents.md](references/incidents.md) before collecting incident.io data. Use the incident.io Runlayer MCP's read-only schedule and incident operations; do not use its conversational agent or any mutation tool.

Determine the user's on-call status only from the native schedule named `Transport On-Call`; explicitly ignore `Transport Team` and every other schedule. Show whether the user is on call now and the current shift end. If not on call, show the nearest upcoming `Transport On-Call` shift within the returned look-ahead. Do not list incidents individually in this section. Instead, show one compact incidents-dashboard link whose label contains both the live active and triage counts. Use high-signal incidents to inform `Daily priorities`, favoring user involvement, immediate urgency, customer impact, and higher severity. Incident data is authoritative for incident status; use Slack, Notion, and GitHub only as supplementary context.

## RFCs needing review

Read [references/rfc-review.md](references/rfc-review.md) and check the configured Notion RFC database every run. Include only RFCs whose current lifecycle is In-Review and whose review-submission date falls within the past two weeks; use the reference's explicit missing-date fallback. Fetch shortlisted pages to establish the requested decision and infrastructure relevance. Render a dedicated `RFCs to review` section; keep RFC-only findings in that section so they do not displace operational signals.

## Daily priorities and yesterday

Read [references/activity-and-watchlist.md](references/activity-and-watchlist.md) before collecting these sections. Treat [references/watchlist.yaml](references/watchlist.yaml) as the only persistent, explicitly approved cross-provider watchlist; an empty list means no shared terms have been approved yet. Read [references/search-memory.md](references/search-memory.md) before using or updating the provider-scoped query memory in [references/search-memory.yaml](references/search-memory.yaml).

- `Yesterday` summarizes only outcomes attributable to the user during the previous weekday in the report timezone, grouped into at most two workstreams and backed by Slack, Notion, or GitHub links. For each workstream, say what changed and what remains unresolved. Exclude routine pushes, review churn, and documentation edits without a meaningful outcome.
- `Daily priorities` has its own visible heading above a ranked list of at most four recommended outcomes for the user today. Base each recommendation on verified work, operational risk, a deadline, or an upcoming decision; state the next action, why it matters now, and supporting links. Distinguish source facts from recommendations and identify the owner when known. Prioritize direct user action, material Transport work, then urgent customer or deadline risks. Collapse related evidence into one priority and omit unchanged background incidents. Use the watchlist and usefulness gate in the activity reference to support these recommendations; keep this separate from the agenda and past activity.
- Keep private-source discoveries inside their source. Never send a term mined from private Slack or Notion content to GitHub or another provider unless the user explicitly adopts it as a shared watch term.
- Default Slack coverage to accessible public channels. Searching private channels or DMs requires the user's explicit consent; label public-only coverage.
- Keep source failures independent and disclose partial coverage without suppressing the rest of the brief.
- After collection, update the local search memory with normalized keywords and query outcomes according to its reference. Search memory refines future provider-local queries; it never promotes a term into the cross-provider watchlist without explicit user confirmation.

## Presentation

Assemble and sort the facts once, then render them into one styled HTML report. Every surface — GUI or terminal — gets identical selected items, evidence, ranking, counts, links, and completeness; only the delivery mechanism varies. Coffee is the day’s single pane of glass: keep all ranked priorities (up to four), the interactive calendar, local to-do list, agenda, on-call/incident status, RFC decisions, review queue and previous-weekday outcomes visible. Use concise labels, actions and structured rows instead of hiding whole domains to shorten the page. Collapse supporting evidence and long explanations. Tea Time leads with unfinished work and a short change TL;DR, then shows a visible snapshot across all five context domains; its full queues may remain expandable. Preserve complete evidence in the snapshot and expandable sections. Do not render an authored-open-PR section, a `Heads-up` section, or an appended heads-up block.

Honor an explicit format request (e.g. plain Markdown) by delivering the same selected content in that format. Keep the HTML companion in local daily history for Tea Time comparisons, and skip HTML delivery.

Across the single combined review table, sort strictly by `updatedAt` ascending so the oldest request is first; place missing or unparseable timestamps last. Break timestamp ties by evidence-backed customer or incident relevance, blocking impact, S/M/L review surface, changed-file count, LOC, and commit count, in that order. Establish customer or incident relevance only from concrete PR-body links, incident.io attachments, linked issues, labels, or clearly affected service context; never from a dramatic title alone. Add a compact reason such as `customer incident`, `blocks rollout`, or `requested directly` only when it helps explain a tie-break. Link every PR and incident. If a section has no items, say `None` rather than omitting it.

Keep the morning brief scannable. Show all retained agenda events, at most four Daily priorities, every eligible hydrated non-draft PR, all eligible RFCs, and at most two Yesterday workstreams. In `Reviews waiting`, render one table with Direct/Team request-type badges and an All/Direct/Team filter. De-duplicate by PR URL, give Direct classification precedence, and retain all matching team labels. Sort the whole merged result oldest-updated-first; filtering and pagination preserve that order. Summarize omitted Yesterday workstreams by outcome name.

Read [references/review-layouts.md](references/review-layouts.md) before rendering `Reviews waiting`. It defines the verified Transport-author default, combined filters, reset behavior, adjustable pagination, complete-row retention and honest filtered/total counts. Use its bundled controls; pagination never limits collection. Review progress defaults to **To review**, with **All** and **Done locally** options. RFCs remain visible with local progress beside separate source approval status.

When any source is incomplete or unavailable, add one compact coverage banner directly beneath the masthead naming the affected sources. Also put one short explanation in each affected section, without consuming an item or signal slot. Keep source-specific headings, omit unsupported counts, and retain successful mixed-source items. Do not repeat the same warning at the end of the brief.

### HTML document

Read [references/rendering.md](references/rendering.md) for the compact snapshot schema. For a format-only preview run the bundled renderer directly; for a new brief publish through the daily history helper, which invokes this renderer:

```sh
python3 "$skill_dir/scripts/render_brief.py" "$snapshot_json" "$report_html"
```

Use the bundled renderer, CSS and script as the maintained default; [rendering.md](references/rendering.md) defines the snapshot and visual contract. Keep current actions, ownership and blockers visible, with longer rationale and exact evidence in native disclosures. Every eligible item remains accessible. Escape source text and use safe links; inline all assets with no rendering-time provider calls.

Coffee shows the interactive calendar from 08:30–17:00 before a plan is saved. Successful submission collapses it; Today’s **Edit schedule** restores it. Optional blocks start unplaced; restore previously submitted choices, and add confirmed blocks to Today only after a successful local save. Support dragging and keyboard placement, preserve fixed events, and reject overlaps. Tea shows actual events and saved choices with conflict markers. Omit Quarter plan and the report footer; PR disclosures contain only context absent from the row. Use 24-hour HH:MM for every UI time, including controls and legacy fields. Session-enabled Coffee and Tea connect to the local server only for user-triggered saves; source systems remain read only.

### Delivery

- If the invoking surface can render an inline HTML artifact (e.g. Claude Desktop, Claude.ai, an IDE extension with artifact support), deliver the saved report as an inline artifact. The local history pair still persists for Tea Time.
- Otherwise (CLI surfaces — Claude Code, Codex CLI — and any GUI surface without artifact support): open the temporary local-session HTML when available, otherwise the HTML returned by the history helper, in the default browser — `open` on macOS, `xdg-open` on Linux. Tell the user in one line that the report opened in the browser, with the file path as a fallback if the open command fails. When history is unavailable or this is a preview, use a temporary HTML file and disclose that it was not saved to daily history.
- Do not print the raw HTML source into the chat transcript in either case.
