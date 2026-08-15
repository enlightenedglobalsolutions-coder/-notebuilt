#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — plant the EGS-STD:schema marker where the schema actually lives
Run from the same folder as index.html:
    python3 fix_schema_std_marker.py

egs-deploy.sh --full greps index.html for a literal `EGS-STD:<id>` comment for
each checkable row in EGS-STANDARDS.md §2. The schema work is shipped and the
deploy's own "Storage schema versioning" probe passes, but the §2 marker was
never planted, so the run still reported:

    WARN  EGS-STD:schema missing — see EGS-STANDARDS.md §2

Marking it satisfied while it is absent would be the same failure the schema
work exists to prevent — a claim nothing reads. So the marker goes on the block
it describes, not somewhere convenient.

Comment-only. Byte-identical executable lines, asserted below.

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


def strip_comments(js):
    """Executable-line view: block and line comments removed, blanks dropped."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    out = []
    for line in js.splitlines():
        line = re.sub(r"//.*$", "", line).rstrip()
        if line.strip():
            out.append(line)
    return "\n".join(out)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")

    old = """/* ---------- storage schema: a number written, and actually read ----------
   Two version systems live in this file, and confusing them is the whole
   risk, so they are named apart at every site they appear:"""
    new = """/* ---------- storage schema: a number written, and actually read ----------
   EGS-STD:schema — the §2 row lives here, on the block it describes.

   Two version systems live in this file, and confusing them is the whole
   risk, so they are named apart at every site they appear:"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "EGS-STD:schema" not in working:
        fail("the marker did not land.")
    if working.count("EGS-STD:schema") != 1:
        fail("the marker is planted more than once.")

    # comment-only: the executable lines must be byte-identical
    before_scripts = re.findall(r"<script>(.*?)</script>", text, re.S)
    after_scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if len(before_scripts) != len(after_scripts):
        fail("script block count changed.")
    for i, (b, a) in enumerate(zip(before_scripts, after_scripts)):
        sb, sa = strip_comments(b), strip_comments(a)
        if sb != sa:
            fail(f"script block {i} changed executable lines — this must be comment-only.")
    exec_lines = len(strip_comments(after_scripts[0]).splitlines())
    print(f"✅ guard: comment-only — {exec_lines} executable lines identical to the previous file")

    # the schema work itself must be untouched
    for needle in ("const NB_SCHEMA_VERSION = 2;",
                   "settings.schemaVersion=nbSchemaReached;",
                   "if(schemaFromFuture) return;",
                   "if(name!=='settings' && persist[name]) persist[name]();",
                   "if(settingsUnreadable) return;",
                   "settingsUnreadable=true;",
                   "if (blank(cur) && !blank(bak)) _set(k, bak);"):
        if needle not in working:
            fail(f"missing after edit: {needle!r}")
    if working.count("nbApplySchema(") != 3:
        fail("expected nbApplySchema defined once and called twice.")
    if working.count("fetch(") != 2:
        fail("fetch( count changed — expected exactly 2.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Planted EGS-STD:schema in {TARGET}")

    js_path = Path("/tmp/_notebuilt_std_marker_check.js")
    js_path.write_text(after_scripts[0], encoding="utf-8")
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

    print("\n✅ the §2 marker now sits on the block it describes.")


if __name__ == "__main__":
    main()
