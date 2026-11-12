# Retained hands-on evidence — 12 November 2026

The original ten records preserve the eight app test reports, the config-consent audit and the post-test cleanup report from the prior session. They are historical observations, not the current grading decision: some record earlier rounds before later visual checks, and some original grades were superseded by the final evidence audit. [comparison-grades.json](../comparison-grades.json) is authoritative for the current report.

The historical archive contains Markdown reports; continuation checks also retain sanitized boolean/count JSON. No raw agent transcripts, authentication files, provider caches, settings snapshots or account identifiers were copied. User paths and organization names are redacted; the deliberately invalid test key and fixed test replies are preserved.

Original screenshots and supporting raw artifacts remain in the prior session scratchpad on the test host. `$ORIGINAL_SCRATCHPAD` in these records means `/private/tmp/claude-501/-Users-ryan-orca-workspaces-dotfiles-hatchetfish/ac55229f-5fc0-4cfa-aa05-d0ae6fc14d81/scratchpad`; these local references are provenance, not portable links. Screenshots were not duplicated in this archive.

## Records

- [Agentastic](hands-on-agentastic.md)
- [Ghostex](hands-on-ghostex.md)
- [OpenChamber](hands-on-openchamber.md)
- [Orca](hands-on-orca.md)
- [Pane](hands-on-pane.md)
- [Paseo](hands-on-paseo.md)
- [Sheprd](hands-on-sheprd.md)
- [T3 Code](hands-on-t3code.md)
- [Config-consent audit](h7-config-consent.md)
- [Cleanup report](cleanup-report.md)

## Follow-up qualification

- [Sheprd startup and input follow-up](sheprd-h3-followup.md), with [sanitized results](sheprd-h3-followup.json): H3 remains Partial; input and startup boundaries are recorded separately.

## Continuation checks

- [Paseo saved login profile and representative PTY input](paseo-h3-followup.md) — passed for that profile/API route; default shell and desktop key-event translation are outside the claim.
- [Sheprd startup and input follow-up](sheprd-h3-followup.md) — partial; persistent GUI login-mode launch unverified.
- [Agentastic input follow-up and cleanup](agentastic-h3-followup.md) — partial; automation could not hold an editable input line.
