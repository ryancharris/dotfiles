# Source connection preflight

Run before fresh source discovery for an initial report, Refresh all, Start today or a scheduled collection. Reopening the existing workspace, viewing an archive and format-only rendering need no provider connection. Keep the private workspace and its local controls available while recovering access.

## Check access

Treat the six source connections as critical for the normal complete brief: GitHub through `gh`, and Calendar, Google Drive, Slack, Notion and incident.io through the host's connected apps/MCPs. An explicit user instruction may authorize a narrower or partial run; carry that authorization forward within its stated scope.

1. Discover the current host's read-only tools and configured server names. A missing tool may mean a lazy catalog, disabled server, failed transport or missing authentication; record the observed state rather than guessing which. Use the host's supported tool discovery or connection-status operation when available, then make one bounded rediscovery if tools are absent.
2. Verify access with a cheap authenticated read for each source, within its existing collection scope: `gh api user --jq .login`; Calendar's profile or primary-day listing; a limited Drive planning search; a public-only Slack search; the configured Notion RFC database read; and incident.io's native Transport On-Call schedule lookup. Reuse successful reads in collection. A server being configured or enabled, an empty tool list, or a successful workspace page GET does not establish source access.
3. Retain a compact per-source result with attempt time, success or failure, and safe recovery action. Keep tokens, credential configuration and raw provider responses out of the report and repository. Preflight success establishes access, not complete source coverage.

## Reconnect before collection

For a failed connection, use one host-supported reconnect/reload attempt and repeat its authenticated read once. Inspect the actual available operations or installed CLI help before invoking recovery; avoid invented reconnect endpoints and retry loops.

- For a configured MCP that needs OAuth, use the current host's reconnect/login flow. In a Codex CLI session, first verify the configured server name with `codex mcp list` and the installed `codex mcp login --help`; `codex mcp login <name>` authenticates that configured OAuth server. Treat listing/configuration as discovery only, and verify the source read afterwards. A CLI login for a different host does not prove the current T3 or connected-app session is authenticated.
- When the host exposes no reconnect action, tell the user which integration needs attention in that host's MCP/app settings and ask them to reconnect or enable that existing integration. Rediscover tools and repeat the read after they confirm. Report a missing server separately from an expired login; a missing server needs host setup, rather than an OAuth retry against an invented name.
- Keep provider scopes and credentials unchanged. Obtain user authentication through the host's private flow; never request tokens in chat. Installing a replacement integration, changing credentials/configuration, enabling remote access or expanding permissions requires separate authorization.

If critical access is still missing, pause fresh collection/publication and name the blocked sources with their recovery actions. The user may reconnect them or explicitly choose a partial report; absence, elapsed time and earlier partial reports do not supply that choice. During an unattended run, retain the current workspace, report the reconnection blocker and stop instead of silently publishing a degraded new day. Honor an existing explicit partial-run authorization when it applies.

If a browser or scheduled request already exists, preserve its exact ID. When recovery cannot finish the run, fail only that matching pending/running request through the workspace lifecycle; a stale request changes nothing. After reconnection, begin a new request if the old one failed or expired. Do not leave a known blocked request labelled running or advance the active snapshot to conceal the failure.

Once access passes (or partial collection is explicitly authorized), follow the collection contract. Later provider failures remain independent: collect the other sources, label coverage honestly, and retain earlier evidence with its original timestamps. Never label retained evidence freshly checked or a partial report complete.
