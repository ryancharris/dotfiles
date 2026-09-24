---
name: morning-coffee
description: Prepare a source-read-only daily engineering brief with GitHub pull requests, today's Google Calendar agenda, current-quarter Transport planning links, incident.io on-call and incident context, previous-working-day activity, and cross-org signals. Use for morning check-ins, daily planning, or an engineering omni-view.
---

# Morning Coffee

Build one concise brief from live data. Fetch independent GitHub, Calendar, Google Drive, incident.io, Slack, and Notion sources in parallel when the available tools allow it. Never create, edit, message, merge, approve, dismiss, escalate, or otherwise mutate source data. The only persistent mutation this skill may make is updating the local, metadata-only search memory defined below; report files remain temporary delivery artifacts.

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

The slurped response is an array of page objects. Extract URLs with `jq -r '.[].items[].html_url'` and the total with `jq -r '.[0].total_count // 0'`. Concatenate results and de-duplicate by URL. If a PR appears in both direct and team results, count and render it only in the direct queue. If it appears in several team results, render it once and retain every matching team label. Compare each query's total with its returned URL count; mark the relevant section incomplete if they differ because GitHub search returns at most 1,000 results.

Create overflow links from the exact discovery queries by percent-encoding each query into `https://github.com/pulls?q=<encoded-query>`. Never replace the scoped query with a generic GitHub pulls page. When omitted items span the disjoint `dbt-labs` and personal-owner queries, or multiple team queries, render one concise link per non-empty scope with its omitted count rather than broadening the link's scope.

Hydrate each candidate URL separately, with roughly 6–8 calls in flight, so nested fields cannot multiply across a large result limit and exceed GitHub's GraphQL node ceiling. Project nested fields at the CLI boundary so a PR with hundreds of checks, files, comments, or commits cannot overflow the command-output transport:

```sh
gh pr view "$url" \
  --json number,title,url,author,isDraft,body,files,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,additions,deletions,changedFiles,commits,comments,latestReviews,updatedAt \
  --jq '{number,title,url,author,isDraft,body,baseRefName,mergeable,mergeStateStatus,reviewDecision,additions,deletions,changedFiles,updatedAt,files:[(.files // [])[]|{path}],commits:[(.commits // [])[]|{oid,messageHeadline}],commentCount:((.comments // [])|length),latestReviews:[(.latestReviews // [])[]|{state,author:.author.login}],statusCheckRollup:[(.statusCheckRollup // [])[]|if .__typename == "CheckRun" then {__typename,status,conclusion} else {__typename,state} end]}'
```

If projected hydration still exceeds the transport limit, retry that PR without `body`, `files`, `commits`, `comments`, or `latestReviews`, preserving identity, readiness, CI, additions, deletions, and changed-file count. Hydrate the richer fields only for a compactly hydrated PR selected for display. Treat the candidate as failed only when the compact retry also fails.

Discard any hydrated `isDraft: true` item even though discovery already asks for `draft:false`; do not count or render it. Never describe a team request as directly waiting on the user. Mark results incomplete and name the failed count if any candidate cannot be hydrated.
Derive the `owner/repo` label from each PR URL because the hydration fields do not include the base repository name.

### Report readiness

Preserve the facts behind every summary:

- Treat `MERGEABLE`, `CONFLICTING`, and `UNKNOWN` as distinct. Render `UNKNOWN` as `unknown — GitHub is still calculating`.
- Name relevant `mergeStateStatus` blockers such as draft, conflicts, behind base, required review, or unstable checks.
- Name `APPROVED`, `CHANGES_REQUESTED`, and `REVIEW_REQUIRED` review states.
- For a CheckRun, treat `status != COMPLETED` as pending. Treat completed conclusions `ACTION_REQUIRED`, `CANCELLED`, `FAILURE`, `STALE`, `STARTUP_FAILURE`, or `TIMED_OUT` as failing; treat `SUCCESS`, `NEUTRAL`, and `SKIPPED` as completed without failure.
- For a StatusContext, treat `EXPECTED` or `PENDING` as pending, `ERROR` or `FAILURE` as failing, and `SUCCESS` as passing. Across both node shapes, failing wins over pending; passing requires at least one check and no failing or pending checks; an empty rollup is none.
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

