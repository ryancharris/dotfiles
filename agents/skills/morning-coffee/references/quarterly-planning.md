# Quarterly Transport Planning

Use only read-only Google Drive search and fetch operations. The fiscal quarter label, workbook URL, and tab IDs change over time, so discover and verify the current documents on every run.

## Discovery

Run at least these two semantic searches with moderate recency:

- `Ops Platform Capacity and Planning Transport_Capacity Quarter start Quarter end`
- `Transport OKRs objectives fiscal quarter spreadsheet`

Search results may contain one row per matching sheet tab and may return semantically related documents that ignore some query terms. Filter locally rather than trusting result order:

1. Retain Google Sheets documents whose title contains an FY-quarter token such as `FY27Q3` or `FY2027 Q3` and whose title or indexed content describes OKRs, objectives, capacity, or planning.
2. Require indexed content for a `Transport`, `Transport_Capacity`, or `Transport_Data` tab. A document that merely mentions transportation or an unrelated Transport team is not eligible.
3. De-duplicate results by document ID, falling back to the canonical spreadsheet URL.
4. Fetch each plausible unique document and inspect its Transport capacity or planning content for explicit `Quarter start` and `Quarter end` dates.

Do not derive the current FY or quarter from the calendar year. A candidate is current only when the report's local date falls within its explicit quarter bounds, inclusive. This makes the workbook's own planning metadata authoritative across fiscal-year and quarter rollovers.

If no candidate contains the current date, do not reuse the previous quarter's link. Around a rollover, a workbook may not yet be indexed or its workday bounds may leave a short calendar gap; report the lookup as unavailable instead of guessing. If several distinct spreadsheets independently satisfy the same current-quarter test, retain all of them and sort by title.

## Links and privacy

Use the canonical `cloud_doc_url` returned by Google Drive. Preserve a sheet-specific URL only when the connector itself returns it; never invent or carry forward a `gid`, because tab IDs can change with each workbook. Link the exact document title and optionally shorten only a redundant `Ops Platform -` prefix in the visible label.

Do not summarize OKR rows, engineer capacity, PTO, or other workbook contents unless the user asks. The default brief exposes only the verified document title, fiscal-quarter label already present in that title, and link.

When Google Drive is unavailable or no current candidate can be verified, render `Transport OKRs unavailable — current-quarter planning sheet not found in Google Drive` under `Today` and name Google Drive in the masthead coverage line. Do not suppress the rest of the brief.
