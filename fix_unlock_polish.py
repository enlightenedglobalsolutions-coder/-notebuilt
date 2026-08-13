#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — three corrections to the unlock, found by testing it
Run from the same folder as index.html:
    python3 fix_unlock_polish.py

1. A PRE-CAP BACKUP LOST ITS OWNER'S STANDING  (the real one)
   -----------------------------------------------------------
   `priorProjects` is stamped at load, from what is on the device at that
   moment. Restore a v2 backup onto a new phone and the order is: stamp 0
   (the phone is empty) → import arrives with 5 projects. The person now
   holds five pre-cap projects and a stamp that says they had none, so the
   cap moment greets them with the cold pitch — "free for 3, you are using
   all 3" — which is both wrong and precisely the rug-pull reading this
   feature is supposed to avoid. Verified in a real browser before the fix:
   5 projects restored, heading came back "Unlock unlimited projects".

   The fix stamps the restored count when the file carries no stamp of its
   own. A v3 file always carries the field, so its absence IS the test for
   "written before the cap existed" — no version sniffing needed, and a
   modern file's own standing is never overwritten.

2. THE COLD PITCH ASSERTED A NUMBER IT DID NOT CHECK
   --------------------------------------------------
   It read "free for 3 projects, and you are using all 3" whenever the
   warm branch did not fire — including for someone holding 6 from an
   unlocked friend's v3 backup, where it is simply false. It now states
   the count it actually has.

3. THE SETTINGS ROW CONTRADICTED ITSELF
   -------------------------------------
   A 5-project person read: "Free — 3 projects / 5 projects, all yours to
   keep." The title now drops the number when the number would fight the
   line beneath it.

Plus the Buy control is an <a> for target=_blank, so it arrived wearing a
link underline no other button in the app has.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — a pre-cap file confers pre-cap standing
    old_stamp = """    settings.lastBackupAt=d.exportedAt||now();
    persist.settings();"""
    new_stamp = """    settings.lastBackupAt=d.exportedAt||now();
    /* UNLOCK — a backup written before the cap existed carries no standing
       of its own, and every project inside it is pre-cap by definition. Take
       the restored count as the stamp, so the person who made that work is
       met with the words they are owed instead of a pitch for a limit that
       arrived after it. Every v3 file carries this field, so its absence is
       exactly the test for "older than the feature" — and a file that does
       carry one never has its own standing overwritten. */
    if(typeof settings.priorProjects!=='number') settings.priorProjects=houses.length;
    persist.settings();"""
    edits.append((old_stamp, new_stamp, "importData(): pre-cap file confers pre-cap standing"))

    # 2 — say the number you actually have
    old_cold = """    : 'Notebuilt is free for '+free+' projects, and you are using all '+free+'.<br><br>'"""
    new_cold = """    : 'Notebuilt is free for '+free+' projects'+(houses.length===free?', and you are using all '+free+'.':', and you have '+houses.length+'.')+'<br><br>'"""
    edits.append((old_cold, new_cold, "unlockPitch(): state the real count"))

    # 3 — the row title must not fight the line under it
    old_title = """<div class="card row" data-help="unlock"><div class="grow"><div>${unlockIsOn()?'Unlocked \\u2713':'Free \\u2014 '+UNLOCK.FREE_PROJECTS+' projects'}</div>"""
    new_title = """<div class="card row" data-help="unlock"><div class="grow"><div>${unlockIsOn()?'Unlocked \\u2713':(houses.length>UNLOCK.FREE_PROJECTS?'Free':'Free \\u2014 '+UNLOCK.FREE_PROJECTS+' projects')}</div>"""
    edits.append((old_title, new_title, "renderSettings(): row title vs its own subtitle"))

    # 4 — the only button in the app wearing a link underline
    old_link = """'<a class="btn primary block" style="margin-top:14px" href="'"""
    new_link = """'<a class="btn primary block" style="margin-top:14px;text-decoration:none" href="'"""
    edits.append((old_link, new_link, "unlockPitch(): drop the anchor underline"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    n_fetch = working.count("fetch(")
    if n_fetch != 1:
        fail(f"expected exactly 1 fetch( in the file, found {n_fetch}.")
    if "if(typeof settings.priorProjects!=='number') settings.priorProjects=houses.length;" not in working:
        fail("the import re-stamp did not land.")
    # The old form asserted the count with no test in front of it. The new one
    # keeps that wording inside a branch, so match the unconditional shape.
    if "' projects, and you are using all '" in working:
        fail("the unconditional count claim survived.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: still exactly one fetch( in the file")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_unlock_polish_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ UNLOCK polish applied: a pre-cap backup keeps its owner's standing.")


if __name__ == "__main__":
    main()
