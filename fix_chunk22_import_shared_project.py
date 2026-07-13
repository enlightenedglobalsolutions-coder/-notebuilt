#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 22: import a shared project
Run this from the same folder as your index.html:
    python3 fix_chunk22_import_shared_project.py

Completes the redacted-share feature from Chunk 8 — until now, "Share
project" could export a file, but there was no way to bring one *in* on
the receiving end. This adds that: a new "Import shared project" button
on the Support & Backup page (separate from "Restore," which replaces
your whole app — this only ever adds one new project, nothing else in
your app is touched).

Creates a brand-new project with fresh IDs for everything (the project
itself, every spec, every to-do, every photo) so there's no chance of
colliding with anything already in your app. Photos and to-dos import
only if the sender chose to include them when they shared it. New
project defaults to the Construction category if it still exists on your
device, otherwise Uncategorized.

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
MARKER = "CHUNK22_IMPORT_SHARED_PROJECT"

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
    # Edit 1: Support & Backup page — add the Import shared project UI
    # ---------------------------------------------------------------
    old1 = """    <div class="row" style="gap:10px;margin:10px 0 22px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>"""
    new1 = """    <div class="row" style="gap:10px;margin:10px 0 22px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>

    <div class="sec-head"><span class="label">Import a shared project</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Received a project file from another Notebuilt user? Bring it in as a brand-new project \u2014 it won't touch anything else already in your app.</div>
    <label class="btn block" style="margin:10px 0 22px;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Import shared project<input type="file" accept="application/json,.json" hidden data-import-project></label>"""
    edits.append((old1, new1, "Support page: add Import shared project UI"))

    # ---------------------------------------------------------------
    # Edit 2: bind() — wire the new file input
    # ---------------------------------------------------------------
    old2 = """  const imp=$app.querySelector('[data-import]'); if(imp) imp.onchange=importData;"""
    new2 = """  const imp=$app.querySelector('[data-import]'); if(imp) imp.onchange=importData;
  const impProj=$app.querySelector('[data-import-project]'); if(impProj) impProj.onchange=importSharedProject;"""
    edits.append((old2, new2, "bind(): wire Import shared project input"))

    # ---------------------------------------------------------------
    # Edit 3: add importSharedProject() right after b64ToBlob()
    # ---------------------------------------------------------------
    old3 = """function b64ToBlob(b64,type='image/jpeg'){ const bin=atob(b64); const a=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i); return new Blob([a],{type}); }"""
    new3 = """function b64ToBlob(b64,type='image/jpeg'){ const bin=atob(b64); const a=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i); return new Blob([a],{type}); }

/* CHUNK22_IMPORT_SHARED_PROJECT */
async function importSharedProject(e){
  const file=e.target.files&&e.target.files[0]; if(!file) return;
  try{
    const text=await file.text(); const d=JSON.parse(text);
    if(d.app!=='notebuilt-project-share') throw new Error('Not a shared Notebuilt project file');
    const p=d.project||{};
    if(!p.name) throw new Error('Missing project name');
    const newId=uid();
    const category=(typeof categoryById==='function'&&categoryById('construction'))?'construction':null;
    const nh={
      id:newId, name:p.name, category,
      status:p.status||'active', jobType:p.jobType||'',
      address:p.address||'', notes:p.notes||'',
      specs:(p.specs||[]).map(s=>({id:uid(),category:s.category,room:s.room,label:s.label,value:s.value,note:s.note,createdAt:now()})),
      photos:[], cover:null, createdAt:now(), updatedAt:now()
    };
    houses.push(nh);
    if(Array.isArray(p.tasks)&&p.tasks.length){
      p.tasks.forEach(t=>{
        tasks.push({id:uid(),text:t.text,status:t.status||'todo',houseId:newId,createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null});
      });
      persist.tasks();
    }
    if(p.photos){
      for(const [oldPid,pd] of Object.entries(p.photos)){
        try{
          const newPid=uid();
          const blob=b64ToBlob(pd.b64);
          await photoPut({id:newPid,blob,houseId:newId,createdAt:pd.createdAt||now()});
          nh.photos.push(newPid);
          if(!nh.cover) nh.cover=newPid;
        }catch(err){}
      }
    }
    persist.houses();
    e.target.value='';
    go('house',newId);
    toast('Project imported');
  }catch(err){
    e.target.value='';
    alert('Could not import: '+(err.message||'that file doesn\\'t look like a shared Notebuilt project'));
  }
}"""
    edits.append((old3, new3, "add importSharedProject()"))

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
        fail("no <script> block found after edit.")
    js_path = Path("/tmp/_notebuilt_chunk22_check.js")
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

    print("\n✅ Chunk 22 applied successfully: import a shared project.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
