# Activity and Priority Signals

## Time window

Use the report timezone. The previous working day is the previous Monday–Friday date; on Monday use Friday. Use a half-open interval from local midnight through the next local midnight and convert it to exact timestamps for each provider. When a provider's bounds are inclusive, client-filter returned timestamps to `start <= timestamp < end`. Do not silently treat a holiday or an all-day event as a non-working day.

For daily-priority signals, search from the start of that previous working day through the report time so Monday includes the weekend.

## What the user did

Collect the three sources in parallel. Report only actions attributable to the user, not messages that merely mention them or documents they only viewed.

### Slack

1. Resolve the current Slack user and ID each run.
2. Search public messages authored by that ID inside the exact timestamp window. Use no keywords, messages only, bots off, include_context: false, chronological order, and paginate fully. Canonicalize thread IDs before hydration so each retained thread is read once.
3. Remove social chatter and notification noise. Group substantive messages by thread, ticket, repository, or project.
4. Read each retained thread before summarizing so later corrections supersede earlier hypotheses.
5. Report the number of work messages summarized and social/noise messages omitted. Label coverage `Slack public channels only`.

Use private-channel and DM search only after explicit user consent. Do not quote customer identifiers, credentials, private URLs, long message excerpts, or personal conversation.

### Notion

1. Check tool access, use AI search when available, and resolve the current Notion user ID.
2. Search separately for pages created by the user in the date range and pages last edited by the user in the date range. Request the connector maximum `page_size: 50` and keep `max_highlight_length` at or below 500; because this search exposes no result cursor, label Notion activity potentially incomplete when a query returns the full cap.
3. Notion date filters can cross local-day boundaries. Client-filter timestamps to the exact half-open interval, de-duplicate by page URL, and let `created` take precedence over `edited`.
4. Fetch the highest-signal pages before summarizing and disclose truncated content.
5. Describe results as `pages created or last edited by you`, not a complete edit audit. For private pages such as 1:1 notes, say only that the notes were updated unless the user asks for detail.

### GitHub

Fetch the authenticated user's recent events with:

```sh
gh api --paginate --slurp 'users/LOGIN/events?per_page=100'
```

Filter exact timestamps and retain only repositories owned by `dbt-labs` or `LOGIN`. Hydrate referenced PRs, then group events into outcome workstreams: opened or merged PRs, teammate reviews that changed an outcome, feedback resolved on the user's own PRs, consequential issue comments, and meaningful pushes. Collapse stacked rollout PRs and de-duplicate pushes by repository, ref, before, and head. Exclude routine pushes, review churn, and documentation edits that produced no meaningful outcome.

Treat the events endpoint as authenticated recent activity, which may include accessible private events, with a 300-event ceiling. Label coverage `GitHub authenticated recent activity`. Mark it truncated only when 300 events were returned and the oldest fetched event is still newer than the window start. Rank incidents, customer impact, decisions, and blockers above PR work, teammate reviews, documentation, personal repositories, and raw branch churn.

## Priority signals

Topics can come from two places:

- **Shared watch terms:** terms the user explicitly defines or confirms. These may be searched across providers and can include aliases, exact phrases, exclusions, and optional repository scopes.
- **Inferred topics:** active PR titles, ticket IDs, calendar titles, and recent activity. Label these as inferred and search them only inside the provider where they were observed.

In `watchlist.yaml`, each `projects` entry has a display `name`, one or more independently searched `aliases`, and optional `github_repositories`. Treat aliases as OR alternatives, never as one AND query. Repository scopes constrain only GitHub searches; do not send repository names to Slack or Notion unless they are also explicit aliases. `keywords` contains standalone shared terms that do not belong to a project cluster.

Never transmit a topic learned from private Slack or Notion content to another provider unless the user explicitly promotes it to the shared watchlist. It is safe to cluster already-fetched results locally using URLs, repository/PR numbers, ticket IDs, and confirmed aliases.

Search each topic or alias independently because Slack keyword arrays are ANDed. For Slack, de-duplicate exact provider-local queries and pass each keyword as one lexical word or a quoted exact phrase; use include_context: false during discovery. Search public Slack from the window start through report time, page fully, collapse hits by thread, and read the best threads. For provider-local Notion topics, force Notion-only search with an effective content filter or a supported non-relevance sort such as `last_edited`, and verify every returned source is Notion before using it. If a Notion-only restriction is unavailable, skip that inferred-topic search and report the coverage gap rather than allowing AI search to reach connected Slack, Mail, or Calendar sources. Search GitHub only for shared terms and keep the existing repository-owner boundary.

