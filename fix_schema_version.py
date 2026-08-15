#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a storage schema number that is WRITTEN and actually READ
Run from the same folder as index.html:
    python3 fix_schema_version.py

THE GAP (Aug 12 audit, EGS-STD:schema)
--------------------------------------
The live stored shape — notebuilt.settings, notebuilt.houses / tasks /
notes / categories, and the IndexedDB photo store — carries no version at
all. `load()` has no branch for an older shape and no branch for a newer
one. The EXPORT format is at version 3, but that is a different thing
entirely: it describes a .json file someone downloaded, not the data
sitting in localStorage on the phone.

The standard asks for a number written into the stored shape AND actually
read on load, with a migration path. A number written but never read is
not versioning — Rollworthy is the live cautionary example.

WHAT THIS ADDS
--------------
1. **NB_SCHEMA_VERSION = 2**, with absent meaning v1: the pre-schema shape
   every existing device is carrying right now.

2. **A ladder that is read at load.** `nbApplySchema()` runs the rungs
   between the stored version and this one, in order. It stamps nothing —
   startup does not write, and that law is not being bent for this.

3. **The stamp lands on an ordinary save.** `saveSettings()` writes the
   number, and `saveSettings()` is only ever reached from something a
   person did. A fresh install stamps on its first real persist; an
   existing install stamps on its next one. Until then "absent" is a
   well-defined answer, not a hole.

4. **Downgrade protection — the case that actually bites.** A stored
   number higher than this build understands means the data was written by
   a newer Notebuilt (a stale cached shell, a phone served an old build
   after updating). The rungs that would bring it forward do not exist
   here, so nothing is migrated, nothing is converted, and the newer
   number is carried through every subsequent write untouched — a save
   never lowers it. The person is told, in the same non-blocking way the
   unreadable-settings notice works: a toast, and a card in Settings that
   stays until the state does.

5. **A rung that is real, not a placeholder.** 1 → 2 is "every project
   carries a category". It models what the next one has to look like, and
   it is where the next shape change MUST register.

6. **The two version systems get named apart at every site they appear.**
   `d.version` (2 / 3) is the EXPORT FORMAT of a file. `schemaVersion` is
   the STORED SHAPE on a device. importData now climbs the ladder using
   the FILE's stored-shape number — which also closes a live gap: an
   export-version-2 backup restored today leaves its projects with no
   category until the next launch, because a restore assigns houses
   directly and never passes a load.

