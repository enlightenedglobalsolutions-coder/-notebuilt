#!/usr/bin/env python3
"""
Notebuilt — Chunk 3: Full-screen photo viewer (pinch-zoom, swipe, delete)
Run this from the same folder as your index.html:
    python3 fix_chunk3_photo_viewer.py

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
MARKER = "CHUNK3_PHOTO_VIEWER"  # already-applied guard

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
    # Edit 1: CSS — full-screen viewer styles
    # ---------------------------------------------------------------
    old1 = """  #toast.show{opacity:1}

  .hidden{display:none!important}"""
    new1 = """  #toast.show{opacity:1}

  /* CHUNK3_PHOTO_VIEWER */
  #viewer{
    position:fixed;inset:0;z-index:60;background:rgba(6,8,10,.96);
    display:flex;flex-direction:column;
  }
  #viewer .v-top{
    display:flex;align-items:center;justify-content:space-between;
    padding:calc(var(--safe-t) + 10px) 12px 10px;flex:none;
  }
  #viewer .icon-btn{background:rgba(255,255,255,.08)}
  #viewer .icon-btn.danger{color:var(--danger)}
  #viewer .v-count{font-family:var(--mono);font-size:12px;color:var(--paper-dim);letter-spacing:.06em}
  #viewer .v-stage{
    flex:1;position:relative;overflow:hidden;
    display:flex;align-items:center;justify-content:center;
    touch-action:none;
  }
  #viewer .v-stage img{
    max-width:100%;max-height:100%;object-fit:contain;
    user-select:none;-webkit-user-drag:none;will-change:transform;
    transform:translate(0px,0px) scale(1);
  }
  #viewer .v-hint{
    text-align:center;font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;
    text-transform:uppercase;color:var(--paper-faint);padding:8px 0 calc(var(--safe-b) + 10px);flex:none;
  }

  .hidden{display:none!important}"""
    edits.append((old1, new1, "CSS: #viewer full-screen styles"))

    # ---------------------------------------------------------------
    # Edit 2: HTML — add the viewer overlay node
    # ---------------------------------------------------------------
    old2 = '<div id="modal-root"></div>\n<div id="toast"></div>'
    new2 = '<div id="modal-root"></div>\n<div id="viewer" class="hidden"></div>\n<div id="toast"></div>'
    edits.append((old2, new2, "HTML: add #viewer node"))

    # ---------------------------------------------------------------
    # Edit 3: renderHouse() photo grid — Camera/Library tiles pinned to top
    # ---------------------------------------------------------------
    old3 = """  const photos=(h.photos||[]);
  const photoGrid=`<div class="sec-head"><span class="label">Photos</span><span class="rule"></span><span class="count">${photos.length}</span></div>
    <div class="photo-grid">
      ${photos.map(pid=>`<div class="ph" data-photo="${pid}"><button class="x" data-del-photo="${pid}" aria-label="Remove photo">${I.x}</button></div>`).join('')}
      <label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>
      <label class="photo-add" aria-label="Choose from library">${I.images}<span>Library</span><input type="file" accept="image/*" multiple hidden data-add-photo></label>
    </div>`;"""
    new3 = """  const photos=(h.photos||[]);
  const photoGrid=`<div class="sec-head"><span class="label">Photos</span><span class="rule"></span><span class="count">${photos.length}</span></div>
    <div class="photo-grid">
      <label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>
      <label class="photo-add" aria-label="Choose from library">${I.images}<span>Library</span><input type="file" accept="image/*" multiple hidden data-add-photo></label>
      ${photos.map(pid=>`<div class="ph" data-photo="${pid}"><button class="x" data-del-photo="${pid}" aria-label="Remove photo">${I.x}</button></div>`).join('')}
    </div>`;"""
    edits.append((old3, new3, "renderHouse(): Camera/Library tiles pinned to top of grid"))

    # ---------------------------------------------------------------
    # Edit 4: bind() — open viewer on photo tap (del button still stops propagation)
    # ---------------------------------------------------------------
    old4 = """  $app.querySelectorAll('[data-del-photo]').forEach(b=>b.onclick=async ev=>{ ev.stopPropagation();
    const pid=b.dataset.delPhoto, h=houseById(view.param);
    await photoDel(pid).catch(()=>{}); h.photos=(h.photos||[]).filter(x=>x!==pid);
    if(h.cover===pid) h.cover=null; h.updatedAt=now(); persist.houses(); render();
  });"""
    new4 = """  $app.querySelectorAll('[data-del-photo]').forEach(b=>b.onclick=async ev=>{ ev.stopPropagation();
    const pid=b.dataset.delPhoto, h=houseById(view.param);
    await photoDel(pid).catch(()=>{}); h.photos=(h.photos||[]).filter(x=>x!==pid);
    if(h.cover===pid) h.cover=null; h.updatedAt=now(); persist.houses(); render();
  });
  $app.querySelectorAll('.photo-grid .ph[data-photo]').forEach(el=>el.onclick=()=>openViewer(view.param, el.dataset.photo));"""
    edits.append((old4, new4, "bind(): open full-screen viewer on photo tap"))

    # ---------------------------------------------------------------
    # Edit 5: add the viewer JS module right after hydratePhotos()
    # ---------------------------------------------------------------
    old5 = """/* fill in any cover/photo backgrounds from IndexedDB after render */
