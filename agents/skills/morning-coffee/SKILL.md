---
name: morning-coffee
description: Prepare a read-only daily engineering brief with GitHub pull requests, today's Google Calendar agenda, current-quarter Transport planning links, incident.io on-call and incident context, previous-working-day activity, and cross-org signals. Use for morning check-ins, daily planning, or an engineering omni-view.
---

# Morning Coffee

Build one concise brief from live data. Fetch independent GitHub, Calendar, Google Drive, incident.io, Slack, and Notion sources in parallel when the available tools allow it. Never create, edit, message, merge, approve, dismiss, escalate, or otherwise mutate source data.

## Establish context

- Use the user's current local date and timezone for the report.
- Resolve the GitHub login with `gh api user --jq .login`; do not hardcode it. Use this API call as the capability check rather than relying on the aggregate exit status of `gh auth status`.
- Limit every GitHub queue to repositories owned by `dbt-labs` or by the authenticated `$login`. Exclude every other repository owner, even when the user authored the PR or was requested for review.
- If `gh-dash/config.yml` exists, use it only to discover `dbt-labs` team review scopes. Ignore unrelated organizations and PR sections.
- Label each source failure in its own section and continue with the other source. Never replace missing live data with examples or guesses.

## GitHub

If `gh api user --jq .login` fails, show `GitHub unavailable — fix or unset an invalid GH_TOKEN/GITHUB_TOKEN, or run gh auth login -h github.com` and continue with the calendar. Do not let a broken account on another host disable a working GitHub account.

Avoid `gh search prs`; its handling of `is:open` is unreliable in this environment. Discover candidate PR URLs through the GitHub Search API instead. Run separate queries for the two allowed, disjoint owner scopes; the REST endpoint rejects combining these qualifiers with `OR`:

```sh
query="is:pr is:open org:dbt-labs author:$login draft:false"
gh api --paginate --slurp -X GET search/issues \
  -f q="$query" -f per_page=100

query="is:pr is:open user:$login author:$login draft:false"
gh api --paginate --slurp -X GET search/issues \
  -f q="$query" -f per_page=100
```

For direct requests, repeat both owner-scope queries with `user-review-requested:@me -author:$login draft:false`. For each configured `dbt-labs` team, query only `org:dbt-labs team-review-requested:dbt-labs/TEAM -author:$login draft:false`. Never query team queues in personal repositories.

The slurped response is an array of page objects. Extract URLs with `jq -r '.[].items[].html_url'` and the total with `jq -r '.[0].total_count // 0'`. Concatenate results and de-duplicate by URL. If a PR appears in both direct and team results, count and render it only in the direct queue. Compare each query's total with its returned URL count; mark the relevant section incomplete if they differ because GitHub search returns at most 1,000 results.

Create overflow links from the exact discovery queries by percent-encoding each query into `https://github.com/pulls?q=<encoded-query>`. Never replace the scoped query with a generic GitHub pulls page. When omitted items span the disjoint `dbt-labs` and personal-owner queries, or multiple team queries, render one concise link per non-empty scope with its omitted count rather than broadening the link's scope.

Hydrate each candidate URL separately, with roughly 6–8 calls in flight, so nested fields cannot multiply across a large result limit and exceed GitHub's GraphQL node ceiling. Project nested fields at the CLI boundary so a PR with hundreds of checks, files, comments, or commits cannot overflow the command-output transport:

```sh
gh pr view "$url" \
  --json number,title,url,author,isDraft,body,files,baseRefName,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup,additions,deletions,changedFiles,commits,comments,latestReviews,updatedAt \
  --jq '{number,title,url,author,isDraft,body,baseRefName,mergeable,mergeStateStatus,reviewDecision,additions,deletions,changedFiles,updatedAt,files:[(.files // [])[]|{path}],commits:[(.commits // [])[]|{oid,messageHeadline}],commentCount:((.comments // [])|length),latestReviews:[(.latestReviews // [])[]|{state,author:.author.login}],statusCheckRollup:[(.statusCheckRollup // [])[]|if .__typename == "CheckRun" then {__typename,status,conclusion} else {__typename,state} end]}'
```

