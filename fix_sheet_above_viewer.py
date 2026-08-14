#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a sheet opened from the photo viewer must be on top of it
Run from the same folder as index.html:
    python3 fix_sheet_above_viewer.py

THE BUG
-------
`.scrim` (every sheet in the app) sits at z-index 40. `#viewer` sits at 60.
Until now no sheet was ever opened from the viewer, so nothing noticed. The
new Share / Save sheet is opened from exactly there, and it rendered
UNDERNEATH the photo — visible as a faint ghost behind the image, with its
buttons unreachable. Caught in a screenshot, not by a return value, which is
the argument for looking at the thing rather than only asserting about it.

THE FIX, AND ITS CEILING
------------------------
The scrim moves to 80. Not higher, and the ceiling is the point:

    scrim (sheets)     40 -> 80
    #viewer            60      sheets now cover it          <-
    #annotate          70      sheets now cover it          <-
    #lock             100      MUST stay above a sheet
    #vault            110      MUST stay above a sheet
    #camera           115      MUST stay above a sheet
    #vault-busy       120      MUST stay above a sheet
    toast             200

A blanket "put modals on top" would have lifted sheets over the PIN gate and
the vault ceremony, which is a security hole rather than a layout
preference: the lock screen exists to be the only thing on the glass. 80
clears the two surfaces a sheet is legitimately opened from and stays under
every surface that is guarding something.

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

    old = """  .scrim{position:fixed;inset:0;z-index:40;background:rgba(0,0,0,.55);display:flex;align-items:flex-end}"""
    new = """  /* 80 clears #viewer (60) and #annotate (70), which sheets are legitimately
     opened from, and stays below #lock (100), #vault (110), #camera (115) and
     #vault-busy (120) — the surfaces that must never have a sheet over them. */
  .scrim{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.55);display:flex;align-items:flex-end}"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    def zindex(selector):
        m = re.search(re.escape(selector) + r"\{[^}]*?z-index:(\d+)", working, re.S)
        if not m:
            fail(f"could not read z-index for {selector}")
        return int(m.group(1))

    scrim = zindex(".scrim")
    for sel, must_be_under in [("#viewer", True), ("#annotate", True)]:
        if not (scrim > zindex(sel)):
            fail(f"sheets do not cover {sel} — a sheet opened from it would be unreachable.")
    for sel in ["#lock", "#vault", "#camera", "#vault-busy"]:
        if not (scrim < zindex(sel)):
            fail(f"sheets would cover {sel} — that surface must stay on top.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")
    print(f"✅ guard: scrim {scrim} — above viewer/annotate, below lock/vault/camera/vault-busy")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_scrim_check.js")
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

    print("\n✅ the send sheet is reachable from the viewer, and the lock screen still owns the glass.")


if __name__ == "__main__":
    main()
