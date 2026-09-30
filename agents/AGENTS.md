# Agent Instructions

Shared conventions for all AI coding agents.

## Philosophy
1. Simplicity over complexity
2. No guessing, always validate and verify
3. Make surgicial changes with minimal blast radius

## Workflows

### 1. Subagent strategy
- Use subagents where possible to keep the main context window clean
- Hand subagents research and analysis tasks to run in parallel
- Choose the most cost-effective model for each subagent

### 2. Self-improvement
- Capture user corrections or learnings during a session
- Review these at the end of the session
- Draft PRs for re-writing the rules upon user approval

### 3. Task management
- Start with a plan: verify facts and user intent before acting
- Validate plan: ask if this is the right approach to solve the given problem
- Track progress: report status and mark items complete as you work
- Summarize changes: high-level explainer of how these changes fit into the larger goal
- Document results: capture proof the implementation works
- Capture lessons: record for future sessions in LESSONS.md

## Validate and verify

### 1. Validation
- We are data driven and use it to make decisions
- No data → get it. Unclear intent → ask
- Validate our approach, not just the result of proposed changes
- Measurement beats intuition, convention, or training recall

### 1. Verification
- Prefer e2e/integration tests over unit tests alone
- All associated tests must pass to consider a task complete

## Git & GitHub
- Always use a feature branch for commits, pushes, and PRs; on `main`/`master`, branch first
- Merge only with explicit user permission
- Force push with `--force-with-lease`

## Personal conventions
- Use diagrams wherever they help, on any topic
- Networking (protocols, routing, DNS, LB, firewalls, CNI, service meshes) or Terraform/IaC: briefly explain the concept — the user is learning both
  - Format as a blockquote headed `📘 Teaching: <topic>`, in any output style
- CLI over GUI; OSS preferred
- TUI apps: new kitty tab (`kitty @ launch --type=tab`), not tmux
