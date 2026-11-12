# API-key evidence audit — before new authenticated probes

This distinguishes endpoint/key transport from completed authenticated inference. The manifest was not edited.

| App | Retained primary result | Defensible scope |
|---|---|---|
| Paseo | Actual OpenRouter assistant timeline returned `PASEO_OPENROUTER_OK`, with request/timeline exit 0. | Authenticated gateway inference passed through Paseo/OpenCode. Its additional Claude/OpenAI successes used subscription identities; those are separate Enterprise evidence, not lab-issued API-key tests. |
| Sheprd | An intentionally invalid key reached OpenRouter through its configured OpenCode ACP route and produced OpenRouter's 401 body. | Key transport/endpoint wiring proven. No successful authenticated model reply is established by that result. |
| Agentastic | An intentionally invalid environment key reached OpenRouter through its bundled CLI and produced 401. | Key transport/endpoint wiring proven. No successful authenticated model reply is established; Provider Pass remained untested. |

The current Paseo note says “OpenAI and Claude requests also passed”; any updated wording should explicitly call those **subscription-account requests**. The Sheprd and Agentastic notes correctly mention 401, but that cannot serve as completed authenticated inference when validating the whole requirement.

The prepared common probe can qualify an app-owned-terminal → installed OpenCode → OpenRouter route once an authorized key is supplied. Record this route exactly; a hosted CLI pass must not be relabelled as a pass for a native wallet/adapter. Direct Anthropic, OpenAI and Google lab-issued API-key requests remain outside these retained tests.

See [Paseo primary receipts](paseo-primary-receipts.json), retained [Sheprd](hands-on-sheprd.md) and [Agentastic](hands-on-agentastic.md) observations, and the [prepared authenticated probe](authenticated-byok-probe.md).
