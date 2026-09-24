# Search Memory

`search-memory.yaml` is a small local ledger for improving future searches. It records normalized keywords and outcome counts, not source content. `watchlist.yaml` remains the sole authority for terms allowed to cross provider boundaries.

Keep the ledger internal. Do not render its terms or maintenance details in the morning brief unless the user asks; only disclose when keyword refinement itself is unavailable.

## Safe contents

Each entry represents one exact keyword or short phrase and contains:

- `term`: normalized text, preserving meaningful ticket or service casing;
- `provider`: `github`, `slack`, `notion`, or `incident_io`;
- `visibility`: `public`, `private`, or `unknown` at the source;
- `first_seen` and `last_seen`: local report dates in `YYYY-MM-DD`;
- `evidence_runs`: number of report runs in which the term had actionable evidence;
- `useful_hits`: cumulative results that passed the cross-org usefulness gate;
- `zero_hit_runs`: consecutive searches with no relevant result.

Store no message excerpts, page titles, customer or person names, channel or DM names, URLs, tokens, credentials, or other source text. Do not store generic words, stop words, broad product nouns, or a term observed only in private 1:1 material. Ticket IDs, repository names, stable service names, incident components, and explicit project names are suitable when they meet these privacy rules.

## Learning loop

After each run:

1. Extract candidate terms only from evidence already collected for the brief: explicit watchlist matches, actionable incidents, rendered PR metadata, and retained Slack or Notion situations.
2. Normalize case-insensitively for de-duplication while preserving the clearest observed display casing.
3. Update an existing provider-scoped entry or add one when the term contributed to an actionable result. Increment `evidence_runs` once per run and `useful_hits` once per qualifying canonical situation, not once per raw search hit.
4. For a term actually queried in its provider, reset `zero_hit_runs` to `0` when relevant evidence was found; otherwise increment it. Do not penalize terms when that provider was unavailable or the query was skipped.
5. Keep at most 40 active entries. Remove entries after 90 days without useful evidence or after 3 consecutive zero-hit runs; when pruning is needed, discard the lowest `useful_hits`, then the oldest `last_seen`.

Use remembered terms only for provider-local discovery, ordered by `useful_hits`, recent `last_seen`, and low `zero_hit_runs`. Start with at most 8 remembered terms per provider each run, search each independently, and apply the normal usefulness gate to all results. A term with `visibility: private` or `unknown` never leaves its provider.

Promotion is explicit: only move a term into `watchlist.yaml` after the user confirms it as a shared watch term. Promotion may include user-confirmed aliases or repository scopes; never infer them from the memory ledger.

If the ledger is missing, initialize it with `version: 1` and `entries: []`. If it is unreadable or invalid, leave it unchanged, label keyword refinement unavailable in the coverage note, and continue the brief.
