# Activity and Watchlist

## Time window

Use the report timezone. The previous working day is the previous Monday–Friday date; on Monday use Friday. Use a half-open interval from local midnight through the next local midnight and convert it to exact timestamps for each provider. When a provider's bounds are inclusive, client-filter returned timestamps to `start <= timestamp < end`. Do not silently treat a holiday or an all-day event as a non-working day.

For cross-org updates, search from the start of that previous working day through the report time so Monday includes the weekend.

## What the user did

Collect the three sources in parallel. Report only actions attributable to the user, not messages that merely mention them or documents they only viewed.

### Slack

1. Resolve the current Slack user and ID each run.
2. Search public messages authored by that ID inside the exact timestamp window. Use no keywords, messages only, bots off, chronological order, and paginate fully.
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

## Cross-org watch

Topics can come from two places:

- **Shared watch terms:** terms the user explicitly defines or confirms. These may be searched across providers and can include aliases, exact phrases, exclusions, and optional repository scopes.
- **Inferred topics:** active PR titles, ticket IDs, calendar titles, and recent activity. Label these as inferred and search them only inside the provider where they were observed.

In `watchlist.yaml`, each `projects` entry has a display `name`, one or more independently searched `aliases`, and optional `github_repositories`. Treat aliases as OR alternatives, never as one AND query. Repository scopes constrain only GitHub searches; do not send repository names to Slack or Notion unless they are also explicit aliases. `keywords` contains standalone shared terms that do not belong to a project cluster.

Never transmit a topic learned from private Slack or Notion content to another provider unless the user explicitly promotes it to the shared watchlist. It is safe to cluster already-fetched results locally using URLs, repository/PR numbers, ticket IDs, and confirmed aliases.

Search each topic or alias independently because Slack keyword arrays are ANDed. For Slack, pass each keyword as one lexical word or a quoted exact phrase. Search public Slack from the window start through report time, page fully, collapse hits by thread, and read the best threads. For provider-local Notion topics, force Notion-only search with an effective content filter or a supported non-relevance sort such as `last_edited`, and verify every returned source is Notion before using it. If a Notion-only restriction is unavailable, skip that inferred-topic search and report the coverage gap rather than allowing AI search to reach connected Slack, Mail, or Calendar sources. Search GitHub only for shared terms and keep the existing repository-owner boundary.

First canonicalize candidates into underlying situations using incident links, repository/PR numbers, tickets, services, and confirmed aliases. One situation gets one output item even when several sources describe it.

Apply a usefulness gate before ranking. A situation is eligible only when the evidence establishes at least one of:

- a concrete action, decision, or response needed from the user;
- verified Transport ownership or active involvement with a current operational or customer consequence;
- a major customer-impacting incident or immediate urgency with a material status change inside the watch window;
- a blocker, security issue, launch risk, or deadline that could alter today's plan.

An incident being active, severe, customer-named, or recently touched is not sufficient by itself. Exclude unchanged background incidents and items whose only available summary is a restatement of their title. When the shared watchlist is empty, do not use the general active-incident list as filler; restrict output to candidates that pass this gate and state that coverage is limited to direct involvement, verified Transport work, and fresh major incidents.

Then rank eligible situations:

1. Action or decision required from the user today.
2. Verified material Transport involvement with an active next step or unresolved blocker.
3. Newly changed major customer impact or immediate incident urgency.
4. Blocker, security, launch, or deadline risk that may change today's plan.
5. Material decision, ownership, or status change.
6. A correction to earlier information.
7. Multiple-source corroboration, authoritative source quality, and recency.

Resolve Transport involvement from explicit evidence: an exact Transport team association returned by incident.io, a source that names the Transport team, or a clearly Transport-owned repository, service, project, or channel. The user's involvement alone is not proof of Transport involvement. When a situation has material Transport involvement, label its single canonical bullet `<Signal> · Transport`, summarize what Transport owns or is doing and the customer or operational impact, and link the strongest primary source. Mention additional related evidence compactly instead of creating more bullets. Place the item at the highest position justified by the normal incident/customer-impact ranking; visual tagging supplies the highlight. Do not add a filler Transport item when no material involvement is found.

Suppress bots, mirrors, self-authored repeats already covered by `Yesterday`, generic keyword collisions, casual chatter, unsupported speculation, and unchanged open incidents. Keep an incident without a watch-term match only when it passes the usefulness gate. Keep at most three situations; render `No new actionable signals` rather than adding filler when no candidates qualify. For each item, show a signal label (`Action`, `Risk`, `Decision`, `Watch`, or `Quiet`), the matched incident or topic, and a one- or two-sentence delta: what changed in the watch window, why it matters now, and the next action or owner when established. Use `incident_show` for a shortlisted incident when the list summary does not establish that delta. State source coverage and any truncation outside the three signal slots.
