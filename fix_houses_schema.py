#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — houses carry their own schema number (th_nb_houses_schema)
Run from the same folder as index.html:
    python3 fix_houses_schema.py

FOUND BY RUNNING THE LIVE BUILD, not by reading it (th_nb_schema_order)
-----------------------------------------------------------------------
146341f served in headless Chrome against v3-shaped storage:

  * `houses` is read, and every record missing `category` is filled in,
    at `let houses` — before settings, and so before any schema number,
    has been read at all.
  * That fill-in is written down by the next ordinary save of houses, so
    a newer build's record (one whose shape renamed `category`) gets a v2
    field put into it. The Settings card says "Nothing has been converted";
    after one edit, on disk, it has been.
  * With settings absent, there is no notice at all, and the first settings
    save stamps schemaVersion:2 over houses the build does not understand.

THE RULE IT BREAKS — EGS-DECISIONS, 2026-10-14
---------------------------------------------
A schema number governs only the data written in the same call as the
number. `settings` and `houses` are two writes; either lands without the
other. So `houses` gets a number of its own, inside its own setItem.

PER RECORD, NOT AN ENVELOPE — proven, not argued
-----------------------------------------------
`{schemaVersion, houses:[...]}` was served to the live build: it threw
`TypeError: houses.forEach is not a function` at boot and the app came up
blank. Every installed copy would do the same. A `schemaVersion` field on
each record is one the live build already carries through untouched (the
probe showed unknown fields surviving its saves).

THE FIX
-------
1. NB_HOUSES_SCHEMA = 2 and nbHouseUp(h): a record above it is left
   exactly as written — not filled in, not restamped. A record at or below
   it gets its category and its number. Safe to run twice.
2. The unconditional fill-in at `let houses` becomes nbHousesUp(), which
   also tells the app whether any record came from a newer build.
3. persist.houses runs it before every write — new projects and shared
   imports never reach storage without a number.
4. Restore runs it on the file's houses, keyed to each record, never to the
   file's settings block.
5. Rung 2 stops touching houses (the conversion moved to the records it
   changes). With it goes the only user of nbSchemaDirty and the
   flush-before-stamp block — the order the Oct 14 decision reverses.
   Nothing is written ahead of the stamp now; a settings rung changes
   settings only.
