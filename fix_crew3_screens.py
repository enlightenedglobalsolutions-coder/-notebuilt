#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 3 of 5: screens
(th_nbp_stage4, spec §8 Screens, §6 rule 11)
Run from the same folder as index.html, after chunks 1 and 2:
    python3 fix_crew3_screens.py

1. A Crew tasks card at the top of the To Do landing for today's lists —
   "From Mike · Oak St reno · 3 of 10 done · 1 waiting" — and a way to the
   older ones. No card at all when there are no crew lists.
2. Two views in the router: `crew` (every list, newest day first) and
   `crewlist/<listId+workerId>`. They live under the To Do tab. A crew list
   id is only accepted if it is on this phone (or crew lists are still
   loading, in which case the screen says so and redraws when they land).
3. The list: a missing-parts banner until every part is in (rule 11); one
   tap on the round mark toggles Done; tapping the row opens Open / Done /
   Waiting on, quick-pick reasons and a note. Cancelled and moved tasks stay
   visible, struck through, with what happened. When the last report went
   out, and how many changes have not been sent.
4. The note sheet is drawn once and never redrawn while it is open: quick
   picks and the status buttons change the nodes in place, so the keyboard
   stays up while typing (the Aug 12 lesson — node identity, not geometry).

Statuses go through EGSCrew.setStatus (the component's one writer for the
worker's fields). The memory copy only changes after the write lands.

Backs up first, anchors asserted, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "function renderCrewList("


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


CSS = """  /* ---- CREW — crew task lists from Notebuilt Pro (worker side) ---- */
  .crew-card{display:block;width:100%;text-align:left;color:inherit;font:inherit}
  .crew-meta{font-size:13px;color:var(--paper-dim);margin-top:3px}
  .punch.waiting{border-color:var(--doing);color:var(--doing)}
  .task.crew-gone .ttext{color:var(--paper-faint);text-decoration:line-through}
  .crew-note{font-size:13px;color:var(--doing);margin-top:3px;white-space:pre-wrap;overflow-wrap:anywhere}
  .crew-parts{border:1px solid var(--brass);font-size:13.5px}
  .crew-send{position:fixed;left:16px;right:16px;z-index:30;max-width:648px;margin:0 auto;
    bottom:calc(var(--tap) + var(--safe-b) + 18px);box-shadow:var(--shadow-pop)}
  .crew-seg{display:flex;gap:8px;margin:12px 0}
  .crew-seg .btn{flex:1;min-width:0;padding-left:6px;padding-right:6px}
  .crew-quick{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}

"""

SCREENS = r"""
/* ---------- CREW — screens ---------- */
const CREW_STATUS_LABEL={open:'Open', done:'Done', waiting:'Waiting on'};
const CREW_QUICK=['Electrician','Plumber','Materials','Inspection','Boss'];
const CREW_KEY_RE=/^[A-Za-z0-9_-]{22}$/;
/* Today as the list format writes a day: the phone's own calendar date. */
function crewToday(){
  const d=new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
function crewStatusOf(rec,tid){ const s=rec.state[tid]; return s?s.status:'open'; }
function crewCounts(rec){
  const c={total:0,done:0,waiting:0,open:0};
  EGSCrew.liveTasksFor(rec.list,rec.workerId).forEach(t=>{ c.total++; c[crewStatusOf(rec,t.id)]++; });
  return c;
}
/* Every report is a full snapshot, so this is simply what has moved since the
   last one went out. */
function crewUnsent(rec){
  const at=rec.report.lastSentAt;
  return EGSCrew.liveTasksFor(rec.list,rec.workerId).filter(t=>{ const s=rec.state[t.id]; return s && s.changedAt>at; }).length;
}
function crewSummary(rec){
  const c=crewCounts(rec);
  return c.done+' of '+c.total+' done'+(c.waiting?' · '+c.waiting+' waiting':'');
}
function crewSorted(){
  return crewRecs.slice().sort((a,b)=> b.list.day<a.list.day?-1 : b.list.day>a.list.day?1
    : (b.receivedAt-a.receivedAt) || (a.key<b.key?-1:a.key>b.key?1:0));
}
function crewWhen(sec){
  const d=new Date(sec*1000), t=d.toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'});
  return d.toDateString()===new Date().toDateString() ? t : d.toLocaleDateString(undefined,{month:'short',day:'numeric'})+', '+t;
}
function crewRowHtml(r){
  const pl=crewPartsLine(r.list.send);
  return `<button class="card crew-card" data-crew-open="${esc(r.key)}">
      <div class="truncate">From <b>${esc(r.list.boss.name)}</b> · ${esc(r.list.job.name)}</div>
      <div class="crew-meta">${esc(crewDayLabel(r.list.day))} · ${esc(crewSummary(r))}</div>
      ${pl?`<div class="crew-meta" style="color:var(--brass)">${esc(pl)}</div>`:''}
    </button>`;
}
/* The To Do landing's card. Nothing at all until there is a crew list. */
function crewCardHtml(){
  if(!crewRecs.length) return '';
  const today=crewToday(), todays=crewSorted().filter(r=>r.list.day===today), older=crewRecs.length-todays.length;
  return `<div class="wrap"><div class="sec-head"><span class="label">Crew tasks</span>${nbHelpMark('crew')}<span class="rule"></span></div>
    ${todays.map(crewRowHtml).join('')}
    ${older?`<button class="btn block sm" data-go="crew">${todays.length?'Older crew lists':'Crew lists'} (${older})</button>`:''}</div>`;
}
function crewTop(eyebrow,title,help){
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${esc(eyebrow)}</span><h1 class="truncate">${esc(title)}${help?' '+nbHelpMark(help):''}</h1></div>
  </div>`;
}
function crewUnreadableHtml(){
  if(!crewUnreadable && !crewFromFuture) return '';
  const n=crewUnreadable;
  return `<div class="card muted" style="font-size:13px;line-height:1.55">${n?n+' crew list'+(n===1?'':'s')+' on this phone couldn’t be read here, so '+(n===1?'it is':'they are')+' left exactly as '+(n===1?'it is':'they are')+'. ':''}${crewFromFuture?'Some crew lists were saved by a newer Notebuilt and are not shown. Close Notebuilt fully and open it twice to update.':''}</div>`;
}
function renderCrew(){
  const head=crewTop('From your boss','Crew lists','crew');
  if(!crewLoaded) return head+'<div class="wrap muted">Loading…</div>';
  if(!crewRecs.length) return head+`<div class="wrap">${crewUnreadableHtml()}</div><div class="empty">${I.today}<div class="t">No crew lists yet</div><div>When your boss sends you a list from Notebuilt Pro, tap the link in the text and it lands here.</div></div>`;
  let out='', day=null;
  crewSorted().forEach(r=>{
    if(r.list.day!==day){ day=r.list.day; out+=`<div class="sec-head"><span class="label">${esc(crewDayLabel(day))}</span><span class="rule"></span></div>`; }
    out+=crewRowHtml(r);
  });
  return head+`<div class="wrap">${crewUnreadableHtml()}${out}</div>`;
}
function renderCrewList(key){
  if(!crewLoaded) return crewTop('Crew list','Loading…')+'';
  const rec=crewByKey(key);
  if(!rec) return crewTop('Crew list','Not on this phone')+`<div class="wrap"><div class="card muted" style="font-size:14px">This list isn’t on this phone.</div><button class="btn block" data-go="crew">All crew lists</button></div>`;
  const L=rec.list, wid=rec.workerId;
  const mine=L.tasks.filter(t=>t.worker===wid), live=mine.filter(t=>!t.gone), gone=mine.filter(t=>t.gone);
  const pl=crewPartsLine(L.send), unsent=crewUnsent(rec);
  const row=t=>{
    const s=rec.state[t.id]||{status:'open',note:''}, st=s.status;
    return `<div class="card task ${st==='done'?'is-done':''}" style="margin-bottom:8px">
      <button class="punch ${st}" data-crew-punch="${esc(t.id)}" aria-label="${esc(CREW_STATUS_LABEL[st])} — tap to mark ${st==='done'?'open':'done'}">${st==='done'?I.check:st==='waiting'?I.dot:''}</button>
      <div class="body" data-crew-task="${esc(t.id)}">
        <div class="ttext">${esc(t.text)}</div>
        <div class="meta"><span>${esc(CREW_STATUS_LABEL[st])}</span></div>
        ${s.note?`<div class="crew-note">${esc(s.note)}</div>`:''}
      </div>
    </div>`;
  };
  const goneRow=t=>`<div class="card task crew-gone" style="margin-bottom:8px">
      <span class="punch" aria-hidden="true"></span>
      <div class="body"><div class="ttext">${esc(t.text)}</div>
        <div class="meta"><span>${t.gone==='reassigned'?'Moved to someone else':'Cancelled'}</span></div></div>
    </div>`;
  const c=crewCounts(rec);
  const sent=rec.report.lastSentAt?'Last report sent '+crewWhen(rec.report.lastSentAt):'No report sent yet';
  return crewTop(L.boss.name+' · '+crewDayLabel(L.day), L.job.name, 'crewstatus')
    +`<div class="wrap">
      ${pl?`<div class="card crew-parts" data-crew-parts>This list isn’t all here yet: ${esc(pl)}. Ask ${esc(L.boss.name)} to send the missing part again if it doesn’t arrive.</div>`:''}
      <div class="muted" style="font-size:13px;margin:2px 0 10px" data-crew-sent>${esc(sent)}${unsent?' · '+unsent+' change'+(unsent===1?'':'s')+' not sent':''} ${nbHelpMark('crewreport')}</div>
      <div class="sec-head"><span class="label">Your tasks</span><span class="rule"></span><span class="count">${c.done} of ${c.total} done</span></div>
      ${live.length?live.map(row).join(''):'<div class="card muted" style="font-size:14px">Nothing for you on this list right now.</div>'}
      ${gone.length?`<div class="sec-head"><span class="label">No longer yours</span><span class="rule"></span></div>${gone.map(goneRow).join('')}`:''}
    </div>
    <button class="btn primary crew-send" data-crew-report="${esc(rec.key)}">Send report</button>`;
}

/* The worker's one writer: the component stamps changedAt (never behind the
   last one, whatever the clock did). The memory copy follows the write. */
/* An edit made after a report was built must read as after it, even inside
   the same second — or "changes not sent" would miss it. So the clock is
   never allowed below the last build + 1. In memory for a report still
   going out in parts; the record's lastSentAt once it has. */
const _crewBuiltAt={};
function crewNow(rec){
  return Math.max(Date.now()/1000, Math.max(rec.report.lastSentAt, _crewBuiltAt[rec.key]||0)+1);
}
async function crewSetStatus(key,tid,status,note){
  const rec=crewByKey(key); if(!rec) return false;
  let state;
  try{ state=EGSCrew.setStatus(rec.state,tid,status,note,crewNow(rec)); }
  catch(e){ toast('That note can’t be saved — '+((e&&e.detail)||'check it')); return false; }
  try{ await crewSave(Object.assign({},rec,{state})); }
  catch(e){ toast('Couldn’t save that on this phone'); return false; }
  return true;
}
function crewPunch(key,tid){
  const rec=crewByKey(key); if(!rec) return;
  const s=rec.state[tid]||{status:'open',note:''};
  crewSetStatus(key,tid,s.status==='done'?'open':'done',s.note).then(ok=>{ if(ok) render(); });
}
/* Drawn ONCE. Nothing in here calls sheet() or render() until Save, so the
   textarea is the same node from the first keystroke to the last. */
function crewStatusSheet(key,tid){
  const rec=crewByKey(key); if(!rec) return;
  const t=rec.list.tasks.find(x=>x.id===tid);
  if(!t || t.gone || t.worker!==rec.workerId) return;
  const s=rec.state[tid]||{status:'open',note:''};
  let pick=s.status;
  sheet(`<h2>Task</h2>
    <div class="card" style="font-size:15px;line-height:1.45;margin-bottom:0">${esc(t.text)}</div>
    <div class="crew-seg" role="radiogroup" aria-label="Status">${['open','done','waiting'].map(k=>
      `<button type="button" class="btn${k===pick?' primary':''}" data-crew-st="${k}" role="radio" aria-checked="${k===pick}">${CREW_STATUS_LABEL[k]}</button>`).join('')}</div>
    <div class="crew-quick">${CREW_QUICK.map(q=>`<button type="button" class="chip-filter" data-crew-q="${esc(q)}">${esc(q)}</button>`).join('')}</div>
    <div class="field"><textarea class="input" id="crew-note" maxlength="280" placeholder="A note for your boss (optional)">${esc(s.note)}</textarea></div>
    <button class="btn primary block" data-crew-save>Save</button>`,'crewstatus');
  const seg=[...$mr.querySelectorAll('[data-crew-st]')], ta=$mr.querySelector('#crew-note');
  const paint=()=>seg.forEach(b=>{ const on=b.dataset.crewSt===pick; b.classList.toggle('primary',on); b.setAttribute('aria-checked',String(on)); });
  seg.forEach(b=>b.onclick=()=>{ pick=b.dataset.crewSt; paint(); });
  $mr.querySelectorAll('[data-crew-q]').forEach(b=>b.onclick=()=>{
    pick='waiting'; paint();
    const q=b.dataset.crewQ, cur=ta.value.trim();
    if(!cur) ta.value='Waiting on '+q.toLowerCase();
    else if(!cur.toLowerCase().includes(q.toLowerCase())) ta.value=cur+' · '+q.toLowerCase();
  });
  $mr.querySelector('[data-crew-save]').onclick=async()=>{
    if(await crewSetStatus(key,tid,pick,ta.value)){ closeSheet(); render(); }
  };
}
/* Crew lists land a moment after boot (IndexedDB). Redraw the screens that
   show them; never one with typing on it. Say so if any came from a newer
   build, unless the settings or projects notice already did. */
function crewAfterLoad(){
  const shown=$lock.classList.contains('hidden') && !document.getElementById('app').classList.contains('hidden');
  if(shown && (view.name==='todo'||view.name==='crew'||view.name==='crewlist')) render();
  if(crewFromFuture && !(schemaFromFuture||housesFromFuture) && !settingsUnreadable)
    setTimeout(()=>{ try{ toast('This data is from a newer Notebuilt — see Settings'); }catch(e){} }, 1800);
}
"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "function crewOnShell(" not in text:
        fail("chunk 2 (fix_crew2_entry.py) has not been applied.")

    edits = []
    edits.append(("  /* ---- FAB ---- */\n", CSS + "  /* ---- FAB ---- */\n", "crew CSS before the FAB block"))

    old_views = "const NAV_VIEWS=new Set(['todo','houses','calc','notes','settings','house','housenotes','note','search','privacy','support']);"
    new_views = "const NAV_VIEWS=new Set(['todo','houses','calc','notes','settings','house','housenotes','note','search','privacy','support','crew','crewlist']);"
    edits.append((old_views, new_views, "router knows the crew views"))

    old_parse = """    return (typeof param==='string' && NAV_ID.test(param) && notes.some(n=>n.id===param)) ? {name,param} : fall;
  }
  return param==null ? {name,param:null} : fall;"""
    new_parse = """    return (typeof param==='string' && NAV_ID.test(param) && notes.some(n=>n.id===param)) ? {name,param} : fall;
  }
  /* CREW — a list id must be on this phone. While crew lists are still
     loading it cannot be checked yet; the screen says so and redraws. */
  if(name==='crewlist')
    return (typeof param==='string' && CREW_KEY_RE.test(param) && (!crewLoaded || crewByKey(param))) ? {name,param} : fall;
  return param==null ? {name,param:null} : fall;"""
    edits.append((old_parse, new_parse, "navParse validates a crew list id"))

    old_disp = "            housenotes:renderHouseNotes,privacy:renderPrivacy,support:renderSupport})[view.name]||renderToday;"
    new_disp = "            housenotes:renderHouseNotes,privacy:renderPrivacy,support:renderSupport,\n            crew:renderCrew,crewlist:renderCrewList})[view.name]||renderToday;"
    edits.append((old_disp, new_disp, "render dispatch"))

    old_nav = "  const active=({house:'houses',note:'notes',search:'todo'})[view.name]||view.name;"
    new_nav = "  const active=({house:'houses',note:'notes',search:'todo',crew:'todo',crewlist:'todo'})[view.name]||view.name;"
    edits.append((old_nav, new_nav, "crew views light the To Do tab"))

    old_bind = "  $app.querySelectorAll('[data-edit-task]').forEach(b=>b.onclick=()=>openEditTask(b.dataset.editTask));\n"
    new_bind = old_bind + """
  /* CREW */
  $app.querySelectorAll('[data-crew-open]').forEach(b=>b.onclick=()=>go('crewlist',b.dataset.crewOpen));
  $app.querySelectorAll('[data-crew-punch]').forEach(b=>b.onclick=()=>crewPunch(view.param,b.dataset.crewPunch));
  $app.querySelectorAll('[data-crew-task]').forEach(b=>b.onclick=()=>crewStatusSheet(view.param,b.dataset.crewTask));
  $app.querySelectorAll('[data-crew-report]').forEach(b=>b.onclick=()=>crewSendReport(b.dataset.crewReport));
