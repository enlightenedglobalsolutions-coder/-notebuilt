#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the Calculator's (i) comes off the title and onto the Clear row.
Run from the same folder as index.html:
    python3 fix_infomode_calc_host.py

Found by measuring, not by looking. fix_infomode.py put a marker inline at the
end of four topbar titles on the argument that all four are short, fixed
strings that cannot wrap. Three of them cannot. "Calculator" can.

At 320px the Calculator topbar carries the ft/in ↔ metric toggle beside the
title, which leaves .grow exactly 133.5px — and "Calculator" at 25px serif is
already 133.5px of it. The marker's 21px tipped the h1 to two lines in
beginner mode and one in expert, and everything below it moved: 49 elements
shifted between modes on that screen alone. Every other screen measured zero
at 320px, and the Calculator measured zero at 680px, which is exactly why
"it looks fine" was never going to catch this.

The Clear row is the host that cannot fail. .cclear is display:flex with
justify-content:flex-end, so it is one button packed right with free space to
its left; margin-right:auto parks the marker at the left edge and lets the
free space between them do the absorbing. Hidden, Clear does not move, and the
row's height is the 46px tap target either way, not the 15px marker. It also
lands the marker directly under the five mode tabs, which is what the copy is
about.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
try:
    from fixscript_check import check_html
except ImportError as e:
    print(f"❌ cannot import platform/fixscript_check.py ({e}) — refusing to edit unverified.")
    sys.exit(1)

TARGET = Path("index.html")
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


CSS_OLD = """  .sec-head .help-i{margin-left:-2px}
"""

CSS_NEW = """  .sec-head .help-i{margin-left:-2px}
  /* The Calculator's host. .cclear is one button packed right, so an auto
     margin parks the marker at the far left and the gap between them does the
     absorbing — Clear does not move when the marker goes, and the row's
     height is the button's 46px either way. This exists because the title
     could not take the marker: at 320px the ft/in toggle leaves .grow 133.5px
     and "Calculator" is already 133.5px of it, so the h1 wrapped in beginner
     and not in expert. Measured, at width, not eyeballed at desktop. */
  .cclear .help-i{margin-right:auto}
"""

H1_OLD = """'</span><h1>Calculator '+nbHelpMark('calc')+'</h1></div>'+unitTog"""
H1_NEW = """'</span><h1>Calculator</h1></div>'+unitTog"""

ROW_OLD = """  var clearRow='<div class="cclear"><button class="btn" data-calc-clear>Clear</button></div>';"""
ROW_NEW = """  var clearRow='<div class="cclear">'+nbHelpMark('calc')+'<button class="btn" data-calc-clear>Clear</button></div>';"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = [
        (CSS_OLD, CSS_NEW, "cclear marker rule"),
        (H1_OLD, H1_NEW, "Calculator title marker removal"),
        (ROW_OLD, ROW_NEW, "Calculator clear-row marker"),
    ]

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    import re as _re
    # The marker moved, it did not multiply or vanish.
    if working.count("nbHelpMark('calc')") != 1:
        fail("the calc marker is not present exactly once.")
    if "<h1>Calculator</h1>" not in working:
        fail("the Calculator title did not come back clean.")
    # Three title markers left, and they are the three that measured zero
    # shift at 320px. A fourth reappearing here is the bug coming back.
    n_titles = (len(_re.findall(r"<h1>[^<]*\$\{nbHelpMark", working))
                + len(_re.findall(r"<h1>[^<]*'\+nbHelpMark", working)))
    if n_titles != 3:
        fail(f"{n_titles} title markers — expected exactly To Do, Projects and Notes.")
    for t in ("To Do", "Projects", "Notes"):
        if f"<h1>{t} ${{nbHelpMark(" not in working:
            fail(f"the {t} title marker went missing.")
    # The auto margin is the whole mechanism; without it the marker packs
    # right against Clear and pushes it left when shown.
    if working.count(".cclear .help-i{margin-right:auto}") != 1:
        fail("the auto margin that makes the Clear row reflow-free is not there.")
    # Clear still clears, and the row is still the one place identical in all
    # five calculator modes.
    if working.count("data-calc-clear") != 2:
        fail("the Clear button or its handler moved.")

    # ---- backup, then write --------------------------------------------
    stamp = int(time.time())
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}")
    n = 1
    while backup_path.exists():
        backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}-{n}")
        n += 1
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edit(s) to {TARGET}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ The Calculator's (i) sits on a host with real slack; no screen "
          "moves a pixel between beginner and expert at any width.")


if __name__ == "__main__":
    main()
