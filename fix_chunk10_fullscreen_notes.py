#!/usr/bin/env python3
"""
Notebuilt — Chunk 10: full-screen project Notes editor
Run this from the same folder as your index.html:
    python3 fix_chunk10_fullscreen_notes.py

Tapping "Notes" (the section header or preview) on a project's detail
screen now opens a dedicated full-screen editor with its own Back button —
same pattern as every other screen in the app, so it feels consistent and
intuitive. The small in-page textarea is replaced with a preview (or a
"tap to add notes" hint when empty).

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
MARKER = "CHUNK10_FULLSCREEN_NOTES"  # already-applied guard

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
    # Edit 1: icon set — add a right-chevron to hint "this opens something"
    # ---------------------------------------------------------------
    old1 = """  back:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',"""
    new1 = """  back:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  /* CHUNK10_FULLSCREEN_NOTES */
  chevronR:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>',"""
    edits.append((old1, new1, "icon set: add I.chevronR"))

    # ---------------------------------------------------------------
    # Edit 2: render dispatch table — add the 'housenotes' view
    # ---------------------------------------------------------------
    old2 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch})[view.name]||renderToday;"""
    new2 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch,
            housenotes:renderHouseNotes})[view.name]||renderToday;"""
    edits.append((old2, new2, "render dispatch: add housenotes view"))

    # ---------------------------------------------------------------
    # Edit 3: renderHouse() — Notes section becomes a tap-to-open preview
    # ---------------------------------------------------------------
    old3 = """    <div class="sec-head"><span class="label">Notes</span><span class="rule"></span></div>
    <div class="card"><textarea class="input" data-house-notes placeholder="Site notes, measurements, reminders…" style="border:none;background:none;padding:0;min-height:70px">${esc(h.notes||'')}</textarea></div>"""
    new3 = """    <div class="sec-head" data-open-house-notes="${h.id}" style="cursor:pointer"><span class="label">Notes</span><span class="rule"></span>${I.chevronR}</div>
    <div class="card" data-open-house-notes="${h.id}" style="cursor:pointer">${h.notes?`<div style="white-space:pre-wrap;color:var(--paper-dim);font-size:14px;max-height:3.6em;overflow:hidden">${esc(h.notes.slice(0,180))}${h.notes.length>180?'…':''}</div>`:`<div class="muted" style="font-size:14px">Tap to add site notes, measurements, reminders…</div>`}</div>"""
    edits.append((old3, new3, "renderHouse(): Notes section becomes tap-to-open preview"))

    # ---------------------------------------------------------------
    # Edit 4: add renderHouseNotes() right after renderHouse's closing brace
    # (anchored to the NOTES section comment banner that already follows it)
    # ---------------------------------------------------------------
    old4 = """/* ============================================================
   NOTES
   ============================================================ */"""
    new4 = """/* ============================================================
   PROJECT NOTES — full-screen editor
   ============================================================ */
function renderHouseNotes(houseId){
  const h=houseById(houseId); if(!h) return renderHouses();
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow truncate">${esc(h.name)}</span><h1>Notes</h1></div>
  </div>
  <div class="wrap">
    <textarea class="input" data-house-notes-full="${h.id}" placeholder="Site notes, measurements, reminders…" style="min-height:calc(100vh - 170px);font-size:15px;line-height:1.5">${esc(h.notes||'')}</textarea>
  </div>`;
}

/* ============================================================
   NOTES
   ============================================================ */"""
    edits.append((old4, new4, "add renderHouseNotes() full-screen editor"))

    # ---------------------------------------------------------------
    # Edit 5: bind() — open the full-screen editor + its autosave
    # (replaces the old inline textarea's onblur wiring)
    # ---------------------------------------------------------------
    old5 = """  const hn=$app.querySelector('[data-house-notes]'); if(hn) hn.onblur=()=>{ const h=houseById(view.param); if(h){h.notes=hn.value;h.updatedAt=now();persist.houses();} };"""
    new5 = """  $app.querySelectorAll('[data-open-house-notes]').forEach(el=>el.onclick=()=>go('housenotes',el.dataset.openHouseNotes));
  const hnFull=$app.querySelector('[data-house-notes-full]');
  if(hnFull){
    const hnId=hnFull.dataset.houseNotesFull;
    const saveHn=()=>{ const h=houseById(hnId); if(h){ h.notes=hnFull.value; h.updatedAt=now(); persist.houses(); } };
    let hnTimer=null;
    hnFull.oninput=()=>{ clearTimeout(hnTimer); hnTimer=setTimeout(saveHn,400); };
    hnFull.onblur=()=>{ clearTimeout(hnTimer); saveHn(); };
  }"""
    edits.append((old5, new5, "bind(): open full-screen notes + autosave"))

    # ---------------------------------------------------------------
    # Edit 6: goBack() — return to the correct project, not just the list
    # ---------------------------------------------------------------
    old6 = """function goBack(){
  const to = ({house:'houses', note:'notes', search:'today'})[view.name] || 'today';
  go(to);
}"""
    new6 = """function goBack(){
  if(view.name==='housenotes'){ go('house', view.param); return; }
  const to = ({house:'houses', note:'notes', search:'today'})[view.name] || 'today';
  go(to);
}"""
    edits.append((old6, new6, "goBack(): housenotes returns to the same project"))

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
    js_path = Path("/tmp/_notebuilt_chunk10_check.js")
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

    print("\n✅ Chunk 10 applied successfully: full-screen project Notes editor.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
