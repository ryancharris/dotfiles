# On-call and Incident Context

Use only read-only operations from the incident.io Runlayer MCP. Prefer structured schedule and incident tools over the conversational `ask` tool. Never create, update, decline, close, escalate, comment on, or otherwise mutate an incident, schedule, shift, or escalation.

## On-call status

1. Call `schedule_list` with `user: "me"`, `query: "Transport On-Call"`, and the maximum page size. Follow `next_cursor` until `has_more` is false.
2. After pagination, retain only a case-insensitive exact name match for `Transport On-Call`. Ignore `Transport Team` and every other schedule even when they contain `user_current_shift`.
3. A retained `Transport On-Call` record with `user_current_shift` means the user is on call now. Render the shift's localized end time.
4. If the retained schedule has no current shift, report `Not on call` and render its `user_next_shift` start and end when present. Do not substitute the next shift from another schedule.
5. If no exact matching schedule is returned, or results are incomplete or fail, report `Transport On-Call status unavailable`; do not infer that the user is not on call. Preserve any external-provider note compactly.

## Incident retrieval

Resolve the exact `Transport` team ID with `team_list` using `query: "Transport"`, maximum page size, full pagination, and a case-insensitive exact-name match. Do not treat fuzzy matches as Transport. Then, in parallel when possible, call `incident_list` three times with `status_category: ["triage", "active"]`, `mode: ["standard"]`, `page_size: 50`, and `include: ["summary", "roles", "custom_fields", "timestamps", "escalation_urgency"]`:

- once without an assignee filter for the organization-wide active set;
- once with `assigned_to: ["me"]` for incidents involving the user. Despite the parameter name, this filter includes participants, observers, collaborators, and named role assignees; describe the user as `involved` unless a returned role explicitly names them.
- once with `team_part_of: ["TRANSPORT_TEAM_ID"]` to identify incidents associated with Transport or its sub-teams. If no exact Transport team is found, skip this call and report Transport incident coverage unavailable rather than inferring membership.

Follow pagination to completion. De-duplicate by incident ID and mark the user's incidents and verified Transport incidents. Use `incident_show` only for a top candidate whose summary is absent, truncated, or insufficient to determine impact; do not fetch every incident individually.

Treat the structured incident summary and status as authoritative. Never infer customer impact merely from a customer-like name. Positive evidence includes an explicit customer-impact statement, affected production service, named customer communications role, customer-facing outage or degradation, or immediate escalation urgency. Preserve explicit `no customer impact` statements and rank those below confirmed customer impact unless the user is assigned.

## Rendering

In `On call & incidents`, do not render individual incident records, titles, summaries, severities, or an omitted-items breakdown. Render one honest dashboard link after the on-call line: `Incidents: N active · M triage`. Derive its stable organization incidents-dashboard URL from a returned incident permalink by removing the final incident identifier, for example `https://app.incident.io/dbt-labs/incidents`. Do not render two different-looking links to the same target, and never invent or guess filter query parameters.

Before ranking incident candidates for `Across the org`, require a current relevance signal: the user is involved and an action remains, Transport is materially involved, immediate urgency is present, or a major customer-impacting incident materially changed inside the cross-org window. An old open status or a fresh `updated_at` without a substantive status update is not enough. Use `incident_show` for shortlisted candidates when the list response does not reveal the latest material change.

For eligible incident candidates, use this sequence:

1. The user is involved; name a specific assignment only when the returned roles establish it.
2. Immediate escalation urgency or confirmed ongoing customer impact.
3. Higher severity, using the organization's displayed severity rather than guessing from wording.
4. Triage before active when the triage item is new and unassessed; otherwise most recently updated. Within every preceding tier, prefer recently updated incidents so a stale open record cannot displace a fresh incident indefinitely.
5. Internal or informational incidents without customer impact.

Do not let a low-value test-like or informational incident outrank confirmed customer impact solely because it is newer.

`Across the org` uses the same incident set as its first candidate pool, but the active set is not itself an output queue. Combine records that describe one underlying situation before ranking, including linked PRs or Transport response work. Apply this priority: direct user action, verified material Transport involvement, newly changed major customer impact or immediate urgency, then the remaining watch ranking. Within a tier, prefer higher severity and the timestamp of the latest substantive change rather than raw record freshness. The incident section provides only the dashboard count link; a retained cross-org item leads with the delta and next action instead of repeating the incident summary.
