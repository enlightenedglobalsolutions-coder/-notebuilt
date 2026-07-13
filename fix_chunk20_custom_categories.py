#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 20: fully custom categories
Run this from the same folder as your index.html:
    python3 fix_chunk20_custom_categories.py

Replaces the fixed 4-category list from Chunk 19 with a user-editable
one: rename any category, change its emoji, reorder them (up/down, more
reliable on mobile than drag-and-drop), add new ones, or delete ones you
don't want. Deleting a category never deletes projects in it \u2014 they
show under a new "Uncategorized" filter chip instead.

Also adds a quick "move to category" picker \u2014 tap the category badge
on an open project's detail page to relocate it in one or two taps,
without opening the full edit sheet.

"Manage categories" is reached via a new "\u2699\ufe0f Edit" chip at the end
of the filter row on the Projects screen.

Requires Chunk 19 (fix_chunk19_category_and_rename.py) already applied.

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
MARKER = "CHUNK20_CUSTOM_CATEGORIES"
PREREQ_MARKER = "CHUNK19_CATEGORY_SYSTEM"

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
    if PREREQ_MARKER not in text:
        fail("Chunk 19 doesn't look applied yet. Run fix_chunk19_category_and_rename.py first.")

    edits = []

    old_K_def = "const K = { houses:'pl.houses', tasks:'pl.tasks', notes:'pl.notes', settings:'pl.settings' };"
    new_K_def = "const K = { houses:'pl.houses', tasks:'pl.tasks', notes:'pl.notes', settings:'pl.settings', categories:'pl.categories' };"
    edits.append((old_K_def, new_K_def, 'K storage keys: add categories'))

    old_persist_def = 'const persist = { houses:()=>save(K.houses,houses), tasks:()=>save(K.tasks,tasks),\n                  notes:()=>save(K.notes,notes), settings:()=>save(K.settings,settings) };'
    new_persist_def = 'const persist = { houses:()=>save(K.houses,houses), tasks:()=>save(K.tasks,tasks),\n                  notes:()=>save(K.notes,notes), settings:()=>save(K.settings,settings),\n                  categories:()=>save(K.categories,categories) };'
    edits.append((old_persist_def, new_persist_def, 'persist object: add categories()'))

    old_cat_constants = "/* CHUNK19_CATEGORY_SYSTEM */\nconst CATEGORIES=['construction','apps','personal','other'];\nconst CATEGORY_LABEL={construction:'Construction',apps:'Apps & Code',personal:'Personal',other:'Other'};\nconst CATEGORY_ICON={construction:'🏗️',apps:'💻',personal:'📋',other:'📁'};\n"
    new_cat_constants = "/* CHUNK20_CUSTOM_CATEGORIES */\nlet categories = load(K.categories, [\n  {id:'construction', label:'Construction', icon:'🏗️'},\n  {id:'apps', label:'Apps & Code', icon:'💻'},\n  {id:'personal', label:'Personal', icon:'📋'},\n  {id:'other', label:'Other', icon:'📁'}\n]);\nfunction categoryById(id){ return categories.find(c=>c.id===id); }\nfunction categoryLabel(id){ const c=categoryById(id); return c?c.label:'Uncategorized'; }\nfunction categoryIcon(id){ const c=categoryById(id); return c?c.icon:'❓'; }\n"
    edits.append((old_cat_constants, new_cat_constants, 'categories become a user-editable list, not fixed constants'))

    old_sort_category_line = "else if(mode==='category') arr.sort((a,b)=>(CATEGORY_LABEL[a.category]||'').localeCompare(CATEGORY_LABEL[b.category]||'')||(b.updatedAt-a.updatedAt));"
    new_sort_category_line = "else if(mode==='category') arr.sort((a,b)=>(categoryLabel(a.category)||'').localeCompare(categoryLabel(b.category)||'')||(b.updatedAt-a.updatedAt));\n"
    edits.append((old_sort_category_line, new_sort_category_line, 'sort-by-category uses categoryLabel() helper'))

    old_renderHouses = 'function renderHouses(){\n  const sortLabel=(SORT_OPTIONS.find(o=>o.id===(settings.sortHouses||\'updated\'))||SORT_OPTIONS[0]).label;\n  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Projects</h1></div>\n    <button class="icon-btn" data-sort-houses aria-label="Sort projects: ${esc(sortLabel)}">${I.square}</button>\n    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;\n  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No projects yet</div><div>Add a project to keep its photos, notes and to-dos in one place — a job site, an app you\'re building, or anything else.</div></div>`;\n  const filterChips=`<div class="row" style="gap:8px;flex-wrap:wrap;margin:12px 0 2px">\n    <button class="chip-filter ${categoryFilter===\'all\'?\'active\':\'\'}" data-cat-filter="all">All</button>\n    ${CATEGORIES.map(c=>`<button class="chip-filter ${categoryFilter===c?\'active\':\'\'}" data-cat-filter="${c}">${CATEGORY_ICON[c]} ${CATEGORY_LABEL[c]}</button>`).join(\'\')}\n  </div>`;\n  const filtered=categoryFilter===\'all\'?houses:houses.filter(h=>h.category===categoryFilter);\n  const cards=filtered.length?sortHousesList(filtered).map(h=>{\n    const open=tasks.filter(t=>t.houseId===h.id&&t.status!==\'done\').length;\n    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:\'\';\n    return `<div class="card house-card" data-house="${h.id}">\n      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>\n      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:\'\'}</div>\n        <span class="cat-badge" title="${esc(CATEGORY_LABEL[h.category]||\'\')}">${CATEGORY_ICON[h.category]||\'\'}</span>\n        <span class="chip status-${h.status}">${esc(h.status)}</span></div>\n        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${jt?`${esc(jt)} · `:\'\'}${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:\'\'}</div>\n      </div></div>`;\n  }).join(\'\'):`<div class="empty" style="padding:40px 20px"><div class="t">No projects in this category</div><div>Switch categories above, or add a new one.</div></div>`;\n  return head+`<div class="wrap">${filterChips}${cards}</div>`;\n}'
    new_renderHouses = 'function renderHouses(){\n  const sortLabel=(SORT_OPTIONS.find(o=>o.id===(settings.sortHouses||\'updated\'))||SORT_OPTIONS[0]).label;\n  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Projects</h1></div>\n    <button class="icon-btn" data-sort-houses aria-label="Sort projects: ${esc(sortLabel)}">${I.square}</button>\n    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;\n  if(!houses.length) return head+`<div class="empty">${I.house}<div class="t">No projects yet</div><div>Add a project to keep its photos, notes and to-dos in one place — a job site, an app you\'re building, or anything else.</div></div>`;\n  const hasUncategorized=houses.some(h=>!categoryById(h.category));\n  const filterChips=`<div class="row" style="gap:8px;flex-wrap:wrap;margin:12px 0 2px">\n    <button class="chip-filter ${categoryFilter===\'all\'?\'active\':\'\'}" data-cat-filter="all">All</button>\n    ${categories.map(c=>`<button class="chip-filter ${categoryFilter===c.id?\'active\':\'\'}" data-cat-filter="${c.id}">${c.icon} ${esc(c.label)}</button>`).join(\'\')}\n    ${hasUncategorized?`<button class="chip-filter ${categoryFilter===\'__none__\'?\'active\':\'\'}" data-cat-filter="__none__">❓ Uncategorized</button>`:\'\'}\n    <button class="chip-filter" data-manage-categories>⚙️ Edit</button>\n  </div>`;\n  const filtered=categoryFilter===\'all\'?houses:(categoryFilter===\'__none__\'?houses.filter(h=>!categoryById(h.category)):houses.filter(h=>h.category===categoryFilter));\n  const cards=filtered.length?sortHousesList(filtered).map(h=>{\n    const open=tasks.filter(t=>t.houseId===h.id&&t.status!==\'done\').length;\n    const jt=h.jobType&&JOB_TYPE_LABEL[h.jobType]?JOB_TYPE_LABEL[h.jobType]:\'\';\n    return `<div class="card house-card" data-house="${h.id}">\n      <div class="house-cover" ${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>\n      <div class="hc-body"><div class="row"><div class="grow"><div class="hc-name">${esc(h.name)}</div>${h.address?`<div class="hc-addr truncate">${esc(h.address)}</div>`:\'\'}</div>\n        <span class="cat-badge" title="${esc(categoryLabel(h.category))}">${categoryIcon(h.category)}</span>\n        <span class="chip status-${h.status}">${esc(h.status)}</span></div>\n        <div class="meta mono" style="font-size:11px;color:var(--paper-faint);margin-top:8px">${jt?`${esc(jt)} · `:\'\'}${(h.specs||[]).length} specs · ${(h.photos||[]).length} photos${open?` · ${open} open`:\'\'}</div>\n      </div></div>`;\n  }).join(\'\'):`<div class="empty" style="padding:40px 20px"><div class="t">No projects in this category</div><div>Switch categories above, or add a new one.</div></div>`;\n  return head+`<div class="wrap">${filterChips}${cards}</div>`;\n}'
    edits.append((old_renderHouses, new_renderHouses, 'renderHouses(): dynamic filter chips, Uncategorized bucket, Edit entry point'))

    old_renderHouse_badge = '<div class="row" style="margin:10px 0 2px"><span class="cat-badge" title="${esc(CATEGORY_LABEL[h.category]||\'\')}">${CATEGORY_ICON[h.category]||\'\'}</span><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:\'\'}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:\'\'}</div>'
    new_renderHouse_badge = '<div class="row" style="margin:10px 0 2px"><span class="cat-badge" data-open-cat-picker="${h.id}" style="cursor:pointer" title="Tap to move to another category">${categoryIcon(h.category)}</span><span class="chip status-${h.status}">${esc(h.status)}</span>${h.jobType&&JOB_TYPE_LABEL[h.jobType]?`<span class="chip" style="color:var(--paper-dim)">${esc(JOB_TYPE_LABEL[h.jobType])}</span>`:\'\'}${h.address?`<span class="muted truncate" style="font-size:13px">${esc(h.address)}</span>`:\'\'}</div>'
    edits.append((old_renderHouse_badge, new_renderHouse_badge, 'renderHouse(): category badge becomes tappable quick-relocate'))

    old_openHouseSheet_catselect = '<div class="field"><label>Category</label><select class="input" id="h-category">${CATEGORIES.map(c=>`<option value="${c}" ${cat===c?\'selected\':\'\'}>${CATEGORY_ICON[c]} ${CATEGORY_LABEL[c]}</option>`).join(\'\')}</select></div>'
    new_openHouseSheet_catselect = '<div class="field"><label>Category</label><select class="input" id="h-category">${categories.map(c=>`<option value="${c.id}" ${cat===c.id?\'selected\':\'\'}>${c.icon} ${esc(c.label)}</option>`).join(\'\')}</select></div>'
    edits.append((old_openHouseSheet_catselect, new_openHouseSheet_catselect, 'openHouseSheet(): category dropdown from dynamic list'))

    old_bind_catfilter = "$app.querySelectorAll('[data-cat-filter]').forEach(b=>b.onclick=()=>{ categoryFilter=b.dataset.catFilter; render(); });"
    new_bind_catfilter = "$app.querySelectorAll('[data-cat-filter]').forEach(b=>b.onclick=()=>{ categoryFilter=b.dataset.catFilter; render(); });\n  $app.querySelectorAll('[data-manage-categories]').forEach(b=>b.onclick=openManageCategories);\n  $app.querySelectorAll('[data-open-cat-picker]').forEach(b=>b.onclick=()=>openCategoryPicker(b.dataset.openCatPicker));"
    edits.append((old_bind_catfilter, new_bind_catfilter, 'bind(): wire Manage Categories + quick-relocate picker'))

    old_insert = 'function openSpecSheet(houseId){'
    new_insert = '/* CHUNK20_CUSTOM_CATEGORIES */\nfunction openCategoryPicker(houseId){\n  const h=houseById(houseId); if(!h) return;\n  sheet(`<h2>Move to category</h2>\n    ${categories.map(c=>`<button class="btn block" data-move-cat="${c.id}" style="justify-content:flex-start;gap:10px;margin-bottom:8px">${c.icon} ${esc(c.label)}${h.category===c.id?\' \'+I.check:\'\'}</button>`).join(\'\')}`);\n  $mr.querySelectorAll(\'[data-move-cat]\').forEach(b=>b.onclick=()=>{\n    h.category=b.dataset.moveCat; h.updatedAt=now(); persist.houses(); closeSheet(); render(); toast(\'Moved to \'+categoryLabel(h.category));\n  });\n}\n\nfunction categoryRowsHtml(){\n  return categories.map((c,i)=>`<div class="card" style="margin-bottom:8px;padding:10px">\n    <div class="row" style="gap:8px;align-items:center">\n      <input class="input" style="width:50px;text-align:center;padding:8px;flex:none" value="${esc(c.icon)}" data-cat-icon="${c.id}" maxlength="4">\n      <input class="input grow" value="${esc(c.label)}" data-cat-label="${c.id}">\n    </div>\n    <div class="row" style="gap:8px;margin-top:8px;justify-content:flex-end">\n      <button class="btn sm" data-cat-up="${c.id}" ${i===0?\'disabled\':\'\'}>\\u2191</button>\n      <button class="btn sm" data-cat-down="${c.id}" ${i===categories.length-1?\'disabled\':\'\'}>\\u2193</button>\n      <button class="btn sm danger" data-cat-del="${c.id}">${I.trash} Delete</button>\n    </div>\n  </div>`).join(\'\');\n}\nfunction wireCategoryRows(){\n  $mr.querySelectorAll(\'[data-cat-icon]\').forEach(inp=>{\n    inp.onblur=()=>{ const c=categoryById(inp.dataset.catIcon); if(c){ c.icon=inp.value.trim()||\'\\ud83c\\udff7\\ufe0f\'; persist.categories(); render(); } };\n  });\n  $mr.querySelectorAll(\'[data-cat-label]\').forEach(inp=>{\n    inp.onblur=()=>{ const c=categoryById(inp.dataset.catLabel); if(c && inp.value.trim()){ c.label=inp.value.trim(); persist.categories(); render(); } };\n  });\n  $mr.querySelectorAll(\'[data-cat-up]\').forEach(b=>b.onclick=()=>moveCategory(b.dataset.catUp,-1));\n  $mr.querySelectorAll(\'[data-cat-down]\').forEach(b=>b.onclick=()=>moveCategory(b.dataset.catDown,1));\n  $mr.querySelectorAll(\'[data-cat-del]\').forEach(b=>b.onclick=()=>deleteCategory(b.dataset.catDel));\n}\nfunction moveCategory(id,dir){\n  const i=categories.findIndex(c=>c.id===id); if(i<0)return;\n  const j=i+dir; if(j<0||j>=categories.length)return;\n  [categories[i],categories[j]]=[categories[j],categories[i]];\n  persist.categories(); render(); openManageCategories();\n}\nfunction deleteCategory(id){\n  const affected=houses.filter(h=>h.category===id).length;\n  const msg=affected?`Delete this category? ${affected} project${affected===1?\'\':\'s\'} using it will show as Uncategorized \\u2014 nothing is deleted.`:\'Delete this category?\';\n  if(!confirm(msg)) return;\n  categories=categories.filter(c=>c.id!==id);\n  houses.forEach(h=>{ if(h.category===id) h.category=null; });\n  if(categoryFilter===id) categoryFilter=\'all\';\n  persist.categories(); persist.houses(); render(); openManageCategories();\n}\nfunction openManageCategories(){\n  sheet(`<h2>Categories</h2>\n    <div class="muted" style="font-size:12.5px;margin-bottom:12px">Rename, change the emoji, reorder, or remove categories. Projects in a deleted category show as Uncategorized instead of disappearing.</div>\n    <div id="cat-list">${categoryRowsHtml()}</div>\n    <div class="card" style="margin-top:4px;background:var(--ink-2)">\n      <div class="row" style="gap:8px;align-items:center">\n        <input class="input" style="width:50px;text-align:center;padding:8px;flex:none" placeholder="\\ud83c\\udff7\\ufe0f" id="cat-new-icon" maxlength="4">\n        <input class="input grow" placeholder="New category name" id="cat-new-label">\n      </div>\n      <button class="btn primary block sm" id="cat-new-save" style="margin-top:8px">${I.plus} Add category</button>\n    </div>`);\n  wireCategoryRows();\n  $mr.querySelector(\'#cat-new-save\').onclick=()=>{\n    const label=$mr.querySelector(\'#cat-new-label\').value.trim(); if(!label)return;\n    const icon=$mr.querySelector(\'#cat-new-icon\').value.trim()||\'\\ud83c\\udff7\\ufe0f\';\n    categories.push({id:uid(),label,icon});\n    persist.categories(); render();\n    openManageCategories();\n  };\n}\n\nfunction openSpecSheet(houseId){'
    edits.append((old_insert, new_insert, 'add category-management functions'))

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
    js_path = Path("/tmp/_notebuilt_chunk20_check.js")
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

    print("\n\u2705 Chunk 20 applied successfully: fully custom categories.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
