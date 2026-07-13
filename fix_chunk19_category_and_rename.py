#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 19: consistent "Project" wording + Category system
Run this from the same folder as your index.html:
    python3 fix_chunk19_category_and_rename.py

Two things in one pass:

1. Wording fix — several spots still said "house" after the bottom nav
   tab was renamed to "Projects": two form buttons, the "Link to house"
   note-form label, the search placeholder, the empty-state message, the
   Notes screen's description text, and the "Job sites" eyebrow label.

2. New Category field — Construction / Apps & Code / Personal / Other,
   chosen when creating a project, separate from the existing Job Type
   (which now only shows for Construction). Category gets filter chips
   on the Projects screen, a sort option, and a badge on each card.
   Existing projects auto-migrate to Construction.

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
MARKER = "CHUNK19_CATEGORY_SYSTEM"

def fail(msg):
    print(f"\n\u274c ABORTED \u2014 no changes were made.\n   Reason: {{msg}}\n")
    sys.exit(1)

def main():
    if not TARGET.exists():
        fail(f"{{TARGET}} not found in this folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("\u2705 Already applied \u2014 nothing to do.")
        return

    edits = []

    old1 = "const HOUSE_STATUS=['active','quoting','done'];\n/* CHUNK1_SORT_JOBTYPE */\nconst JOB_TYPES=['paneling','flooring','trim','painting','drywall','electrical','plumbing','general'];\nconst JOB_TYPE_LABEL={paneling:'Paneling',flooring:'Flooring',trim:'Trim / Finish Carpentry',painting:'Painting',drywall:'Drywall',electrical:'Electrical',plumbing:'Plumbing',general:'General / Other'};\nconst SORT_OPTIONS=[\n  {id:'updated',label:'Last updated'},\n  {id:'created',label:'Date created (newest)'},\n  {id:'alpha',label:'Alphabetical (A\\u2013Z)'},\n  {id:'status',label:'Status'},\n  {id:'jobtype',label:'Job type'},\n  {id:'open',label:'Open to-dos (most first)'}\n];\nfunction sortHousesList(list){\n  const mode=settings.sortHouses||'updated';\n  const statusOrder={active:0,quoting:1,done:2};\n  const openCount=h=>tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;\n  const arr=[...list];\n  if(mode==='created') arr.sort((a,b)=>(b.createdAt||0)-(a.createdAt||0));\n  else if(mode==='alpha') arr.sort((a,b)=>(a.name||'').localeCompare(b.name||''));\n  else if(mode==='status') arr.sort((a,b)=>(statusOrder[a.status]??9)-(statusOrder[b.status]??9)||(b.updatedAt-a.updatedAt));\n  else if(mode==='jobtype') arr.sort((a,b)=>(JOB_TYPE_LABEL[a.jobType]||'').localeCompare(JOB_TYPE_LABEL[b.jobType]||'')||(b.updatedAt-a.updatedAt));\n  else if(mode==='open') arr.sort((a,b)=>openCount(b)-openCount(a)||(b.updatedAt-a.updatedAt));\n  else arr.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));\n  return arr;\n}"
    new1 = "const HOUSE_STATUS=['active','quoting','done'];\n/* CHUNK1_SORT_JOBTYPE */\nconst JOB_TYPES=['paneling','flooring','trim','painting','drywall','electrical','plumbing','general'];\nconst JOB_TYPE_LABEL={paneling:'Paneling',flooring:'Flooring',trim:'Trim / Finish Carpentry',painting:'Painting',drywall:'Drywall',electrical:'Electrical',plumbing:'Plumbing',general:'General / Other'};\n/* CHUNK19_CATEGORY_SYSTEM */\nconst CATEGORIES=['construction','apps','personal','other'];\nconst CATEGORY_LABEL={construction:'Construction',apps:'Apps & Code',personal:'Personal',other:'Other'};\nconst CATEGORY_ICON={construction:'🏗️',apps:'💻',personal:'📋',other:'📁'};\nconst SORT_OPTIONS=[\n  {id:'updated',label:'Last updated'},\n  {id:'created',label:'Date created (newest)'},\n  {id:'alpha',label:'Alphabetical (A\\u2013Z)'},\n  {id:'status',label:'Status'},\n  {id:'category',label:'Category'},\n  {id:'jobtype',label:'Job type'},\n  {id:'open',label:'Open to-dos (most first)'}\n];\nlet categoryFilter='all';\nfunction sortHousesList(list){\n  const mode=settings.sortHouses||'updated';\n  const statusOrder={active:0,quoting:1,done:2};\n  const openCount=h=>tasks.filter(t=>t.houseId===h.id&&t.status!=='done').length;\n  const arr=[...list];\n  if(mode==='created') arr.sort((a,b)=>(b.createdAt||0)-(a.createdAt||0));\n  else if(mode==='alpha') arr.sort((a,b)=>(a.name||'').localeCompare(b.name||''));\n  else if(mode==='status') arr.sort((a,b)=>(statusOrder[a.status]??9)-(statusOrder[b.status]??9)||(b.updatedAt-a.updatedAt));\n  else if(mode==='category') arr.sort((a,b)=>(CATEGORY_LABEL[a.category]||'').localeCompare(CATEGORY_LABEL[b.category]||'')||(b.updatedAt-a.updatedAt));\n  else if(mode==='jobtype') arr.sort((a,b)=>(JOB_TYPE_LABEL[a.jobType]||'').localeCompare(JOB_TYPE_LABEL[b.jobType]||'')||(b.updatedAt-a.updatedAt));\n  else if(mode==='open') arr.sort((a,b)=>openCount(b)-openCount(a)||(b.updatedAt-a.updatedAt));\n  else arr.sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));\n  return arr;\n}"
    edits.append((old1, new1, 'constants: add CATEGORIES + category sort + categoryFilter state'))

    old2 = 'let houses = load(K.houses,[]);'
    new2 = "let houses = load(K.houses,[]);\nhouses.forEach(h=>{ if(!h.category) h.category='construction'; });"
    edits.append((old2, new2, 'migrate existing projects to Construction category'))

    old3 = 'function renderHouses(){\n  const sortLabel=(SORT_OPTIONS.find(o=>o.id===(settings.sortHouses||\'updated\'))||SORT_OPTIONS[0]).label;\n  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">Job sites</span><h1>Projects</h1></div>\n    <button class="icon-btn" data-sort-houses aria-label="Sort projects: ${esc(sortLabel)}">${I.square}</button>\n    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;\n  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No houses yet</div><div>Add a house to keep its paint colors, flooring, photos and to-dos in one place.</div></div>`;\n  const cards=sortHousesList(houses).map(h=>{\n    const open=tasks.filter(t=>t.houseId===h.id&&t.status!==\'done\').length;\n    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:\'\';\n    return `<div class="card house-card" data-house="${h.id}">\n      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>\n      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:\'\'}</div>\n        <span class="chip status-${h.status}">${esc(h.status)}</span></div>\n        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${jt?`${esc(jt)} · `:\'\'}${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:\'\'}</div>\n      </div></div>`;\n  }).join(\'\');\n  return head+`<div class="wrap">${cards}</div>`;\n}'
    new3 = 'function renderHouses(){\n  const sortLabel=(SORT_OPTIONS.find(o=>o.id===(settings.sortHouses||\'updated\'))||SORT_OPTIONS[0]).label;\n  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Projects</h1></div>\n    <button class="icon-btn" data-sort-houses aria-label="Sort projects: ${esc(sortLabel)}">${I.square}</button>\n    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;\n  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No projects yet</div><div>Add a project to keep its photos, notes and to-dos in one place — a job site, an app you\'re building, or anything else.</div></div>`;\n  const filterChips=`<div class="row" style="gap:8px;flex-wrap:wrap;margin:12px 0 2px">\n    <button class="chip-filter ${categoryFilter===\'all\'?\'active\':\'\'}" data-cat-filter="all">All</button>\n    ${CATEGORIES.map(c=>`<button class="chip-filter ${categoryFilter===c?\'active\':\'\'}" data-cat-filter="${c}">${CATEGORY_ICON[c]} ${CATEGORY_LABEL[c]}</button>`).join(\'\')}\n  </div>`;\n  const filtered=categoryFilter===\'all\'?houses:houses.filter(h=>h.category===categoryFilter);\n  const cards=filtered.length?sortHousesList(filtered).map(h=>{\n    const open=tasks.filter(t=>t.houseId===h.id&&t.status!==\'done\').length;\n    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:\'\';\n    return `<div class="card house-card" data-house="${h.id}">\n      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>\n      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:\'\'}</div>\n        <span class="cat-badge" title="${esc(CATEGORY_LABEL[h.category]||\'\')}">${CATEGORY_ICON[h.category]||\'\'}</span>\n        <span class="chip status-${h.status}">${esc(h.status)}</span></div>\n        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${jt?`${esc(jt)} · `:\'\'}${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:\'\'}</div>\n      </div></div>`;\n  }).join(\'\'):`<div class="empty" style="padding:40px 20px"><div class="t">No projects in this category</div><div>Switch categories above, or add a new one.</div></div>`;\n  return head+`<div class="wrap">${filterChips}${cards}</div>`;\n}'
    edits.append((old3, new3, 'renderHouses(): rename + filter chips + category badge'))

    old4 = '<div class="row" style="margin:10px 0 2px"><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:\'\'}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:\'\'}</div>'
    new4 = '<div class="row" style="margin:10px 0 2px"><span class="cat-badge" title="${esc(CATEGORY_LABEL[h.category]||\'\')}">${CATEGORY_ICON[h.category]||\'\'}</span><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:\'\'}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:\'\'}</div>'
    edits.append((old4, new4, 'renderHouse(): category badge on detail page'))

    old5 = 'function openHouseSheet(edit=null){\n  const h=edit||{};\n  sheet(`<h2>${edit?\'Edit project\':\'New project\'}</h2>\n    <div class="field"><label>Name</label><input class="input" id="h-name" placeholder="e.g. Maple St reno" value="${esc(h.name||\'\')}"></div>\n    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(h.address||\'\')}"></div>\n    <div class="field"><label>Status</label><select class="input" id="h-status">${HOUSE_STATUS.map(s=>`<option ${h.status===s?\'selected\':\'\'}>${s}</option>`).join(\'\')}</select></div>\n    <div class="field"><label>Job type</label><select class="input" id="h-jobtype">${JOB_TYPES.map(j=>`<option value="${j}" ${h.jobType===j?\'selected\':\'\'}>${JOB_TYPE_LABEL[j]}</option>`).join(\'\')}</select></div>\n    <button class="btn primary block" id="h-save">${edit?\'Save\':\'Create house\'}</button>\n    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete house</button>`:\'\'}`);\n  setTimeout(()=>$mr.querySelector(\'#h-name\').focus(),50);\n  $mr.querySelector(\'#h-save\').onclick=()=>{\n    const name=$mr.querySelector(\'#h-name\').value.trim(); if(!name){$mr.querySelector(\'#h-name\').focus();return;}\n    const addr=$mr.querySelector(\'#h-addr\').value.trim(), st=$mr.querySelector(\'#h-status\').value, jt=$mr.querySelector(\'#h-jobtype\').value;\n    if(edit){ edit.name=name; edit.address=addr; edit.status=st; edit.jobType=jt; edit.updatedAt=now(); persist.houses(); closeSheet(); render(); toast(\'Saved\'); }\n    else{ const nh={id:uid(),name,address:addr,status:st,jobType:jt,specs:[],photos:[],cover:null,notes:\'\',createdAt:now(),updatedAt:now()};\n      houses.push(nh); persist.houses(); closeSheet(); go(\'house\',nh.id); toast(\'Project added\'); }\n  };\n  if(edit) $mr.querySelector(\'#h-del\').onclick=()=>{\n    if(!confirm(`Delete "${edit.name}" and its specs? Photos and to-dos for it stay but unlink.`)) return;\n    (edit.photos||[]).forEach(pid=>photoDel(pid).catch(()=>{}));\n    houses=houses.filter(x=>x.id!==edit.id);\n    tasks.forEach(t=>{ if(t.houseId===edit.id) t.houseId=null; });\n    notes.forEach(nn=>{ if(nn.houseId===edit.id) nn.houseId=null; });\n    persist.houses(); persist.tasks(); persist.notes(); closeSheet(); go(\'houses\'); toast(\'Project deleted\');\n  };\n}'
    new5 = 'function openHouseSheet(edit=null){\n  const h=edit||{};\n  const cat=h.category||\'construction\';\n  sheet(`<h2>${edit?\'Edit project\':\'New project\'}</h2>\n    <div class="field"><label>Category</label><select class="input" id="h-category">${CATEGORIES.map(c=>`<option value="${c}" ${cat===c?\'selected\':\'\'}>${CATEGORY_ICON[c]} ${CATEGORY_LABEL[c]}</option>`).join(\'\')}</select></div>\n    <div class="field"><label>Name</label><input class="input" id="h-name" placeholder="e.g. Maple St reno" value="${esc(h.name||\'\')}"></div>\n    <div class="field"><label>Address (optional)</label><input class="input" id="h-addr" placeholder="123 Maple St" value="${esc(h.address||\'\')}"></div>\n    <div class="field"><label>Status</label><select class="input" id="h-status">${HOUSE_STATUS.map(s=>`<option ${h.status===s?\'selected\':\'\'}>${s}</option>`).join(\'\')}</select></div>\n    <div class="field" id="h-jobtype-field" style="${cat===\'construction\'?\'\':\'display:none\'}"><label>Job type</label><select class="input" id="h-jobtype">${JOB_TYPES.map(j=>`<option value="${j}" ${h.jobType===j?\'selected\':\'\'}>${JOB_TYPE_LABEL[j]}</option>`).join(\'\')}</select></div>\n    <button class="btn primary block" id="h-save">${edit?\'Save\':\'Create project\'}</button>\n    ${edit?`<button class="btn danger block" id="h-del" style="margin-top:10px">${I.trash} Delete project</button>`:\'\'}`);\n  setTimeout(()=>$mr.querySelector(\'#h-name\').focus(),50);\n  $mr.querySelector(\'#h-category\').onchange=()=>{\n    const show=$mr.querySelector(\'#h-category\').value===\'construction\';\n    $mr.querySelector(\'#h-jobtype-field\').style.display=show?\'\':\'none\';\n  };\n  $mr.querySelector(\'#h-save\').onclick=()=>{\n    const name=$mr.querySelector(\'#h-name\').value.trim(); if(!name){$mr.querySelector(\'#h-name\').focus();return;}\n    const category=$mr.querySelector(\'#h-category\').value;\n    const addr=$mr.querySelector(\'#h-addr\').value.trim(), st=$mr.querySelector(\'#h-status\').value, jt=$mr.querySelector(\'#h-jobtype\').value;\n    if(edit){ edit.name=name; edit.category=category; edit.address=addr; edit.status=st; edit.jobType=jt; edit.updatedAt=now(); persist.houses(); closeSheet(); render(); toast(\'Saved\'); }\n    else{ const nh={id:uid(),name,category,address:addr,status:st,jobType:jt,specs:[],photos:[],cover:null,notes:\'\',createdAt:now(),updatedAt:now()};\n      houses.push(nh); persist.houses(); closeSheet(); go(\'house\',nh.id); toast(\'Project added\'); }\n  };\n  if(edit) $mr.querySelector(\'#h-del\').onclick=()=>{\n    if(!confirm(`Delete "${edit.name}" and its specs? Photos and to-dos for it stay but unlink.`)) return;\n    (edit.photos||[]).forEach(pid=>photoDel(pid).catch(()=>{}));\n    houses=houses.filter(x=>x.id!==edit.id);\n    tasks.forEach(t=>{ if(t.houseId===edit.id) t.houseId=null; });\n    notes.forEach(nn=>{ if(nn.houseId===edit.id) nn.houseId=null; });\n    persist.houses(); persist.tasks(); persist.notes(); closeSheet(); go(\'houses\'); toast(\'Project deleted\');\n  };\n}'
    edits.append((old5, new5, 'openHouseSheet(): Category field + conditional Job Type + rename'))

    old6 = '  if(!notes.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn\'t belong to a single house — ideas, supplier info, measurements.</div></div>`;'
    new6 = '  if(!notes.length) return head+`<div class="empty">${I.note}<div class="t">No notes yet</div><div>Keep anything that doesn\'t belong to a single project — ideas, supplier info, measurements.</div></div>`;'
    edits.append((old6, new6, 'Notes empty state: house -> project'))

    old7 = '<div class="field"><label>Link to house</label>'
    new7 = '<div class="field"><label>Link to project</label>'
    edits.append((old7, new7, 'note form label: house -> project'))

    old8 = '<div class="grow"><input class="input" id="q" placeholder="Search houses, notes, to-dos…" autocomplete="off"></div>'
    new8 = '<div class="grow"><input class="input" id="q" placeholder="Search projects, notes, to-dos…" autocomplete="off"></div>'
    edits.append((old8, new8, 'search placeholder: houses -> projects'))

    old9 = "  const sortBtn=$app.querySelector('[data-sort-houses]'); if(sortBtn) sortBtn.onclick=openSortSheet;"
    new9 = "  const sortBtn=$app.querySelector('[data-sort-houses]'); if(sortBtn) sortBtn.onclick=openSortSheet;\n  $app.querySelectorAll('[data-cat-filter]').forEach(b=>b.onclick=()=>{ categoryFilter=b.dataset.catFilter; render(); });"
    edits.append((old9, new9, 'bind(): wire category filter chips'))

    old10 = '  .chip.status-active{color:var(--brass)}'
    new10 = '  .chip.status-active{color:var(--brass)}\n  /* CHUNK19_CATEGORY_SYSTEM */\n  .chip-filter{\n    font-family:var(--mono);font-size:11px;letter-spacing:.05em;\n    padding:6px 12px;border-radius:999px;border:1px solid var(--line-soft);\n    background:var(--ink-2);color:var(--paper-dim);white-space:nowrap;\n  }\n  .chip-filter.active{background:var(--brass);color:#231a07;border-color:var(--brass)}\n  .cat-badge{font-size:15px;line-height:1;flex:none}'
    edits.append((old10, new10, 'CSS: .chip-filter + .cat-badge'))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"\u270f\ufe0f  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit.")
    js_path = Path("/tmp/_notebuilt_chunk19_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("\u26a0\ufe0f  node not found \u2014 skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("\u2705 JS syntax check passed (node --check)")

    print("\n\u2705 Chunk 19 applied successfully: consistent Project wording + Category system.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