6. The newer-data notice fires for newer houses as well as newer settings.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "const NB_HOUSES_SCHEMA = 2;"


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return

    edits = []

    # 1+2 — the per-record number, read before the record is interpreted --
    old_load = """let houses = load(K.houses,[]);
houses.forEach(h=>{ if(!h.category) h.category='construction'; });
"""
    new_load = """/* ---------- houses carry their own schema number ----------
   EGS-STD:schema — the per-record half of row 11.

   A schema number governs only the data written in the same call as the
   number (EGS-DECISIONS, 2026-10-14). `settings` is a separate write from
   this key, so its number says nothing reliable about houses: either can
   land without the other. So every project carries its own
   `schemaVersion`, inside the very setItem that writes it, and the number
   is read off the record before anything about that record is touched.

   Per record, never an envelope round the array: an older Notebuilt runs
   houses.forEach on whatever this key holds, and an object there blanks
   the app at boot (proven on 146341f). A field on each record is one an
   older build already carries through its saves untouched.

   NB_HOUSES_SCHEMA is the shape of ONE PROJECT RECORD. It is not
   NB_SCHEMA_VERSION (the settings shape) and not a backup file's
   `version` (the export format). The three are never compared. */
const NB_HOUSES_SCHEMA = 2;
/* 1 -> 2: every project carries a category. A record above this build's
   number came from a newer Notebuilt and is left exactly as that version
   wrote it — not filled in, not restamped — because a field this build
   thinks is missing may be one the newer shape renamed. Returns true for
   such a record. Safe to run twice. */
function nbHouseUp(h){
  if(!h || typeof h!=='object') return false;
  if(nbSchemaOf(h)>NB_HOUSES_SCHEMA) return true;
  if(!h.category) h.category='construction';
  h.schemaVersion=NB_HOUSES_SCHEMA;
  return false;
}
/* Every way houses come in or go out runs this: load, restore, and
   persist.houses — the last covers new projects and shared imports, so no
   record reaches storage without its number. */
function nbHousesUp(){
  let future=false;
  houses.forEach(h=>{ if(nbHouseUp(h)) future=true; });
  return future;
}
let houses = load(K.houses,[]);
/* In memory only — nothing about startup may write. The numbers land on
   disk with the next ordinary save of houses, in the same write as the
   shape they describe. */
let housesFromFuture = nbHousesUp();
"""
    edits.append((old_load, new_load, "houses: per-record number before the fill-in"))

    # header — three version systems, not two -------------------------------
    old_hdr = """   Two version systems live in this file, and confusing them is the whole
   risk, so they are named apart at every site they appear:

     * NB_SCHEMA_VERSION — the shape of what is IN localStorage on THIS
       device. Written into settings by an ordinary save, read here at
       load, climbed by the ladder below.
     * a backup file's `version` (2 or 3) — the shape of an EXPORTED .json.
       Read by backupManifest(). It describes the FILE, never the device.
"""
    new_hdr = """   Three version systems live in this file, and confusing them is the
   whole risk, so they are named apart at every site they appear:

     * NB_SCHEMA_VERSION — the shape of `settings` on THIS device. Written
       into settings by an ordinary save, read here at load, climbed by
       the ladder below. It governs settings and nothing else: a number
       describes only what is written in the same call as it.
     * NB_HOUSES_SCHEMA — the shape of one project record. Each record
       carries its own, read at load by nbHouseUp() above.
     * a backup file's `version` (2 or 3) — the shape of an EXPORTED .json.
       Read by backupManifest(). It describes the FILE, never the device.
"""
    edits.append((old_hdr, new_hdr, "schema header names three systems"))

    # 5 — rung 2 leaves houses; the dirty set and its flush go -------------
    old_rungs = """/* The ladder. The key is the version being migrated TO, and the function
   takes the stored shape from key-1 up to key, in place. A rung must be
   safe to run twice. Every future change to what this app writes into
   localStorage MUST add a rung here — that registration is the point of
   the object, not the machinery around it. */
/* A rung runs in memory, because nothing about startup may write. So the
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
    new_rungs = """/* The ladder. The key is the version being migrated TO, and the function
   takes the settings shape from key-1 up to key, in place. A rung must be
   safe to run twice. A rung changes `settings` and NOTHING ELSE: this
   number is written with settings alone, so it cannot speak for any other
   key. A change to the shape of another key gives that key's records a
   number of their own, written with them — the way houses carry
   NB_HOUSES_SCHEMA — and the conversion is keyed to that. Every future
   change to the shape of settings MUST add a rung here. */
const NB_MIGRATIONS = {
  /* 1 -> 2: every project carries a category. That conversion used to run
     here, keyed to this number — a number written with `settings`, never
     with `houses`, and flushed ahead of the stamp to cover the gap. It now
     lives with the records it changes, in nbHouseUp(), keyed to each
     record's own number. The rung keeps its place so the ladder's
     numbering stays whole; there is nothing in settings for it to do. */
  2: function(){}
};"""
    edits.append((old_rungs, new_rungs, "rung 2 leaves houses; nbSchemaDirty removed"))

    old_flush = """  /* Whatever a rung changed in memory gets written down BEFORE the number
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
"""
    new_flush = """  /* Nothing is written ahead of the stamp. This save used to flush any
     store a rung had changed first, so the number would not outrun the
     data — but a number in settings never described another store in the
     first place (EGS-DECISIONS 2026-10-14, which reverses that order).
     Rungs now change settings only, so the number and everything it
     describes go down in this one write. */
"""
    edits.append((old_flush, new_flush, "saveSettings(): flush-before-stamp removed"))

    # 3 — every houses write carries the numbers ---------------------------
    old_persist = "const persist = { houses:()=>save(K.houses,houses), tasks:"
    new_persist = "const persist = { houses:()=>{ nbHousesUp(); save(K.houses,houses); }, tasks:"
    edits.append((old_persist, new_persist, "persist.houses stamps every record"))

    # 4 — restore keys houses to their own records -------------------------
    old_restore = """    nbApplySchema((d.settings && typeof d.settings==='object') ? nbSchemaOf(d.settings) : 1);
    persist.houses(); persist.tasks(); persist.notes();"""
    new_restore = """    nbApplySchema((d.settings && typeof d.settings==='object') ? nbSchemaOf(d.settings) : 1);
    /* Houses answer to their own records, never to the file's settings
       block: a record without a number predates it and is brought up; one
       from a newer build is left as it came. */
    housesFromFuture=nbHousesUp();
    persist.houses(); persist.tasks(); persist.notes();"""
    edits.append((old_restore, new_restore, "restore: houses keyed per record"))

    # 6 — the notice covers newer houses -----------------------------------
    old_toast = """   about. Same shape of notice as above: a toast now, and a card in
   Settings that lasts as long as the state does. The two cannot both be
   true — unreadable settings carry no version to be from the future. */
