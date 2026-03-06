---
description: Push branch and open a ready-for-review GitHub PR
---
Create a GitHub pull request (ready for review) for the current branch using the `gh` CLI.

## Steps

1. Run `git branch --show-current` to get the current branch name. If it is `main`, stop and tell the user — PRs must come from a feature branch.

2. Run `git log main..HEAD --oneline` to list the commits that will be in the PR.

3. Run `git push -u origin HEAD` to push the branch (safe to re-run if already pushed).

4. Run `git diff main...HEAD` to read the full diff for the PR.

5. Draft a PR title and body:
   - **Title:** short (≤ 70 characters), imperative mood, describes the change — not the branch name
   - **Body format:**
     ```
     ## Summary
     - <bullet points covering what changed and why>

     ## Test plan
     - <checklist of how to verify the changes>

     🤖 Generated with [Claude Code](https://claude.com/claude-code)
     ```
   - Keep bullets concise; focus on intent, not line-by-line description of the diff

6. Create the PR (ready for review) using a HEREDOC to preserve formatting:
   ```
   gh pr create --title "<title>" --body "$(cat <<'EOF'
   ## Summary
   ...

   ## Test plan
   ...

   🤖 Generated with [Claude Code](https://claude.com/claude-code)
   EOF
   )"
   ```

7. Run `gh pr view --web` to open the PR in the browser, and print the PR URL for the user.
