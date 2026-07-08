#!/usr/bin/env python3
"""
Notebuilt — Chunk 4: Rotate photo (in the full-screen viewer)
Run this from the same folder as your index.html:
    python3 fix_chunk4_rotate_photo.py

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
MARKER = "CHUNK4_ROTATE_PHOTO"  # already-applied guard

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
    # Edit 1: CSS — group rotate + delete buttons on the right of the top bar
    # ---------------------------------------------------------------
    old1 = """  #viewer .icon-btn.danger{color:var(--danger)}"""
    new1 = """  /* CHUNK4_ROTATE_PHOTO */
  #viewer .icon-btn.danger{color:var(--danger)}
  #viewer .v-actions{display:flex;gap:8px}"""
    edits.append((old1, new1, "CSS: .v-actions button group"))

    # ---------------------------------------------------------------
    # Edit 2: icon set — add a rotate icon
    # ---------------------------------------------------------------
    old2 = """  trash:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>',"""
    new2 = """  trash:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M5 7h14M9 7V5h6v2M7 7l1 13h8l1-13"/></svg>',
  rotate:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/></svg>',"""
    edits.append((old2, new2, "icon set: add I.rotate"))

    # ---------------------------------------------------------------
    # Edit 3: renderViewerFrame() — add rotate button + wire it
    # ---------------------------------------------------------------
    old3 = """  $viewer.innerHTML=`
    <div class="v-top">
      <button class="icon-btn" data-v-close aria-label="Close">${I.x}</button>
      <span class="v-count">${vw.index+1} of ${vw.photos.length}</span>
      <button class="icon-btn danger" data-v-del aria-label="Delete photo">${I.trash}</button>
    </div>
    <div class="v-stage" id="v-stage"><img id="v-img" alt="Photo"></div>
    <div class="v-hint">${vw.photos.length>1?'Swipe to browse \\u00b7 pinch or double-tap to zoom':'Pinch or double-tap to zoom'}</div>`;
  $viewer.querySelector('[data-v-close]').onclick=closeViewer;
  $viewer.querySelector('[data-v-del]').onclick=deleteViewerPhoto;"""
    new3 = """  $viewer.innerHTML=`
    <div class="v-top">
      <button class="icon-btn" data-v-close aria-label="Close">${I.x}</button>
      <span class="v-count">${vw.index+1} of ${vw.photos.length}</span>
      <div class="v-actions">
        <button class="icon-btn" data-v-rotate aria-label="Rotate photo">${I.rotate}</button>
        <button class="icon-btn danger" data-v-del aria-label="Delete photo">${I.trash}</button>
      </div>
    </div>
    <div class="v-stage" id="v-stage"><img id="v-img" alt="Photo"></div>
    <div class="v-hint">${vw.photos.length>1?'Swipe to browse \\u00b7 pinch or double-tap to zoom':'Pinch or double-tap to zoom'}</div>`;
  $viewer.querySelector('[data-v-close]').onclick=closeViewer;
  $viewer.querySelector('[data-v-del]').onclick=deleteViewerPhoto;
  $viewer.querySelector('[data-v-rotate]').onclick=rotatePhoto;"""
    edits.append((old3, new3, "renderViewerFrame(): add + wire rotate button"))

    # ---------------------------------------------------------------
    # Edit 4: add rotatePhoto() function right after deleteViewerPhoto()
    # ---------------------------------------------------------------
    old4 = """async function deleteViewerPhoto(){
  if(!confirm('Delete this photo?'))return;
  const pid=vw.photos[vw.index], h=houseById(vw.houseId);
  await photoDel(pid).catch(()=>{});
  if(h){ h.photos=(h.photos||[]).filter(x=>x!==pid); if(h.cover===pid) h.cover=h.photos[0]||null; h.updatedAt=now(); persist.houses(); }
  vw.photos=vw.photos.filter(x=>x!==pid);
  if(view.name==='house') render();
  if(!vw.photos.length){ closeViewer(); toast('Photo deleted'); return; }
  if(vw.index>=vw.photos.length) vw.index=vw.photos.length-1;
  renderViewerFrame(); toast('Photo deleted');
}"""
    new4 = """async function deleteViewerPhoto(){
  if(!confirm('Delete this photo?'))return;
  const pid=vw.photos[vw.index], h=houseById(vw.houseId);
  await photoDel(pid).catch(()=>{});
  if(h){ h.photos=(h.photos||[]).filter(x=>x!==pid); if(h.cover===pid) h.cover=h.photos[0]||null; h.updatedAt=now(); persist.houses(); }
  vw.photos=vw.photos.filter(x=>x!==pid);
  if(view.name==='house') render();
  if(!vw.photos.length){ closeViewer(); toast('Photo deleted'); return; }
  if(vw.index>=vw.photos.length) vw.index=vw.photos.length-1;
  renderViewerFrame(); toast('Photo deleted');
}

/* CHUNK4_ROTATE_PHOTO — rotate the stored image 90deg clockwise and re-save it */
async function rotatePhoto(){
  const pid=vw.photos[vw.index]; if(!pid)return;
  toast('Rotating…');
  try{
    const rec=await photoGet(pid); if(!rec) throw new Error('missing photo');
    const url=URL.createObjectURL(rec.blob);
    const img=new Image();
    await new Promise((res,rej)=>{ img.onload=res; img.onerror=rej; img.src=url; });
    const c=document.createElement('canvas'); c.width=img.height; c.height=img.width;
    const ctx=c.getContext('2d');
    ctx.translate(c.width/2,c.height/2); ctx.rotate(Math.PI/2); ctx.drawImage(img,-img.width/2,-img.height/2);
    URL.revokeObjectURL(url);
    const blob=await new Promise(res=>c.toBlob(res,'image/jpeg',0.9));
    if(!blob) throw new Error('encode failed');
    await photoPut({id:pid,blob,houseId:rec.houseId,createdAt:rec.createdAt});
    if(_objUrls.has(pid)){ URL.revokeObjectURL(_objUrls.get(pid)); _objUrls.delete(pid); }
    vw.scale=1; vw.tx=0; vw.ty=0;
    const freshUrl=await photoURL(pid);
    const vimg=$viewer.querySelector('#v-img');
    if(vimg){ vimg.style.transform='translate(0px,0px) scale(1)'; vimg.src=freshUrl; }
    if(view.name==='house') render();
    toast('Rotated');
  }catch(err){ toast('Could not rotate photo'); }
}"""
    edits.append((old4, new4, "add rotatePhoto() function"))

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
    js_path = Path("/tmp/_notebuilt_chunk4_check.js")
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

    print("\n✅ Chunk 4 applied successfully: rotate photo in the full-screen viewer.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
