# Dense Ledger Review Layout

Render the oldest-first review dataset using the five-per-subsection selection rule in `SKILL.md`. Every visible PR must keep its link, author, status, TL;DR, review-effort label and inputs, tie-break reason when present, queue membership, team label when applicable, and overflow accounting.

## Layout

- Use one CSS-grid row per PR with columns for identifier/title, author, and status.
- Put the one-sentence TL;DR on its own second block line spanning the grid.
- Put `Review effort` and its evidence on its own third block line spanning the grid. Never place it beside or on the same line as the TL;DR.
- Let long titles and summaries wrap rather than truncate source text.
- Use a hairline between rows. On a narrow viewport, collapse the metadata to a two-column grid while keeping the title, TL;DR, and review-effort lines full width.

This layout optimizes sequential scanning and maximum visible queue depth.
