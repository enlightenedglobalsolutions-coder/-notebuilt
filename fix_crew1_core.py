#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 1 of 5: component + storage
(th_nbp_stage4, spec docs/specs/notebuilt-pro-phase1-spec.md §8)
Run from the same folder as index.html:
    python3 fix_crew1_core.py

1. THE COMPONENT — platform/crew_task.js, pasted BYTE-IDENTICAL between its
   BEGIN/END marker lines, flush-left, in its own <script> ahead of the app's.
   It is read from the platform file at run time, never retyped, so the copy
   cannot drift on the way in; platform/check_crew_copies.sh proves it after.
   Nothing it owns is re-implemented here (spec §4).

2. STORAGE — a separate IndexedDB database, `notebuilt-crew`, store `crew`.
   NOT the `notebuilt` database at version 2, which is what spec §8 said.
   Proven on the live build (146341f / b4175c0) before this was written:
     * with `notebuilt` at v2, an older Notebuilt that runs afterwards (a
       stuck service-worker cache, a second tab) gets VersionError on every
       photo read and every photo save;
     * an older copy still open blocks the upgrade outright.
   A database of its own is never opened by an older build, so the photos
   database is never touched and comes through byte-identical by
   construction. Decided 2026-10-15.

3. ONE JUDGE — crewJudge(), for what is loaded and for what a backup
   carries. The stored list goes back through EGSCrew.validate (the path a
   received payload takes); the worker's own statuses go through it as a
   report. Each record carries its own schemaVersion (the Oct 14 rule); one
   above this build's is kept exactly as it is and never shown or merged.

Nothing here is visible yet. Backs up first, anchors asserted ==1,
node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
CANON = Path(__file__).resolve().parent.parent.parent / "platform" / "crew_task.js"
MARKER = "const CREW_DB='notebuilt-crew'"
BEGIN = "/* EGS-SHARED:crew-task BEGIN */"
END = "/* EGS-SHARED:crew-task END */"


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


