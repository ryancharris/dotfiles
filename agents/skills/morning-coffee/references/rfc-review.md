# RFCs to review

Check the user-designated [RFC Database](https://app.notion.com/p/dbtlabs/78c0827273f64bc2a92704fccdd839de?v=72474252c0754dfab0582eab62cda8ff) every run. Resolve its current data-source URL, schema, and In-Review saved view with Notion fetch.

## Scope

Enumerate the exact current `In-Review` lifecycle fully through the saved view, paging until `has_more: false`; use an equivalent schema-aware structured query if no suitable view is available. Verify fetched pages are direct members of that data source and remain In-Review.

Interpret “past two weeks” as the rolling 14-day interval ending at report time, using `Submitted for review` as the date. Client-filter `window_start <= submitted_at <= report_time`. When submission is absent, use Created time and visibly label the fallback. Interpret date-only values at local midnight in the report timezone. Unknown or unparseable dates cannot establish eligibility; disclose that coverage gap. Creation and recent edits never override a known submission outside the window. Drafting, Paused, Approved, Superseded, Obsolete, and Withdrawn lifecycle states are outside scope, regardless of submission date or pending user assignment.

## Verify requests and approvals

Resolve the current Notion user with get_self. Apply the lifecycle/date gate before full hydration. Fetch each retained RFC and each unique linked approval record once, batching or using bounded concurrency when supported; match the resolved user ID against the approval record's Stakeholder property. Preserve the approval status verbatim, including on a shared stakeholder record. Use Notion search for any content discovery, restricted to the fetched data source and a supported Notion-only filter or non-relevance sort.

Display independent request and completion indicators:

- `📨 Requested from you`: the user's ID is explicitly assigned as a review stakeholder or a fetched source explicitly requests that user's review. Author, sponsor, general team relevance, and a title containing the user's name do not establish a direct review request.
- `👀 Optional review`: all linked approval records were readable and no direct user assignment or explicit request was found.
- `❓ Request status unknown`: missing approval records or truncated assignment evidence prevent determining whether a request exists.
- `✓ Approved by you`: an individual approval record or recorded approval actor proves the user approved and the approval status is exactly `Accept`. For an accepted shared stakeholder record without an individual actor, show `Accepted — shared team response` without a personal approval checkmark and name that scope; do not attribute the approval to the user personally. Keep the RFC visible while its lifecycle remains In-Review and its submission remains inside the window. Another stakeholder's Accept, lifecycle Approved, N/A, a comment, or a prior review is insufficient evidence for the checkmark.

Waiting on feedback and Request Changes require reading relevant discussions to establish who owes the next response before claiming an action is waiting on the user. When that direction is unclear, show the exact status and say who should clarify it. Never fabricate a checkmarked example when the live set contains none.

## Render

Render a dedicated RFCs to review section after Daily priorities and before Reviews waiting. Include the database link and a short “In review · submitted in the past two weeks” scope line. For each retained RFC, show the linked title, request emoji plus readable label, any approval checkmark plus readable label, exact lifecycle and user approval status, submission date (or labeled creation fallback), practical infrastructure consequence, and next action or owner. Summaries come from fetched proposal content, not title or AI-summary text alone.

Rank pending direct user requests first, then other material Transport or infrastructure decisions, then already-approved user items. Display all eligible RFCs within this bounded scope and keep the full eligible count. Link the scoped database view for source access. Canonicalize related Daily priorities into one full summary with a cross-reference. Render None if no RFC qualifies.

Keep discovery, hydration, date eligibility, assignment, and approval failures independent. Add a compact section explanation and shared coverage-banner note only when a material gap affects these facts. A discussion-inventory truncation does not make verified proposal metadata or a complete linked approval set incomplete. Persist no RFC seen-state or content; preview iterations keep all artifacts temporary and leave search memory unchanged.
