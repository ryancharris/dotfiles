# Agent environment comparison

An evidence-based comparison of Orca, Paseo, cmux, Herdr, Sheprd and T3 Code against the requirements printed in the report. Conductor is excluded by user decision. CPU/RAM and Kitty appearance parity are outside this report's current scope; existing zsh configuration remains required.

- `ade-comparison-share.html`: standalone report with all six apps.
- `ade-comparison-detailed.html`: the same report with two-app selectors.
- `ade-comparison-social.png`: full desktop export of the standalone report.
- `comparison-grades.json`: the explicit per-field evidence grades and rubric.
- `comparison-validation.json`: retained browser verification results.
- `sheprd-evidence.md` and `t3-evidence.md`: pinned primary-source research for the new entries.

Every one of the eight comparison fields has a visible grade. **Proven** means a local test or definitive primary record establishes the stated scope; **Supported** means source/documentation supports the capability but runtime remains unverified; **Partial** means only part of the requirement is established; **Gap** means an observed mismatch; **Unknown** means insufficient evidence, not failure. Grades are never added into a total, and open-source/free extras cannot compensate for a hard requirement.

The notes delimit each grade. In particular, a working credential route is not proof of this user's Enterprise account; documented current source is not a tested installed release; and launch without product login is limited to the observed local path. The grading change introduces no new product runtime qualification claims.

## Verify and refresh the export

On macOS with Google Chrome installed at its usual application path, run from the repository root:

```sh
python3 work/validate-comparison.py
```

The standard-library script uses a disposable headless browser profile. It validates both views at 390, 768 and 1400 CSS pixels, all 48 cell grades against the manifest, identical table contents, the legend and requirements disclosure, outer-page overflow, all 36 selector pairs, and show-all. It updates the validation JSON and social PNG. Narrow tables scroll horizontally by design.
