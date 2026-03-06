---
description: Summarize and review all uncommitted changes, then suggest improvements
---
Summarize and review all uncommitted changes (staged and unstaged), then suggest improvements where applicable.

## Steps

1. Run `git status` to see what files have changed.
2. Run `git diff` to get unstaged changes.
3. Run `git diff --staged` to get staged changes.
4. Combine both diffs for a complete picture of all uncommitted work.

## Summary

Write a concise plain-English summary of what the changes do:
- Group related changes together (e.g. "adds X feature", "fixes Y bug", "updates Z config")
- Note which files are new, modified, or deleted
- Keep it brief — a few sentences or a short bullet list

## Review

Analyse the changes and suggest improvements in any of these areas, if relevant:

- **Correctness** — logic errors, edge cases, off-by-one errors, unhandled errors
- **Safety** — hardcoded secrets, missing input validation, insecure patterns
- **Test coverage** — untested paths, missing assertions, dry-run not covered
- **Conventions** — deviations from patterns established in the codebase
- **Clarity** — confusing naming, missing context, overly complex logic that could be simplified

Format the review as a numbered list. For each issue found:
- State what the problem is and where (file + line if possible)
- Explain why it matters
- Suggest a concrete fix

If no meaningful improvements are found, say so explicitly — do not invent nitpicks.
