# RFC discovery and surfacing

Check the user-designated [RFC Database](https://app.notion.com/p/dbtlabs/78c0827273f64bc2a92704fccdd839de?v=72474252c0754dfab0582eab62cda8ff) every run. Fetch its current schema, data-source URL and **All RFCs** view. Saved view names do not establish their filters: verify that discovery covers the full RFC data source rather than a personal, recent or In-Review subset.

## Discover once, select reproducibly

Collect all active database rows as metadata before choosing what to hydrate. Page the All RFCs view until `has_more: false`, preserving each returned cursor. If its filters omit RFCs, use an equivalent schema-backed unfiltered structured query. Where supported, count rows in the same source/archive scope and compare with unique discovered page IDs. Keep raw pages outside the repository. A cap, missing cursor, failed page or count mismatch is incomplete discovery, not an empty queue.

Write a temporary discovery JSON with `data_source_url`, `checked_at`, `has_more`, optional `expected_count`, and concatenated `rows`. Preserve source fields `url`, `Name`, `RFC Status`, `Created time`, `Last edited time`, `date:Submitted for review:start` and `Approvals ` (including its trailing space). Run the bundled selection helper:

```sh
python3 "$morning_skill/scripts/select_rfcs.py" "$discovery_json" \
  --at "$report_timestamp" --timezone "$timezone" --output "$rfc_selection_json"
```

The helper defines two independent surfaces:

- **Review queue:** every current `In-Review` RFC, regardless of submission age. Missing, malformed or future submission dates get a visible uncertainty label; they never hide an open review. Submitted/created dates provide context and ordering, not eligibility cutoffs.
- **Recent RFC activity:** other lifecycles whose authoritative `Last edited time` falls within the rolling 14 days ending at report time. Include Drafting, Paused, Approved, Superseded, Obsolete and Withdrawn with their exact status. Order newest edit first. An edit establishes recent activity, not a lifecycle-transition date, review request or decision made at that time.

An In-Review RFC appears only in the review queue. Older inactive or unchanged non-review RFCs remain accessible through the database link. Keep the two surfaces separate from the four ranked recommendations; source relevance may justify a recommendation under the shared ranking contract.

Hydrate every selected proposal and verify direct membership and current lifecycle against discovery. If a lifecycle changed, reselect from updated metadata. Preserve selected metadata as a clearly labelled placeholder when proposal content is unavailable, with unknown request status for an unreadable review; failed hydration must not silently remove a row. Author summaries from fetched proposal content and resolve author names from verified user metadata. Activity rows need no personal approval lookup because they do not claim to await review.

Copy the helper's `discovery` manifest into `rfcs.discovery` and retain its selected URLs in `rfcs.items` and `rfcs.activity`. Carry `date_label`, `lifecycle`, and selection warnings into the normalized report. Publication rejects omitted, duplicated or misclassified selected RFCs. Full lifecycle enumeration is independent of proposal and approval coverage; report those failures separately. Full enumeration can retire an old review when its verified lifecycle changed even if another Notion approval is inaccessible. Local Done marks remain independent and survive reclassification.

## Verify requests and approvals

Resolve the current Notion user with get_self. Fetch each selected proposal once and every unique approval record linked from the In-Review queue, batching or using bounded concurrency when supported; match the resolved user ID against the approval record's Stakeholder property. Preserve the approval status verbatim, including on a shared stakeholder record. Use Notion search for any content discovery, restricted to the fetched data source and a supported Notion-only filter or non-relevance sort.

Display independent request and completion indicators:

- `📨 Requested from you`: the user's ID is explicitly assigned as a review stakeholder or a fetched source explicitly requests that user's review. Author, sponsor, general team relevance, and a title containing the user's name do not establish a direct review request.
- `👀 Optional review`: all linked approval records were readable and no direct user assignment or explicit request was found.
- `❓ Request status unknown`: missing approval records or truncated assignment evidence prevent determining whether a request exists.
- `✓ Approved by you`: an individual approval record or recorded approval actor proves the user approved and the approval status is exactly `Accept`. For an accepted shared stakeholder record without an individual actor, show `Accepted — shared team response` without a personal approval checkmark and name that scope; do not attribute the approval to the user personally. Keep the RFC in the review surface while its lifecycle remains In-Review, regardless of age. Another stakeholder's Accept, lifecycle Approved, N/A, a comment, or a prior review is insufficient evidence for the checkmark.

Waiting on feedback and Request Changes require reading relevant discussions to establish who owes the next response before claiming an action is waiting on the user. When that direction is unclear, show the exact status and say who should clarify it. Never fabricate a checkmarked example when the live set contains none.

## Render

Keep the full RFC section after Pull requests. Its review queue shows direct requests first, other pending reviews next, then the existing collapsed Approved or done group. Show submission age/date context without hiding old work. Personal approval and local completion remain separate from the RFC's lifecycle.

Show **Recent RFC activity** as a separate, initially expanded disclosure inside the section, with its own count. Each row has the linked title, exact lifecycle, last-update label and concise proposal summary (or an honest unavailable-content placeholder). Drafts, paused work and source-approved RFCs in this surface have no To review label, personal approval checkmark or local review-completion control. Navigation distinguishes review and update counts. Link the full database for older work.

Keep discovery, hydration, assignment and approval failures independent. Preserve every selected row and disclose gaps in section coverage and the shared banner. A truncated discussion inventory does not make fully fetched proposal metadata or a complete approval set incomplete. Preview iterations use temporary artifacts and leave source facts, local marks and search memory unchanged.
