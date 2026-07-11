#!/usr/bin/env python3
"""
Notebuilt — Chunk 11: Important notes + project-linked notebook
Run this from the same folder as your index.html:
    python3 fix_chunk11_important_notes.py

Adds:
  - A "Mark as Important" flag on any note
  - The Notes tab pins an "Important" section at the top, everything else below
  - A project's detail screen now shows a "Notebook" section listing notes
    linked to that project (with an "Add note" shortcut that pre-links it),
    so quick notes are visible both from the main Notes tab and from inside
    a project
  - The existing per-project "Site Notes" scratchpad section is relabeled
    "Site Notes" to avoid confusion with the new Notebook section
  - Delete-from-inside-a-note already existed (with confirmation) and is
    untouched by this chunk

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
MARKER = "CHUNK11_IMPORTANT_NOTES"  # already-applied guard

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

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: icon set — add a filled star for the Important badge
    # ---------------------------------------------------------------
    old1 = """  note:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5h9l4 4V20.5H6z"/><path d="M14.5 3.5V8h4.5M9 13h6M9 16.5h6"/></svg>',"""
    new1 = """  note:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3.5h9l4 4V20.5H6z"/><path d="M14.5 3.5V8h4.5M9 13h6M9 16.5h6"/></svg>',
  /* CHUNK11_IMPORTANT_NOTES */
  star:'<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.9 5.8 21.2 7 14.2 2 9.3l7.1-.7L12 2z"/></svg>',"""
    edits.append((old1, new1, "icon set: add I.star"))

    # ---------------------------------------------------------------
    # Edit 2: global state — track a pending house-link for a new note
    # ---------------------------------------------------------------
    old2 = "let notes  = load(K.notes,[]);"
    new2 = "let notes  = load(K.notes,[]);\nlet pendingNoteHouseId=null;"
    edits.append((old2, new2, "global state: pendingNoteHouseId"))

    # ---------------------------------------------------------------
    # Edit 3: renderNotes() — shared note-card renderer + pinned Important section
    # ---------------------------------------------------------------
    old3 = """function renderNotes(){
  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">Notebook</span><h1>Notes</h1></div>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;
  if(!notes.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn't belong to a single house — ideas, supplier info, measurements.</div></div>`;
  const cards=[...notes].sort((a,b)=>b.updatedAt-a.updatedAt).map(n=>{
    const h=n.houseId?houseById(n.houseId):null;
    const body=(n.body||'').replace(/\\s+/g,' ').trim();
    return `<div class="card" data-note="${n.id}">
      <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${esc(n.title||'Untitled')}</div>
      ${body?`<div class="muted truncate" style="font-size:13px;margin-top:2px">${esc(body)}</div>`:''}</div></div>
      <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${relDate(n.updatedAt)}${h?` · <span style="color:var(--brass)">${esc(h.name)}</span>`:''}</div>
    </div>`;
  }).join('');
  return head+`<div class="wrap">${cards}</div>`;
}"""
    new3 = """function noteCardHtml(n){
  const h=n.houseId?houseById(n.houseId):null;
  const body=(n.body||'').replace(/\\s+/g,' ').trim();
  return `<div class="card" data-note="${n.id}">
    <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${n.important?`<span style="color:var(--brass)">${I.star}</span> `:''}${esc(n.title||'Untitled')}</div>
    ${body?`<div class="muted truncate" style="font-size:13px;margin-top:2px">${esc(body)}</div>`:''}</div></div>
    <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${relDate(n.updatedAt)}${h?` · <span style="color:var(--brass)">${esc(h.name)}</span>`:''}</div>
  </div>`;
}

function renderNotes(){
  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">Notebook</span><h1>Notes</h1></div>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;
  if(!notes.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn't belong to a single house — ideas, supplier info, measurements.</div></div>`;
  const sorted=[...notes].sort((a,b)=>b.updatedAt-a.updatedAt);
  const important=sorted.filter(n=>n.important);
  const rest=sorted.filter(n=>!n.important);
  const impBlock=important.length?`<div class="sec-head"><span class="label" style="color:var(--brass)">Important</span><span class="rule"></span><span class="count">${important.length}</span></div>${important.map(noteCardHtml).join('')}`:'';
  return head+`<div class="wrap">${impBlock}${rest.map(noteCardHtml).join('')}</div>`;
}"""
    edits.append((old3, new3, "renderNotes(): shared card renderer + pinned Important section"))

    # ---------------------------------------------------------------
    # Edit 4: renderNote() — Important checkbox + pre-linked house from project screen
    # ---------------------------------------------------------------
    old4 = """function renderNote(id){
  const isNew=id==='new';
  const n=isNew?{title:'',body:'',houseId:null}:notes.find(x=>x.id===id)||{title:'',body:'',houseId:null};
  const opts=houses.map(h=>`<option value="${h.id}" ${n.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${isNew?'New note':'Note'}</span><h1>Note</h1></div>
    <button class="btn sm primary" data-save-note="${isNew?'new':n.id}">Save</button>
  </div>
  <div class="wrap">
    <div class="field"><input class="input" id="note-title" placeholder="Title" value="${esc(n.title)}" style="font-family:var(--serif);font-size:19px"></div>
    <div class="field"><textarea class="input" id="note-body" placeholder="Write…" style="min-height:240px">${esc(n.body)}</textarea></div>
    <div class="field"><label>Link to house</label>
      <select class="input" id="note-house"><option value="">— none —</option>${opts}</select></div>
    ${isNew?'':`<button class="btn danger block" data-del-note="${n.id}">${I.trash} Delete note</button>`}
  </div>`;
}"""
    new4 = """function renderNote(id){
  const isNew=id==='new';
  const presetHouseId=pendingNoteHouseId; pendingNoteHouseId=null;
  const n=isNew?{title:'',body:'',houseId:presetHouseId,important:false}:notes.find(x=>x.id===id)||{title:'',body:'',houseId:null,important:false};
  const opts=houses.map(h=>`<option value="${h.id}" ${n.houseId===h.id?'selected':''}>${esc(h.name)}</option>`).join('');
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${isNew?'New note':'Note'}</span><h1>Note</h1></div>
    <button class="btn sm primary" data-save-note="${isNew?'new':n.id}">Save</button>
  </div>
  <div class="wrap">
    <div class="field"><input class="input" id="note-title" placeholder="Title" value="${esc(n.title)}" style="font-family:var(--serif);font-size:19px"></div>
    <div class="field"><label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-family:var(--mono);letter-spacing:.05em;text-transform:uppercase;font-size:12.5px;color:var(--brass)"><input type="checkbox" id="note-important" ${n.important?'checked':''} style="width:22px;height:22px;accent-color:var(--brass)"> Mark as Important</label></div>
    <div class="field"><textarea class="input" id="note-body" placeholder="Write…" style="min-height:220px">${esc(n.body)}</textarea></div>
    <div class="field"><label>Link to house</label>
      <select class="input" id="note-house"><option value="">— none —</option>${opts}</select></div>
    ${isNew?'':`<button class="btn danger block" data-del-note="${n.id}">${I.trash} Delete note</button>`}
  </div>`;
}"""
    edits.append((old4, new4, "renderNote(): Important checkbox + house pre-link"))

    # ---------------------------------------------------------------
    # Edit 5: doSaveNote() — persist the Important flag
    # ---------------------------------------------------------------
    old5 = """function doSaveNote(id){
  const title=$app.querySelector('#note-title').value.trim();
  const body=$app.querySelector('#note-body').value;
  const houseId=$app.querySelector('#note-house').value||null;
  if(!title && !body.trim()){ go('notes'); return; }
  if(id==='new'){ notes.push({id:uid(),title,body,houseId,createdAt:now(),updatedAt:now()}); }
  else{ const n=notes.find(x=>x.id===id); if(n){ n.title=title; n.body=body; n.houseId=houseId; n.updatedAt=now(); } }
  persist.notes(); go('notes'); toast('Saved');
}"""
    new5 = """function doSaveNote(id){
  const title=$app.querySelector('#note-title').value.trim();
  const body=$app.querySelector('#note-body').value;
  const houseId=$app.querySelector('#note-house').value||null;
  const important=$app.querySelector('#note-important').checked;
  if(!title && !body.trim()){ go('notes'); return; }
  if(id==='new'){ notes.push({id:uid(),title,body,houseId,important,createdAt:now(),updatedAt:now()}); }
  else{ const n=notes.find(x=>x.id===id); if(n){ n.title=title; n.body=body; n.houseId=houseId; n.important=important; n.updatedAt=now(); } }
  persist.notes(); go('notes'); toast('Saved');
}"""
    edits.append((old5, new5, "doSaveNote(): persist Important flag"))

    # ---------------------------------------------------------------
    # Edit 6: renderHouse() — define notebookBlock (linked notes + Add note)
    # ---------------------------------------------------------------
    old6 = """  const houseTasks=tasks.filter(t=>t.houseId===id).sort((a,b)=>(a.status==='done')-(b.status==='done')||b.createdAt-a.createdAt);
  const taskBlock=`<div class="sec-head"><span class="label">To-dos</span><span class="rule"></span><span class="count">${houseTasks.filter(t=>t.status!=='done').length} open</span></div>
    ${houseTasks.length?houseTasks.map(taskRow).join(''):'<div class="card muted" style="text-align:center;padding:18px">No to-dos for this house.</div>'}
    <button class="btn block sm" data-add-house-task style="margin-top:4px">${I.plus} Add to-do</button>`;"""
    new6 = """  const houseTasks=tasks.filter(t=>t.houseId===id).sort((a,b)=>(a.status==='done')-(b.status==='done')||b.createdAt-a.createdAt);
  const taskBlock=`<div class="sec-head"><span class="label">To-dos</span><span class="rule"></span><span class="count">${houseTasks.filter(t=>t.status!=='done').length} open</span></div>
    ${houseTasks.length?houseTasks.map(taskRow).join(''):'<div class="card muted" style="text-align:center;padding:18px">No to-dos for this house.</div>'}
    <button class="btn block sm" data-add-house-task style="margin-top:4px">${I.plus} Add to-do</button>`;

  const houseNotes=notes.filter(n=>n.houseId===id).sort((a,b)=>(b.important-a.important)||(b.updatedAt-a.updatedAt));
  const notebookBlock=`<div class="sec-head"><span class="label">Notebook</span><span class="rule"></span><span class="count">${houseNotes.length}</span></div>
    ${houseNotes.length?houseNotes.map(noteCardHtml).join(''):'<div class="card muted" style="text-align:center;padding:18px">No notes for this project yet.</div>'}
    <button class="btn block sm" data-add-note-house="${h.id}" style="margin-top:4px">${I.plus} Add note</button>`;"""
    edits.append((old6, new6, "renderHouse(): define notebookBlock"))

    # ---------------------------------------------------------------
    # Edit 7: renderHouse() — relabel Site Notes + insert notebookBlock
    # ---------------------------------------------------------------
    old7 = """    <div class="sec-head" data-open-house-notes="${h.id}" style="cursor:pointer"><span class="label">Notes</span><span class="rule"></span>${I.chevronR}</div>
    <div class="card" data-open-house-notes="${h.id}" style="cursor:pointer">${h.notes?`<div style="white-space:pre-wrap;color:var(--paper-dim);font-size:14px;max-height:3.6em;overflow:hidden">${esc(h.notes.slice(0,180))}${h.notes.length>180?'…':''}</div>`:`<div class="muted" style="font-size:14px">Tap to add site notes, measurements, reminders…</div>`}</div>

    ${taskBlock}"""
    new7 = """    <div class="sec-head" data-open-house-notes="${h.id}" style="cursor:pointer"><span class="label">Site Notes</span><span class="rule"></span>${I.chevronR}</div>
    <div class="card" data-open-house-notes="${h.id}" style="cursor:pointer">${h.notes?`<div style="white-space:pre-wrap;color:var(--paper-dim);font-size:14px;max-height:3.6em;overflow:hidden">${esc(h.notes.slice(0,180))}${h.notes.length>180?'…':''}</div>`:`<div class="muted" style="font-size:14px">Tap to add site notes, measurements, reminders…</div>`}</div>

    ${notebookBlock}

    ${taskBlock}"""
    edits.append((old7, new7, "renderHouse(): relabel Site Notes + insert Notebook section"))

    # ---------------------------------------------------------------
    # Edit 8: bind() — wire "Add note" on the project screen
    # ---------------------------------------------------------------
    old8 = """  const addHT=$app.querySelector('[data-add-house-task]'); if(addHT) addHT.onclick=()=>openTaskSheet(view.param);"""
    new8 = """  const addHT=$app.querySelector('[data-add-house-task]'); if(addHT) addHT.onclick=()=>openTaskSheet(view.param);
  const addNoteH=$app.querySelector('[data-add-note-house]'); if(addNoteH) addNoteH.onclick=()=>{ pendingNoteHouseId=addNoteH.dataset.addNoteHouse; go('note','new'); };"""
    edits.append((old8, new8, "bind(): wire Add note on project screen"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk11_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check. Review the diff manually.")
        result = None

    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 11 applied successfully: Important notes + project-linked notebook.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
