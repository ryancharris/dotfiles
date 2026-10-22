# Agent Instructions

Shared conventions for all AI coding agents.

## Philosophy
1. Simplicity over complexity
2. No guessing, always validate and verify
3. Make surgicial changes with minimal blast radius

## Workflows

### Task management
- Start with a plan: verify facts and user intent before acting
- Clarify uncertainty that materially affects scope or outcome before acting
- Track progress: report status and mark items complete as you work

## Validate and verify

### 1. Validation
- We are data driven and use it to make decisions
- No data → get it. Unclear intent → ask
- Validate our approach, not just the result of proposed changes
- Measurement beats intuition, convention, or training recall

### 1. Verification
- Prefer e2e/integration tests over unit tests alone

## Personal conventions
- Use diagrams wherever they help, on any topic
- Networking (protocols, routing, DNS, LB, firewalls, CNI, service meshes) or Terraform/IaC: briefly explain the concept — the user is learning both
  - Format as a blockquote headed `📘 Teaching: <topic>`, in any output style
- CLI over GUI; OSS preferred
- TUI apps: new kitty tab (`kitty @ launch --type=tab`), not tmux
