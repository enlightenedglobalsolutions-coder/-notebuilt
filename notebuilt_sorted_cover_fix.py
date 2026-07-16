#!/usr/bin/env python3
"""
Notebuilt fix-script — Sorted engine (v1) + cover-photo picker.

WHAT THIS DOES (purely additive — no existing behaviour changes):
  * Adds the reusable "Sorted" media engine block (self-contained, marker-delimited).
  * First feature built on it: a cover-photo picker.
      - Tap the big cover image at the top of a project  -> pick any photo as the cover.
      - Open any photo, tap the new star (top-left)       -> set that photo as the cover.
      - The current cover is starred in the picker grid.
  * The delete-falls-back-to-first-photo guard already existed and is untouched.

SAFETY:
  * Backs up index.html to index.html.bak.<timestamp> before touching anything.
  * Each anchor must match EXACTLY ONCE, or the whole script aborts and changes nothing.
  * Safe to re-run: if the engine is already present, it exits cleanly.

USAGE:
  python3 notebuilt_sorted_cover_fix.py /path/to/notebuilt/index.html
  (defaults to ./index.html if no path given)
"""

import sys, os, time, shutil

PATH = sys.argv[1] if len(sys.argv) > 1 else "index.html"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# ---- idempotency guard -------------------------------------------------------
if "SORTED ENGINE START" in src:
    print("Already applied (Sorted engine present). Nothing to do.")
    sys.exit(0)

edits = []  # (label, old, new)

# ---- 1. CSS: picker grid styles ---------------------------------------------
css_anchor = "  .house-cover svg{width:34px;height:34px;position:relative}\n"
css_add = css_anchor + """  /* ===== SORTED ENGINE — picker grid ===== */
  .sorted-grid{
    display:grid;grid-template-columns:repeat(3,1fr);gap:8px;
    margin-top:12px;max-height:60vh;overflow-y:auto;padding-bottom:4px;
  }
  .sorted-cell{
    position:relative;aspect-ratio:1/1;border-radius:var(--radius-sm);
    background:var(--ink-2) center/cover no-repeat;border:1px solid var(--line);
    padding:0;cursor:pointer;overflow:hidden;
  }
  .sorted-cell.is-current{border-color:var(--brass);box-shadow:0 0 0 2px var(--brass)}
  .sorted-star{
    position:absolute;top:5px;right:5px;display:grid;place-items:center;
    width:26px;height:26px;border-radius:50%;
    background:rgba(21,24,29,.72);color:var(--brass);
  }
  .sorted-star svg{width:16px;height:16px}
"""
edits.append(("CSS picker-grid styles", css_anchor, css_add))

# ---- 2. Sorted engine JS block ----------------------------------------------
engine_anchor = "/* fill in any cover/photo backgrounds from IndexedDB after render */"
engine_add = """/* ===== SORTED ENGINE START =====
   Sorted - reusable media-sorting engine, shared across EGS apps (Notebuilt, Kept, standalone Sorted).
   The engine never touches storage: the host passes media-item refs plus a resolve() that turns a
   ref into a displayable URL, and receives the user's choice via callback. The host owns persistence.
   First feature built on it: the cover-photo picker below. Later features (dedupe, corruption
   detection, integrity manifest) reuse this same list + resolve + grid spine. */
const Sorted=(function(){
  /* Open a picker sheet: a grid of media thumbnails, the current pick starred, tap to choose.
     opts = { items:[ref,...], resolve:ref=>Promise<url|null>, current:ref|null, title, onPick:ref=>void } */
  function pickGrid(opts){
    const items=(opts.items||[]);
    if(!items.length){ toast('No photos to choose from yet'); return; }
    const cur=opts.current;
    const cells=items.map(ref=>`<button class="sorted-cell${ref===cur?' is-current':''}" data-sorted-pick="${esc(ref)}" data-sorted-thumb="${esc(ref)}" aria-label="Choose photo">${ref===cur?`<span class="sorted-star">${I.star}</span>`:''}</button>`).join('');
    sheet(`<h2>${esc(opts.title||'Choose photo')}</h2><div class="sorted-grid">${cells}</div>`);
    $mr.querySelectorAll('[data-sorted-thumb]').forEach(async el=>{
      const u=await opts.resolve(el.getAttribute('data-sorted-thumb'));
      if(u) el.style.backgroundImage=`url(${u})`;
    });
    $mr.querySelectorAll('[data-sorted-pick]').forEach(el=>el.onclick=()=>{
      const ref=el.getAttribute('data-sorted-pick');
      closeSheet();
      if(opts.onPick) opts.onPick(ref);
    });
  }
  return { pickGrid };
})();

/* Cover-photo picker (first feature on the Sorted engine) */
function openCoverPicker(houseId){
  const h=houseById(houseId); if(!h) return;
  Sorted.pickGrid({
    items:(h.photos||[]),
    resolve:photoURL,
    current:h.cover,
    title:'Choose cover photo',
    onPick:(pid)=>{ h.cover=pid; h.updatedAt=now(); persist.houses(); render(); toast('Cover updated'); }
  });
}
/* Set the currently-viewed photo as the project cover, straight from the viewer */
function setViewerCover(){
  const pid=vw.photos[vw.index], h=houseById(vw.houseId);
  if(!h||!pid) return;
  h.cover=pid; h.updatedAt=now(); persist.houses();
  if(view.name==='house') render();
  toast('Set as cover');
}
/* ===== SORTED ENGINE END ===== */

/* fill in any cover/photo backgrounds from IndexedDB after render */"""
edits.append(("Sorted engine JS block", engine_anchor, engine_add))