async function hydratePhotos(){
  for(const el of $app.querySelectorAll('[data-cover]')){
    const u=await photoURL(el.getAttribute('data-cover')); if(u){ el.style.backgroundImage=`url(${u})`; el.innerHTML=''; }
  }
  for(const el of $app.querySelectorAll('[data-photo]')){
    const u=await photoURL(el.getAttribute('data-photo')); if(u) el.style.backgroundImage=`url(${u})`;
  }
}"""
    new5 = """/* fill in any cover/photo backgrounds from IndexedDB after render */
async function hydratePhotos(){
  for(const el of $app.querySelectorAll('[data-cover]')){
    const u=await photoURL(el.getAttribute('data-cover')); if(u){ el.style.backgroundImage=`url(${u})`; el.innerHTML=''; }
  }
  for(const el of $app.querySelectorAll('[data-photo]')){
    const u=await photoURL(el.getAttribute('data-photo')); if(u) el.style.backgroundImage=`url(${u})`;
  }
}

/* ============================================================
   PHOTO VIEWER — full-screen, pinch-zoom, swipe, delete
   CHUNK3_PHOTO_VIEWER
   ============================================================ */
const $viewer=document.getElementById('viewer');
let vw={houseId:null,photos:[],index:0,scale:1,tx:0,ty:0};

function openViewer(houseId,photoId){
  const h=houseById(houseId); if(!h)return;
  const photos=(h.photos||[]).slice();
  const idx=photos.indexOf(photoId);
  vw={houseId,photos,index:idx<0?0:idx,scale:1,tx:0,ty:0};
  document.body.style.overflow='hidden';
  $viewer.classList.remove('hidden');
  renderViewerFrame();
}
function closeViewer(){
  $viewer.classList.add('hidden'); $viewer.innerHTML='';
  document.body.style.overflow='';
}
async function renderViewerFrame(){
  const pid=vw.photos[vw.index]; if(!pid){ closeViewer(); return; }
  vw.scale=1; vw.tx=0; vw.ty=0;
  $viewer.innerHTML=`
    <div class="v-top">
      <button class="icon-btn" data-v-close aria-label="Close">${I.x}</button>
      <span class="v-count">${vw.index+1} of ${vw.photos.length}</span>
      <button class="icon-btn danger" data-v-del aria-label="Delete photo">${I.trash}</button>
    </div>
    <div class="v-stage" id="v-stage"><img id="v-img" alt="Photo"></div>
    <div class="v-hint">${vw.photos.length>1?'Swipe to browse \\u00b7 pinch or double-tap to zoom':'Pinch or double-tap to zoom'}</div>`;
  $viewer.querySelector('[data-v-close]').onclick=closeViewer;
  $viewer.querySelector('[data-v-del]').onclick=deleteViewerPhoto;
  const img=$viewer.querySelector('#v-img');
  const url=await photoURL(pid); if(url) img.src=url;
  bindViewerGestures();
}

