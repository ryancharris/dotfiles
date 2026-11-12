# Authenticated BYOK probe — prepared, not executed

The runner targets installed **OpenCode 2.2.5** with an inherited `OPENROUTER_API_KEY`. No key has been loaded and no model request was made while preparing it. It refuses inference without both `--execute` and a nonempty inherited key. It never searches transcripts, keychains or prior profiles for credentials.

Run it **inside each ADE-owned test terminal**, after the authorized key has been supplied to that terminal's environment. Keep the ADE terminal launch receipt separately: a command-line label cannot independently establish the hosting app.

```sh
python3 /absolute/path/to/authenticated-byok-probe.py \
  --app-route 'Sheprd app-owned terminal -> OpenCode -> OpenRouter' \
  --model openrouter/openai/gpt-4.1-nano \
  --marker ADE_SHEPRD_BYOK_OK \
  --result /absolute/path/to/sheprd-authenticated-byok-result.json \
  --execute
```

Select a model allowed by the supplied key; the example is not an availability or entitlement check. Omit `--execute` to produce only a clearly labelled preparation record. Use a separate marker/result for every app. This tests the hosted CLI route, not the app's native provider adapter, Provider Pass wallet or ACP configuration unless that separate route is actually exercised.

## Supported recipe

- `--standalone` uses a private server and inherits the caller's environment; `run --format json` emits JSONL. Both flags were checked against installed help and [official CLI documentation](https://opencode.ai/docs/cli/commands/).
- The temporary XDG config declares a dedicated primary agent, one step, and deny-all rules at both global and selected-agent levels. V2 uses `permissions` rules, not the V1 `permission` mapping. Later agent rules override global rules, so the selected agent also denies everything. [Permissions](https://opencode.ai/docs/permissions/), [agents](https://opencode.ai/docs/agents/).
- Provider configuration references `{env:OPENROUTER_API_KEY}`; it never contains the raw key. All four XDG roots and the working directory are temporary; existing OpenCode config/auth stores and the shared background service are not targeted. [Configuration and environment substitution](https://opencode.ai/docs/config/).
- The parser follows the [pinned 2.2.5 JSON emitter](https://github.com/anomalyco/opencode/blob/v2.2.5/packages/cli/src/run/noninteractive.ts): it accepts only completed `text` events carrying assistant `messageID`, part ID, session ID and `time.end`. Titles, user text, synthetic text, plain stdout and arbitrary marker substrings do not count. A pass additionally requires exit 0, one assistant message/session, the exact response, no tool events and no error events. A final accounting event is recorded separately.

Only sanitized result fields and the expected marker are retained. Raw stdout/stderr stay in memory; failure output is not copied into the result. The runner checks for the supplied key in captured output and temporary files, terminates only its private process group, and deletes its temporary profile. It fails closed if the installed version differs from 2.2.5. Background title/summary agents are disabled to avoid incidental maintenance requests.

Syntax and parser fixtures were checked without running OpenCode inference. These checks validate parser behavior, not authentication; no authenticated success is claimed yet.
