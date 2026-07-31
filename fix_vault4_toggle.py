#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 4 of 5: turning protection on and off, and never writing plaintext
Run this from the same folder as your index.html:
    python3 fix_vault4_toggle.py

Requires scripts 1-3.

Turning protection ON runs the ceremony if the vault doesn't exist yet, then
encrypts the project in place with a progress bar. The ordering is the whole
trick:

    h.protected = true            <- set FIRST
    settings.vault.migration = {} <- journal written BEFORE the first record
    ...encrypt record by record, persisting after each...
    settings.vault.migration = null

At every instant of an interrupted run the project reads as protected and
renders locked, so it can never flash its contents. And because each record
carries its own {enc:1} marker, re-running the pass simply skips whatever is
already done — resume is just "run it again", and there is no rollback path to
get wrong. Turning protection OFF is the same in reverse, with h.protected
cleared LAST for the same reason.

Also closes every plaintext write path into a protected project: saving a note,
autosaving one, adding or editing a to-do, adding a spec, typing site notes,
and all four ways a photo can be written (camera/library, crop, rotate, markup).
Autosave seals before it persists rather than after, so a crash mid-edit loses
the edit rather than leaking it.

And the forgot-passphrase escape: a locked project can be deleted without the
passphrase, behind two confirmations that state the item count. Its notes and
to-dos are deleted rather than unlinked — orphaned ciphertext nobody can ever
read is not a kindness.

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
MARKER = "VAULT_TOGGLE"
REQUIRES = ["VAULT_CORE", "VAULT_CEREMONY", "VAULT_RENDER"]

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
    # Edit 1: the toggle, the migration engine, the delete escape
    # ---------------------------------------------------------------
    old = r"""function protectedCount(){ return houses.filter(h=>h.protected).length; }"""

    new = r"""function protectedCount(){ return houses.filter(h=>h.protected).length; }

/* ============================================================
   VAULT_TOGGLE — protect on/off, encrypt-in-place, and the delete escape
   ============================================================ */
let _vaultMigrating=false;

/* Bring a record's fields into line with where it now lives: sealed inside a
   protected project, plain outside one. Handles a note being moved either way. */
async function vaultAlignRecord(rec, fields, houseId){
  const want=isProtected(houseId);
  if(!vaultUnlocked()){
    /* Nothing to do if it is already in the right shape; otherwise refuse
       rather than write the wrong thing. */
    return !fields.some(f=>isEnc(rec[f])!==want);
  }
  for(const f of fields){
    if(want){
      if(isEnc(rec[f])) continue;
      const plain=rec[f]==null?'':String(rec[f]);
      rec[f]=await vaultSealText(plain);
      _vaultCache.set(rec[f].iv, plain);      /* keep the open screen readable */
    }else{
      if(!isEnc(rec[f])) continue;
      rec[f]=await vaultOpenText(rec[f]);
    }
  }
  return true;
}

/* One record, one direction. Both vaultSealField and vaultOpenField are no-ops
   on a record that is already in the target state — that is what makes an
   interrupted run safe to simply re-run. */
async function vaultMigrateOne(h, job, seal){
  const conv = seal ? vaultSealField : vaultOpenField;
  if(job.kind==='house'){
    h.address=await conv(h.address); h.notes=await conv(h.notes); persist.houses(); return;
  }
  if(job.kind==='spec'){
    const s=(h.specs||[]).find(x=>x.id===job.id); if(!s) return;
    s.room=await conv(s.room); s.label=await conv(s.label);
    s.value=await conv(s.value); s.note=await conv(s.note); persist.houses(); return;
  }
  if(job.kind==='note'){
    const n=notes.find(x=>x.id===job.id); if(!n) return;
    n.title=await conv(n.title); n.body=await conv(n.body); persist.notes(); return;
  }
  if(job.kind==='task'){
    const t=tasks.find(x=>x.id===job.id); if(!t) return;
    t.text=await conv(t.text); persist.tasks(); return;
  }
  if(job.kind==='photo'){
    const rec=await photoGet(job.id); if(!rec) return;
    const stale=_objUrls.get(job.id);
    if(stale){ URL.revokeObjectURL(stale); _objUrls.delete(job.id); _vaultUrlIds.delete(job.id); }
    if(seal){
      if(isEncPhoto(rec)) return;                       /* already sealed — resume skips it */
      const sealed=await vaultSealBytes(new Uint8Array(await rec.blob.arrayBuffer()));
      const out={ id:rec.id, enc:1, iv:sealed.iv, ct:sealed.ct,
                  type:(rec.blob&&rec.blob.type)||'image/jpeg',
                  houseId:rec.houseId, createdAt:rec.createdAt };
      if(rec.cropped) out.cropped=true;
      await photoPut(out);
    }else{
      if(!isEncPhoto(rec)) return;                      /* already plain */
      const pt=await vaultOpenBytes(rec.iv, rec.ct);
      const out={ id:rec.id, blob:new Blob([pt],{type:rec.type||'image/jpeg'}),
                  houseId:rec.houseId, createdAt:rec.createdAt };
      if(rec.cropped) out.cropped=true;
      await photoPut(out);
    }
    return;
  }
}

/* The pass itself. Photos go last: they are the slow part, and the text records
   are cheap enough that the bar moves straight away. */
async function vaultRunMigration(houseId, dir){
  if(_vaultMigrating) return false;
  const h=houseById(houseId); if(!h) return false;
  if(!vaultUnlocked()) return false;
  const seal = dir==='on';
  _vaultMigrating=true;
  const jobs=[{kind:'house'}];
  (h.specs||[]).forEach(s=>jobs.push({kind:'spec',id:s.id}));
  notes.forEach(n=>{ if(n.houseId===houseId) jobs.push({kind:'note',id:n.id}); });
  tasks.forEach(t=>{ if(t.houseId===houseId) jobs.push({kind:'task',id:t.id}); });
  (h.photos||[]).forEach(pid=>jobs.push({kind:'photo',id:pid}));
  const total=jobs.length;
  const title=seal?('Protecting '+h.name):('Removing protection');
  const sub=seal?'Encrypting on this device':'Decrypting on this device';
  try{
    await vaultBusy(title, sub, 0);
    for(let i=0;i<jobs.length;i++){
      await vaultMigrateOne(h, jobs[i], seal);
      await vaultBusy(title, sub+' — '+(i+1)+' of '+total, Math.round(((i+1)/total)*100));
    }
    /* Cleared LAST, for the same reason it was set first. */
    if(!seal) h.protected=false;
    h.updatedAt=now(); persist.houses();
    if(settings.vault) settings.vault.migration=null;
    persist.settings();
    _vaultCache.clear();
    vaultBusyDone(); _vaultMigrating=false;
    return true;
  }catch(err){
    vaultBusyDone(); _vaultMigrating=false;
    /* The journal stays put. The project stays protected and renders locked, and
       reopening it picks up exactly where this stopped. Nothing is lost.
       Losing the key mid-pass (the app was backgrounded) is the expected case,
       not a fault, so say so plainly rather than reporting a failure. */
    alert(vaultUnlocked()
      ? 'That did not finish.\n\nNothing was lost — open the project again and it will carry on from where it stopped.'
      : 'The vault locked before that finished.\n\nNothing was lost — unlock the project again and it will carry on from where it stopped.');
    return false;
  }
}

/* An interrupted pass finishes itself the next time the vault opens. */
async function vaultResumeMigration(){
  const m=settings.vault&&settings.vault.migration;
  if(!m || !vaultUnlocked() || _vaultMigrating) return;
  const h=houseById(m.houseId);
  if(!h){ settings.vault.migration=null; persist.settings(); return; }
  if(await vaultRunMigration(m.houseId, m.dir)){ render(); toast('Finished where it left off'); }
}

async function vaultProtectOn(houseId){
  const h=houseById(houseId); if(!h || h.protected) return;
  let firstEver=false;
  if(!vaultExists()){
    if(!(await vaultRunCeremony())) return;      /* gates 1-3 are the confirmation */
    firstEver=true;
  }else if(!vaultUnlocked()){
    vaultUnlockSheet({ title:'Unlock to protect', body:'Enter your vault passphrase to put another project behind it.',
                       onOpen:()=>vaultProtectOn(houseId) });
    return;
  }else if(!confirm('Protect "'+h.name+'"?\n\nIts notes, to-dos, specs and photos will be encrypted on this device. Without your vault passphrase nobody can read them — including EGS.')){
    return;
  }
  /* Set FIRST, journal BEFORE the first record: from here on, an interruption
     leaves a project that reads as protected and renders locked. */
  h.protected=true; h.updatedAt=now(); persist.houses();
  settings.vault.migration={ houseId, dir:'on', startedAt:now() }; persist.settings();
  if(!(await vaultRunMigration(houseId,'on'))) { render(); return; }
  /* Gate 4 — only the first time, when the passphrase is new and unproven. */
  if(firstEver) await vaultVerificationGate();
  go('house',houseId);
  toast('Protected');
}

async function vaultProtectOff(houseId){
  const h=houseById(houseId); if(!h || !h.protected) return;
  if(!vaultUnlocked()){
    vaultUnlockSheet({ title:'Unlock to remove protection', body:'Enter your vault passphrase.',
                       onOpen:()=>vaultProtectOff(houseId) });
    return;
  }
  if(!confirm('Remove protection from "'+h.name+'"?\n\nIts notes, to-dos, specs and photos go back to being stored unencrypted on this device — readable by anything that can read this app\'s storage.')) return;
  settings.vault.migration={ houseId, dir:'off', startedAt:now() }; persist.settings();
  if(await vaultRunMigration(houseId,'off')){ render(); toast('Protection removed'); }
  else render();
}

/* The forgot-passphrase escape. Deleting is the only thing that can be done to
   a locked project without the passphrase, so it has to be possible — and hard
   to do by accident. Notes and to-dos are deleted rather than unlinked: leaving
   ciphertext nobody can ever read floating around is not a kindness. */
async function vaultDeleteLocked(houseId){
  const h=houseById(houseId); if(!h) return;
  const nSpecs=(h.specs||[]).length, nPhotos=(h.photos||[]).length;
  const nNotes=notes.filter(n=>n.houseId===houseId).length;
  const nTasks=tasks.filter(t=>t.houseId===houseId).length;
  const total=nSpecs+nPhotos+nNotes+nTasks;
  const pl=(n,w)=>n+' '+w+(n===1?'':'s');
  if(!confirm('Delete "'+h.name+'" and everything in it?\n\n'
    +pl(nNotes,'note')+', '+pl(nTasks,'to-do')+', '+pl(nSpecs,'spec')+', '+pl(nPhotos,'photo')+'.\n\n'
    +'This data cannot be recovered. Deleting is the only option without the passphrase.')) return;
  if(!confirm('Last check.\n\nAll '+pl(total,'item')+' in "'+h.name+'" will be gone permanently. There is no undo, and no copy anywhere else.\n\nDelete it?')) return;
  for(const pid of (h.photos||[])){ await photoDel(pid).catch(()=>{}); }
  notes=notes.filter(n=>n.houseId!==houseId);
  tasks=tasks.filter(t=>t.houseId!==houseId);
  houses=houses.filter(x=>x.id!==houseId);
  if(settings.vault && settings.vault.migration && settings.vault.migration.houseId===houseId){
    settings.vault.migration=null; persist.settings();
  }
  persist.houses(); persist.notes(); persist.tasks();
  go('houses'); toast('Project deleted');
}"""
    edits.append((old, new, "toggle, migration engine, delete escape"))

    # ---------------------------------------------------------------
    # Edit 2: an interrupted pass resumes the moment the vault opens
    # ---------------------------------------------------------------
    old = r"""  }catch(e){ _vaultKey=prev; return false; }
  vaultTouch();
  return true;
}"""
    new = r"""  }catch(e){ _vaultKey=prev; return false; }
  vaultTouch();
  vaultResumeMigration();   /* VAULT_TOGGLE — finish anything that was interrupted */
  return true;
}"""
    edits.append((old, new, "vaultUnlock(): resume hook"))

    # ---------------------------------------------------------------
    # Edit 3: Edit-project sheet — the protect toggle, vt() address, safe delete
    # ---------------------------------------------------------------
    old = r"""    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(h.address||'')}"></div>"""
    new = r"""    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(vt(h.address))}"></div>"""
    edits.append((old, new, "openHouseSheet(): vt() the address"))

    old = r"""    <button class="btn primary block" id="h-save">${edit?'Save':'Create project'}</button>
    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete project</button>`:''}`);"""
    new = r"""    ${edit?`<div class="card" style="background:var(--ink-2);margin:4px 0 14px">
      <div class="row"><div class="grow">
        <div>${edit.protected?'Protected':'Protect this project'}</div>
        <div class="muted" style="font-size:12.5px;line-height:1.5;margin-top:2px">${edit.protected
          ? 'Its contents are encrypted behind your vault passphrase.'
          : 'Encrypt its notes, to-dos, specs and photos behind a passphrase of their own.'}</div>
      </div><button class="btn sm ${edit.protected?'':'primary'}" id="h-protect">${edit.protected?'Turn off':'Turn on'}</button></div>
    </div>`:''}
    <button class="btn primary block" id="h-save">${edit?'Save':'Create project'}</button>
    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete project</button>`:''}`);"""
    edits.append((old, new, "openHouseSheet(): protect toggle row"))

    old = r"""  $mr.querySelector('#h-save').onclick=()=>{
    const name=$mr.querySelector('#h-name').value.trim(); if(!name){$mr.querySelector('#h-name').focus();return;}
    const category=$mr.querySelector('#h-category').value;
    const addr=$mr.querySelector('#h-addr').value.trim(), st=$mr.querySelector('#h-status').value, jt=$mr.querySelector('#h-jobtype').value;
    if(edit){ edit.name=name; edit.category=category; edit.address=addr; edit.status=st; edit.jobType=jt; edit.updatedAt=now(); persist.houses(); closeSheet(); render(); toast('Saved'); }
    else{ const nh={id:uid(),name,category,address:addr,status:st,jobType:jt,specs:[],photos:[],cover:null,notes:'',createdAt:now(),updatedAt:now()};
      houses.push(nh); persist.houses(); closeSheet(); go('house',nh.id); toast('Project added'); }
  };
  if(edit) $mr.querySelector('#h-del').onclick=()=>{
    if(!confirm(`Delete "${edit.name}" and its specs? Photos and to-dos for it stay but unlink.`)) return;"""
    new = r"""  if(edit) $mr.querySelector('#h-protect').onclick=()=>{
    closeSheet();
    if(edit.protected) vaultProtectOff(edit.id); else vaultProtectOn(edit.id);
  };
  $mr.querySelector('#h-save').onclick=async()=>{
    const name=$mr.querySelector('#h-name').value.trim(); if(!name){$mr.querySelector('#h-name').focus();return;}
    const category=$mr.querySelector('#h-category').value;
    const addr=$mr.querySelector('#h-addr').value.trim(), st=$mr.querySelector('#h-status').value, jt=$mr.querySelector('#h-jobtype').value;
    if(edit){ edit.name=name; edit.category=category; edit.address=addr; edit.status=st; edit.jobType=jt; edit.updatedAt=now();
      /* VAULT_TOGGLE — seal before it reaches storage, never after. */
      if(!(await vaultAlignRecord(edit,['address'],edit.id))){ toast('Unlock the vault to save that'); return; }
      persist.houses(); closeSheet(); render(); toast('Saved'); }
    else{ const nh={id:uid(),name,category,address:addr,status:st,jobType:jt,specs:[],photos:[],cover:null,notes:'',createdAt:now(),updatedAt:now()};
      houses.push(nh); persist.houses(); closeSheet(); go('house',nh.id); toast('Project added'); }
  };
  if(edit) $mr.querySelector('#h-del').onclick=()=>{
    /* A protected project's notes and to-dos are unreadable ciphertext — unlinking
       them would strand it. Route to the escape hatch, which deletes them. */
    if(edit.protected){ closeSheet(); vaultDeleteLocked(edit.id); return; }
    if(!confirm(`Delete "${edit.name}" and its specs? Photos and to-dos for it stay but unlink.`)) return;"""
    edits.append((old, new, "openHouseSheet(): save/delete/protect handlers"))

    # ---------------------------------------------------------------
    # Edit 4: new to-do — seal before persisting
    # ---------------------------------------------------------------
    old = r"""  const submit=()=>{ const text=inp.value.trim(); if(!text){inp.focus();return;}
    tasks.push({id:uid(),text,status:'todo',houseId:$mr.querySelector('#t-house').value||null,createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null});
    persist.tasks(); closeSheet(); render(); toast('Added to Today'); };"""
    new = r"""  const submit=async()=>{ const text=inp.value.trim(); if(!text){inp.focus();return;}
    const hid=$mr.querySelector('#t-house').value||null;
    const nt={id:uid(),text,status:'todo',houseId:hid,createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null};
    tasks.push(nt);
    if(!(await vaultAlignRecord(nt,['text'],hid))){ tasks.pop(); toast('Unlock the vault to add that'); return; }
    persist.tasks(); closeSheet(); render(); toast('Added to Today'); };"""
    edits.append((old, new, "openTaskSheet(): seal new to-do"))

    # ---------------------------------------------------------------
    # Edit 5: edit to-do — seal before persisting
    # ---------------------------------------------------------------
    old = r"""  $mr.querySelector('#t-save').onclick=()=>{
    const txt=$mr.querySelector('#t-text').value.trim(); if(!txt)return;
    t.text=txt; t.houseId=$mr.querySelector('#t-house').value||null; t.status=$mr.querySelector('#t-status').value;
    t.doneAt=t.status==='done'?now():null; t.updatedAt=now(); persist.tasks(); closeSheet(); render();
  };"""
    new = r"""  $mr.querySelector('#t-save').onclick=async()=>{
    const txt=$mr.querySelector('#t-text').value.trim(); if(!txt)return;
    t.text=txt; t.houseId=$mr.querySelector('#t-house').value||null; t.status=$mr.querySelector('#t-status').value;
    t.doneAt=t.status==='done'?now():null; t.updatedAt=now();
    if(!(await vaultAlignRecord(t,['text'],t.houseId))){ toast('Unlock the vault to save that'); return; }
    persist.tasks(); closeSheet(); render();
  };"""
    edits.append((old, new, "openEditTask(): seal on save"))

    # ---------------------------------------------------------------
    # Edit 6: add spec — seal before persisting
    # ---------------------------------------------------------------
    old = r"""  $mr.querySelector('#s-save').onclick=()=>{
    const label=$mr.querySelector('#s-label').value.trim(); if(!label){$mr.querySelector('#s-label').focus();return;}
    h.specs=h.specs||[];
    h.specs.push({id:uid(),category:$mr.querySelector('#s-cat').value,room:$mr.querySelector('#s-room').value.trim(),
      label,value:$mr.querySelector('#s-val').value.trim(),note:$mr.querySelector('#s-note').value.trim(),createdAt:now()});
    h.updatedAt=now(); persist.houses(); closeSheet(); render(); toast('Spec added');
  };"""
    new = r"""  $mr.querySelector('#s-save').onclick=async()=>{
    const label=$mr.querySelector('#s-label').value.trim(); if(!label){$mr.querySelector('#s-label').focus();return;}
    h.specs=h.specs||[];
    const ns={id:uid(),category:$mr.querySelector('#s-cat').value,room:$mr.querySelector('#s-room').value.trim(),
      label,value:$mr.querySelector('#s-val').value.trim(),note:$mr.querySelector('#s-note').value.trim(),createdAt:now()};
    h.specs.push(ns);
    if(!(await vaultAlignRecord(ns,['room','label','value','note'],h.id))){ h.specs.pop(); toast('Unlock the vault to add that'); return; }
    h.updatedAt=now(); persist.houses(); closeSheet(); render(); toast('Spec added');
  };"""
    edits.append((old, new, "openSpecSheet(): seal new spec"))

    # ---------------------------------------------------------------
    # Edit 7: site notes autosave — seal, then persist
    # ---------------------------------------------------------------
    old = r"""    const saveHn=()=>{ const h=houseById(hnId); if(h){ h.notes=hnFull.value; h.updatedAt=now(); persist.houses(); } };"""
    new = r"""    /* VAULT_TOGGLE — seal first, persist second. If we die in between, the edit
       is lost rather than written to disk in the clear. */
    const saveHn=()=>{ const h=houseById(hnId); if(!h) return;
      h.notes=hnFull.value; h.updatedAt=now();
      if(isProtected(hnId)) vaultAlignRecord(h,['notes'],hnId).then(ok=>{ if(ok) persist.houses(); });
      else persist.houses(); };"""
    edits.append((old, new, "bind(): seal site notes before persisting"))

    # ---------------------------------------------------------------
    # Edit 8: note autosave — seal, then persist
    # ---------------------------------------------------------------
    old = r"""  if(id==='new'){
    // promote the new note to a saved one so we don't duplicate on next autosave
    const nn={id:uid(),title,body,houseId,important,createdAt:now(),updatedAt:now()};
    notes.push(nn); _lastAutosavedNewId=nn.id; persist.notes();
  } else {
    const n=notes.find(x=>x.id===id);
    if(n){ n.title=title; n.body=body; n.houseId=houseId; n.important=important; n.updatedAt=now(); persist.notes(); }
  }"""
    new = r"""  /* VAULT_TOGGLE — into a protected project, seal before persisting. This runs
     synchronously from render(), so the write is deferred to the seal's promise
     rather than being made async: a crash mid-edit loses the edit, never leaks it. */
  const saveNoteRec=(n)=>{
    if(isProtected(n.houseId)) vaultAlignRecord(n,['title','body'],n.houseId).then(ok=>{ if(ok) persist.notes(); });
    else persist.notes();
  };
  if(id==='new'){
    // promote the new note to a saved one so we don't duplicate on next autosave
    const nn={id:uid(),title,body,houseId,important,createdAt:now(),updatedAt:now()};
    notes.push(nn); _lastAutosavedNewId=nn.id; saveNoteRec(nn);
  } else {
    const n=notes.find(x=>x.id===id);
    if(n){ n.title=title; n.body=body; n.houseId=houseId; n.important=important; n.updatedAt=now(); saveNoteRec(n); }
  }"""
    edits.append((old, new, "autosaveOpenNote(): seal before persisting"))

    # ---------------------------------------------------------------
    # Edit 9: explicit note save
    # ---------------------------------------------------------------
    old = r"""function doSaveNote(id){
  const title=$app.querySelector('#note-title').value.trim();
  const body=$app.querySelector('#note-body').value;
  const houseId=$app.querySelector('#note-house').value||null;
  const important=$app.querySelector('#note-important').checked;
  if(!title && !body.trim()){ go('notes'); return; }
  if(id==='new'){ notes.push({id:uid(),title,body,houseId,important,createdAt:now(),updatedAt:now()}); }
  else{ const n=notes.find(x=>x.id===id); if(n){ n.title=title; n.body=body; n.houseId=houseId; n.important=important; n.updatedAt=now(); } }
  persist.notes(); go('notes'); toast('Saved');
}"""
    new = r"""async function doSaveNote(id){
  const title=$app.querySelector('#note-title').value.trim();
  const body=$app.querySelector('#note-body').value;
  const houseId=$app.querySelector('#note-house').value||null;
  const important=$app.querySelector('#note-important').checked;
  if(!title && !body.trim()){ go('notes'); return; }
  let rec;
  if(id==='new'){ rec={id:uid(),title,body,houseId,important,createdAt:now(),updatedAt:now()}; notes.push(rec); }
  else{ rec=notes.find(x=>x.id===id); if(rec){ rec.title=title; rec.body=body; rec.houseId=houseId; rec.important=important; rec.updatedAt=now(); } }
  /* VAULT_TOGGLE — align with wherever it now lives, then write. Moving a note
     into a protected project seals it; moving one out unseals it. */
  if(rec && !(await vaultAlignRecord(rec,['title','body'],houseId))){ toast('Unlock the vault to save that'); return; }
  persist.notes(); go(houseId&&isProtected(houseId)?'house':'notes', houseId&&isProtected(houseId)?houseId:null); toast('Saved');
}"""
    edits.append((old, new, "doSaveNote(): seal on save"))

    # ---------------------------------------------------------------
    # Edit 10-13: every photo write path through photoPutFor()
    # ---------------------------------------------------------------
    old = r"""      const blob=await downscale(file); const id=uid();
      await photoPut({id,blob,houseId,createdAt:now()});"""
    new = r"""      const blob=await downscale(file); const id=uid();
      await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});"""
    edits.append((old, new, "handlePhoto(): photoPutFor()"))

    old = r"""      await photoPut({id,blob,houseId,createdAt:now(),cropped:true});"""
    new = r"""      await photoPutFor(houseId,{id,blob,houseId,createdAt:now(),cropped:true});"""
    edits.append((old, new, "crop editor: photoPutFor()"))

    old = r"""    const rec=await photoGet(pid); if(!rec) throw new Error('missing photo');
    const url=URL.createObjectURL(rec.blob);
    const img=new Image();
    await new Promise((res,rej)=>{ img.onload=res; img.onerror=rej; img.src=url; });
    const c=document.createElement('canvas'); c.width=img.height; c.height=img.width;
    const ctx=c.getContext('2d');
    ctx.translate(c.width/2,c.height/2); ctx.rotate(Math.PI/2); ctx.drawImage(img,-img.width/2,-img.height/2);
    URL.revokeObjectURL(url);
    const blob=await new Promise(res=>c.toBlob(res,'image/jpeg',0.9));
    if(!blob) throw new Error('encode failed');
    await photoPut({id:pid,blob,houseId:rec.houseId,createdAt:rec.createdAt});
    if(_objUrls.has(pid)){ URL.revokeObjectURL(_objUrls.get(pid)); _objUrls.delete(pid); }"""
    new = r"""    const rec=await photoGet(pid); if(!rec) throw new Error('missing photo');
    /* VAULT_TOGGLE — a sealed record has no .blob to read; photoURL() decrypts it. */
    const url=await photoURL(pid); if(!url) throw new Error('cannot open photo');
    const img=new Image();
    await new Promise((res,rej)=>{ img.onload=res; img.onerror=rej; img.src=url; });
    const c=document.createElement('canvas'); c.width=img.height; c.height=img.width;
    const ctx=c.getContext('2d');
    ctx.translate(c.width/2,c.height/2); ctx.rotate(Math.PI/2); ctx.drawImage(img,-img.width/2,-img.height/2);
    const blob=await new Promise(res=>c.toBlob(res,'image/jpeg',0.9));
    if(!blob) throw new Error('encode failed');
    /* photoPutFor() revokes and drops the stale object URL for this id. */
    await photoPutFor(rec.houseId,{id:pid,blob,houseId:rec.houseId,createdAt:rec.createdAt});"""
    edits.append((old, new, "rotatePhoto(): decrypt-aware read + photoPutFor()"))

    old = r"""    await photoPut({id:newId,blob,houseId:an.houseId,createdAt:now()});"""
    new = r"""    await photoPutFor(an.houseId,{id:newId,blob,houseId:an.houseId,createdAt:now()});"""
    edits.append((old, new, "saveAnnotation(): photoPutFor()"))

    # ---------------------------------------------------------------
    # Edit 14: bind() — the delete escape on the locked screen
    # ---------------------------------------------------------------
    old = r"""  const vLockNow=$app.querySelector('[data-vault-lock-now]');
  if(vLockNow) vLockNow.onclick=()=>{ vaultRelock(); toast('Locked'); };"""
    new = r"""  const vLockNow=$app.querySelector('[data-vault-lock-now]');
  if(vLockNow) vLockNow.onclick=()=>{ vaultRelock(); toast('Locked'); };
  $app.querySelectorAll('[data-vault-del]').forEach(b=>b.onclick=()=>vaultDeleteLocked(b.dataset.vaultDel));"""
    edits.append((old, new, "bind(): delete-locked-project escape"))

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
    js_path = Path("/tmp/_notebuilt_vault4_check.js")
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

    print("\n✅ Vault 4/5 applied: protect on/off, encrypt-in-place, no plaintext writes.")
    print("   Next: fix_vault5_backup.py")

if __name__ == "__main__":
    main()
