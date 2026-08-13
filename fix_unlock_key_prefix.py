#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the issued keys carry a prefix, so the normaliser must too
Run from the same folder as index.html:
    python3 fix_unlock_key_prefix.py

THE REAL SHAPE
--------------
A key issued by the product looks like

    NBLT-CFC46983-FAF6-4948-A8A3-FB2838755CD8

which is a 4-character prefix followed by the familiar 8-4-4-4-12. That is
36 alphanumerics, not 32.

WHAT WAS WRONG
--------------
`unlockNormalizeKey` rebuilt the canonical shape only when the typed key
held exactly 32 alphanumerics. At 36 it fell through to "uppercase it and
strip the spaces", so:

  * a key typed exactly as printed  → worked, by luck of the fall-through
  * the same key typed without dashes, or with spaces where the dashes go
    → passed through unseparated and would have come back 404

Which is the forgiving behaviour the brief asked for failing in exactly
the case a person on a phone produces — reading a key off an email and
retyping it.

THE FIX
-------
The prefix moves into UNLOCK as `KEY_PREFIX`, next to every other string
that describes the product, and the normaliser rebuilds around it:

  NBLT + 32  → NBLT-8-4-4-4-12      (prefix present, however punctuated)
  32 alone   → NBLT-8-4-4-4-12      (prefix forgotten — put it back)
  anything else → uppercased, spaces stripped, left alone

Setting KEY_PREFIX to '' restores the plain 32-character behaviour, so a
future product that issues unprefixed keys needs no code change. The
placeholder in the entry field is built from the same constant rather
than hard-coded, so it can never drift from what is actually accepted.

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

    # 1 — the prefix is a property of the product, so it lives with the product
    old_cfg = """  ORG_ID: 'dd1c6def-7b26-4d7d-86eb-fa3f915074a5',
  LABEL: 'Notebuilt'
};"""
    new_cfg = """  ORG_ID: 'dd1c6def-7b26-4d7d-86eb-fa3f915074a5',
  LABEL: 'Notebuilt',
  /* Issued keys are shaped NBLT-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX. Set
     this to '' for a product whose keys carry no prefix — the normaliser
     and the placeholder both follow it, and neither needs editing. */
  KEY_PREFIX: 'NBLT'
};"""
    edits.append((old_cfg, new_cfg, "UNLOCK_CONFIG: KEY_PREFIX"))

    # 2 — rebuild around the prefix instead of only around a bare 32
    old_norm = """function unlockNormalizeKey(s){
  const up=String(s==null?'':s).toUpperCase().replace(/\\s+/g,'');
  const core=up.replace(/[^A-Z0-9]/g,'');
  if(core.length===32) return core.replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/,'$1-$2-$3-$4-$5');
  return up;
}"""
    new_norm = """function unlockNormalizeKey(s){
  const up=String(s==null?'':s).toUpperCase().replace(/\\s+/g,'');
  const core=up.replace(/[^A-Z0-9]/g,'');
  const pre=String(UNLOCK.KEY_PREFIX||'').toUpperCase();
  const group=t=>t.replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/,'$1-$2-$3-$4-$5');
  /* Typed with the prefix, however the dashes fell. */
  if(pre && core.length===pre.length+32 && core.indexOf(pre)===0) return pre+'-'+group(core.slice(pre.length));
  /* Typed without it — every key this product issues has one, so put it
     back rather than send a request that can only ever be refused. */
  if(core.length===32) return (pre?pre+'-':'')+group(core);
  return up;
}"""
    edits.append((old_norm, new_norm, "unlockNormalizeKey(): prefix-aware"))

    # 3 — the example must be built from the rule it illustrates
    old_ph = """placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX\""""
    new_ph = """placeholder="'+(UNLOCK.KEY_PREFIX?UNLOCK.KEY_PREFIX+'-':'')+'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX\""""
    edits.append((old_ph, new_ph, "unlockKeySheet(): placeholder follows KEY_PREFIX"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    if "KEY_PREFIX: 'NBLT'" not in working:
        fail("KEY_PREFIX did not land in the config block.")
    # The sandbox must never be what ships. The config block's comment names
    # the sandbox host on purpose — that is the switching instruction — so the
    # guard tests the assigned VALUES, not any mention of the string.
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not set to production.")
    if "ORG_ID: 'dd1c6def-7b26-4d7d-86eb-fa3f915074a5'" not in working:
        fail("ORG_ID is not set to the production organisation.")
    for stray, why in [
        ("API_BASE: 'https://sandbox-api.polar.sh'", "a sandbox endpoint would ship"),
        ("19004685-5905-41a6-bd1f-acbd5b8abb6d", "the sandbox org id would ship"),
        ("NBLT-CFC46983", "a real issued key would ship"),
    ]:
        if stray in working:
            fail(f"{why} — found {stray!r}")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: production config only — no sandbox endpoint, org or key in the file")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_unlock_prefix_check.js")
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

    print("\n✅ the normaliser now rebuilds the shape the product actually issues.")


if __name__ == "__main__":
    main()