WHAT MUST NOT MOVE
------------------
The v1355 guards are asserted byte-true after the edit: the startup-write
law, the corrupt-settings self-heal, and the both-copies-unreadable
refusal. The unconditional category backfill stays exactly where it is —
the rung does not replace it, because the restore path never passes a load
and would lose it.

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

    # 1 — the number, the ladder, and the read ---------------------------
    old_load = """let settings = loadSettings();
if(!settings.sortHouses) settings.sortHouses='updated';
if(!settings.units) settings.units='imperial';"""
    new_load = """let settings = loadSettings();
if(!settings.sortHouses) settings.sortHouses='updated';
if(!settings.units) settings.units='imperial';

/* ---------- storage schema: a number written, and actually read ----------
   Two version systems live in this file, and confusing them is the whole
   risk, so they are named apart at every site they appear:

     * NB_SCHEMA_VERSION — the shape of what is IN localStorage on THIS
       device. Written into settings by an ordinary save, read here at
       load, climbed by the ladder below.
     * a backup file's `version` (2 or 3) — the shape of an EXPORTED .json.
       Read by backupManifest(). It describes the FILE, never the device.

   They are never compared and never assigned across. A number written but
   never read is not versioning, it is decoration; this one is read on the
   last line of this block and branched on. */
const NB_SCHEMA_VERSION = 2;

/* The ladder. The key is the version being migrated TO, and the function
   takes the stored shape from key-1 up to key, in place. A rung must be
   safe to run twice. Every future change to what this app writes into
   localStorage MUST add a rung here — that registration is the point of
   the object, not the machinery around it. */
const NB_MIGRATIONS = {
  /* 1 -> 2: every project carries a category. Projects made before
     categories existed have none and answer "Uncategorized". The
     unconditional backfill up at `let houses` still stands and is not
     replaced by this: a restore assigns houses directly and never passes
     a load, so removing it would strip the only pass those projects get.
     Which means on today's data this rung finds the work already done —
     it is here as the first real rung, and as the shape the next one
     copies, not as a placeholder. */
  2: function(){ houses.forEach(h=>{ if(!h.category) h.category='construction'; }); }
};

/* Absent means the pre-schema shape, v1 — what every device was carrying
   before this build. Anything that is not a sane number reads the same
   way: the conservative answer, never a guess upward. */
function nbSchemaOf(o){
  const v=o&&o.schemaVersion;
  return (typeof v==='number' && isFinite(v) && v>=1) ? Math.floor(v) : 1;
}

/* nbSchemaReached is what the stamp will write: the version the data is
   actually IN, not the one this build aspires to. A rung that throws
   leaves the shape half-done, and stamping that "current" would hide the
   damage from every load afterwards. */
let nbSchemaReached=1;
let schemaFromFuture=false;
function nbApplySchema(from){
  schemaFromFuture = from>NB_SCHEMA_VERSION;
  nbSchemaReached = from;
  /* Newer than this build understands. The rungs that would bring it
     forward do not exist here, so nothing is migrated and nothing is
     converted — the data is left exactly as the newer version left it,
     and its number is carried through untouched so that version still
     recognises its own shape when it comes back. */
  if(schemaFromFuture) return;
  for(let v=from+1; v<=NB_SCHEMA_VERSION; v++){
    try{ const rung=NB_MIGRATIONS[v]; if(rung) rung(); nbSchemaReached=v; }
    catch(e){ console.warn('Notebuilt: migration to schema v'+v+' did not complete',e); break; }
  }
}
/* Read at load. It migrates in memory only — nothing about startup may
   write, so the number waits for the next ordinary save to be stamped. */
nbApplySchema(nbSchemaOf(settings));"""
    edits.append((old_load, new_load, "NB_SCHEMA_VERSION + the ladder + the read"))

    # 2 — the stamp, on an ordinary save and nowhere else -----------------
    old_save = """  if(prev){
    if(settings.unlock===undefined && prev.unlock && prev.unlock.activationId) settings.unlock=prev.unlock;
    if(settings.vault===undefined  && prev.vault)  settings.vault =prev.vault;
  }
  save(K.settings,settings);"""
    new_save = """  if(prev){
    if(settings.unlock===undefined && prev.unlock && prev.unlock.activationId) settings.unlock=prev.unlock;
    if(settings.vault===undefined  && prev.vault)  settings.vault =prev.vault;
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
    edits.append((old_save, new_save, "saveSettings(): the stamp"))

    # 3 — say it, without blocking the app --------------------------------
    old_toast = """  setTimeout(()=>{ try{ toast('Saved settings could not be read \\u2014 see Settings'); }catch(e){} }, 1800);
}"""
    new_toast = """  setTimeout(()=>{ try{ toast('Saved settings could not be read \\u2014 see Settings'); }catch(e){} }, 1800);
}

/* The data was written by a newer Notebuilt than this one. Nothing was
   migrated and nothing was stamped down — but this build may not show
   everything the newer one stored, and that is not a thing to stay quiet
   about. Same shape of notice as above: a toast now, and a card in
   Settings that lasts as long as the state does. The two cannot both be
   true — unreadable settings carry no version to be from the future. */
