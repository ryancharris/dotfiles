#!/usr/bin/env python3
"""Report drift between orca/settings.json and Orca's live settings.

Orca keeps settings in a SQLite document store it owns, with no CLI or config
file to feed. This reads a copy of the DB (never the live file) and diffs only
the keys tracked in settings.json. Exit 0 = in sync, 1 = drift.
"""
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ORCA = Path.home() / "Library/Application Support/orca"
WANT = json.loads((Path(__file__).parent / "settings.json").read_text())

profile = json.loads((ORCA / "orca-profile-index.json").read_text())["activeProfileId"]
src = ORCA / "profiles" / profile

with tempfile.TemporaryDirectory() as tmp:
    for suffix in ("", "-wal", "-shm"):
        f = src / f"profile-state.db{suffix}"
        if f.exists():
            shutil.copy(f, Path(tmp) / f.name)
    db = sqlite3.connect(f"file:{tmp}/profile-state.db?mode=ro", uri=True)
    row = db.execute(
        "select payload from profile_state_documents where domain='settings'"
    ).fetchone()
live = json.loads(row[0])

drift = {k: (live.get(k), v) for k, v in WANT.items() if live.get(k) != v}
if not drift:
    print(f"orca settings in sync ({len(WANT)} keys)")
    sys.exit(0)
for k, (have, want) in drift.items():
    print(f"DRIFT {k}\n  live: {json.dumps(have)[:120]}\n  want: {json.dumps(want)[:120]}")
sys.exit(1)
