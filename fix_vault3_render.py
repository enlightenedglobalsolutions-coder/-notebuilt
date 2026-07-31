#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 3 of 5: locked screens and the decoy-proof filtering
Run this from the same folder as your index.html:
    python3 fix_vault3_render.py

Requires fix_vault1_core.py and fix_vault2_ceremony.py.

This is the script that makes the rule real. Every surface that could show a
protected project's contents now goes through the shared filter from script 1:

  * The Projects list — the cross-project view, and the one that mattered most.
    A protected project's cover photo was being painted there in full. Now a
    protected project is a name and a lock: no cover, no address, no status, no
    "3 specs · 12 photos · 2 open". How much is in there is itself information.
  * The project screen — locked, it renders the name, a lock, an Unlock button,
    and the delete escape for a lost passphrase. Nothing else is even built.
  * Notes, To Do, Search — a protected project's notes and to-dos never appear
    outside their own project, locked or unlocked. One rule, no exceptions to
    remember.
  * The cover picker, the photo viewer, the share sheet, hydratePhotos.

Text is read through vt(), which returns plaintext for a decrypted value and an
empty string for one that is still sealed — so esc() can never be handed a
ciphertext object and print [object Object] on screen.

hydratePhotos() gets an independent second check that works off the screen you
are actually on, rather than trusting the markup the renderers emitted.

Backs up first, applies edits with exact-match anchors, aborts atomically
if anything doesn't match, and validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "VAULT_RENDER"
REQUIRES = ["VAULT_CORE", "VAULT_CEREMONY"]

def fail(msg):
    print(f"\n❌ ABORTED — no changes were made.\n   Reason: {msg}\n")
    sys.exit(1)

