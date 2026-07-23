---
description: Push branch and open a GitHub PR, ready for review or as a draft
---
Create a GitHub pull request for the current branch using the `gh` CLI. If the argument `draft` is given, create it as a draft.

## Steps

1. Run `git branch --show-current` to get the current branch name. If it is `main`, stop and tell the user — PRs must come from a feature branch.

2. Run `git log main..HEAD --oneline` to list the commits that will be in the PR.

3. Run `git push -u origin HEAD` to push the branch (safe to re-run if already pushed).

4. Run `git diff main...HEAD` to read the full diff for the PR.

5. Draft a PR title and body using the format from `agents/AGENTS.md`:
   - **Title:** short (≤ 70 characters), imperative mood, describes the change — not the branch name
   - **Body format:**
     ```
     ## Why
     - <the problem or gap that prompted this>

     ## Effect
     - <what's observably different after this merges — behavior, not lines changed>

     ## Notes
     - <caveats, tradeoffs, follow-up work — omit if none>

     ## Validation
     - <how to verify>
     ```

6. Create the PR using a HEREDOC to preserve formatting. Add `--draft` if the argument `draft` was given:
   ```
   gh pr create --title "<title>" --body "$(cat <<'EOF'
   ## Why
   ...

   ## Effect
   ...

   ## Notes
   ...

   ## Validation
   ...
   EOF
   )"
   ```

7. Run `gh pr view --web` to open the PR in the browser, and print the PR URL for the user.
