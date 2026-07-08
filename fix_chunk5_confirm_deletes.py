#!/usr/bin/env python3
"""
Notebuilt — Chunk 5: Confirm before deleting anything
Run this from the same folder as your index.html:
    python3 fix_chunk5_confirm_deletes.py

Adds a confirm() prompt to the three delete actions that didn't have one yet:
  - Deleting a to-do (task edit sheet)
  - Deleting a spec row (paint/flooring/trim entry on a project)
  - Deleting a photo from the grid's "X" button

(House delete, note delete, the full-screen viewer's photo delete, and
restore-backup already had confirmations — this fills in the rest.)

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
MARKER = "CHUNK5_CONFIRM_DELETES"  # already-applied guard

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
    # Edit 1: spec delete — add confirm()
    # ---------------------------------------------------------------
    old1 = """  $app.querySelectorAll('[data-del-spec]').forEach(b=>b.onclick=()=>{
    const h=houseById(view.param); h.specs=h.specs.filter(s=>s.id!==b.dataset.delSpec); h.updatedAt=now(); persist.houses(); render();
  });"""
    new1 = """  /* CHUNK5_CONFIRM_DELETES */
  $app.querySelectorAll('[data-del-spec]').forEach(b=>b.onclick=()=>{
    if(!confirm('Delete this spec?'))return;
    const h=houseById(view.param); h.specs=h.specs.filter(s=>s.id!==b.dataset.delSpec); h.updatedAt=now(); persist.houses(); render();
  });"""
    edits.append((old1, new1, "spec delete: add confirm()"))

    # ---------------------------------------------------------------
    # Edit 2: photo grid "X" delete — add confirm()
    # ---------------------------------------------------------------
    old2 = """  $app.querySelectorAll('[data-del-photo]').forEach(b=>b.onclick=async ev=>{ ev.stopPropagation();
    const pid=b.dataset.delPhoto, h=houseById(view.param);
    await photoDel(pid).catch(()=>{}); h.photos=(h.photos||[]).filter(x=>x!==pid);
    if(h.cover===pid) h.cover=null; h.updatedAt=now(); persist.houses(); render();
  });"""
    new2 = """  $app.querySelectorAll('[data-del-photo]').forEach(b=>b.onclick=async ev=>{ ev.stopPropagation();
    if(!confirm('Delete this photo?'))return;
    const pid=b.dataset.delPhoto, h=houseById(view.param);
    await photoDel(pid).catch(()=>{}); h.photos=(h.photos||[]).filter(x=>x!==pid);
    if(h.cover===pid) h.cover=null; h.updatedAt=now(); persist.houses(); render();
  });"""
    edits.append((old2, new2, "photo grid delete: add confirm()"))

    # ---------------------------------------------------------------
    # Edit 3: to-do delete (edit sheet) — add confirm()
    # ---------------------------------------------------------------
    old3 = """  $mr.querySelector('#t-del').onclick=()=>{ tasks=tasks.filter(x=>x.id!==id); persist.tasks(); closeSheet(); render(); toast('Deleted'); };"""
    new3 = """  $mr.querySelector('#t-del').onclick=()=>{ if(!confirm('Delete this to-do?'))return; tasks=tasks.filter(x=>x.id!==id); persist.tasks(); closeSheet(); render(); toast('Deleted'); };"""
    edits.append((old3, new3, "to-do delete: add confirm()"))

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
    js_path = Path("/tmp/_notebuilt_chunk5_check.js")
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

    print("\n✅ Chunk 5 applied successfully: every delete action now requires confirmation.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
