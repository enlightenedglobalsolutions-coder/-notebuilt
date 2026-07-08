#!/usr/bin/env python3
"""
Notebuilt — Chunk 1: Project sorting + Job Type field
Run this from the same folder as your index.html:
    python3 fix_chunk1_sort_jobtype.py

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
MARKER = "CHUNK1_SORT_JOBTYPE"  # already-applied guard

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
    # Edit 1: constants — add JOB_TYPES + SORT_OPTIONS after HOUSE_STATUS
    # ---------------------------------------------------------------
    old1 = "const HOUSE_STATUS=['active','quoting','done'];"
    new1 = (
        "const HOUSE_STATUS=['active','quoting','done'];\n"
        "/* CHUNK1_SORT_JOBTYPE */\n"
        "const JOB_TYPES=['paneling','flooring','trim','painting','drywall','electrical','plumbing','general'];\n"
        "const JOB_TYPE_LABEL={paneling:'Paneling',flooring:'Flooring',trim:'Trim / Finish Carpentry',painting:'Painting',drywall:'Drywall',electrical:'Electrical',plumbing:'Plumbing',general:'General / Other'};\n"
        "const SORT_OPTIONS=[\n"
        "  {id:'updated',label:'Last updated'},\n"
        "  {id:'created',label:'Date created (newest)'},\n"
        "  {id:'alpha',label:'Alphabetical (A\\u2013Z)'},\n"
        "  {id:'status',label:'Status'},\n"
        "  {id:'jobtype',label:'Job type'},\n"
        "  {id:'open',label:'Open to-dos (most first)'}\n"
        "];\n"
        "function sortHousesList(list){\n"
        "  const mode=settings.sortHouses||'updated';\n"
        "  const statusOrder={active:0,quoting:1,done:2};\n"
        "  const openCount=h=>tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;\n"
        "  const arr=[...list];\n"
        "  if(mode==='created') arr.sort((a,b)=>(b.createdAt||0)-(a.createdAt||0));\n"
        "  else if(mode==='alpha') arr.sort((a,b)=>(a.name||'').localeCompare(b.name||''));\n"
        "  else if(mode==='status') arr.sort((a,b)=>(statusOrder[a.status]??9)-(statusOrder[b.status]??9)||(b.updatedAt-a.updatedAt));\n"
        "  else if(mode==='jobtype') arr.sort((a,b)=>(JOB_TYPE_LABEL[a.jobType]||'').localeCompare(JOB_TYPE_LABEL[b.jobType]||'')||(b.updatedAt-a.updatedAt));\n"
        "  else if(mode==='open') arr.sort((a,b)=>openCount(b)-openCount(a)||(b.updatedAt-a.updatedAt));\n"
        "  else arr.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));\n"
        "  return arr;\n"
        "}"
    )
    edits.append((old1, new1, "constants: JOB_TYPES / SORT_OPTIONS / sortHousesList()"))

    # ---------------------------------------------------------------
    # Edit 2: settings default — add sortHouses preference
    # ---------------------------------------------------------------
    old2 = "let settings = load(K.settings,{ pinHash:null, pinSalt:null });"
    new2 = (
        "let settings = load(K.settings,{ pinHash:null, pinSalt:null });\n"
        "if(!settings.sortHouses) settings.sortHouses='updated';"
    )
    edits.append((old2, new2, "settings: default sortHouses preference"))

    # ---------------------------------------------------------------
    # Edit 3: renderHouses() — sort button in topbar + use sortHousesList + jobtype chip
    # ---------------------------------------------------------------
    old3 = """function renderHouses(){
  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">Job sites</span><h1>Projects</h1></div>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;
  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No houses yet</div><div>Add a house to keep its paint colors, flooring, photos and to-dos in one place.</div></div>`;
  const cards=[...houses].sort((a,b)=>b.updatedAt-a.updatedAt).map(h=>{
    const open=tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;
    return `<div class="card house-card" data-house="${h.id}">
      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:''}>${h.cover?'':`<div class="blueprint"></div>${I.house}`}</div>
      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:''}</div>
        <span class="chip status-${h.status}">${esc(h.status)}</span></div>
        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:''}</div>
      </div></div>`;
  }).join('');
  return head+`<div class="wrap">${cards}</div>`;
}"""
    new3 = """function renderHouses(){
  const sortLabel=(SORT_OPTIONS.find(o=>o.id===(settings.sortHouses||'updated'))||SORT_OPTIONS[0]).label;
  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">Job sites</span><h1>Projects</h1></div>
    <button class="icon-btn" data-sort-houses aria-label="Sort projects: ${esc(sortLabel)}">${I.square}</button>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;
  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No houses yet</div><div>Add a house to keep its paint colors, flooring, photos and to-dos in one place.</div></div>`;
  const cards=sortHousesList(houses).map(h=>{
    const open=tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;
    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:'';
    return `<div class="card house-card" data-house="${h.id}">
      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:''}>${h.cover?'':`<div class="blueprint"></div>${I.house}`}</div>
      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:''}</div>
        <span class="chip status-${h.status}">${esc(h.status)}</span></div>
        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${jt?`${esc(jt)} · `:''}${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:''}</div>
      </div></div>`;
  }).join('');
  return head+`<div class="wrap">${cards}</div>`;
}"""
    edits.append((old3, new3, "renderHouses(): sort button + sortHousesList() + jobtype chip"))

    # ---------------------------------------------------------------
    # Edit 4: renderHouse() detail — show job type chip next to status
    # ---------------------------------------------------------------
    old4 = """    <div class="row" style="margin:10px 0 2px"><span class="chip status-${h.status}">${esc(h.status)}</span>${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:''}</div>"""
    new4 = """    <div class="row" style="margin:10px 0 2px"><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:''}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:''}</div>"""
    edits.append((old4, new4, "renderHouse(): job type chip on detail screen"))

    # ---------------------------------------------------------------
    # Edit 5: openHouseSheet() — add Job type select + save + create defaults
    # ---------------------------------------------------------------
    old5 = """function openHouseSheet(edit=null){
  const h=edit||{};
  sheet(`<h2>${edit?'Edit project':'New project'}</h2>
    <div class="field"><label>Name</label><input class="input" id="h-name" placeholder="e.g. Maple St reno" value="${esc(h.name||'')}"></div>
    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(h.address||'')}"></div>
    <div class="field"><label>Status</label><select class="input" id="h-status">${HOUSE_STATUS.map(s=>`<option ${h.status===s?'selected':''}>${s}</option>`).join('')}</select></div>
    <button class="btn primary block" id="h-save">${edit?'Save':'Create house'}</button>
    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete house</button>`:''}`);
  setTimeout(()=>$mr.querySelector('#h-name').focus(),50);
  $mr.querySelector('#h-save').onclick=()=>{
    const name=$mr.querySelector('#h-name').value.trim(); if(!name){$mr.querySelector('#h-name').focus();return;}
    const addr=$mr.querySelector('#h-addr').value.trim(), st=$mr.querySelector('#h-status').value;
    if(edit){ edit.name=name; edit.address=addr; edit.status=st; edit.updatedAt=now(); persist.houses(); closeSheet(); render(); toast('Saved'); }
    else{ const nh={id:uid(),name,address:addr,status:st,specs:[],photos:[],cover:null,notes:'',createdAt:now(),updatedAt:now()};
      houses.push(nh); persist.houses(); closeSheet(); go('house',nh.id); toast('Project added'); }
  };"""
    new5 = """function openHouseSheet(edit=null){
  const h=edit||{};
  sheet(`<h2>${edit?'Edit project':'New project'}</h2>
    <div class="field"><label>Name</label><input class="input" id="h-name" placeholder="e.g. Maple St reno" value="${esc(h.name||'')}"></div>
    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(h.address||'')}"></div>
    <div class="field"><label>Status</label><select class="input" id="h-status">${HOUSE_STATUS.map(s=>`<option ${h.status===s?'selected':''}>${s}</option>`).join('')}</select></div>
    <div class="field"><label>Job type</label><select class="input" id="h-jobtype">${JOB_TYPES.map(j=>`<option value="${j}" ${h.jobType===j?'selected':''}>${JOB_TYPE_LABEL[j]}</option>`).join('')}</select></div>
    <button class="btn primary block" id="h-save">${edit?'Save':'Create house'}</button>
    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete house</button>`:''}`);
  setTimeout(()=>$mr.querySelector('#h-name').focus(),50);
  $mr.querySelector('#h-save').onclick=()=>{
    const name=$mr.querySelector('#h-name').value.trim(); if(!name){$mr.querySelector('#h-name').focus();return;}
    const addr=$mr.querySelector('#h-addr').value.trim(), st=$mr.querySelector('#h-status').value, jt=$mr.querySelector('#h-jobtype').value;
    if(edit){ edit.name=name; edit.address=addr; edit.status=st; edit.jobType=jt; edit.updatedAt=now(); persist.houses(); closeSheet(); render(); toast('Saved'); }
    else{ const nh={id:uid(),name,address:addr,status:st,jobType:jt,specs:[],photos:[],cover:null,notes:'',createdAt:now(),updatedAt:now()};
      houses.push(nh); persist.houses(); closeSheet(); go('house',nh.id); toast('Project added'); }
  };"""
    edits.append((old5, new5, "openHouseSheet(): job type field + save + create default"))

    # ---------------------------------------------------------------
    # Edit 6: bind() — wire the sort button to open the sort-picker sheet
    # ---------------------------------------------------------------
    old6 = """  $app.querySelectorAll('[data-house]').forEach(c=>c.onclick=()=>go('house',c.dataset.house));
  $app.querySelectorAll('[data-edit-house]').forEach(b=>b.onclick=()=>openHouseSheet(houseById(b.dataset.editHouse)));"""
    new6 = """  $app.querySelectorAll('[data-house]').forEach(c=>c.onclick=()=>go('house',c.dataset.house));
  $app.querySelectorAll('[data-edit-house]').forEach(b=>b.onclick=()=>openHouseSheet(houseById(b.dataset.editHouse)));
  const sortBtn=$app.querySelector('[data-sort-houses]'); if(sortBtn) sortBtn.onclick=openSortSheet;"""
    edits.append((old6, new6, "bind(): wire sort button"))

    # ---------------------------------------------------------------
    # Edit 7: add openSortSheet() function — place right before openHouseSheet
    # ---------------------------------------------------------------
    old7 = "function openHouseSheet(edit=null){"
    new7 = """function openSortSheet(){
  const cur=settings.sortHouses||'updated';
  sheet(`<h2>Sort projects</h2>
    ${SORT_OPTIONS.map(o=>`<button class="btn block" data-sort-opt="${o.id}" style="justify-content:space-between;margin-bottom:8px">${esc(o.label)}${o.id===cur?I.check:''}</button>`).join('')}`);
  $mr.querySelectorAll('[data-sort-opt]').forEach(b=>b.onclick=()=>{
    settings.sortHouses=b.dataset.sortOpt; persist.settings(); closeSheet(); render(); toast('Sorted: '+(SORT_OPTIONS.find(o=>o.id===b.dataset.sortOpt)||{}).label);
  });
}

function openHouseSheet(edit=null){"""
    edits.append((old7, new7, "add openSortSheet() function"))

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
    js_path = Path("/tmp/_notebuilt_chunk1_check.js")
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
            # restore from backup since we already wrote the bad file
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 1 applied successfully: project sorting + job type field.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