if(schemaFromFuture){
  setTimeout(()=>{ try{ toast('This data is from a newer Notebuilt \\u2014 see Settings'); }catch(e){} }, 1800);
}"""
    edits.append((old_toast, new_toast, "the newer-data toast"))

    # 4 — the lasting surface, in Settings --------------------------------
    old_card = """    <div class="sec-head"><span class="label">Security</span><span class="rule"></span></div>"""
    new_card = """    ${schemaFromFuture?`<div class="card" style="border:1px solid var(--gold,#C89F47);margin-bottom:14px">
      <div style="font-weight:600;margin-bottom:6px">This data was saved by a newer Notebuilt</div>
      <div class="muted" style="font-size:13px;line-height:1.6">Your projects, notes, to-dos and photos are exactly as that version left them. Nothing has been converted and nothing has been dropped.<br><br>
      This copy of the app is older than the data it found, so it may not show everything the newer one stored, and edits made here may not carry back to it.<br><br>
      Close Notebuilt fully and open it twice to pick up the current version. If this message is still here after that, restore the most recent backup made by the version you were using.</div>
    </div>`:''}
    <div class="sec-head"><span class="label">Security</span><span class="rule"></span></div>"""
    edits.append((old_card, new_card, "renderSettings(): the newer-data card"))

    # 5 — a restore climbs the same ladder --------------------------------
    old_import = """    houses=d.houses||[]; tasks=d.tasks||[]; notes=d.notes||[];
    persist.houses(); persist.tasks(); persist.notes();"""
    new_import = """    houses=d.houses||[]; tasks=d.tasks||[]; notes=d.notes||[];
    /* SCHEMA — restored data climbs the same ladder a load would put it
       on, before any of it is written down. The number read is the FILE's
       STORED-SHAPE number, which travels inside its settings block; a file
       with no settings block predates the schema entirely and reads as v1.
       Do NOT read `d.version` here — that is the file's EXPORT FORMAT, a
       different system with its own numbering, and conflating the two is
       exactly the bug this comment exists to prevent. */
    nbApplySchema((d.settings && typeof d.settings==='object') ? nbSchemaOf(d.settings) : 1);
    persist.houses(); persist.tasks(); persist.notes();"""
    edits.append((old_import, new_import, "importData(): the restored shape climbs the ladder"))

    # 6 — name the two systems apart at the export site -------------------
    old_dump = """  const dump={ app:'notebuilt', version:3, exportedAt:now(), houses, tasks, notes, photos:photoData,"""
    new_dump = """  /* SCHEMA — `version:3` here is the EXPORT FORMAT of this file and nothing
     else. The device's stored-shape number rides inside `settings` below,
     as `schemaVersion`. Two systems, two jobs: this one tells a reader
     what the FILE holds, that one tells a load what shape the DEVICE is
     in. They are never compared. */
  const dump={ app:'notebuilt', version:3, exportedAt:now(), houses, tasks, notes, photos:photoData,"""
    edits.append((old_dump, new_dump, "export site: which version is which"))

    # 7 — and at the manifest site ----------------------------------------
    old_manifest = """    version:    d.version || 1,"""
    new_manifest = """    /* the FILE's export format (2 or 3), never the device's storage
       schemaVersion — that one travels inside d.settings. */
    version:    d.version || 1,"""
    edits.append((old_manifest, new_manifest, "manifest site: which version is which"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards: the new thing works ------------------------------------
    if "const NB_SCHEMA_VERSION = 2;" not in working:
        fail("the schema version constant is missing.")
    # written AND read — the whole point of the standard
    if working.count("nbApplySchema(") != 3:
        fail("expected nbApplySchema defined once and called twice (load + restore).")
    if "settings.schemaVersion=stamp;" not in working:
        fail("the stamp is missing from saveSettings().")
    if working.count("settings.schemaVersion=") != 1:
        fail("the schema number is stamped from more than one site.")
    if "if(schemaFromFuture) return;" not in working:
        fail("the downgrade-protection branch is missing.")
    if working.count("schemaFromFuture?") != 1:
        fail("the newer-data notice is not surfaced in Settings.")
    # the ladder must never write; startup does not persist
    ladder = working[working.find("const NB_MIGRATIONS = {"):working.find("function nbSchemaOf(")]
    if not ladder:
        fail("could not isolate the migration ladder for inspection.")
    for banned in ("persist.", "save(", "localStorage.setItem"):
        if banned in ladder:
            fail(f"a migration rung writes to storage ({banned!r}) — rungs migrate in memory only.")

    # ---- guards: v1355 must be byte-true --------------------------------
    body = working[working.find("let settings = loadSettings();"):working.find("const uid =")]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("unlockPriorProjects()") or s.startswith("persist.settings()") or s.startswith("saveSettings()"):
            fail(f"a settings write survives at startup: {s!r}")
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
    if "load(K.settings," in working:
        fail("the old silent-fallback settings load reappeared.")
    # the unconditional backfill must survive alongside the rung
    if working.count("houses.forEach(h=>{ if(!h.category) h.category='construction'; });") != 2:
        fail("expected the unconditional category backfill AND the v2 rung.")
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
    print("✅ guard: schema number is written (1 stamp site) and read (2 call sites)")
    print("✅ guard: migration rungs touch memory only, never storage")
    print("✅ guard: no settings write remains at startup")
    print("✅ guard: self-heal, backup-copy recovery and unreadable refusal intact")
    print("✅ guard: unconditional category backfill kept alongside the v2 rung")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_schema_check.js")
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

    print("\n✅ the stored shape now carries a version, and the load reads it.")


if __name__ == "__main__":
    main()