# ---- 3. Make the project-detail cover tappable ------------------------------
hero_anchor = ('    <div class="house-cover" style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px" '
               '${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>')
hero_new = ('    <div class="house-cover" data-edit-cover="${h.id}" '
            'style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px;cursor:pointer" '
            '${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>')
edits.append(("Project-detail cover tappable", hero_anchor, hero_new))

# ---- 4. Wire the cover tap ---------------------------------------------------
bind_anchor = "  $app.querySelectorAll('.photo-grid .ph[data-photo]').forEach(el=>el.onclick=()=>openViewer(view.param, el.dataset.photo));"
bind_new = (bind_anchor + "\n"
            "  $app.querySelectorAll('[data-edit-cover]').forEach(el=>el.onclick=()=>openCoverPicker(el.dataset.editCover));")
edits.append(("Cover-tap binding", bind_anchor, bind_new))

# ---- 5a. Add the "set as cover" star to the photo viewer ---------------------
vactions_anchor = ('      <div class="v-actions">\n'
                   '        <button class="icon-btn" data-v-rotate aria-label="Rotate photo">${I.rotate}</button>')
vactions_new = ('      <div class="v-actions">\n'
                '        <button class="icon-btn" data-v-cover aria-label="Set as project cover">${I.star}</button>\n'
                '        <button class="icon-btn" data-v-rotate aria-label="Rotate photo">${I.rotate}</button>')
edits.append(("Viewer set-as-cover button", vactions_anchor, vactions_new))

# ---- 5b. Wire the viewer star ------------------------------------------------
vbind_anchor = "  $viewer.querySelector('[data-v-markup]').onclick=openAnnotate;"
vbind_new = (vbind_anchor + "\n"
             "  $viewer.querySelector('[data-v-cover]').onclick=setViewerCover;")
edits.append(("Viewer cover-button binding", vbind_anchor, vbind_new))

# ---- verify every anchor matches exactly once BEFORE writing anything --------
problems = []
for label, old, new in edits:
    n = src.count(old)
    if n != 1:
        problems.append(f"  [{label}] matched {n} times (need exactly 1)")

if problems:
    print("ABORTED — anchors did not match cleanly, nothing was changed:")
    print("\n".join(problems))
    print("\nYour file may differ from the version this script was built against.")
    print("Re-upload the current index.html so the script can be rebuilt to match.")
    sys.exit(1)

# ---- back up, then apply all edits ------------------------------------------
backup = f"{PATH}.bak.{int(time.time())}"
shutil.copy2(PATH, backup)

out = src
for label, old, new in edits:
    out = out.replace(old, new, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(out)

print("Applied cleanly. All 6 edits landed.")
print(f"Backup saved: {backup}")
print(f"File: {PATH}  ({len(out)} bytes, was {len(src)})")