def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found in this folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ Already applied — nothing to do.")
        return
    for req in REQUIRES:
        if req not in text:
            fail(f"{req} not found — run the earlier vault scripts first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: CSS for the big lock on the locked project screen
    # ---------------------------------------------------------------
    old = r"""  .lock-chip svg{width:12px;height:12px}"""
    new = r"""  .lock-chip svg{width:12px;height:12px}
  .lock-hero{display:inline-grid;place-items:center;color:var(--brass)}
  .lock-hero svg{width:46px;height:46px}"""
    edits.append((old, new, "CSS: locked-screen lock mark"))

    # ---------------------------------------------------------------
    # Edit 2: Today — protected to-dos never appear here
    # ---------------------------------------------------------------
    old = r"""  const list=[...tasks].sort((a,b)=> (order[a.status]-order[b.status]) || (b.createdAt-a.createdAt));"""
    new = r"""  /* VAULT_RENDER — a protected project's to-dos live only inside that project. */
  const list=tasks.filter(t=>!isProtected(t.houseId)).sort((a,b)=> (order[a.status]-order[b.status]) || (b.createdAt-a.createdAt));"""
    edits.append((old, new, "renderToday(): exclude protected to-dos"))

    # ---------------------------------------------------------------
    # Edit 3: taskRow — read text through vt()
    # ---------------------------------------------------------------
    old = r"""      <div class="ttext">${esc(t.text)}</div>"""
    new = r"""      <div class="ttext">${esc(vt(t.text))}</div>"""
    edits.append((old, new, "taskRow(): vt() the task text"))

    # ---------------------------------------------------------------
    # Edit 4: Projects list — a protected project is a name and a lock
    # ---------------------------------------------------------------
    old = r"""  const cards=filtered.length?sortHousesList(filtered).map(h=>{
    const open=tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;
    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:'';
    return `<div class="card house-card" data-house="${h.id}">
      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:''}>${h.cover?'':`<div class="blueprint"></div>${I.house}`}</div>"""
    new = r"""  const cards=filtered.length?sortHousesList(filtered).map(h=>{
    /* VAULT_RENDER — this list is a cross-project view, so a protected project
       shows its name and nothing else: no cover, no address, no status, no
       counts. How much is in there is itself information. */
    if(h.protected) return `<div class="card house-card" data-house="${h.id}">
      <div class="hc-body" style="padding:17px 14px"><div class="row">
        <div class="grow"><div class="hc-name">${esc(h.name)}</div></div>
        <span class="lock-chip">${I.lock} Protected</span>
      </div></div></div>`;
    const open=tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;
    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:'';
    const cov=coverFor(h.id,null);
    return `<div class="card house-card" data-house="${h.id}">
      <div class="house-cover" ${cov?`data-cover="${cov}"`:''}>${cov?'':`<div class="blueprint"></div>${I.house}`}</div>"""
    edits.append((old, new, "renderHouses(): locked project card"))

    # ---------------------------------------------------------------
    # Edit 5: renderHouse — locked screen + every field through vt()/photosFor()
    # ---------------------------------------------------------------
    old = r"""function renderHouse(id){
  const h=houseById(id); if(!h) return renderHouses();
  const specsByCat={};
  (h.specs||[]).forEach(s=>{ (specsByCat[s.category]=specsByCat[s.category]||[]).push(s); });
  const specBlocks=SPEC_CATS.filter(c=>specsByCat[c]).map(c=>`
    <div class="sec-head"><span class="label">${c}</span><span class="rule"></span></div>
    <div class="card spec-cat">${specsByCat[c].map(s=>`
      <div class="spec-row">
        ${s.room?`<div class="spec-room">${esc(s.room)}</div>`:'<div class="spec-room faint">—</div>'}
        <div class="spec-main"><div class="spec-label">${esc(s.label)}</div>${s.value?`<div class="spec-val">${esc(s.value)}</div>`:''}${s.note?`<div class="spec-note">${esc(s.note)}</div>`:''}</div>
        <button class="icon-btn" style="width:34px;height:34px;background:none" data-del-spec="${s.id}" aria-label="Delete spec">${I.trash}</button>
      </div>`).join('')}</div>`).join('');

  const photos=(h.photos||[]);"""

    new = r"""/* VAULT_RENDER — a locked project. The name, a lock, a way in, and the one
   honest way out if the passphrase is gone. Nothing else is even built. */
function renderHouseLocked(h){
  const items=(h.specs||[]).length+(h.photos||[]).length
    +notes.filter(n=>n.houseId===h.id).length+tasks.filter(t=>t.houseId===h.id).length;
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">Protected</span><h1 class="truncate">${esc(h.name)}</h1></div>
  </div>
  <div class="wrap">
    <div style="text-align:center;padding:50px 20px 28px">
      <span class="lock-hero">${I.lock}</span>
      <div style="font-family:var(--serif);font-size:19px;margin-top:12px">${esc(h.name)} is locked</div>
      <div class="muted" style="font-size:13.5px;line-height:1.65;margin-top:8px">Its notes, to-dos, specs and photos are encrypted on this device. Nothing here is readable — not by this app, not by anyone — without your vault passphrase.</div>
    </div>
    <button class="btn primary block" data-vault-open="${h.id}">${I.lock} Unlock</button>

    <div class="sec-head" style="margin-top:28px"><span class="label">Lost the passphrase?</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13px;line-height:1.65">There is no recovery — that is the design, not an oversight. EGS cannot reset it, and neither can anyone else. If the passphrase is gone, the only thing left to do with this project is delete it.</div>
    <button class="btn danger block" data-vault-del="${h.id}" style="margin-top:8px">${I.trash} Delete this project (${items} item${items===1?'':'s'})</button>
  </div>`;
}

function renderHouse(id){
  const h=houseById(id); if(!h) return renderHouses();
  if(h.protected && !vaultUnlocked()) return renderHouseLocked(h);
  vaultEnsureProject(id);
  const specsByCat={};
  (h.specs||[]).forEach(s=>{ (specsByCat[s.category]=specsByCat[s.category]||[]).push(s); });
  const specBlocks=SPEC_CATS.filter(c=>specsByCat[c]).map(c=>`
    <div class="sec-head"><span class="label">${c}</span><span class="rule"></span></div>
    <div class="card spec-cat">${specsByCat[c].map(s=>{
      const sRoom=vt(s.room), sLabel=vt(s.label), sVal=vt(s.value), sNote=vt(s.note);
      return `
      <div class="spec-row">
        ${sRoom?`<div class="spec-room">${esc(sRoom)}</div>`:'<div class="spec-room faint">—</div>'}
        <div class="spec-main"><div class="spec-label">${esc(sLabel)}</div>${sVal?`<div class="spec-val">${esc(sVal)}</div>`:''}${sNote?`<div class="spec-note">${esc(sNote)}</div>`:''}</div>
        <button class="icon-btn" style="width:34px;height:34px;background:none" data-del-spec="${s.id}" aria-label="Delete spec">${I.trash}</button>
      </div>`;}).join('')}</div>`).join('');

  const photos=photosFor(id,id);"""
    edits.append((old, new, "renderHouse(): locked screen, vt() specs, photosFor()"))

    # ---------------------------------------------------------------
    # Edit 6: renderHouse — cover, address, site notes, share button
    # ---------------------------------------------------------------
    old = r"""  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">Project</span><h1 class="truncate">${esc(h.name)}</h1></div>
    <button class="icon-btn" data-share-house="${h.id}" aria-label="Share project">${I.share}</button>
    <button class="icon-btn" data-edit-house="${h.id}" aria-label="Edit project">${I.edit}</button>
  </div>
  <div class="wrap">
    <div class="house-cover" data-edit-cover="${h.id}" style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px;cursor:pointer" ${h.cover?`data-cover="${h.cover}"`:''}>${h.cover?'':`<div class="blueprint"></div>${I.house}`}</div>
    <div class="row" style="margin:10px 0 2px"><span class="cat-badge" data-open-cat-picker="${h.id}" style="cursor:pointer" title="Tap to move to another category">${categoryIcon(h.category)}</span><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:''}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:''}</div>"""

    new = r"""  const cover=coverFor(id,id);
  const addr=vt(h.address);
  const siteNotes=vt(h.notes);
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${h.protected?'Protected · unlocked':'Project'}</span><h1 class="truncate">${esc(h.name)}</h1></div>
    ${h.protected?`<button class="icon-btn" data-vault-lock-now aria-label="Lock this project now">${I.lock}</button>`:`<button class="icon-btn" data-share-house="${h.id}" aria-label="Share project">${I.share}</button>`}
    <button class="icon-btn" data-edit-house="${h.id}" aria-label="Edit project">${I.edit}</button>
  </div>
  <div class="wrap">
    <div class="house-cover" data-edit-cover="${h.id}" style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px;cursor:pointer" ${cover?`data-cover="${cover}"`:''}>${cover?'':`<div class="blueprint"></div>${I.house}`}</div>
    <div class="row" style="margin:10px 0 2px"><span class="cat-badge" data-open-cat-picker="${h.id}" style="cursor:pointer" title="Tap to move to another category">${categoryIcon(h.category)}</span><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:''}${addr?`<span class="muted truncate" style="font-size:13px">${esc(addr)}</span>`:''}</div>"""
    edits.append((old, new, "renderHouse(): cover/address/lock button"))

    # ---------------------------------------------------------------
    # Edit 7: renderHouse — site notes preview through vt()
    # ---------------------------------------------------------------
    old = r"""    <div class="card" data-open-house-notes="${h.id}" style="cursor:pointer">${h.notes?`<div style="white-space:pre-wrap;color:var(--paper-dim);font-size:14px;max-height:3.6em;overflow:hidden">${esc(h.notes.slice(0,180))}${h.notes.length>180?'…':''}</div>`:`<div class="muted" style="font-size:14px">Tap to add site notes, measurements, reminders…</div>`}</div>"""
    new = r"""    <div class="card" data-open-house-notes="${h.id}" style="cursor:pointer">${siteNotes?`<div style="white-space:pre-wrap;color:var(--paper-dim);font-size:14px;max-height:3.6em;overflow:hidden">${esc(siteNotes.slice(0,180))}${siteNotes.length>180?'…':''}</div>`:`<div class="muted" style="font-size:14px">Tap to add site notes, measurements, reminders…</div>`}</div>"""
    edits.append((old, new, "renderHouse(): site notes preview"))

    # ---------------------------------------------------------------
    # Edit 8: full-screen site notes editor
    # ---------------------------------------------------------------
    old = r"""function renderHouseNotes(houseId){
  const h=houseById(houseId); if(!h) return renderHouses();
  return `<div class="topbar">"""
    new = r"""function renderHouseNotes(houseId){
  const h=houseById(houseId); if(!h) return renderHouses();
  if(h.protected && !vaultUnlocked()) return renderHouseLocked(h);
  vaultEnsureProject(houseId);
  return `<div class="topbar">"""
    edits.append((old, new, "renderHouseNotes(): lock gate"))

    old = r"""    <textarea class="input" data-house-notes-full="${h.id}" placeholder="Site notes, measurements, reminders…" style="min-height:calc(100vh - 170px);font-size:15px;line-height:1.5">${esc(h.notes||'')}</textarea>"""
    new = r"""    <textarea class="input" data-house-notes-full="${h.id}" placeholder="Site notes, measurements, reminders…" style="min-height:calc(100vh - 170px);font-size:15px;line-height:1.5">${esc(vt(h.notes))}</textarea>"""
    edits.append((old, new, "renderHouseNotes(): vt() the body"))

    # ---------------------------------------------------------------
    # Edit 9: note cards through vt()
    # ---------------------------------------------------------------
    old = r"""  const body=(n.body||'').replace(/\s+/g,' ').trim();"""
    new = r"""  const body=vt(n.body).replace(/\s+/g,' ').trim();"""
    edits.append((old, new, "noteCardHtml(): vt() the body"))

    old = r"""    <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${n.important?`<span class="note-star" style="color:var(--brass)">${I.star}</span> `:''}${esc(n.title||'Untitled')}</div>"""
    new = r"""    <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${n.important?`<span class="note-star" style="color:var(--brass)">${I.star}</span> `:''}${esc(vt(n.title)||'Untitled')}</div>"""
    edits.append((old, new, "noteCardHtml(): vt() the title"))

    # ---------------------------------------------------------------
    # Edit 10: Notes list — protected notes never appear here
    # ---------------------------------------------------------------
    old = r"""  if(!notes.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn't belong to a single project — ideas, supplier info, measurements.</div></div>`;
  const sorted=[...notes].sort((a,b)=>b.updatedAt-a.updatedAt);"""
    new = r"""  /* VAULT_RENDER — a protected project's notes live only inside that project. */
  const visible=notes.filter(n=>!isProtected(n.houseId));
  if(!visible.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn't belong to a single project — ideas, supplier info, measurements.</div></div>`;
  const sorted=[...visible].sort((a,b)=>b.updatedAt-a.updatedAt);"""
    edits.append((old, new, "renderNotes(): exclude protected notes"))

    # ---------------------------------------------------------------
    # Edit 11: note editor — lock gate, vt(), and a picker that hides protected projects
    # ---------------------------------------------------------------
    old = r"""  const n=isNew?{title:'',body:'',houseId:presetHouseId,important:false}:notes.find(x=>x.id===id)||{title:'',body:'',houseId:null,important:false};
  const opts=houses.map(h=>`<option value="${h.id}" ${n.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');"""
    new = r"""  const n=isNew?{title:'',body:'',houseId:presetHouseId,important:false}:notes.find(x=>x.id===id)||{title:'',body:'',houseId:null,important:false};
  if(isProtected(n.houseId) && !vaultUnlocked()) return renderHouseLocked(houseById(n.houseId));
  vaultEnsureProject(n.houseId);
  const opts=pickableHouses(n.houseId).map(h=>`<option value="${h.id}" ${n.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');"""
    edits.append((old, new, "renderNote(): lock gate + picker"))

    old = r"""    <div class="field"><input class="input" id="note-title" placeholder="Title" value="${esc(n.title)}" style="font-family:var(--serif);font-size:19px"></div>"""
    new = r"""    <div class="field"><input class="input" id="note-title" placeholder="Title" value="${esc(vt(n.title))}" style="font-family:var(--serif);font-size:19px"></div>"""
    edits.append((old, new, "renderNote(): vt() the title"))

    old = r"""    <div class="field"><textarea class="input" id="note-body" placeholder="Write…" style="min-height:220px">${esc(n.body)}</textarea></div>"""
    new = r"""    <div class="field"><textarea class="input" id="note-body" placeholder="Write…" style="min-height:220px">${esc(vt(n.body))}</textarea></div>"""
    edits.append((old, new, "renderNote(): vt() the body"))

    # ---------------------------------------------------------------
    # Edit 12: Search — protected projects and their contents stay out
    # ---------------------------------------------------------------
    old = r"""  houses.forEach(h=>{ const hay=[h.name,h.address,h.notes,...(h.specs||[]).flatMap(s=>[s.label,s.value,s.room,s.note])].join(' ').toLowerCase();
    if(hay.includes(q)) hits.push({t:'Project',title:h.name,sub:h.address||'',go:()=>go('house',h.id)}); });
  notes.forEach(n=>{ if((n.title+' '+n.body).toLowerCase().includes(q)) hits.push({t:'Note',title:n.title||'Untitled',sub:(n.body||'').slice(0,60),go:()=>go('note',n.id)}); });
  tasks.forEach(t=>{ if((t.text||'').toLowerCase().includes(q)){ const h=houseById(t.houseId); hits.push({t:'To-do',title:t.text,sub:(h?h.name+' · ':'')+STATUS_LABEL[t.status],go:()=> h?go('house',h.id):go('todo')}); } });"""
    new = r"""  /* VAULT_RENDER — protected projects are not searchable, locked or unlocked.
     Contents live inside the project or nowhere. Same rule as photos. */
  houses.forEach(h=>{ if(h.protected) return;
    const hay=[h.name,h.address,h.notes,...(h.specs||[]).flatMap(s=>[s.label,s.value,s.room,s.note])].join(' ').toLowerCase();
    if(hay.includes(q)) hits.push({t:'Project',title:h.name,sub:h.address||'',go:()=>go('house',h.id)}); });
  notes.forEach(n=>{ if(isProtected(n.houseId)) return;
    if((n.title+' '+n.body).toLowerCase().includes(q)) hits.push({t:'Note',title:n.title||'Untitled',sub:(n.body||'').slice(0,60),go:()=>go('note',n.id)}); });
  tasks.forEach(t=>{ if(isProtected(t.houseId)) return;
    if((t.text||'').toLowerCase().includes(q)){ const h=houseById(t.houseId); hits.push({t:'To-do',title:t.text,sub:(h?h.name+' · ':'')+STATUS_LABEL[t.status],go:()=> h?go('house',h.id):go('todo')}); } });"""
    edits.append((old, new, "runSearch(): exclude protected projects"))

    # ---------------------------------------------------------------
    # Edit 13: the shared picker helper + project pickers
    # ---------------------------------------------------------------
    old = r"""function openTaskSheet(houseId=null){
  const opts=houses.map(h=>`<option value="${h.id}" ${houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');"""
    new = r"""/* VAULT_RENDER — a cross-project picker never offers a protected project.
   The only exception is the one an item already belongs to, so editing an item
   from inside an unlocked protected project still shows where it lives. */
function pickableHouses(currentId){ return houses.filter(h=>!h.protected || h.id===currentId); }

function openTaskSheet(houseId=null){
  const opts=pickableHouses(houseId).map(h=>`<option value="${h.id}" ${houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');"""
    edits.append((old, new, "pickableHouses() + openTaskSheet picker"))

    old = r"""  const opts=houses.map(h=>`<option value="${h.id}" ${t.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');
  sheet(`<h2>Edit to-do</h2>
    <div class="field"><input class="input" id="t-text" value="${esc(t.text)}"></div>"""
    new = r"""  const opts=pickableHouses(t.houseId).map(h=>`<option value="${h.id}" ${t.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');
  sheet(`<h2>Edit to-do</h2>
    <div class="field"><input class="input" id="t-text" value="${esc(vt(t.text))}"></div>"""
    edits.append((old, new, "openEditTask(): picker + vt()"))

    # ---------------------------------------------------------------
    # Edit 14: share — never for a protected project
    # ---------------------------------------------------------------
    old = r"""function openShareSheet(houseId){
  const h=houseById(houseId); if(!h)return;"""
    new = r"""function openShareSheet(houseId){
  const h=houseById(houseId); if(!h)return;
  /* VAULT_RENDER — sharing a protected project would hand its contents to
     whatever app the share sheet points at. Not offered, at all. */
  if(h.protected){ toast('Protected projects cannot be shared'); return; }"""
    edits.append((old, new, "openShareSheet(): block protected"))

    old = r"""async function doShareHouse(houseId,opts){
  const h=houseById(houseId); if(!h)return;"""
    new = r"""async function doShareHouse(houseId,opts){
  const h=houseById(houseId); if(!h || h.protected)return;"""
    edits.append((old, new, "doShareHouse(): block protected"))

    old = r"""      for(const pid of h.photos){"""
    new = r"""      for(const pid of photosFor(houseId,houseId)){"""
    edits.append((old, new, "doShareHouse(): route photos through the filter"))

    # ---------------------------------------------------------------
    # Edit 15: cover picker + viewer through the filter
    # ---------------------------------------------------------------
    old = r"""  if(!(h.photos||[]).length){ toast('Add photos to this project first'); return; }
  Sorted.pickGrid({
    items:(h.photos||[]),"""
    new = r"""  const pickable=photosFor(houseId,houseId);
  if(!pickable.length){ toast('Add photos to this project first'); return; }
  Sorted.pickGrid({
    items:pickable,"""
    edits.append((old, new, "openCoverPicker(): route through the filter"))

    old = r"""  const photos=(h.photos||[]).slice();
  const idx=photos.indexOf(photoId);"""
    new = r"""  const photos=photosFor(houseId,houseId).slice();
  const idx=photos.indexOf(photoId);"""
    edits.append((old, new, "openViewer(): route through the filter"))

    # ---------------------------------------------------------------
    # Edit 16: hydratePhotos — an independent second check
    # ---------------------------------------------------------------
    old = r"""/* fill in any cover/photo backgrounds from IndexedDB after render */
async function hydratePhotos(){
  for(const el of $app.querySelectorAll('[data-cover]')){
    const u=await photoURL(el.getAttribute('data-cover')); if(u){ el.style.backgroundImage=`url(${u})`; el.innerHTML=''; }
  }
  for(const el of $app.querySelectorAll('[data-photo]')){
    const u=await photoURL(el.getAttribute('data-photo')); if(u) el.style.backgroundImage=`url(${u})`;
  }
}"""
    new = r"""/* VAULT_RENDER — which project owns this photo? Answered from the plaintext
   photos[] arrays, so it still works with the vault locked. */
function vaultPhotoPaintable(pid, scopeHouseId){
  const owner=houses.find(h=>(h.photos||[]).indexOf(pid)>=0);
  if(!owner) return true;                       /* orphan: nothing protects it */
  return photoAllowedFor(owner.id, scopeHouseId);
}

/* fill in any cover/photo backgrounds from IndexedDB after render.
   The renderers already gate on photoAllowedFor(); this re-derives the answer
   from the screen we are actually on, so a stray data-cover or data-photo can
   never paint a protected photo even if a renderer is changed carelessly. */
async function hydratePhotos(){
  const scope = view.name==='house' ? view.param : null;
  for(const el of $app.querySelectorAll('[data-cover]')){
    const pid=el.getAttribute('data-cover');
    if(!vaultPhotoPaintable(pid,scope)) continue;
    const u=await photoURL(pid); if(u){ el.style.backgroundImage=`url(${u})`; el.innerHTML=''; }
  }
  for(const el of $app.querySelectorAll('[data-photo]')){
    const pid=el.getAttribute('data-photo');
    if(!vaultPhotoPaintable(pid,scope)) continue;
    const u=await photoURL(pid); if(u) el.style.backgroundImage=`url(${u})`;
  }
}"""
    edits.append((old, new, "hydratePhotos(): independent second check"))

    # ---------------------------------------------------------------
    # Edit 17: bind() — Unlock button and the per-project Lock now button
    # ---------------------------------------------------------------
    old = r"""  $app.querySelectorAll('[data-house]').forEach(c=>c.onclick=()=>go('house',c.dataset.house));"""
    new = r"""  $app.querySelectorAll('[data-house]').forEach(c=>c.onclick=()=>go('house',c.dataset.house));
  $app.querySelectorAll('[data-vault-open]').forEach(b=>b.onclick=()=>vaultUnlockSheet({
    title:'Unlock this project',
    body:'Enter your vault passphrase. This is not your app PIN, and there is no way to recover it.'
  }));
  const vLockNow=$app.querySelector('[data-vault-lock-now]');
  if(vLockNow) vLockNow.onclick=()=>{ vaultRelock(); toast('Locked'); };"""
    edits.append((old, new, "bind(): unlock + per-project lock buttons"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_vault3_check.js")
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

    print("\n✅ Vault 3/5 applied: locked screens and decoy-proof filtering.")
    print("   Next: fix_vault4_toggle.py")

if __name__ == "__main__":
    main()