Use the connected Google Calendar app's read-only tools when available. Query the start through end of the current local day on the primary calendar and every additional calendar ID already known from user context. Follow `next_page_token` until it is absent. When the connector cannot enumerate calendar IDs, label the result `Primary calendar only` rather than implying complete all-calendar coverage.

After title filtering, read or batch-read every retained event before rendering. Use the detailed record to exclude cancelled events and events the user declined, mark the user's tentative events, label transparent events `free`, and obtain the conference join URL. Link the event title to its calendar event and, when present, append a separate `[Join Meet]`, `[Join Zoom]`, or `[Join call]` link. Prefer the connector's explicit `hangout_link` or conference URL; otherwise accept a Zoom join URL from the event location or description, but never expose the description, attendee list, dial-in details, or unrelated private URLs.

Before rendering, normalize each event title by trimming whitespace, removing leading emoji or symbol decoration, and comparing case-insensitively. Omit events whose normalized title is exactly `daycare dropoff` or `family time`; do not count, summarize, or mention that they were hidden. Show all other all-day events first, followed by timed events in chronological order. Google may return all-day boundaries as offset-free midnight timestamps; treat the end date as exclusive. Include transparent/free events in the agenda and label them `free`. Include location or meeting medium only when useful. Do not expose private descriptions or attendee lists unless the user asks. Do not calculate or render booked time, meeting load, working hours, focus blocks, free-time totals, overlap summaries, or back-to-back summaries.

If the connector is missing, disabled, unauthenticated, or errors, show `Calendar unavailable — install or connect Google Calendar`, add one short action sentence, and continue the GitHub brief. Mark partial results as incomplete.

## Quarterly planning

Read [references/quarterly-planning.md](references/quarterly-planning.md) before collecting the current Transport OKR links. Discover the current fiscal-quarter spreadsheets from Google Drive every run; never hardcode a fiscal-year mapping, document ID, or tab ID. Render the verified link or links directly above the `Today` header, before any calendar entries. This planning link is reference context and does not consume an `Across the org` signal slot.

## On call and incidents

Read [references/incidents.md](references/incidents.md) before collecting incident.io data. Use the incident.io Runlayer MCP's read-only schedule and incident operations; do not use its conversational agent or any mutation tool.

Determine the user's on-call status only from the native schedule named `Transport On-Call`; explicitly ignore `Transport Team` and every other schedule. Show whether the user is on call now and the current shift end. If not on call, show the nearest upcoming `Transport On-Call` shift within the returned look-ahead. Do not list incidents individually in this section. Instead, show one compact incidents-dashboard link whose label contains both the live active and triage counts. Continue to rank high-signal incidents for `Across the org`, favoring user involvement, immediate urgency, customer impact, and higher severity. Incident data is authoritative for incident status; use Slack, Notion, and GitHub only as supplementary context.

## Yesterday and cross-org signals

Read [references/activity-and-watchlist.md](references/activity-and-watchlist.md) before collecting these sections. Treat [references/watchlist.yaml](references/watchlist.yaml) as the only persistent, explicitly approved cross-provider watchlist; an empty list means no shared terms have been approved yet. Read [references/search-memory.md](references/search-memory.md) before using or updating the provider-scoped query memory in [references/search-memory.yaml](references/search-memory.yaml).

