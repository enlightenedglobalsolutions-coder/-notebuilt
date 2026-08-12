#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — an imported file cannot inject HTML
Run from the same folder as index.html:
    python3 fix_import_safe.py

THE BUG (audit-verified; re-anchored against HEAD c9141cb)
----------------------------------------------------------
`importData` takes `d.categories` verbatim — no shape validation — and
`c.icon` / `c.id` then reach innerHTML unescaped. The in-app icon field
carries maxlength=4; an import bypasses that entirely, so the 4-character
ceiling that made this look survivable does not apply to the actual
attack path.

SCOPE CORRECTION — the brief names categories; the same imports feed two
more sinks of the identical class, and both were verified against the
file:

  * `class="chip status-${h.status}"` at L1287 and L1365 — unescaped, and
    `h.status` comes verbatim from **importSharedProject** (`p.status
    ||'active'`), which is the path the brief itself calls out as the one
    strangers will use once marketing starts.
  * `class="punch ${t.status}"` at L1246 — same, from a full restore.

Shipping a fix that escapes the category icon while leaving `status`
open, reachable from the very same shared file the gate describes, would
declare this closed while it is not. They are fixed together.

Checked and NOT a sink, so deliberately untouched:
  * `s.category` — grouped through the constant SPEC_CATS
    (`SPEC_CATS.filter(c=>specsByCat[c])`), so a value from a file never
    reaches the heading. Note in passing: an imported spec whose category
    is not one of the constants renders nowhere at all. Pre-existing, and
    a data-visibility question rather than a security one.
  * `settings.*` — `sortHouses`/`units` are only ever compared, never
    interpolated.

THE FIX — both layers
---------------------
1. **Escape every sink.** `c.icon` (3 direct + 2 via `categoryIcon()`),
   `c.id` (5 attributes), `h.status` (2), `t.status`/`t.id` (1 each).

2. **Validate on the way in.** `importUnsafeField()` walks the parsed
   file before anything is committed and refuses ids that are not a safe
   charset and statuses that are not plain lowercase words — covering
   every `data-*="${…id}"` attribute in one place instead of thirty.
   `importSanitizeCategories()` then coerces label/icon to strings and
   caps the icon at 4, matching the in-app rule.

**Reject, don't rewrite.** Ids are referential — `h.photos[]`, `h.cover`,
`t.houseId`, `n.houseId` all point at them — so silently rewriting a
hostile id would break the references it appears in. Refusing the whole
import keeps the existing no-partial-restore guarantee and leaves the
device untouched. Every id this app has ever minted is `uid()` (a UUID)
or a short literal like `construction`, so a legitimate file always
passes and still restores byte-identical.

