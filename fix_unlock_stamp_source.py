#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the pre-cap stamp must be read off the FILE, not off the merge
Run from the same folder as index.html:
    python3 fix_unlock_stamp_source.py

WHAT WAS WRONG
--------------
fix_unlock_polish.py re-stamped `priorProjects` on import when the field
was absent, reasoning that only a pre-cap file lacks it. That test was
applied to the wrong object.

`settings` is stamped at load, from the device. On a fresh phone that
writes `priorProjects = 0` before any file is opened. A v2 backup carries
no `settings` block at all, so the import leaves the device's settings
in place — field present, value 0 — and the re-stamp never fires. Retested
in a real browser after that fix: 5 projects restored, prior still 0,
heading still the cold "Unlock unlimited projects".

The field's presence describes the DEVICE. What the rule needs to know is
whether the FILE brought standing with it, so the test moves onto `d`:

  * v2 file            — no `d.settings` at all        → pre-cap, stamp it
  * v3 before this build — `d.settings`, no stamp       → pre-cap, stamp it
  * v3 after this build  — `d.settings.priorProjects`   → its own standing,
                                                           already merged,
                                                           left alone

Same intent as the previous fix, evaluated against the object that
actually answers the question.

Backs up first, exact-match anchor asserted ==1, node --check, atomic.
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

    old = """       arrived after it. Every v3 file carries this field, so its absence is
       exactly the test for "older than the feature" — and a file that does
       carry one never has its own standing overwritten. */
    if(typeof settings.priorProjects!=='number') settings.priorProjects=houses.length;"""
    new = """       arrived after it.

       The test is on the FILE, not on the merged settings: this device
       stamped itself at load — 0 on a fresh phone — and a v2 backup carries
       no settings block to overwrite that, so asking whether the field
       exists here only ever describes the phone. Asking `d` describes the
       backup, which is the thing being judged. A file that brought its own
       standing has already merged it and is left alone. */
    if(!(d.settings && typeof d.settings.priorProjects==='number')) settings.priorProjects=houses.length;"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    if "if(typeof settings.priorProjects!=='number') settings.priorProjects=houses.length;" in working:
        fail("the old device-side test survived.")
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_unlock_stamp_check.js")
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

    print("\n✅ the pre-cap stamp now reads the file that is being restored.")


if __name__ == "__main__":
    main()
