#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 2 of 5: arrival
(th_nbp_stage4, spec §8 Entry, §6 rules 1, 5, 7, 11)
Run from the same folder as index.html, after fix_crew1_core.py:
    python3 fix_crew2_entry.py

1. THE LINK LEAVES THE ADDRESS FIRST. Before navBoot() — so before the
   router sees it, and before anything renders — a `#crew=` hash is taken
   into memory and the entry is replaced with `#/crew`. Back, reload and
   restore can never re-import it, and the payload does not linger in
   history (rule 5). Read the live router before writing this: navBoot()
   sends any hash it does not know to To Do, so it would otherwise have
   silently dropped the list.
2. SAME-DOCUMENT ARRIVAL — a link opened in a tab that already has the app
   is a hashchange, not a load. It reloads, which is the cold path above.
3. THE PIN COMES FIRST. crewOnShell() runs at each of the three places the
   shell is revealed (no PIN; PIN accepted; new PIN set after recovery), so
   nothing about the list is decoded or drawn behind the keypad.
4. PREVIEW, THEN ADD. Decoded by the component (untrusted input, rule 1),
   refused whole with its own plain sentence. The preview says who it is
   from, the job, the day and how many are yours, and which parts are still
   missing (rule 11). Add merges under the component's rules — check-offs
   and notes are never overwritten — and lands on that list.
5. A whole-crew list is refused: Pro sends private links only (spec §2),
   and on the worker side a crew list would have to ask who you are.
6. The cap stays out of it (rule 7): nothing here touches projects.

Backs up first, anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "function crewOnShell("


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


ENTRY = r"""/* CREW — a list link arrives as https://notebuilt.ca/#crew=<payload>.
   Taken out of the address HERE, before navBoot() reads the hash and before
   anything renders: the entry becomes #/crew, so back, reload and restore
   can never import it again and the payload does not sit in history
   (spec §6 rule 5). What arrived is held in memory until the shell is
   showing — past the PIN, if there is one. What follows #crew= is kept
   exactly as it came and handed to EGSCrew.decode(), the one validator:
   it is what tells a damaged link from one made by a NEWER app (which
   must say "update the app", not "damaged"). A pre-filter here would
   blur the two. */
let crewArrival=null;
(function crewTakeHash(){
  const h=location.hash;
  if(typeof h!=='string' || h.indexOf('#crew=')!==0) return;
  crewArrival={ payload:h.slice('#crew='.length) };
  try{ history.replaceState(null,'',location.pathname+location.search+'#/crew'); }catch(e){}
})();
/* Opened in a tab that already has the app: the browser changes the hash
   without loading. Reload, and the path above takes it. */
window.addEventListener('hashchange',()=>{ if(location.hash.indexOf('#crew=')===0) location.reload(); });
"""

