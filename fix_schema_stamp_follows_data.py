#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the schema stamp must never outrun the data it describes
Run from the same folder as index.html:
    python3 fix_schema_stamp_follows_data.py

FOUND BY THE GATE, not by reading
---------------------------------
Seeded a pre-schema install (no schemaVersion, one project from before
categories existed), loaded it, tapped one real control. Result:

    notebuilt.settings  ->  schemaVersion: 2
    notebuilt.houses    ->  [ {no category}, {category:'apps'} ]

The number says the stored shape is v2. The stored shape is v1.

The cause is structural, not a typo. A rung migrates IN MEMORY, because
nothing about startup may write — that law is not negotiable and is not
being bent. But the stamp lands on the next ordinary save, and that save
only writes `settings`. So the number advances while the store the rung
actually changed is still sitting on disk in its old shape. Next load
reads v2, skips the rung, and the data never gets migrated again.

Rung 2 happens to survive this, because the unconditional category
backfill at `let houses` still runs on every load and does the same work.
That is luck, and it is exactly the kind of luck that makes a ladder look
fine right up until the rung that matters is added. A ladder whose rungs
can be permanently skipped is not a migration path.

THE FIX
-------
A rung that changes something says so, by naming the store it touched.
The same ordinary save that stamps the number writes those stores down
first — still not at startup, still on a person's action, but now the
number and the shape it describes land together, in that order.

If that write fails, the stamp is held back and the save returns without
writing settings at all. A number claiming v2 over data still shaped v1
is worse than no number: it turns a retryable failure into a rung that is
skipped forever. Nothing is lost by waiting for the next save.

`settings` can never be in the dirty set — persist.settings IS this
function, and the loop would recurse. Asserted below, and skipped in the
loop as well as asserted, because one of those is a test and the other is
the behaviour.

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

    # 1 — a rung declares what it changed -------------------------------
    old_rungs = """const NB_MIGRATIONS = {
  /* 1 -> 2: every project carries a category. Projects made before
     categories existed have none and answer "Uncategorized". The
     unconditional backfill up at `let houses` still stands and is not
     replaced by this: a restore assigns houses directly and never passes
     a load, so removing it would strip the only pass those projects get.
     Which means on today's data this rung finds the work already done —
     it is here as the first real rung, and as the shape the next one
     copies, not as a placeholder. */
  2: function(){ houses.forEach(h=>{ if(!h.category) h.category='construction'; }); }
};"""
    new_rungs = """/* A rung runs in memory, because nothing about startup may write. So the
   store it changed has to be written down by the same ordinary save that
   stamps the number, or the number goes out describing a shape that is
   not on disk yet — and the rung, now skipped, never gets another chance.
   A rung that changed something names its store here. `settings` must
   never be named: persist.settings IS the save doing the flushing. */
const nbSchemaDirty=new Set();

const NB_MIGRATIONS = {
  /* 1 -> 2: every project carries a category. Projects made before
     categories existed have none and answer "Uncategorized". The
     unconditional backfill up at `let houses` still stands and is not
     replaced by this: a restore assigns houses directly and never passes
     a load, so removing it would strip the only pass those projects get.
     Which means on today's data this rung finds the work already done —
     it is here as the first real rung, and as the shape the next one
     copies, not as a placeholder. */
  2: function(){
    let changed=0;
    houses.forEach(h=>{ if(!h.category){ h.category='construction'; changed++; } });
    if(changed) nbSchemaDirty.add('houses');
  }
};"""
    edits.append((old_rungs, new_rungs, "rungs declare the store they changed"))

    # 2 — the stamp follows the data, never leads it ---------------------
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
    new_stamp = """  /* Whatever a rung changed in memory gets written down BEFORE the number
     that describes it — the stamp follows the data, it never leads it. If
     one of these writes fails, the stamp is held back and this save does
     nothing at all: a number claiming v2 over data still shaped v1 turns a
     retryable failure into a rung skipped forever, which is the one
     outcome worth losing a save to avoid. */
  if(nbSchemaDirty.size){
    try{ for(const name of nbSchemaDirty){ if(name!=='settings' && persist[name]) persist[name](); } }
    catch(e){ console.warn('Notebuilt: migrated data would not persist — the schema number is held back',e); return; }
    nbSchemaDirty.clear();
  }
  /* THE STAMP — here and nowhere else. This function is only ever reached
     from something a person did, which is what keeps the number out of
     startup without needing a guard of its own. A save never LOWERS the
     number: if storage already holds a higher one, another tab or a newer
     build put it there since this one loaded, and their reading of the
     shape beats ours. */
  const stamp=(prev && typeof prev.schemaVersion==='number' && prev.schemaVersion>nbSchemaReached)
    ? prev.schemaVersion : nbSchemaReached;
  settings.schemaVersion=stamp;
  save(K.settings,settings);"""
    edits.append((old_stamp, new_stamp, "saveSettings(): flush migrated stores before stamping"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "const nbSchemaDirty=new Set();" not in working:
        fail("the dirty-store set is missing.")
    if "nbSchemaDirty.add('settings')" in working:
        fail("a rung marks 'settings' dirty — persist.settings is the flusher and would recurse.")
    if "if(name!=='settings' && persist[name]) persist[name]();" not in working:
        fail("the flush does not skip 'settings'.")
    if working.count("nbSchemaDirty.clear();") != 1:
        fail("the dirty set must be cleared exactly once, after a successful flush.")
    # the flush must sit ABOVE the stamp, or it is pointless
    if working.find("nbSchemaDirty.clear();") > working.find("settings.schemaVersion=stamp;"):
        fail("the flush runs after the stamp — the stamp would still outrun the data.")
    # the ladder still must not write directly at load
    ladder = working[working.find("const NB_MIGRATIONS = {"):working.find("function nbSchemaOf(")]
    for banned in ("persist.", "save(", "localStorage.setItem"):
        if banned in ladder:
            fail(f"a migration rung writes to storage ({banned!r}) — rungs migrate in memory only.")

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
    print("✅ guard: migrated stores are flushed BEFORE the number is stamped")
    print("✅ guard: a failed flush holds the stamp back")
    print("✅ guard: 'settings' can never be in the dirty set")
    print("✅ guard: rungs still touch memory only; startup still writes nothing")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_schema_stamp_check.js")
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

    print("\n✅ the number can no longer describe a shape that is not on disk.")


if __name__ == "__main__":
    main()
