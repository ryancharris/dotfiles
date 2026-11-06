# Scheduled Morning Coffee

A scheduled invocation runs the same generation workflow as a manual invocation. Resolve today in the user's IANA timezone at execution time, collect all six sources through preflight and the collection contract, publish a new `morning-coffee` generation, apply it, and open the private workspace URL through [workspace lifecycle](workspace.md). A new run carries unfinished work forward while preserving local decisions and immutable history.

If collection cannot produce a valid snapshot, preserve the active report and disclose the failure. Verify the resulting local date and source coverage. Creating or changing a schedule requires the user's request; verify its cadence, timezone and next run through the host scheduler.

Suggested task prompt, substituting the user's timezone:

> Run $morning-coffee for today in America/Toronto. Collect all six sources, publish and apply a new report, preserve local work, and open it in the default browser. Follow the installed skill and verify the completed report's local date. Append today's YYYY-MM-DD to the session title.
