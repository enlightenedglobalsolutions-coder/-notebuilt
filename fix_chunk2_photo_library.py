#!/usr/bin/env python3
"""
Notebuilt — Chunk 2: Photo library picker
Run this from the same folder as your index.html:
    python3 fix_chunk2_photo_library.py

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
MARKER = "CHUNK2_PHOTO_LIBRARY"  # already-applied guard

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
    # Edit 1: CSS — .photo-add becomes a flex column (icon + tiny label),
    # add explicit svg sizing so the icon doesn't render oversized.
    # ---------------------------------------------------------------
    old1 = """  .photo-add{
    aspect-ratio:1;border:1.5px dashed var(--line);border-radius:8px;
    display:grid;place-items:center;color:var(--paper-dim);
  }"""
    new1 = """  /* CHUNK2_PHOTO_LIBRARY */
  .photo-add{
    aspect-ratio:1;border:1.5px dashed var(--line);border-radius:8px;
    display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;color:var(--paper-dim);
  }
  .photo-add svg{width:24px;height:24px}
  .photo-add span{font-family:var(--mono);font-size:9px;letter-spacing:.05em;text-transform:uppercase}"""
    edits.append((old1, new1, "CSS: .photo-add flex layout + icon sizing + label"))

    # ---------------------------------------------------------------
    # Edit 2: icon set — add a gallery/library icon next to the camera icon
    # ---------------------------------------------------------------
    old2 = """  camera:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.2"/></svg>',"""
    new2 = """  camera:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 8h3l1.5-2h7L17 8h3v11H4z"/><circle cx="12" cy="13" r="3.2"/></svg>',
  images:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 15.5l4.5-4.5 3 3 4-4.5 5.5 6"/><circle cx="8.5" cy="8.5" r="1.4"/></svg>',"""
    edits.append((old2, new2, "icon set: add I.images (gallery icon)"))

    # ---------------------------------------------------------------
    # Edit 3: renderHouse() photo grid — two tiles: Camera + Library
    # ---------------------------------------------------------------
    old3 = """  const photos=(h.photos||[]);
  const photoGrid=`<div class="sec-head"><span class="label">Photos</span><span class="rule"></span><span class="count">${photos.length}</span></div>
    <div class="photo-grid">
      ${photos.map(pid=>`<div class="ph" data-photo="${pid}"><button class="x" data-del-photo="${pid}" aria-label="Remove photo">${I.x}</button></div>`).join('')}
      <label class="photo-add">${I.camera}<input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>
    </div>`;"""
    new3 = """  const photos=(h.photos||[]);
  const photoGrid=`<div class="sec-head"><span class="label">Photos</span><span class="rule"></span><span class="count">${photos.length}</span></div>
    <div class="photo-grid">
      ${photos.map(pid=>`<div class="ph" data-photo="${pid}"><button class="x" data-del-photo="${pid}" aria-label="Remove photo">${I.x}</button></div>`).join('')}
      <label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>
      <label class="photo-add" aria-label="Choose from library">${I.images}<span>Library</span><input type="file" accept="image/*" multiple hidden data-add-photo></label>
    </div>`;"""
    edits.append((old3, new3, "renderHouse(): two photo-add tiles (camera + library)"))

    # ---------------------------------------------------------------
    # Edit 4: handlePhoto() — support multiple files (library multi-select)
    # ---------------------------------------------------------------
    old4 = """async function handlePhoto(e,houseId){
  const file=e.target.files&&e.target.files[0]; if(!file)return;
  toast('Saving photo…');
  try{
    const blob=await downscale(file); const id=uid();
    await photoPut({id,blob,houseId,createdAt:now()});
    const h=houseById(houseId); h.photos=h.photos||[]; h.photos.push(id);
    if(!h.cover) h.cover=id; h.updatedAt=now(); persist.houses(); render(); toast('Photo saved');
  }catch(err){ toast('Could not read that image'); }
}"""
    new4 = """async function handlePhoto(e,houseId){
  const files=e.target.files?Array.from(e.target.files):[]; if(!files.length)return;
  const multi=files.length>1;
  toast(multi?`Saving ${files.length} photos…`:'Saving photo…');
  const h=houseById(houseId); h.photos=h.photos||[];
  let saved=0, failed=0;
  for(const file of files){
    try{
      const blob=await downscale(file); const id=uid();
      await photoPut({id,blob,houseId,createdAt:now()});
      h.photos.push(id);
      if(!h.cover) h.cover=id;
      saved++;
    }catch(err){ failed++; }
  }
  h.updatedAt=now(); persist.houses(); render();
  e.target.value='';
  if(saved && failed) toast(`${saved} saved, ${failed} could not be read`);
  else if(failed) toast('Could not read those images');
  else toast(multi?`${saved} photos saved`:'Photo saved');
}"""
    edits.append((old4, new4, "handlePhoto(): multi-file support + reset input"))

    # ---------------------------------------------------------------
    # Edit 5: bind() — wire both photo-add inputs (was single querySelector)
    # ---------------------------------------------------------------
    old5 = """  const addPhoto=$app.querySelector('[data-add-photo]'); if(addPhoto) addPhoto.onchange=e=>handlePhoto(e,view.param);"""
    new5 = """  $app.querySelectorAll('[data-add-photo]').forEach(el=>el.onchange=e=>handlePhoto(e,view.param));"""
    edits.append((old5, new5, "bind(): wire both camera + library inputs"))

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
    js_path = Path("/tmp/_notebuilt_chunk2_check.js")
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

    print("\n✅ Chunk 2 applied successfully: photo library picker (camera + library, multi-select).")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
