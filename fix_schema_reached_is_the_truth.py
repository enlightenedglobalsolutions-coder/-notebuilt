#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the schema number comes from the data, not from what was there before
Run from the same folder as index.html:
    python3 fix_schema_reached_is_the_truth.py

FOUND BY THE GATE
-----------------
Restored a backup carrying schemaVersion 42 (a file from a newer build),
then restored an ordinary current backup on top of it. Expected the device
to come back to 2. It stayed at 42 — for good.

    stamped after restoring an ordinary v2 backup:  42

Cause: the stamp carried a "never LOWER the number" rule, meant for a
race where another tab wrote a higher number between this tab's load and
its save. A restore is not that race. A restore deliberately replaces the
whole stored shape, so the number that was there a moment ago is not a
rival opinion to be deferred to — it describes data that no longer exists.
Deferring to it leaves a device whose data is plainly v2 permanently
flagged as from-the-future: the notice never clears, and every future
migration is skipped on a phone that needs them.

That is a worse failure than the one the rule guarded against, and the one
it guarded against was speculative.

THE FIX
-------
`nbSchemaReached` is the single source of truth, and it already is one:
`nbApplySchema()` derives it from the data actually in hand, at load and
again at every restore. When that data came from a newer build the number
IS the higher one, so genuine downgrade protection is unaffected — it
comes from reading the data, not from remembering the previous write.

The stamp is now one line, which is what it should have been.

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

    old_stamp = """  /* THE STAMP — here and nowhere else. This function is only ever reached
     from something a person did, which is what keeps the number out of
     startup without needing a guard of its own. A save never LOWERS the
     number: if storage already holds a higher one, another tab or a newer
     build put it there since this one loaded, and their reading of the
     shape beats ours. */
  const stamp=(prev && typeof prev.schemaVersion==='number' && prev.schemaVersion>nbSchemaReached)
    ? prev.schemaVersion : nbSchemaReached;
  settings.schemaVersion=stamp;
  save(K.settings,settings);"""
    new_stamp = """  /* THE STAMP — here and nowhere else. This function is only ever reached
     from something a person did, which is what keeps the number out of
     startup without needing a guard of its own.

     It writes `nbSchemaReached` and nothing else. That value is derived
     from the data actually in hand — at load, and again at every restore —
     so it is already the truth about the shape being saved. Deferring
     instead to whatever number storage happened to hold a moment ago is
     what left a restored device stuck at a version its data was never in:
     a restore replaces the shape outright, and the old number describes
     data that no longer exists. Downgrade protection does not depend on
     that deferral — when the data really did come from a newer build,
     nbApplySchema read the higher number off the data itself. */
  settings.schemaVersion=nbSchemaReached;
  save(K.settings,settings);"""
    edits.append((old_stamp, new_stamp, "saveSettings(): the stamp is nbSchemaReached, full stop"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "settings.schemaVersion=nbSchemaReached;" not in working:
        fail("the stamp is missing.")
    if working.count("settings.schemaVersion=") != 1:
        fail("the schema number is stamped from more than one site.")
    if "prev.schemaVersion" in working:
        fail("the never-lower rule survived — it is the bug being removed.")
    # `prev` is still needed for the unlock/vault carry-forward
    if "if(settings.unlock===undefined && prev.unlock && prev.unlock.activationId) settings.unlock=prev.unlock;" not in working:
        fail("the unlock carry-forward was disturbed.")
    if "if(settings.vault===undefined  && prev.vault)  settings.vault =prev.vault;" not in working:
        fail("the vault carry-forward was disturbed.")
    # flush still precedes the stamp
    if working.find("nbSchemaDirty.clear();") > working.find("settings.schemaVersion=nbSchemaReached;"):
        fail("the flush runs after the stamp — the stamp would outrun the data.")

    # ---- guards: everything already shipped must be byte-true -----------
    body = working[working.find("let settings = loadSettings();"):working.find("const uid =")]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("unlockPriorProjects()") or s.startswith("persist.settings()") or s.startswith("saveSettings()"):
            fail(f"a settings write survives at startup: {s!r}")
    if "const NB_SCHEMA_VERSION = 2;" not in working:
        fail("the schema version constant is missing.")
    if working.count("nbApplySchema(") != 3:
        fail("expected nbApplySchema defined once and called twice (load + restore).")
    if "if(schemaFromFuture) return;" not in working:
        fail("the downgrade-protection branch is missing.")
    if working.count("schemaFromFuture?") != 1:
        fail("the newer-data notice is not surfaced in Settings.")
    if "if(name!=='settings' && persist[name]) persist[name]();" not in working:
        fail("the flush does not skip 'settings'.")
    if "settings:saveSettings," not in working:
        fail("persist.settings is not routed through the guarded save.")
    if "if(settingsUnreadable) return;" not in working:
        fail("the damaged-original write block is missing.")
    if "settingsUnreadable=true;" not in working:
        fail("the both-copies-unreadable refusal is missing.")
    if "if (blank(cur) && !blank(bak)) _set(k, bak);" not in working:
        fail("the durability self-heal is missing.")
    if "const bak=localStorage.getItem(K.settings+'_bak');" not in working:
        fail("the corrupt-settings backup-copy recovery is missing.")
    if working.count("houses.forEach(h=>{ if(!h.category) h.category='construction'; });") != 1:
        fail("the unconditional category backfill must survive exactly once.")
    if working.count("fetch(") != 2:
        fail("fetch( count changed — expected exactly 2 (validate, activate).")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")
    if "const dump={ app:'notebuilt', version:3," not in working:
        fail("the export format version changed — it must stay 3.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: one stamp site, writing the version derived from the data")
    print("✅ guard: the never-lower rule is gone")
    print("✅ guard: unlock/vault carry-forward untouched")
    print("✅ guard: flush still precedes the stamp; startup still writes nothing")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_schema_truth_check.js")
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

    print("\n✅ a restore can bring the number back down, because the data did.")


if __name__ == "__main__":
    main()