async function deleteViewerPhoto(){
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

function viewerNav(dir){
  const n=vw.photos.length; if(n<2)return;
  vw.index=(vw.index+dir+n)%n;
  renderViewerFrame();
}

function bindViewerGestures(){
  const stage=document.getElementById('v-stage'), img=document.getElementById('v-img');
  let mode=null;
  let startDist=0, startScale=1, startMidX=0, startMidY=0, startTx=0, startTy=0;
  let startX=0, startY=0, dragDX=0, dragDY=0;
  let lastTapT=0, lastTapX=0, lastTapY=0;

  const dist=t=>Math.hypot(t[0].clientX-t[1].clientX, t[0].clientY-t[1].clientY);
  const mid=t=>({x:(t[0].clientX+t[1].clientX)/2, y:(t[0].clientY+t[1].clientY)/2});

  function apply(){ img.style.transform=`translate(${vw.tx}px,${vw.ty}px) scale(${vw.scale})`; }
  function clampPan(){
    const r=stage.getBoundingClientRect();
    const maxX=Math.max(0,(r.width*(vw.scale-1))/2);
    const maxY=Math.max(0,(r.height*(vw.scale-1))/2);
    vw.tx=Math.max(-maxX,Math.min(maxX,vw.tx));
    vw.ty=Math.max(-maxY,Math.min(maxY,vw.ty));
  }

  stage.addEventListener('touchstart',e=>{
    if(e.touches.length===2){
      mode='pinch';
      startDist=dist(e.touches); startScale=vw.scale;
      const r=stage.getBoundingClientRect(); const m=mid(e.touches);
      startMidX=m.x-r.left-r.width/2; startMidY=m.y-r.top-r.height/2;
      startTx=vw.tx; startTy=vw.ty;
    }else if(e.touches.length===1){
      const t=e.touches[0]; startX=t.clientX; startY=t.clientY; dragDX=0; dragDY=0;
      startTx=vw.tx; startTy=vw.ty;
      mode=vw.scale>1.02?'pan':'swipe';
    }
  },{passive:true});

  stage.addEventListener('touchmove',e=>{
    if(mode==='pinch'&&e.touches.length===2){
      e.preventDefault();
      const r=dist(e.touches)/startDist;
      vw.scale=Math.max(1,Math.min(4,startScale*r));
      vw.tx=startMidX-vw.scale*(startMidX-startTx)/startScale;
      vw.ty=startMidY-vw.scale*(startMidY-startTy)/startScale;
      clampPan(); apply();
    }else if(mode==='pan'&&e.touches.length===1){
      e.preventDefault();
      const t=e.touches[0];
      vw.tx=startTx+(t.clientX-startX); vw.ty=startTy+(t.clientY-startY);
      clampPan(); apply();
    }else if(mode==='swipe'&&e.touches.length===1){
      const t=e.touches[0]; dragDX=t.clientX-startX; dragDY=t.clientY-startY;
      if(Math.abs(dragDX)>Math.abs(dragDY)) e.preventDefault();
      img.style.transform=`translate(${dragDX}px,0px) scale(1)`;
    }
  },{passive:false});

  stage.addEventListener('touchend',()=>{
    if(mode==='pinch'){
      if(vw.scale<1.02){ vw.scale=1; vw.tx=0; vw.ty=0; apply(); }
      mode=null; return;
    }
    if(mode==='pan'){ mode=null; return; }
    if(mode==='swipe'){
      if(Math.abs(dragDX)>60&&Math.abs(dragDX)>Math.abs(dragDY)){
        viewerNav(dragDX<0?1:-1);
      }else{
        img.style.transform=`translate(0px,0px) scale(1)`;
        const t0=Date.now(), dx=startX-lastTapX, dy=startY-lastTapY;
        if(t0-lastTapT<320&&Math.hypot(dx,dy)<30){
          const r=stage.getBoundingClientRect();
          const ox=startX-r.left-r.width/2, oy=startY-r.top-r.height/2;
          if(vw.scale>1){ vw.scale=1; vw.tx=0; vw.ty=0; }
          else{ vw.scale=2.5; vw.tx=ox*(1-vw.scale); vw.ty=oy*(1-vw.scale); clampPan(); }
          apply(); lastTapT=0;
        }else{ lastTapT=t0; lastTapX=startX; lastTapY=startY; }
      }
      mode=null;
    }
  });

  stage.addEventListener('touchcancel',()=>{ mode=null; });
}"""
    edits.append((old5, new5, "add full-screen photo viewer module (viewer state, gestures, delete)"))

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
    js_path = Path("/tmp/_notebuilt_chunk3_check.js")
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

    print("\n✅ Chunk 3 applied successfully: full-screen photo viewer with pinch-zoom, swipe, delete.")
    print("   Camera/Library tiles are now pinned to the top of the photo grid.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