If projected hydration still exceeds the transport limit, retry that PR without `body`, `files`, `commits`, `comments`, or `latestReviews`, preserving identity, readiness, CI, additions, deletions, and changed-file count. Hydrate the richer fields only for a compactly hydrated PR selected for display. Treat the candidate as failed only when the compact retry also fails.

Discard any hydrated `isDraft: true` item from the user's PR queue even though discovery already asks for `draft:false`; do not count or render it. Never describe a team request as directly waiting on the user. Mark results incomplete and name the failed count if any candidate cannot be hydrated.
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

For every rendered direct or team review item, include both:

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

Read [references/activity-and-watchlist.md](references/activity-and-watchlist.md) before collecting these sections. Treat [references/watchlist.yaml](references/watchlist.yaml) as the only persistent, explicitly approved cross-provider watchlist; an empty list means no shared terms have been approved yet.

- `Yesterday` summarizes only outcomes attributable to the user during the previous weekday in the report timezone, grouped into at most two workstreams and backed by Slack, Notion, or GitHub links. For each workstream, say what changed and what remains unresolved. Exclude routine pushes, review churn, and documentation edits without a meaningful outcome.
- `Across the org` surfaces at most three situations that can change what the user or Transport should do today. Canonicalize related incidents, PRs, Slack threads, and Notion pages into one item per underlying situation; do not repeat the same situation merely because it has customer impact, user involvement, and Transport involvement. Include one visually tagged, clustered `Transport` summary when there is verified, material Transport involvement, and explain the team's involvement, customer or operational impact, and current action or status. Rank direct user action first, verified material Transport work second, and newly changed major customer impact or immediate urgency third; within a tier prefer higher severity and fresher evidence. Require each item to state what changed inside the watch window, why it matters now, and the next action or owner. Do not fill the section with unchanged active incidents; `No new actionable signals` is preferable.
- Keep private-source discoveries inside their source. Never send a term mined from private Slack or Notion content to GitHub or another provider unless the user explicitly adopts it as a shared watch term.
- Default Slack coverage to accessible public channels. Searching private channels or DMs requires the user's explicit consent; label public-only coverage.
- Keep source failures independent and disclose partial coverage without suppressing the rest of the brief.

## Presentation

Assemble and sort the facts once, then render them for the current client. Desktop and CLI must contain the same selected items, evidence, ranking, counts, links, and completeness; only wording density and layout may differ. Use this action-first top-level order in both clients: `Today`, `On call & incidents`, `Across the org`, the adjacent PR sections `Your open PRs` and `Reviews waiting`, then `Yesterday`. Do not render a `Heads-up` section or append a heads-up block.

Honor an explicit format request. Otherwise use client context supplied to the agent: choose desktop when it identifies Codex Desktop or the app, and terminal when it identifies the Codex CLI or TUI. If the client is unclear, use desktop Markdown. Do not infer the visible client from shell environment variables such as `TERM`, TTY state, or `NO_COLOR`.

Sort the user's non-draft PRs by action severity, then most recently updated. Use this severity order: conflicts or changes requested, failing CI, behind base, required review, pending CI, ready, unknown. Within each review queue, sort by evidence-backed customer or incident relevance, blocking impact, S/M/L review surface, changed-file count, LOC, commit count, and oldest `updatedAt`, in that order. Establish customer or incident relevance only from concrete PR-body links, incident.io attachments, linked issues, labels, or clearly affected service context; never from a dramatic title alone. Add a compact reason such as `customer incident`, `blocks rollout`, or `requested directly` only when it explains why an item outranked another. Link every PR and incident. If a section has no items, say `None` rather than omitting it.

Keep the morning brief scannable. In both Desktop and CLI, show all retained agenda events, at most 3 of the user's non-draft PRs, 3 direct review requests, 3 team review requests total across all configured teams, 3 cross-org situations, and 2 `Yesterday` workstreams. Counts always reflect the full fetched sets. Under `Team requests`, select from the globally ranked cross-team queue first, then group the selected items into one subsection per configured team; in the current configuration, always render `Transport` and `Ops Platform` as sibling subsections with each team's exact full count. Preserve the combined 3-item cap rather than granting each team its own allowance. When a PR queue has omitted items, end that queue with linked overflow text such as `View 7 remaining non-draft PRs`, `View 4 remaining direct requests`, or a team-specific `View 9 remaining Transport requests`; use the exact scoped GitHub search link or links defined above. Put each team-specific overflow link inside its team subsection, including when that team has no selected card. Summarize omitted Yesterday workstreams by outcome name and omitted cross-org situations by signal category.