- `Yesterday` summarizes only outcomes attributable to the user during the previous weekday in the report timezone, grouped into at most two workstreams and backed by Slack, Notion, or GitHub links. For each workstream, say what changed and what remains unresolved. Exclude routine pushes, review churn, and documentation edits without a meaningful outcome.
- `Across the org` surfaces at most three situations that can change what the user or Transport should do today. Canonicalize related incidents, PRs, Slack threads, and Notion pages into one item per underlying situation; do not repeat the same situation merely because it has customer impact, user involvement, and Transport involvement. Include one visually tagged, clustered `Transport` summary when there is verified, material Transport involvement, and explain the team's involvement, customer or operational impact, and current action or status. Rank direct user action first, verified material Transport work second, and newly changed major customer impact or immediate urgency third; within a tier prefer higher severity and fresher evidence. Require each item to state what changed inside the watch window, why it matters now, and the next action or owner. Do not fill the section with unchanged active incidents; `No new actionable signals` is preferable.
- Keep private-source discoveries inside their source. Never send a term mined from private Slack or Notion content to GitHub or another provider unless the user explicitly adopts it as a shared watch term.
- Default Slack coverage to accessible public channels. Searching private channels or DMs requires the user's explicit consent; label public-only coverage.
- Keep source failures independent and disclose partial coverage without suppressing the rest of the brief.
- After collection, update the local search memory with normalized keywords and query outcomes according to its reference. Search memory refines future provider-local queries; it never promotes a term into the cross-provider watchlist without explicit user confirmation.

## Presentation

Assemble and sort the facts once, then render them into one styled HTML report. Every surface — GUI or terminal — gets identical selected items, evidence, ranking, counts, links, and completeness; only the delivery mechanism varies. Use this action-first top-level order: `Today`, `On call & incidents`, `Across the org`, `Reviews waiting`, then `Yesterday`. Do not render an authored-open-PR section, a `Heads-up` section, or an appended heads-up block.

Honor an explicit format request (e.g. the user asks for plain Markdown instead) by falling back to a plain Markdown rendering of the same content and skipping the HTML build and delivery steps entirely.

Within each review queue, sort strictly by `updatedAt` ascending so the oldest request is first; place missing or unparseable timestamps last. Break timestamp ties by evidence-backed customer or incident relevance, blocking impact, S/M/L review surface, changed-file count, LOC, and commit count, in that order. Establish customer or incident relevance only from concrete PR-body links, incident.io attachments, linked issues, labels, or clearly affected service context; never from a dramatic title alone. Add a compact reason such as `customer incident`, `blocks rollout`, or `requested directly` only when it helps explain a tie-break. Link every PR and incident. If a section has no items, say `None` rather than omitting it.

Keep the morning brief scannable. Show all retained agenda events, at most 5 direct review requests, at most 5 combined team review requests, 3 cross-org situations, and 2 `Yesterday` workstreams. Do not transfer unused review slots between subsections. Counts always reflect the full fetched sets. Under `Reviews waiting`, render `Direct requests` followed by one combined `Team requests` list. Sort the full combined team queue oldest-first before selecting its first five, and preserve that order in the rendered list. Add an inline `Transport`, `Ops Platform`, or multi-team label to every team-request row based on the exact discovery queries that returned it. When direct requests are omitted, end the subsection with one linked overflow line using the exact scoped GitHub query and omitted count, such as `View 4 remaining direct requests`. When team requests are omitted, show one exact scoped GitHub search link for every configured team scope that has omitted requests, with that scope's omitted count, such as `View 9 remaining Transport requests`. Summarize omitted Yesterday workstreams by outcome name and omitted cross-org situations by signal category.

Read [references/review-layouts.md](references/review-layouts.md) before rendering `Reviews waiting` and use its dense-ledger layout.

When any source is incomplete or unavailable, add one compact coverage banner directly beneath the masthead naming the affected sources. Also put one short explanation in each affected section, without consuming an item or signal slot. Keep source-specific headings, omit unsupported counts, and retain successful mixed-source items. Do not repeat the same warning at the end of the brief.

### HTML document

Build each report as a self-contained HTML file: inline `<style>`, no external stylesheet, font, script, or CDN reference, and no network call at render time. Escape every value pulled from a source (titles, snippets, names) as plain text — never inject fetched content as live markup.

