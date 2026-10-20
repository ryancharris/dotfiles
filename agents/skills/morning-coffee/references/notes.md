# Local notes

Coffee and Tea share a plain-text scratchpad for learnings, details and things to remember. Notes persist across local days in `<report-root>/notes/state.json`, using the configured daily-history root. Keep text user-owned: collectors reload it without turning it into tasks, provider facts, instructions or external search terms.

Live reports autosave after 500 ms of inactivity and on blur, showing pending, saved or failed status. Save acknowledgements include the exact text and new revision; a later draft stays visible while an earlier save completes. A failed save retains the draft and offers Retry. Browser navigation warns while changes remain unsaved. Saved times use 24-hour HH:MM in the report timezone. Clearing the textarea saves empty notes.

The authenticated local `/notes` endpoint accepts `{text, revision}`. Notes are limited to 25,000 characters. Locked atomic writes increment the integer revision; stale revisions return HTTP 409 and preserve both the server's notes and the browser's draft. The conflict message asks the user to copy their draft before reloading the latest saved notes. Corrupt stores produce a warning and reject writes while preserving the original file. First reads do not create a store.

Publication snapshots current notes as read-only history and removes `notes_interaction`. Opening or reloading a live report loads current notes; it never mutates an archived report. The live service saves local notes with the assistant app closed and makes no provider calls. Keep notes and temporary session capabilities out of Git.