if(schemaFromFuture){"""
    new_toast = """   about. Same shape of notice as above: a toast now, and a card in
   Settings that lasts as long as the state does. Newer project records
   count as much as a newer settings number — they carry their own. With
   settings unreadable as well, the unreadable-settings toast above is the
   one shown, as the more urgent; both cards still appear in Settings. */
if((schemaFromFuture||housesFromFuture) && !settingsUnreadable){"""
    edits.append((old_toast, new_toast, "newer-data toast covers houses"))

    old_card = "${schemaFromFuture?`<div class=\"card\" style=\"border:1px solid var(--brass);margin-bottom:14px\">"
    new_card = "${(schemaFromFuture||housesFromFuture)?`<div class=\"card\" style=\"border:1px solid var(--brass);margin-bottom:14px\">"
    edits.append((old_card, new_card, "newer-data Settings card covers houses"))

    old_bk = """  /* SCHEMA — `version:3` here is the EXPORT FORMAT of this file and nothing
     else. The device's stored-shape number rides inside `settings` below,
     as `schemaVersion`. Two systems, two jobs: this one tells a reader
     what the FILE holds, that one tells a load what shape the DEVICE is
     in. They are never compared. */"""
    new_bk = """  /* SCHEMA — `version:3` here is the EXPORT FORMAT of this file and nothing
     else. The settings shape number rides inside `settings` below, and
     each project carries its own `schemaVersion` inside `houses`. This one
     tells a reader what the FILE holds, those tell a load what shape the
     data is in. They are never compared. */"""
    edits.append((old_bk, new_bk, "backup comment names the per-record number"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "nbSchemaDirty" in working:
        fail("nbSchemaDirty survives somewhere — the flush-before-stamp is not fully gone.")
    if "h.category='construction'" not in working[working.find("function nbHouseUp("):working.find("function nbHousesUp(")]:
        fail("the category fill-in is not inside nbHouseUp().")
    if working.count("h.category='construction'") != 1:
        fail("a category fill-in exists outside nbHouseUp() — it would run ungated.")
    if working.find(MARKER) > working.find("let houses = load(K.houses,[]);"):
        fail("NB_HOUSES_SCHEMA is declared after houses are read (TDZ).")
    if working.count("nbHousesUp()") != 4:  # def, load, persist, restore
        fail(f"expected nbHousesUp at definition + load + persist + restore, found {working.count('nbHousesUp()')}.")
    ladder = working[working.find("const NB_MIGRATIONS = {"):working.find("function nbSchemaOf(")]
    if "houses.forEach" in ladder or "persist." in ladder or "save(" in ladder:
        fail("a settings rung still touches houses or storage.")
    if "settings.schemaVersion=nbSchemaReached;" not in working:
        fail("the settings stamp is missing.")
    if "if(schemaFromFuture) return;" not in working:
        fail("the settings downgrade-protection branch is missing.")
    if working.count("EGS-STD:schema") < 2:
        fail("the EGS-STD:schema marker is missing from the new block.")

    # ---- syntax ---------------------------------------------------------
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", working, flags=re.S)
    with tempfile.TemporaryDirectory() as td:
        for i, s in enumerate(scripts):
            p = Path(td) / f"s{i}.js"
            p.write_text(s, encoding="utf-8")
            r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                fail(f"script block {i} fails node --check:\n{r.stderr}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_name(f"{TARGET.name}.bak.{stamp}")
    shutil.copy2(TARGET, bak)
    TARGET.write_text(working, encoding="utf-8")
    print(f"✅ applied {len(edits)} edits. Backup: {bak}")


if __name__ == "__main__":
    main()