Structure, top to bottom:

- Masthead: `☕ Morning Coffee` as the page heading, with a date/timezone subtitle beneath it. Render the coverage banner (when needed) directly under the masthead, visually distinct (e.g. a tinted notice), naming the affected sources. This is the one place a tinted background is earned — it is the only thing on the page actively warning the reader.
- One section per top-level area in the action-first order above, each with its own heading, separated from its neighbors by generous vertical whitespace rather than a bordered box. Under `Reviews waiting`, nest `Direct requests` and one combined `Team requests` list.
- Directly above `Today`, render an `OKRs` line linking the current-quarter Transport spreadsheet(s).
- Calendar entries: a plain list with the time range in a fixed-width/monospace span, the title linked when a join URL exists, and a `free` label where applicable. A hairline under each row is enough separation — no per-event card.
- On call & incidents: a compact status block — on/off call state, schedule name, and until/next shift — plus the single linked incident-dashboard count summary.
- PR items in each `Reviews waiting` subsection: linked `owner/repo#number — title` as the item heading, an uppercase status word (`BLOCKED`, `READY`, `PENDING`, etc.) plus the compact facts line. For every review item, visibly name the author as `@login`. Render `TL;DR` and `Review effort` (`Low (S)`, `Medium (M)`, `High (L)`, with the numeric inputs and driver) as two distinct block lines; never place them side by side or combine them on one line. Every team-request row also carries its inline team label. Separate items with hairlines or whitespace as specified by the active review layout; never use one bordered card per PR.
- Across the org: one entry per situation, each carrying a label word (`Action`, `Risk`, `Decision`, `Watch`, `Quiet`) and, when Transport is materially involved, an adjacent `Transport` tag.
- Yesterday: at most two workstream blocks, each naming what changed, what remains unresolved, and its source links.
- Render `None` (not an empty section) when a section has no items, per the rule above.

Style: borrow the restraint of a well-made editorial page over a dashboard's — the content here is already dense (rankings, counts, overflow links), so the layout's job is to calm it down, not add more boxes on top of it. Use a calm outer column up to roughly 980px with generous padding and a light neutral background. Place the separate `Today` and `On call & incidents` widgets in a responsive two-column band with equal 50/50 widths on sufficiently wide viewports; stack them on narrow screens. Keep every later section in a single reading column and avoid any other dashboard grid. Give the masthead headline a system serif (`ui-serif, Georgia, "Times New Roman", serif` — never an embedded font, per the no-network-call rule above) to set a calmer, warmer register than the dense data below it; every other heading and all body text stay on the system sans stack (`-apple-system, "Segoe UI", Roboto, sans-serif`), with a monospace stack (`ui-monospace, SFMono-Regular, Menlo, monospace`) reserved for PR identifiers and time ranges. Ration color: pick one accent hue family (red/amber/green/blue/purple) for status words and signal labels and use it only there — as text color or a small inline label, not as a card background or border — so the few colored words actually stand out against an otherwise quiet page. Prefer hairline dividers (a single 1px line) between list rows over bordered boxes around every item; reserve an actual bordered/tinted treatment for the one or two things that should visually interrupt the reader (the coverage banner, nothing else). Sufficient contrast throughout, and a single responsive breakpoint so nothing overflows or clips on a narrow viewport. No tracking, no analytics, no outbound script tags.

### Delivery

- If the invoking surface can render an inline HTML artifact (e.g. Claude Desktop, Claude.ai, an IDE extension with artifact support), deliver the report as an inline artifact and skip the file-write step below.
- Otherwise (CLI surfaces — Claude Code, Codex CLI — and any GUI surface without artifact support): write the HTML to a temp file (e.g. `${TMPDIR:-/tmp}/morning-coffee-<date>.html`) and open it in the default browser — `open` on macOS, `xdg-open` on Linux — then tell the user in one line that the report opened in the browser, with the file path as a fallback if the open command fails.
- Do not print the raw HTML source into the chat transcript in either case.