The label cap is deliberately generous (200) rather than tight: the
in-app label field has no maxlength, so a tight cap would silently
truncate a legitimate long category name and break byte-identity on
restore. The label is escaped at every sink, so its length is a sanity
bound, not the defence.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "IMPORT_SAFE"


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

    edits = []

    # ---------------------------------------------------------------
    # LAYER 1 — escape every sink.
    # ---------------------------------------------------------------
    old_task = """    <button class="punch ${t.status}" data-punch="${t.id}" aria-label="${STATUS_LABEL[t.status]} — tap to advance">${icon}</button>"""
    new_task = """    <button class="punch ${esc(t.status)}" data-punch="${esc(t.id)}" aria-label="${esc(STATUS_LABEL[t.status]||t.status||'')} — tap to advance">${icon}</button>"""
    edits.append((old_task, new_task, "escape t.status / t.id (punch button)"))

    old_chip = """    ${categories.map(c=>`<button class="chip-filter ${categoryFilter===c.id?'active':''}" data-cat-filter="${c.id}">${c.icon} ${esc(c.label)}</button>`).join('')}"""
    new_chip = """    ${categories.map(c=>`<button class="chip-filter ${categoryFilter===c.id?'active':''}" data-cat-filter="${esc(c.id)}">${esc(c.icon)} ${esc(c.label)}</button>`).join('')}"""
    edits.append((old_chip, new_chip, "escape c.id / c.icon (category filter chips)"))

    old_badge = """        <span class="cat-badge" title="${esc(categoryLabel(h.category))}">${categoryIcon(h.category)}</span>
        <span class="chip status-${h.status}">${esc(h.status)}</span></div>"""
    new_badge = """        <span class="cat-badge" title="${esc(categoryLabel(h.category))}">${esc(categoryIcon(h.category))}</span>
        <span class="chip status-${esc(h.status)}">${esc(h.status)}</span></div>"""
    edits.append((old_badge, new_badge, "escape categoryIcon / h.status (project card)"))

    old_row = """    <div class="row" style="margin:10px 0 2px"><span class="cat-badge" data-open-cat-picker="${h.id}" style="cursor:pointer" title="Tap to move to another category">${categoryIcon(h.category)}</span><span class="chip status-${h.status}">${esc(h.status)}</span>"""
    new_row = """    <div class="row" style="margin:10px 0 2px"><span class="cat-badge" data-open-cat-picker="${esc(h.id)}" style="cursor:pointer" title="Tap to move to another category">${esc(categoryIcon(h.category))}</span><span class="chip status-${esc(h.status)}">${esc(h.status)}</span>"""
    edits.append((old_row, new_row, "escape categoryIcon / h.status (project header)"))

    old_sel = """    <div class="field"><label>Category</label><select class="input" id="h-category">${categories.map(c=>`<option value="${c.id}" ${cat===c.id?'selected':''}>${c.icon} ${esc(c.label)}</option>`).join('')}</select></div>"""
    new_sel = """    <div class="field"><label>Category</label><select class="input" id="h-category">${categories.map(c=>`<option value="${esc(c.id)}" ${cat===c.id?'selected':''}>${esc(c.icon)} ${esc(c.label)}</option>`).join('')}</select></div>"""
    edits.append((old_sel, new_sel, "escape c.id / c.icon (project category select)"))

    old_move = """    ${categories.map(c=>`<button class="btn block" data-move-cat="${c.id}" style="justify-content:flex-start;gap:10px;margin-bottom:8px">${c.icon} ${esc(c.label)}${h.category===c.id?' '+I.check:''}</button>`).join('')}`);"""
    new_move = """    ${categories.map(c=>`<button class="btn block" data-move-cat="${esc(c.id)}" style="justify-content:flex-start;gap:10px;margin-bottom:8px">${esc(c.icon)} ${esc(c.label)}${h.category===c.id?' '+I.check:''}</button>`).join('')}`);"""
    edits.append((old_move, new_move, "escape c.id / c.icon (move-to-category sheet)"))

    old_editor = """      <input class="input" style="width:50px;text-align:center;padding:8px;flex:none" value="${esc(c.icon)}" data-cat-icon="${c.id}" maxlength="4">
      <input class="input grow" value="${esc(c.label)}" data-cat-label="${c.id}">"""
    new_editor = """      <input class="input" style="width:50px;text-align:center;padding:8px;flex:none" value="${esc(c.icon)}" data-cat-icon="${esc(c.id)}" maxlength="4">
      <input class="input grow" value="${esc(c.label)}" data-cat-label="${esc(c.id)}">"""
    edits.append((old_editor, new_editor, "escape c.id (category editor inputs)"))

    # ---------------------------------------------------------------
    # LAYER 2 — validate on the way in.
    # ---------------------------------------------------------------
    old_helpers = """/* CHUNK22_IMPORT_SHARED_PROJECT */
async function importSharedProject(e){"""
    new_helpers = """/* ============================================================
   IMPORT_SAFE — a file is not a trusted input, whoever sent it.
   Everything below runs on data that arrived from disk: a full backup, or
   a shared project from another person. Escaping at the sinks is the
   defence; this is the second layer, and the place where the thirty-odd
   `data-*="${...id}"` attributes get covered once instead of thirty times.
   Ids are REFERENTIAL — h.photos[], h.cover, t.houseId, n.houseId all
   point at them — so a hostile id is refused, never rewritten: rewriting
   would break the very references it appears in. Every id this app mints
   is uid() or a short literal, so a real file always passes.
   ============================================================ */
const IMPORT_ID_RE     = /^[A-Za-z0-9._:-]{1,64}$/;
const IMPORT_STATUS_RE = /^[a-z]{1,16}$/;
function importOkId(v){ return typeof v==='string' && IMPORT_ID_RE.test(v); }
function importOkStatus(v){ return v==null || v==='' || (typeof v==='string' && IMPORT_STATUS_RE.test(v)); }
function importCap(v,max){ return String(v==null?'':v).slice(0,max); }

/* Returns a human phrase naming the first bad value, or null when clean. */
function importUnsafeField(d){
  for(const c of (Array.isArray(d.categories)?d.categories:[])){
    if(!c || typeof c!=='object' || !importOkId(c.id)) return 'a category id';
  }
  for(const h of (Array.isArray(d.houses)?d.houses:[])){
    if(!h || typeof h!=='object' || !importOkId(h.id)) return 'a project id';
    if(!importOkStatus(h.status)) return 'a project status';
    if(h.cover!=null && !importOkId(h.cover)) return 'a cover photo id';
    for(const pid of (Array.isArray(h.photos)?h.photos:[])) if(!importOkId(pid)) return 'a photo id';
    for(const s of (Array.isArray(h.specs)?h.specs:[])){
      if(!s || typeof s!=='object' || !importOkId(s.id)) return 'a spec id';
    }
  }
  for(const t of (Array.isArray(d.tasks)?d.tasks:[])){
    if(!t || typeof t!=='object' || !importOkId(t.id)) return 'a to-do id';
    if(!importOkStatus(t.status)) return 'a to-do status';
  }
  for(const n of (Array.isArray(d.notes)?d.notes:[])){
    if(!n || typeof n!=='object' || !importOkId(n.id)) return 'a note id';
  }
  for(const pid of Object.keys(d.photos||{})) if(!importOkId(pid)) return 'a photo id';
  return null;
}

/* Ids are already proven safe by the time this runs; this coerces the two
   free-text fields. The icon cap matches the in-app maxlength=4 exactly.
   The label cap is deliberately loose — the in-app label field has no
   maxlength, so a tight cap would silently truncate a legitimate name and
   break byte-identical restore. Length is a sanity bound here, not the
   defence; esc() at every sink is the defence. Key order is preserved so
   a legitimate file still round-trips byte-for-byte. */
function importSanitizeCategories(arr){
  return arr.map(c=>({
    id:    c.id,
    label: importCap(c.label,200),
    icon:  importCap(c.icon,4)
  }));
}

/* CHUNK22_IMPORT_SHARED_PROJECT */
async function importSharedProject(e){"""
    edits.append((old_helpers, new_helpers, "IMPORT_SAFE helpers"))

    # importData: reject before anything is committed
    old_gate = """  const m=backupManifest(d);"""
    new_gate = """  /* IMPORT_SAFE — refuse a hostile value before the manifest is even shown,
     so nothing on this device is touched and no passphrase is asked for. */
  const badField=importUnsafeField(d);
  if(badField){
    reset();
    alert('Could not restore: this file contains '+badField+' that is not a valid value.\\n\\n'
         +'Nothing on this device was touched.');
    return;
  }
  const m=backupManifest(d);"""
    edits.append((old_gate, new_gate, "importData(): reject unsafe ids/statuses up front"))

    old_cats = """    if(Array.isArray(d.categories) && d.categories.length){ categories=d.categories; persist.categories(); }"""
    new_cats = """    if(Array.isArray(d.categories) && d.categories.length){ categories=importSanitizeCategories(d.categories); persist.categories(); }"""
    edits.append((old_cats, new_cats, "importData(): sanitize categories on commit"))

    # importSharedProject: ids are regenerated, but status and text are verbatim
    old_share = """      id:newId, name:p.name, category,
      status:p.status||'active', jobType:p.jobType||'',"""
    new_share = """      /* IMPORT_SAFE — the ids here are all freshly minted below, so the risk
         is the free-text and the status, which arrive verbatim from whoever
         sent the file. status lands in a class attribute; anything that is
         not a plain lowercase word is not a status. */
      id:newId, name:importCap(p.name,200), category,
      status:importOkStatus(p.status)&&p.status?p.status:'active', jobType:importCap(p.jobType,40),"""
    edits.append((old_share, new_share, "importSharedProject(): clamp status + text"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # Mutation guard: no unescaped category/status sink may survive.
    for stray, why in [
        ("${c.icon}", "c.icon still reaches innerHTML unescaped"),
        ('data-cat-filter="${c.id}"', "c.id still unescaped in an attribute"),
        ('value="${c.id}"', "c.id still unescaped in an attribute"),
        ('data-move-cat="${c.id}"', "c.id still unescaped in an attribute"),
        ('data-cat-icon="${c.id}"', "c.id still unescaped in an attribute"),
        ('data-cat-label="${c.id}"', "c.id still unescaped in an attribute"),
        ("status-${h.status}", "h.status still unescaped in a class attribute"),
        ('class="punch ${t.status}"', "t.status still unescaped in a class attribute"),
        ("${categoryIcon(h.category)}", "categoryIcon() still reaches innerHTML unescaped"),
    ]:
        if stray in working:
            fail(f"{why} — found {stray!r}")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: no unescaped category icon/id or status sink remains")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_import_safe_check.js")
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

    print("\n✅ IMPORT_SAFE applied: sinks escaped, hostile ids and statuses refused at the door.")


if __name__ == "__main__":
    main()
