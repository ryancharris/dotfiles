# Retained hands-on evidence — 12 November 2026

The original ten records preserve the eight app test reports, the config-consent audit and the post-test cleanup report from the prior session. They are historical observations, not the current grading decision: some record earlier rounds before later visual checks, and some original grades were superseded by the final evidence audit. [comparison-grades.json](../comparison-grades.json) is authoritative for the current report.

The historical archive contains Markdown reports; continuation checks also retain sanitized boolean/count JSON. No raw agent transcripts, authentication files, provider caches, settings snapshots or account identifiers were copied. User paths and organization names are redacted; the deliberately invalid test key and fixed test replies are preserved.

Original screenshots and supporting raw artifacts remain in the prior session scratchpad on the test host. `$ORIGINAL_SCRATCHPAD` in these records means `/private/tmp/claude-501/-Users-ryan-orca-workspaces-dotfiles-hatchetfish/ac55229f-5fc0-4cfa-aa05-d0ae6fc14d81/scratchpad`; these local references are provenance, not portable links. A small set of unmodified, personally inspected chat/diff captures is now retained in `primary-screenshots/` with provenance hashes; screenshots containing private shell context remain local.

## Current validation overview

- [Top-three validation](top-three-validation.md): ranked recommendations and exact tested setups; overall validation remains incomplete pending authenticated BYOK for Sheprd and Agentastic.
- [API-key evidence audit](top-three-api-key-evidence-audit.md) and [prepared authenticated probe](authenticated-byok-probe.md): 401 wiring and subscription sign-in are distinct from an authenticated API-key assistant reply.

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

## Continuation checks

- [Paseo primary validation matrix](paseo-validation-matrix.md), [fresh delegation receipt](paseo-delegation-result.json) and [runner](paseo-delegation-validation.py).
- [Paseo saved login profile and representative PTY input](paseo-h3-followup.md); [separate config/skill consent comparison](paseo-config-consent-result.json).
- [Sheprd configured-core validation](sheprd-validation-notes.md), [guarded startup/raw-TUI receipt](sheprd-validation-startup-guards.json), [native-chat/child receipt](sheprd-validation-final.json) and [reproducible probe](sheprd-validation-run.py).
- [Agentastic actual GUI input validation](agentastic-validation-h3.md) and [startup executable/loader wiring](agentastic-startup-wiring.md).
- [Personally reviewed original chat/diff captures](primary-screenshots/provenance.json), with their historical date and provenance.

## Earlier continuation attempts — superseded

- [Sheprd startup/input follow-up](sheprd-h3-followup.md): the earlier unverified persistent-launch route was superseded by the explicitly configured core-0.1.18 validation above; the bundled-0.1.13 limitation remains explicit.
- [Agentastic input follow-up](agentastic-h3-followup.md): the earlier automation failure to hold an editable line was superseded by the actual GUI key probe above.

## Specific license verification

- [Paseo, Sheprd and Agentastic](licenses-top-three.json): release-pinned Apache-2.0 records and the separately scoped current Agentastic MIT/closed-source notices.
- [Orca, Pane, Ghostex, T3 Code and OpenChamber](licenses-other-five.json): immutable release license sources, exact SPDX identifiers, added terms and distribution/service boundaries.

The displayed main-project license does not replace third-party notices. Pane's extra terms are explicit; Agentastic's current website notice is not represented as a release-specific binary license verification.