When any source is incomplete or unavailable, add one compact coverage line directly beneath the masthead naming the affected sources. Also put one short explanation in each affected section, without consuming an item or signal slot. Keep source-specific headings, omit unsupported counts, and retain successful mixed-source items. Do not repeat the same warning at the end of the brief.

### Desktop Markdown

- Start with `# ☕ Morning Coffee` and an italic date/timezone subtitle.
- Use `##` headings for open PRs, reviews, today, on call and incidents, yesterday, and across the org. Under `Reviews waiting`, use `### Direct requests` and `### Team requests`; nest `#### Transport` and `#### Ops Platform` beneath `Team requests`.
- Render each PR as a linked `owner/repo#number — title`, followed by one indented facts line.
- Under each review item, render the `TL;DR` and `Review effort` on separate indented lines.
- Use bold only for action state, review-effort label, incident status, cross-org signal label, event times, and summary labels.
- Directly above the `Today` heading, render `**Transport OKRs:**` followed by one linked spreadsheet title, or a short bulleted list when multiple current-quarter spreadsheets qualify.
- Render calendar entries as bullets with bold times.
- Render `Yesterday` as at most two outcome-oriented workstream bullets with source links and one compact totals line.
- Render `Across the org` as no more than three linked situation bullets labeled `Action`, `Risk`, `Decision`, `Watch`, or `Quiet`. When Transport is materially involved, put a `Transport` tag beside the signal label on its clustered summary item.
- Do not use a code fence or table.

### CLI TUI

- Keep important content within 72 visible columns and use hanging indentation when wrapping. Count only the rendered link label, not the hidden Markdown URL target, toward that width.
- Use a two-line uppercase title/date masthead followed by one short Unicode rule. Use uppercase section labels and place compact counts or coverage on the same heading line, such as `YOUR OPEN PRS · 10 NON-DRAFT`, `DIRECT · 10`, or `TODAY · Primary calendar only`.
- Use a stable card rhythm. Separate cards with one blank line, but keep a card's identity, title, status, TL;DR, and effort lines adjacent. Number direct-review cards; use bullets for the user's PRs and team-review cards. Under `REVIEWS WAITING`, render `DIRECT · N`, then `TEAM REQUESTS · N`, with `TRANSPORT · N` and `OPS PLATFORM · N` as indented sibling subsection labels beneath it. Put overflow links immediately after their queue, unbulleted; keep each team-scope overflow link inside its matching team subsection.
- Render each PR card as a linked `owner/repo#number` identity line, the verbatim title on the next indented line, then a compact uppercase state line. Use words such as `BLOCKED`, `READY`, and `PENDING`; never rely on color alone.
- Preserve PR titles verbatim when they fit. Calculate the title budget from the 72-column target after subtracting indentation. Ellipsize only to the remaining visible width rather than paraphrasing it; never ellipsize the linked PR identity.
- For a review card, use `TL;DR:` followed by its wrapped summary, then `Review effort: [S] Low · ...`, `[M] Medium · ...`, or `[L] High · ...` with the numeric inputs on that line. Put the qualitative review driver on one immediately following continuation line without repeating the effort label.
- Directly above the `TODAY` heading, render `OKRS` in the time gutter followed by the current-quarter Transport spreadsheet link or links.
- Use a fixed-width calendar gutter wide enough for `HH:MM–HH:MM`; render full start/end ranges and align all-day events in the same column.
- Render `ON CALL & INCIDENTS` as a compact status block: `ON CALL` or `OFF CALL` in a fixed left gutter, schedule name to its right, then `UNTIL` or `NEXT` on the next line. Put the single linked incident count summary on the following line.
- Render `CROSS-ORG WATCH` with a fixed signal-label gutter and hanging summaries. For Transport, put the tag directly after the signal label before the primary link, for example `ACTION     TRANSPORT · [link]`; continuation lines align with the content column.
- Keep standard Markdown links on PR labels so the client can provide native links without showing long URLs.
- Do not wrap the actual response in a code fence. Do not emit ANSI control sequences, OSC 8 links, dynamic box drawing, or Markdown tables.