STORAGE = r"""/* ---------- CREW — crew task lists, worker side (spec §8) ----------
   A boss using Notebuilt Pro sends each worker a private list as a link.
   Everything a list or report IS lives in the shared component above
   (EGSCrew); this file only stores, shows and sends.

   Its own database, never the photos one. Spec §8 put a `crew` store in
   `notebuilt` at version 2; tested on the live build, that locks every
   older copy out of its photos (VersionError on every read and save) the
   moment it runs after this one, and an older copy left open blocks the
   upgrade. `notebuilt-crew` is never opened by an older build, so the
   photos database is untouched. Decided 2026-10-15.

   EGS-STD:schema — every record carries its own schemaVersion, written in
   the same put as the record (EGS-DECISIONS 2026-10-14). One above
   CREW_SCHEMA came from a newer Notebuilt: kept exactly as it is, never
   shown, never merged, never written over.

   Record: { key, schemaVersion, listId, workerId, list, state, receivedAt,
             report:{ lastSentAt, send:null|{id,parts,ticked:[n…]} } }
   key = listId + workerId — both fixed-length ids, so the pair is
   unambiguous, and spec §4 says anything per worker is keyed by both. */
const CREW_DB='notebuilt-crew', CREW_STORE='crew', CREW_SCHEMA=1;
const CREW_SEND_RE=/^[A-Za-z0-9_-]{8}$/;
const CREW_MAX_PARTS=330;   /* the component's own ceiling: tasks + workers */
let _crewDb=null;
let crewRecs=[];            /* the judged records this build can show */
let crewLoaded=false, crewFromFuture=false, crewUnreadable=0;
function crewDb(){
  if(_crewDb) return Promise.resolve(_crewDb);
  return new Promise((res,rej)=>{
    let r;
    try{ r=indexedDB.open(CREW_DB,1); }catch(e){ rej(e); return; }
    r.onupgradeneeded=()=>{ const d=r.result; if(!d.objectStoreNames.contains(CREW_STORE)) d.createObjectStore(CREW_STORE,{keyPath:'key'}); };
    r.onsuccess=()=>{
      _crewDb=r.result;
      /* A later build asking for a newer version gets out of its way at once,
         instead of leaving it blocked behind this tab. */
      _crewDb.onversionchange=()=>{ try{ _crewDb.close(); }catch(e){} _crewDb=null; };
      res(_crewDb);
    };
    r.onerror=()=>rej(r.error);
    r.onblocked=()=>rej(new Error('Crew lists are held open by another copy of Notebuilt. Close it, then try again.'));
  });
}
async function crewAll(){
  const d=await crewDb();
  return new Promise((res,rej)=>{ const out=[]; const c=d.transaction(CREW_STORE,'readonly').objectStore(CREW_STORE).openCursor();
    c.onsuccess=e=>{ const cur=e.target.result; if(cur){ out.push(cur.value); cur.continue(); } else res(out); }; c.onerror=()=>rej(c.error); });
}
async function crewPut(rec){
  const d=await crewDb();
  return new Promise((res,rej)=>{ const t=d.transaction(CREW_STORE,'readwrite'); t.objectStore(CREW_STORE).put(rec); t.oncomplete=res; t.onerror=()=>rej(t.error); t.onabort=()=>rej(t.error); });
}
/* A restore: the whole store, in ONE transaction — every record lands or none
   does, so a failure leaves the store exactly as it was. */
async function crewReplaceAll(recs){
  const d=await crewDb();
  return new Promise((res,rej)=>{ const t=d.transaction(CREW_STORE,'readwrite'), s=t.objectStore(CREW_STORE);
    s.clear(); recs.forEach(r=>s.put(r)); t.oncomplete=res; t.onerror=()=>rej(t.error); t.onabort=()=>rej(t.error); });
}

/* THE ONE JUDGE of a stored crew record — for what is read from this phone
   and for what a backup carries. Returns {ok:true, rec} with a clean record
   (unknown keys dropped), {ok:true, future:true, rec} for a record from a
   newer build (kept exactly), or {ok:false, why}. The list goes back through
   EGSCrew.validate, the path a received link takes; the statuses go through
   it as a report. Nothing here re-implements a check the component owns. */
function crewJudge(rec){
  const no=why=>({ok:false, why});
  if(!rec || typeof rec!=='object' || Array.isArray(rec)) return no('not a record');
  if(nbSchemaOf(rec)>CREW_SCHEMA) return {ok:true, future:true, rec};
  const L=rec.list;
  if(!L || typeof L!=='object' || Array.isArray(L)) return no('no list');
  const probe=Object.assign({}, L, {sendId:'AAAAAAAA', part:1, parts:1}); delete probe.send;
  const v=EGSCrew.validate(probe,'list');
  if(!v.ok) return no('list: '+v.detail);
  const list=v.value; delete list.sendId; delete list.part; delete list.parts;
  if(list.mode!=='private') return no('not a private list');
  const wid=list.workers[0].id;
  if(rec.listId!==list.listId || rec.workerId!==wid || rec.key!==list.listId+wid) return no('key does not match its list');
  const int=(n,lo,hi)=>typeof n==='number' && Number.isInteger(n) && n>=lo && n<=hi;
  const parts=(o,field)=>{
    if(!o || typeof o!=='object' || !CREW_SEND_RE.test(o.id) || !int(o.parts,1,CREW_MAX_PARTS) || !Array.isArray(o[field])) return null;
    const ns=o[field];
    if(!ns.every(n=>int(n,1,o.parts)) || new Set(ns).size!==ns.length) return null;
    return {id:o.id, parts:o.parts, [field]:ns.slice().sort((a,b)=>a-b)};
  };
  if(L.send!=null){ const s=parts(L.send,'have'); if(!s) return no('bad send record'); list.send=s; }
  const st=rec.state;
  if(!st || typeof st!=='object' || Array.isArray(st)) return no('no state');
  const ids=new Set(list.tasks.map(t=>t.id));
  const tids=Object.keys(st);
  if(!tids.every(id=>ids.has(id))) return no('a status for a task not on the list');
  const rv=EGSCrew.validate({f:'egs-crew', v:EGSCrew.VERSION, k:'report', listId:list.listId, workerId:wid, sentAt:1500000000,
    sendId:'AAAAAAAA', part:1, parts:1,
    tasks:tids.map(id=>({id, status:st[id]&&st[id].status, note:st[id]&&st[id].note, changedAt:st[id]&&st[id].changedAt}))},'report');
  if(!rv.ok) return no('state: '+rv.detail);
  const state={};
  rv.value.tasks.forEach(t=>{ state[t.id]={status:t.status, note:t.note, changedAt:t.changedAt}; });
  if(!int(rec.receivedAt,0,4102444800)) return no('bad receivedAt');
  const R=rec.report;
  if(!R || typeof R!=='object' || !int(R.lastSentAt,0,4102444800)) return no('bad report record');
  let send=null;
  if(R.send!=null){ send=parts(R.send,'ticked'); if(!send) return no('bad report send'); }
  return {ok:true, rec:{key:rec.key, schemaVersion:CREW_SCHEMA, listId:list.listId, workerId:wid, list, state,
                        receivedAt:rec.receivedAt, report:{lastSentAt:R.lastSentAt, send}}};
}
/* A backup's crew section, judged whole: one bad record, or one key twice,
   refuses the lot (spec §6 rule 1 — no partial imports). */
function crewJudgeAll(arr){
  if(!Array.isArray(arr)) return {ok:false, why:'not a list of records'};
  const out=[], seen=new Set();
  for(const r of arr){
    const j=crewJudge(r);
    if(!j.ok) return j;
    if(seen.has(j.rec.key)) return {ok:false, why:'one list twice'};
    seen.add(j.rec.key); out.push(j.rec);
  }
  return {ok:true, recs:out};
}
/* Read at boot, in memory only — startup writes nothing. A record that does
   not pass is left on disk exactly as it is and kept off screen: it is the
   only evidence, and nothing here may write over it. */
let crewReady=null;
function crewLoad(){
  crewReady=crewAll().then(all=>{
    const ok=[];
    let future=false, bad=0;
    for(const r of all){
      const j=crewJudge(r);
      if(!j.ok){ bad++; console.warn('Notebuilt: a crew list did not pass its check and is left as it is —', j.why); continue; }
      if(j.future){ future=true; continue; }
      ok.push(j.rec);
    }
    crewRecs=ok; crewFromFuture=future; crewUnreadable=bad;
  }).catch(e=>{ console.warn('Notebuilt: crew lists could not be read',e); })
    .then(()=>{ crewLoaded=true; });
  return crewReady;
}
function crewByKey(key){ return crewRecs.find(r=>r.key===key)||null; }
/* Write one record, then hold it in memory — the memory copy only ever
   follows a write that landed. */
async function crewSave(rec){
  rec.schemaVersion=CREW_SCHEMA;
  await crewPut(rec);
  const i=crewRecs.findIndex(r=>r.key===rec.key);
  if(i<0) crewRecs.push(rec); else crewRecs[i]=rec;
}

"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    if not CANON.exists():
        fail(f"canonical component not found at {CANON}")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    canon = CANON.read_text(encoding="utf-8")
    if not (canon.startswith(BEGIN + "\n") and canon.endswith(END + "\n")):
        fail("the canonical file does not start/end with its marker lines.")
    if "EGS-SHARED:crew-task" in text:
        fail("index.html already mentions the crew-task markers, but not this chunk's code — stop and look.")

    edits = []
    old_tag = '<div id="toast"></div>\n\n<script>\n"use strict";\n'
    new_tag = '<div id="toast"></div>\n\n<script>\n' + canon + '</script>\n<script>\n"use strict";\n'
    edits.append((old_tag, new_tag, "component block ahead of the app script"))

    old_st = "/* downscale to <=1000px longest edge, JPEG ~0.8, return Blob */\n"
    new_st = STORAGE + old_st
    edits.append((old_st, new_st, "crew storage after the photo database"))

    old_boot = "navBoot();                                         /* NB_BACK_HASH — before the first render */\n"
    new_boot = ("crewLoad();                                        /* CREW — memory only; renders when it lands */\n"
                + old_boot)
    edits.append((old_boot, new_boot, "crew load at boot"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    lines = working.split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        fail("the marker lines are not each present exactly once, flush-left.")
    b, e = lines.index(BEGIN), lines.index(END)
    if "\n".join(lines[b:e + 1]) + "\n" != canon:
        fail("the pasted block is not byte-identical to platform/crew_task.js.")
    if "indexedDB.open('notebuilt',1)" not in working or "indexedDB.open('notebuilt',2)" in working:
        fail("the photos database open changed — it must stay exactly at version 1.")
    if working.count("indexedDB.open(") != 2:
        fail("expected exactly two database opens: photos (notebuilt v1) and crew (notebuilt-crew v1).")
    if "crewPut" in working[working.find("function crewLoad("):working.find("function crewByKey(")]:
        fail("crewLoad writes — startup must not write.")

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
    n = 1
    while bak.exists():          # never overwrite an earlier backup (same-second runs)
        n += 1
        bak = TARGET.with_name(f"{TARGET.name}.bak.{stamp}-{n}")
    shutil.copy2(TARGET, bak)
    TARGET.write_text(working, encoding="utf-8")
    print(f"✅ applied {len(edits)} edits. Backup: {bak}")


if __name__ == "__main__":
    main()
