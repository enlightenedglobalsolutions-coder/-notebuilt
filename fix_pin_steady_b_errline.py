#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — PIN screen: the last 0.84 pixels (th_nb_pin)
Run from the same folder as index.html, AFTER fix_pin_steady.py:
    python3 fix_pin_steady_b_errline.py

Measuring the fixed lock screen turned up one residual shift that the
build-once rewrite does not cover, and it is the brief's suspect 2 after
all — just at a scale you would never find by reading:

    .err height, empty ......... 18.000px   (min-height:18px)
    .err height, "Wrong PIN" ... 18.844px   (13px x 1.45 line box)
    growth ..................... 0.844px

`min-height:18px` was meant to reserve the error line, and it very nearly
does — it is 0.84px short of the natural line box. So the row grows the
instant a message appears, and because `#lock` centres its column that
growth splits: everything above rises 0.42px, everything below drops
0.42px. Measured, on a wrong PIN:

    mark   -0.42px      keypad +0.42px      forgot-link +0.42px

Sub-pixel, but it lands on exactly the frame where the user already
mistyped, and it is free to remove: pin the line box to the same 19px the
empty box reserves, and the height cannot change at all.

Left deliberately alone: `.err` on the recovery screens shares this rule
and carries longer sentences that may wrap to two lines. Those screens
have no keypad under the thumb and no rapid entry, so a wrap there is
ordinary reflow rather than the reported bug.

Backs up first, exact-match anchor asserted ==1, node --check.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "PIN_STEADY_ERRLINE"


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
    if "PIN_STEADY" not in text:
        fail("fix_pin_steady.py has not been applied yet — run that first.")

    old = """  #lock .err{color:var(--danger);font-size:13px;min-height:18px;margin-top:6px}"""
    new = """  /* PIN_STEADY_ERRLINE — min-height:18px reserved the row but fell 0.84px short
     of the 13px/1.45 line box, so the row grew the moment a message appeared and
     the centred column split the growth above and below. Pinning line-height to
     the same 19px the empty box reserves makes the height unconditional. */
  #lock .err{color:var(--danger);font-size:13px;min-height:19px;line-height:19px;margin-top:6px}"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_pin_errline_check.js")
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

    print("\n✅ PIN_STEADY_ERRLINE applied: the error row's height is now unconditional.")


if __name__ == "__main__":
    main()
