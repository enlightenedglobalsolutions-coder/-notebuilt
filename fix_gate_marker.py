#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — name the gate so the deploy script can see it
Run from the same folder as index.html:
    python3 fix_gate_marker.py

WHAT CHANGES
------------
One comment line, and nothing else.

Notebuilt is the app that actually implements EGS-STANDARDS §2 row 9 — three
free projects, one-time Polar key, unlock keyed on a completed activation —
and it is the only one that does. But `egs-deploy.sh --full` asserts row 9 by
grepping `index.html` for the marker `EGS-STD:gate`, and that string was not
in the file. So the one app with a gate was the one app the check could not
confirm had one. §7 has carried that as an open item since the gate shipped
(2026-08-13); this closes it.

The marker goes on the UNLOCK_CONFIG block, which is where the gate's strings
and ids live, so the comment sits on the thing it names rather than floating.

No behaviour changes. Backs up first, anchor asserted ==1, node --check.
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

    if "EGS-STD:gate" in text:
        fail("the marker is already in the file — nothing to do.")

    old = """/* ============================================================
   UNLOCK_CONFIG — every string and id the paid unlock needs, in one
   place, on purpose."""
    new = """/* ============================================================
   EGS-STD:gate — §2 row 9 lives here. All features free, three free
   projects, one-time Polar key, unlock keyed on a completed activation
   rather than on a key merely being present. The cap UI is a plain
   banner and never a nag loop (Tier 1 rule 10).

   UNLOCK_CONFIG — every string and id the paid unlock needs, in one
   place, on purpose."""

    if text.count(old) != 1:
        fail(f"anchor matched {text.count(old)} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("EGS-STD:gate") != 1:
        fail("the marker must appear exactly once.")
    # The comment must not have swallowed any code.
    stripped_old = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    stripped_new = re.sub(r"/\*.*?\*/", "", working, flags=re.S)
    if stripped_old != stripped_new:
        fail("something outside a comment changed — this edit must be comment-only.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print("✏️  Applied 1 edit to index.html")
    print("✅ guard: marker present exactly once")
    print("✅ guard: comment-only — every non-comment byte is identical")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    js_path = Path("/tmp/_notebuilt_gate_marker_check.js")
    js_path.write_text(max(scripts, key=len), encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check, on the app's script block)")

    print("\n✅ the gate is now named where the deploy script looks for it.")


if __name__ == "__main__":
    main()