SHELL = r"""
/* ---------- CREW — arrival: preview, then add ---------- */
async function crewGet(key){
  const d=await crewDb();
  return new Promise((res,rej)=>{ const r=d.transaction(CREW_STORE,'readonly').objectStore(CREW_STORE).get(key); r.onsuccess=()=>res(r.result||null); r.onerror=()=>rej(r.error); });
}
/* "Mon, Sep 28" — the list's own day, read as a calendar date, never as a
   moment in time, so no timezone can move it. */
function crewDayLabel(day){
  const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(day||''); if(!m) return day||'';
  return new Date(+m[1],+m[2]-1,+m[3]).toLocaleDateString(undefined,{weekday:'short',month:'short',day:'numeric'});
}
/* Rule 11: a list missing parts never looks complete. null when it is. */
function crewPartsLine(send){
  const ps=EGSCrew.partsStatus(send);
  if(ps.complete) return null;
  const and=a=>a.length<2?String(a[0]):a.slice(0,-1).join(', ')+' and '+a[a.length-1];
  return (ps.have.length===1?'part ':'parts ')+and(ps.have)+' of '+ps.parts
    +', waiting on '+(ps.missing.length===1?'part ':'parts ')+and(ps.missing);
}
function crewRefuse(reason){
  sheet(`<h2>Couldn’t open this list</h2>
    <div class="muted" style="font-size:14px;line-height:1.6;margin-bottom:14px">${esc(reason)}</div>
    <div class="muted" style="font-size:12.5px;line-height:1.55;margin-bottom:14px">Nothing on this phone was changed.</div>
    <button class="btn primary block" data-crew-ok>OK</button>`,'crew');
  $mr.querySelector('[data-crew-ok]').onclick=closeSheet;
}
const CREW_NEWER_HERE='This list was saved by a newer Notebuilt, or can’t be read here, so I left it alone. Close Notebuilt fully and open it twice to update, then open the link again.';
/* Called wherever the shell is revealed. Does nothing unless a link came in. */
async function crewOnShell(){
  if(!crewArrival) return;
  const a=crewArrival; crewArrival=null;
  if(crewReady) await crewReady;
  if(!a.payload){ crewRefuse(EGSCrew.REASONS.damaged); return; }
  const d=await EGSCrew.decode(a.payload,'list');
  if(!d.ok){ crewRefuse(d.reason); return; }
  const inc=d.value;
  if(inc.mode!=='private'){ crewRefuse('This is a whole-crew list. Ask for your own link, the one with just your tasks.'); return; }
  const wid=inc.workers[0].id, key=inc.listId+wid;
  let raw=null;
  try{ raw=await crewGet(key); }catch(e){ crewRefuse('I couldn’t read the crew lists on this phone, so I didn’t add this one. Try again.'); return; }
  const cur=crewByKey(key);
  if(raw && !cur){ crewRefuse(CREW_NEWER_HERE); return; }
  const m=EGSCrew.mergeList(cur?cur.list:null, inc);
  if(!m.ok){ crewRefuse(m.reason); return; }
  if(cur && !m.changed){ go('crewlist',key); toast('You already have this — nothing changed'); return; }
  const mine=EGSCrew.liveTasksFor(m.list,wid).length;
  const partsLine=crewPartsLine(m.list.send);
  sheet(`<h2>${cur?'Update to your crew list':'Crew list'}</h2>
    <div class="card" style="font-size:15px;line-height:1.55;margin-bottom:10px">Tasks from <b>${esc(inc.boss.name)}</b> · ${esc(inc.job.name)} · ${esc(crewDayLabel(inc.day))} · ${mine} for you</div>
    ${partsLine?`<div class="card" data-crew-parts style="border:1px solid var(--brass);font-size:13.5px;margin-bottom:10px">${esc(partsLine)}</div>`:''}
    ${cur?'<div class="muted" style="font-size:13px;line-height:1.55;margin-bottom:10px">This adds to the list you already have. What you’ve checked off and your notes stay as they are.</div>':''}
    <div class="muted" style="font-size:12.5px;line-height:1.55;margin-bottom:14px">Open crew links in Chrome, where your Notebuilt lives. Another browser keeps its own separate copy, and the list would land there instead.</div>
    <button class="btn primary block" data-crew-add>${cur?'Update':'Add'}</button>
    <button class="btn block" data-crew-cancel style="margin-top:8px">Cancel</button>`,'crew');
  $mr.querySelector('[data-crew-cancel]').onclick=closeSheet;
  $mr.querySelector('[data-crew-add]').onclick=async()=>{
    /* Merge again against what is stored NOW — another tab may have added a
       part since the preview was drawn. */
    const now=Math.floor(Date.now()/1000);
    let raw2=null; try{ raw2=await crewGet(key); }catch(e){}
    const cur2=crewByKey(key);
    if(raw2 && !cur2){ crewRefuse(CREW_NEWER_HERE); return; }
    const m2=EGSCrew.mergeList(cur2?cur2.list:null, inc);
    if(!m2.ok){ crewRefuse(m2.reason); return; }
    const rec=cur2 ? Object.assign({}, cur2, {list:m2.list, receivedAt:now})
                   : {key, schemaVersion:CREW_SCHEMA, listId:inc.listId, workerId:wid, list:m2.list, state:{}, receivedAt:now, report:{lastSentAt:0, send:null}};
    try{ await crewSave(rec); }
    catch(e){ crewRefuse('I couldn’t save this list on this phone ('+((e&&e.name)||'the write failed')+'). Nothing was changed.'); return; }
    closeSheet(); go('crewlist',key); toast(cur2?'List updated':'List added');
  };
}
"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "const CREW_DB='notebuilt-crew'" not in text:
        fail("chunk 1 (fix_crew1_core.py) has not been applied.")

    edits = []
    old_boot = "crewLoad();                                        /* CREW — memory only; renders when it lands */\n"
    edits.append((old_boot, ENTRY + old_boot, "take the hash before navBoot"))

    old_after = "function crewByKey(key){ return crewRecs.find(r=>r.key===key)||null; }\n"
    edits.append((old_after, old_after + SHELL, "arrival functions after crewByKey"))

    old_nopin = "  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); return; }"
    new_nopin = "  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); crewOnShell(); return; }"
    edits.append((old_nopin, new_nopin, "no-PIN shell reveal"))

    old_pin = "      if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); maybeOfferRecoveryCode(); }"
    new_pin = "      if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); maybeOfferRecoveryCode(); crewOnShell(); }"
    edits.append((old_pin, new_pin, "PIN accepted shell reveal"))

    old_rec = "  const done=()=>{ $lock.classList.add('hidden'); $lock.innerHTML=''; showShell(true); render(); toast('New PIN set'); };"
    new_rec = "  const done=()=>{ $lock.classList.add('hidden'); $lock.innerHTML=''; showShell(true); render(); toast('New PIN set'); crewOnShell(); };"
    edits.append((old_rec, new_rec, "PIN recovery shell reveal"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("showShell(true)") != working.count("crewOnShell();"):
        fail("a place that reveals the shell does not call crewOnShell() — an import could be lost or skip the PIN.")
    take = working.find("(function crewTakeHash(){")
    if take < 0 or take > working.find("navBoot();                                         /* NB_BACK_HASH"):
        fail("the hash is not taken before navBoot().")

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