"""
    edits.append((old_bind, new_bind, "bind crew controls"))

    old_after = "const CREW_NEWER_HERE="
    edits.append((old_after, SCREENS.lstrip("\n") + "\n" + old_after, "crew screens before the arrival code"))

    old_load = "crewLoad();                                        /* CREW — memory only; renders when it lands */\n"
    new_load = "crewLoad().then(crewAfterLoad);                    /* CREW — memory only; renders when it lands */\n"
    edits.append((old_load, new_load, "redraw when crew lists land"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # the To Do landing's two returns both carry the card — exactly two
    old_ret = "return head+nbGuideNoticeHtml()+`"
    if working.count(old_ret) != 2:
        fail(f"expected the To Do landing's two returns, found {working.count(old_ret)}.")
    working = working.replace(old_ret, "return head+nbGuideNoticeHtml()+crewCardHtml()+`")

    # ---- guards ---------------------------------------------------------
    if working.count("crewCardHtml()+`") != 2:
        fail("the crew card is not on both To Do returns.")
    sheet_fn = working[working.find("function crewStatusSheet("):working.find("function crewAfterLoad(")]
    after_draw = sheet_fn[sheet_fn.find("const seg="):]
    if "sheet(" in after_draw or after_draw.replace("closeSheet(); render();", "").count("render(") != 0:
        fail("the note sheet redraws itself while open — the keyboard would drop.")

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
    print(f"✅ applied {len(edits) + 1} edits. Backup: {bak}")


if __name__ == "__main__":
    main()
