#!/usr/bin/env python3
"""
Notebuilt — Chunk 8: Redacted project share (export)
Run this from the same folder as your index.html:
    python3 fix_chunk8_share_project.py

Adds a Share button to each project's detail screen. Tapping it opens a
checklist (Address / Site notes / Photos / To-dos — specs and the project
name are always included) and generates a separate, dedicated JSON file
(distinct from your full app backup) via the phone's native share sheet,
falling back to a plain download if Web Share isn't available.

This is EXPORT only — importing a shared project on another device is a
separate, later chunk.

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
MARKER = "CHUNK8_SHARE_PROJECT"  # already-applied guard

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
    # Edit 1: icon set — add a share icon
    # ---------------------------------------------------------------
    old1 = """  edit:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 5l5 5M4 20l1-4L16 5l4 4L9 20z"/></svg>',"""
    new1 = """  edit:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 5l5 5M4 20l1-4L16 5l4 4L9 20z"/></svg>',
  /* CHUNK8_SHARE_PROJECT */
  share:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M12 4l-4 4M12 4l4 4"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',"""
    edits.append((old1, new1, "icon set: add I.share"))

    # ---------------------------------------------------------------
    # Edit 2: renderHouse() topbar — add Share button
    # ---------------------------------------------------------------
    old2 = """  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">Project</span><h1 class="truncate">${esc(h.name)}</h1></div>
    <button class="icon-btn" data-edit-house="${h.id}" aria-label="Edit project">${I.edit}</button>
  </div>"""
    new2 = """  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">Project</span><h1 class="truncate">${esc(h.name)}</h1></div>
    <button class="icon-btn" data-share-house="${h.id}" aria-label="Share project">${I.share}</button>
    <button class="icon-btn" data-edit-house="${h.id}" aria-label="Edit project">${I.edit}</button>
  </div>"""
    edits.append((old2, new2, "renderHouse(): add Share button to topbar"))

    # ---------------------------------------------------------------
    # Edit 3: bind() — wire the Share button
    # ---------------------------------------------------------------
    old3 = """  $app.querySelectorAll('[data-edit-house]').forEach(b=>b.onclick=()=>openHouseSheet(houseById(b.dataset.editHouse)));"""
    new3 = """  $app.querySelectorAll('[data-edit-house]').forEach(b=>b.onclick=()=>openHouseSheet(houseById(b.dataset.editHouse)));
  $app.querySelectorAll('[data-share-house]').forEach(b=>b.onclick=()=>openShareSheet(b.dataset.shareHouse));"""
    edits.append((old3, new3, "bind(): wire Share button"))

    # ---------------------------------------------------------------
    # Edit 4: add openShareSheet() + doShareHouse() right after openHouseSheet()
    # ---------------------------------------------------------------
    old4 = "function openHouseSheet(edit=null){"
    new4 = """function openShareSheet(houseId){
  const h=houseById(houseId); if(!h)return;
  sheet(`<h2>Share "${esc(h.name)}"</h2>
    <div class="muted" style="font-size:13px;margin-bottom:14px">Creates a file another Notebuilt user can import as a new project. Specs and the project name are always included.</div>
    <div class="field"><label style="display:flex;align-items:center;gap:10px;cursor:pointer"><input type="checkbox" id="sh-addr" style="width:20px;height:20px;accent-color:var(--brass)"> Address</label></div>
    <div class="field"><label style="display:flex;align-items:center;gap:10px;cursor:pointer"><input type="checkbox" id="sh-notes" checked style="width:20px;height:20px;accent-color:var(--brass)"> Site notes</label></div>
    <div class="field"><label style="display:flex;align-items:center;gap:10px;cursor:pointer"><input type="checkbox" id="sh-photos" style="width:20px;height:20px;accent-color:var(--brass)"> Photos (${(h.photos||[]).length})</label></div>
    <div class="field"><label style="display:flex;align-items:center;gap:10px;cursor:pointer"><input type="checkbox" id="sh-tasks" style="width:20px;height:20px;accent-color:var(--brass)"> To-dos</label></div>
    <button class="btn primary block" id="sh-go">${I.share} Share project</button>`);
  $mr.querySelector('#sh-go').onclick=()=>doShareHouse(houseId,{
    address:$mr.querySelector('#sh-addr').checked,
    notes:$mr.querySelector('#sh-notes').checked,
    photos:$mr.querySelector('#sh-photos').checked,
    tasks:$mr.querySelector('#sh-tasks').checked
  });
}

async function doShareHouse(houseId,opts){
  const h=houseById(houseId); if(!h)return;
  closeSheet();
  toast('Preparing share…');
  try{
    const project={
      name:h.name, status:h.status, jobType:h.jobType||'',
      specs:(h.specs||[]).map(s=>({category:s.category,room:s.room,label:s.label,value:s.value,note:s.note}))
    };
    if(opts.address) project.address=h.address||'';
    if(opts.notes) project.notes=h.notes||'';
    if(opts.tasks){
      project.tasks=tasks.filter(t=>t.houseId===houseId).map(t=>({text:t.text,status:t.status}));
    }
    if(opts.photos && (h.photos||[]).length){
      const photoData={};
      for(const pid of h.photos){
        const rec=await photoGet(pid);
        if(rec) photoData[pid]={b64:await blobToB64(rec.blob)};
      }
      project.photos=photoData;
    }
    const dump={ app:'notebuilt-project-share', version:1, exportedAt:now(), project };
    const json=JSON.stringify(dump);
    const filename='notebuilt-'+(h.name||'project').toLowerCase().replace(/[^a-z0-9]+/g,'-').slice(0,40)+'-'+todayKey()+'.json';
    const file=new File([json],filename,{type:'application/json'});
    if(navigator.share && navigator.canShare && navigator.canShare({files:[file]})){
      await navigator.share({files:[file], title:'Notebuilt project: '+h.name});
      toast('Shared');
    }else{
      const blob=new Blob([json],{type:'application/json'});
      const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
      a.download=filename; a.click();
      setTimeout(()=>URL.revokeObjectURL(a.href),1000);
      toast('Downloaded');
    }
  }catch(err){
    if(err && err.name==='AbortError'){ toast('Share cancelled'); return; }
    toast('Could not share project');
  }
}

function openHouseSheet(edit=null){"""
    edits.append((old4, new4, "add openShareSheet() + doShareHouse()"))

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
    js_path = Path("/tmp/_notebuilt_chunk8_check.js")
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

    print("\n✅ Chunk 8 applied successfully: redacted project share (export).")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
