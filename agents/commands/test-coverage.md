---
description: Audit test coverage for all changes on the current branch
---
Analyse all changes introduced on the current branch and verify that every piece of new or modified functionality has adequate test coverage — including edge cases and important permutations.

## Steps

1. Run `git merge-base HEAD main` (or `master` if `main` doesn't exist) to find the common ancestor, then run `git diff <merge-base>...HEAD --name-only` to get the full list of changed files.

2. Run `git diff <merge-base>...HEAD` to read the complete diff.

3. Identify all **changed source files** (non-test files) and their corresponding test files. Common conventions:
   - `src/foo.ts` → `src/foo.test.ts`, `src/foo.spec.ts`, `tests/foo.test.ts`, etc.
   - `lib/bar.py` → `tests/test_bar.py`, `lib/bar_test.py`, etc.
   - `pkg/baz.go` → `pkg/baz_test.go`
   - Use `git diff <merge-base>...HEAD --name-only` output plus the filesystem (Glob/Read) to locate existing test files.

4. For each changed source file, read both the diff and the current state of the file to understand:
   - New functions, methods, classes, or modules added
   - Modified behaviour in existing functions (changed conditionals, new branches, updated logic)
   - Deleted or renamed functionality
   - Important edge cases: empty inputs, null/undefined, boundary values, error paths, async failures, auth/permission checks, etc.

5. Read the corresponding test files (if they exist) to assess what is already covered.

6. Build a coverage map: for each unit of changed behaviour, mark it as **covered**, **partially covered**, or **missing**.

## Output

### If all changed functionality is fully covered:

Print a celebration message, for example:

```
🎉 All changed functionality is covered by tests!

Here's what was verified:
- <FileName>: <list of covered behaviours>
- ...

Nice work — ship it. ✅
```

### If coverage gaps exist:

Do NOT write or apply any code changes. Instead, produce a detailed report:

#### Coverage Gaps

For each gap, include:
- **File:** the source file containing the uncovered behaviour
- **Behaviour:** a plain-English description of what isn't covered
- **Suggested test:** the name of the test file to update (or create), the test case name, and a description of what it should assert — including the specific inputs/scenarios to exercise

Group suggestions by test file so the user can work through them one file at a time.

#### Example format:

```
## Coverage Gaps

### `src/auth/token.ts`

**Uncovered behaviour:** `refreshToken()` when the refresh token is expired
- Test file: `src/auth/token.test.ts`
- Test case: `refreshToken › throws TokenExpiredError when refresh token is expired`
- Should call `refreshToken()` with an expired token and assert it throws `TokenExpiredError`

**Uncovered behaviour:** `refreshToken()` concurrent calls (race condition guard)
- Test file: `src/auth/token.test.ts`
- Test case: `refreshToken › only issues one refresh request when called concurrently`
- Should fire multiple simultaneous calls and assert only one network request was made

---

### `src/api/users.ts`

...
```

Be thorough — cover happy paths, error paths, boundary values, and any branching logic introduced by the diff. Do not suggest tests for behaviour that was not changed.
