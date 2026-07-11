#!/usr/bin/env python3
"""
Notebuilt — Chunk 13: rename backup from "punchlist" to "notebuilt"
Run this from the same folder as your index.html:
    python3 fix_chunk13_rename_backup.py

Changes the full-app backup's downloaded filename and internal format
marker from the old "punchlist" naming to "notebuilt". Old backups you've
already saved (with the old marker) will still restore fine — the restore
check now accepts both.

Does NOT touch the IndexedDB database name ('punchlist') that your photos
are actually stored under on-device — renaming that would orphan every
photo you've already saved, so it stays exactly as-is, invisibly, forever.

Backs up first, applies edits with exact-match anchors, aborts atomically
if anything doesn't match, and validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "CHUNK13_RENAME_BACKUP"  # already-applied guard

def fail(msg):
    print(f"\n❌ ABORTED — no changes were made.\n   Reason: {msg}\n")
    sys.exit(1)

def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found in this folder.")

    text = TARGET.read_text(encoding="utf-8")

    if MARKER in text:
        print("✅ Already applied — nothing to do.")
        return

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: exportData() — new format marker
    # ---------------------------------------------------------------
    old1 = """  const dump={ app:'punchlist', version:1, exportedAt:now(), houses, tasks, notes, photos:photoData };"""
    new1 = """  /* CHUNK13_RENAME_BACKUP */
  const dump={ app:'notebuilt', version:1, exportedAt:now(), houses, tasks, notes, photos:photoData };"""
    edits.append((old1, new1, "exportData(): new format marker 'notebuilt'"))

    # ---------------------------------------------------------------
    # Edit 2: exportData() — new downloaded filename
    # ---------------------------------------------------------------
    old2 = "  a.download=`punchlist-backup-${todayKey()}.json`; a.click();"
    new2 = "  a.download=`notebuilt-backup-${todayKey()}.json`; a.click();"
    edits.append((old2, new2, "exportData(): new backup filename"))

    # ---------------------------------------------------------------
    # Edit 3: importData() — accept both old and new markers
    # ---------------------------------------------------------------
    old3 = """    if(d.app!=='punchlist') throw new Error('Not a Punch List backup');"""
    new3 = """    if(d.app!=='notebuilt' && d.app!=='punchlist') throw new Error('Not a Notebuilt backup');"""
    edits.append((old3, new3, "importData(): accept both old and new backup markers"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk13_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check. Review the diff manually.")
        result = None

    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 13 applied successfully: backups now save as 'notebuilt-backup-*.json'.")
    print("   Old 'punchlist-backup-*.json' files will still restore fine.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