For Notion, de-duplicate identical provider-local queries across watch aliases and remembered terms. Search compound aliases and identifiers as quoted phrases when supported; quotes alone do not prove exact matching. Check the returned title/highlight for the full normalized alias before shortlisting (case-insensitive, collapse whitespace, ignore highlight markup). Fetch plausible pages to verify the match when highlights omit it. Reject generic token collisions such as `API` for `api-gateway`. A full 50-result response is potentially incomplete, even if few matches survive local filtering. Refine once using an already-verified relevant page/data-source scope or exact phrase. If the response still hits the cap, report that topic's discovery as partial; do not hydrate unrelated hits or imply that local filtering restored completeness. Preserve Notion-only restrictions and keep inferred terms inside Notion.

## Recommendation ranking

On every initial collection, same-day refresh and Start today, independently build and rank candidates from all six current collections: GitHub, Calendar, Google Drive, incident.io, Slack and Notion. Respect each source's scope and privacy limits, including Drive's link-only planning evidence. Prior snapshots, saved tasks and legacy selected priorities identify evidence to recheck; neither their list order nor persistence earns a recommendation slot. Consider fresh work across the collections before selecting the top outcomes, including time-sensitive PR or RFC decisions. A source need not contribute an item.

First canonicalize candidates into underlying situations using incident links, repository/PR numbers, tickets, services, and confirmed aliases. One situation gets one output item even when several sources describe it.

Apply a usefulness gate before ranking. A situation is eligible only when the evidence establishes at least one of:

- a concrete action, decision, or response needed from the user;
- verified Transport ownership or active involvement with a current operational or customer consequence;
- a major customer-impacting incident or immediate urgency with a material status change inside the watch window;
- a blocker, security issue, launch risk, or deadline that could alter today's plan.

An incident being active, severe, customer-named, or recently touched is not sufficient by itself. Exclude unchanged background incidents and items whose only available summary is a restatement of their title. When the shared watchlist is empty, do not use the general active-incident list as filler; restrict output to candidates that pass this gate and state that coverage is limited to direct involvement, verified Transport work, and fresh major incidents.

Every selected outcome needs concrete **Why today** evidence: a dated request or decision window, imminent deadline, verified active blocker and its consequence, or material operational change that makes action useful today. Being unresolved or previously selected alone is insufficient. A currently verified ongoing situation can remain recommended across runs when it still outranks alternatives; fresh ranking does not require new wording, a new identity or forced turnover.

Then rank eligible situations:

1. Action or decision required from the user today.
2. Verified material Transport involvement with an active next step or unresolved blocker.
3. Newly changed major customer impact or immediate incident urgency.
4. Blocker, security, launch, or deadline risk that may change today's plan.
5. Material decision, ownership, or status change.
6. A correction to earlier information.
7. Multiple-source corroboration, authoritative source quality, and recency.

Resolve Transport involvement from explicit evidence: an exact Transport team association returned by incident.io, a source that names the Transport team, or a clearly Transport-owned repository, service, project, or channel. The user's involvement alone is not proof of Transport involvement. When a situation has material Transport involvement, identify Transport ownership in its single canonical priority, summarize what Transport owns or is doing and the customer or operational impact, and link the strongest primary source. Mention additional related evidence compactly instead of creating more bullets. Place the item at the highest position justified by the normal incident/customer-impact ranking; visual tagging supplies the highlight. Do not add a filler Transport item when no material involvement is found.

Suppress bots, mirrors, self-authored repeats already covered by `Yesterday`, generic keyword collisions, casual chatter and unsupported speculation. Keep an incident without a watch-term match only when it passes the usefulness gate. Publish at most four ranked outcomes in `priorities`, labelled **Recommended priorities**; render None rather than adding filler when none qualifies. For each, use `context` for the specific Why today rationale, `action` for the next step, `done` for an observable completion criterion, and `evidence` for supporting facts, primary links and established owners. Clearly distinguish the recommendation from those facts. Use `incident_show` when a shortlisted incident's summary cannot establish its current relevance.

Keep **Last checked** separate from meaningful source change: `checked_at` records the actual verification time; an event time or substantive state supports a change claim. Preserve the same outcome identity and `material_key` through polling, rank changes and wording changes. A newer check time or source `updatedAt` alone does not establish new urgency or a new material version.

Rank within honestly reported coverage when a source is partial or unavailable. Keep retained evidence's original timestamp and uncertainty; an attempted check cannot turn old evidence into a current fact. Preserve earlier unresolved evidence for rechecking without automatically filling recommendation slots. Absence from a new ranking establishes neither completion nor resolution; those require authoritative evidence or a separately attributed user answer. State source failures, scope and truncation outside the four-item list. Saved commitments and acceptance/dismissal behavior follow [workspace reconciliation](workspace.md#reconcile-work-without-resetting-choices).
