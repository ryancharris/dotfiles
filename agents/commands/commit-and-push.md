---
description: Stage all changes, create a Conventional Commit, and push to remote
---
Stage all changes, create a git commit following Conventional Commits, and push to the remote branch.

## Steps

1. Run `git status` to see what has changed.
2. Run `git add -A` to stage everything (new files, modifications, deletions).
3. Run `git diff --staged` to read the full staged diff.
4. Run `git log --oneline -10` to see recent commit messages and match the project's tone/style.
5. Analyse the diff and write a commit message:
   - **Format:** `<type>[optional scope]: <description>`
   - **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `build`, `ci`
   - **Rules:**
     - Description is lowercase, imperative mood, no trailing period
     - Breaking changes: append `!` after the type/scope, and add a `BREAKING CHANGE:` footer
     - Multi-concern changes: use the most significant type; list the rest in the body
     - Keep the subject line ≤ 72 characters
   - Add a short body if the diff contains non-obvious intent (why, not what)
6. Commit using the message. Use a HEREDOC to preserve formatting:
   ```
   git commit -m "$(cat <<'EOF'
   <subject>

   <optional body>
   EOF
   )"
   ```
7. Push to the remote branch with `git push`.
8. Show the final `git log --oneline -1` so the user can see the result.
