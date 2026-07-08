#!/usr/bin/env python3
"""
Notebuilt — Chunk 6: Photo markup (freehand draw + text labels)
Run this from the same folder as your index.html:
    python3 fix_chunk6_photo_annotate.py

Adds a "Markup" button to the full-screen photo viewer that opens a
full-screen editor: pen tool, text tool, 3 color presets (red/brass/white),
undo, and Save (creates a NEW photo with the markup baked in — your
original photo is never touched).

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
MARKER = "CHUNK6_PHOTO_ANNOTATE"  # already-applied guard

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
    # Edit 1: CSS — annotate overlay, toolbar, tool buttons, swatches
    # ---------------------------------------------------------------
    old1 = """  #viewer .v-actions{display:flex;gap:8px}"""
    new1 = """  #viewer .v-actions{display:flex;gap:8px}

  /* CHUNK6_PHOTO_ANNOTATE */
  #annotate{
    position:fixed;inset:0;z-index:70;background:rgba(6,8,10,.97);
    display:flex;flex-direction:column;
  }
  #annotate .icon-btn{background:rgba(255,255,255,.08)}
  #annotate .a-top{
    display:flex;align-items:center;justify-content:space-between;
    padding:calc(var(--safe-t) + 10px) 12px 8px;flex:none;
  }
  #annotate .a-title{font-family:var(--serif);font-size:16px;color:var(--paper)}
  #annotate .a-tools{
    display:flex;align-items:center;gap:8px;padding:4px 12px 10px;flex:none;overflow-x:auto;
  }
  .a-tool{
    width:44px;height:44px;border-radius:10px;background:var(--ink-2);color:var(--paper-dim);
    display:grid;place-items:center;font-family:var(--mono);font-weight:700;font-size:15px;flex:none;
  }
  .a-tool.active{background:var(--brass);color:#231a07}
  .a-tool svg{width:20px;height:20px}
  .a-swatches{display:flex;align-items:center;gap:8px;margin:0 4px;flex:none}
  .a-swatch{width:30px;height:30px;border-radius:50%;border:2px solid transparent;flex:none}
  .a-swatch.active{border-color:var(--paper)}
  #annotate .a-stage{
    flex:1;position:relative;display:flex;align-items:center;justify-content:center;
    overflow:hidden;touch-action:none;padding:16px;
  }
  #annotate .a-stage canvas{touch-action:none;background:#000;border-radius:4px}"""
    edits.append((old1, new1, "CSS: #annotate overlay + toolbar styles"))

    # ---------------------------------------------------------------
    # Edit 2: icon set — add an undo icon
    # ---------------------------------------------------------------
    old2 = """  rotate:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/></svg>',"""
    new2 = """  rotate:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/></svg>',
  undo:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 1 0 2.34-5.66"/><path d="M4 4v5h5"/></svg>',"""
    edits.append((old2, new2, "icon set: add I.undo"))

    # ---------------------------------------------------------------
    # Edit 3: HTML — add the annotate overlay node next to #viewer
    # ---------------------------------------------------------------
    old3 = '<div id="viewer" class="hidden"></div>'
    new3 = '<div id="viewer" class="hidden"></div>\n<div id="annotate" class="hidden"></div>'
    edits.append((old3, new3, "HTML: add #annotate node"))

    # ---------------------------------------------------------------
    # Edit 4: renderViewerFrame() — add Markup button to v-actions + wire it
    # ---------------------------------------------------------------
    old4 = """async function renderViewerFrame(){
  const pid=vw.photos[vw.index]; if(!pid){ closeViewer(); return; }
  vw.scale=1; vw.tx=0; vw.ty=0;
  $viewer.innerHTML=`
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
  $viewer.querySelector('[data-v-rotate]').onclick=rotatePhoto;
  const img=$viewer.querySelector('#v-img');
  const url=await photoURL(pid); if(url) img.src=url;
  bindViewerGestures();
}"""
    new4 = """async function renderViewerFrame(){
  const pid=vw.photos[vw.index]; if(!pid){ closeViewer(); return; }
  vw.scale=1; vw.tx=0; vw.ty=0;
  $viewer.innerHTML=`
    <div class="v-top">
      <button class="icon-btn" data-v-close aria-label="Close">${I.x}</button>
      <span class="v-count">${vw.index+1} of ${vw.photos.length}</span>
      <div class="v-actions">
        <button class="icon-btn" data-v-rotate aria-label="Rotate photo">${I.rotate}</button>
        <button class="icon-btn" data-v-markup aria-label="Add markup">${I.edit}</button>
        <button class="icon-btn danger" data-v-del aria-label="Delete photo">${I.trash}</button>
      </div>
    </div>
    <div class="v-stage" id="v-stage"><img id="v-img" alt="Photo"></div>
    <div class="v-hint">${vw.photos.length>1?'Swipe to browse \\u00b7 pinch or double-tap to zoom':'Pinch or double-tap to zoom'}</div>`;
  $viewer.querySelector('[data-v-close]').onclick=closeViewer;
  $viewer.querySelector('[data-v-del]').onclick=deleteViewerPhoto;
  $viewer.querySelector('[data-v-rotate]').onclick=rotatePhoto;
  $viewer.querySelector('[data-v-markup]').onclick=openAnnotate;
  const img=$viewer.querySelector('#v-img');
  const url=await photoURL(pid); if(url) img.src=url;
  bindViewerGestures();
}"""
    edits.append((old4, new4, "renderViewerFrame(): add + wire Markup button"))

    # ---------------------------------------------------------------
    # Edit 5: add the full annotate module after bindViewerGestures()
    # ---------------------------------------------------------------
    old5 = """  stage.addEventListener('touchcancel',()=>{ mode=null; });
}"""
    new5 = """  stage.addEventListener('touchcancel',()=>{ mode=null; });
}

/* ============================================================
   PHOTO MARKUP — freehand draw + text labels, saved as a new photo
   CHUNK6_PHOTO_ANNOTATE
   ============================================================ */
const $annotate=document.getElementById('annotate');
let an={houseId:null,srcId:null,tool:'pen',color:'#D7A94B'};
let anUndo=[];

async function openAnnotate(){
  const pid=vw.photos[vw.index]; if(!pid)return;
  an={houseId:vw.houseId,srcId:pid,tool:'pen',color:'#D7A94B'};
  anUndo=[];
  $annotate.classList.remove('hidden');
  await renderAnnotateFrame();
}
function closeAnnotate(){
  $annotate.classList.add('hidden'); $annotate.innerHTML=''; anUndo=[];
}
function cancelAnnotate(){
  if(anUndo.length){ if(!confirm('Discard this markup?')) return; }
  closeAnnotate();
}

async function renderAnnotateFrame(){
  $annotate.innerHTML=`
    <div class="a-top">
      <button class="icon-btn" data-a-cancel aria-label="Cancel">${I.x}</button>
      <span class="a-title">Markup</span>
      <button class="btn primary sm" data-a-save>Save</button>
    </div>
    <div class="a-tools">
      <button class="a-tool active" data-a-tool="pen" aria-label="Pen">${I.edit}</button>
      <button class="a-tool" data-a-tool="text" aria-label="Text">T</button>
      <span class="a-swatches">
        <button class="a-swatch" data-a-color="#C8654B" style="background:#C8654B" aria-label="Red"></button>
        <button class="a-swatch active" data-a-color="#D7A94B" style="background:#D7A94B" aria-label="Brass"></button>
        <button class="a-swatch" data-a-color="#FFFFFF" style="background:#FFFFFF" aria-label="White"></button>
      </span>
      <button class="icon-btn" data-a-undo aria-label="Undo">${I.undo}</button>
    </div>
    <div class="a-stage" id="a-stage"><canvas id="a-canvas"></canvas></div>`;
  $annotate.querySelector('[data-a-cancel]').onclick=cancelAnnotate;
  $annotate.querySelector('[data-a-save]').onclick=saveAnnotation;
  $annotate.querySelectorAll('[data-a-tool]').forEach(b=>b.onclick=()=>{
    an.tool=b.dataset.aTool;
    $annotate.querySelectorAll('[data-a-tool]').forEach(x=>x.classList.toggle('active',x===b));
  });
  $annotate.querySelectorAll('[data-a-color]').forEach(b=>b.onclick=()=>{
    an.color=b.dataset.aColor;
    $annotate.querySelectorAll('[data-a-color]').forEach(x=>x.classList.toggle('active',x===b));
  });
  $annotate.querySelector('[data-a-undo]').onclick=annotateUndo;

  const stage=document.getElementById('a-stage'), canvas=document.getElementById('a-canvas');
  const url=await photoURL(an.srcId); if(!url){ toast('Could not load photo'); cancelAnnotate(); return; }
  const img=new Image();
  await new Promise((res,rej)=>{ img.onload=res; img.onerror=rej; img.src=url; });
  const natW=img.naturalWidth||img.width, natH=img.naturalHeight||img.height;
  canvas.width=natW; canvas.height=natH;
  const ctx=canvas.getContext('2d');
  ctx.drawImage(img,0,0,natW,natH);
  fitAnnotateCanvas(canvas,stage,natW,natH);
  bindAnnotateGestures(canvas,stage,ctx);
}

function fitAnnotateCanvas(canvas,stage,natW,natH){
  const r=stage.getBoundingClientRect();
  const availW=Math.max(60,r.width-32), availH=Math.max(60,r.height-32);
  const scale=Math.min(availW/natW, availH/natH);
  canvas.style.width=Math.round(natW*scale)+'px';
  canvas.style.height=Math.round(natH*scale)+'px';
}

function pushAnnotateUndo(ctx,canvas){
  try{
    if(anUndo.length>=15) anUndo.shift();
    anUndo.push(ctx.getImageData(0,0,canvas.width,canvas.height));
  }catch(e){}
}
function annotateUndo(){
  const canvas=document.getElementById('a-canvas'); if(!canvas||!anUndo.length)return;
  const ctx=canvas.getContext('2d');
  const snap=anUndo.pop();
  ctx.putImageData(snap,0,0);
}

function bindAnnotateGestures(canvas,stage,ctx){
  let drawing=false, lastPt=null;
  const ptFromEvent=(clientX,clientY)=>{
    const r=canvas.getBoundingClientRect();
    return { x:(clientX-r.left)*(canvas.width/r.width), y:(clientY-r.top)*(canvas.height/r.height) };
  };
  const lineW=()=>Math.max(4,canvas.width*0.007);

  canvas.addEventListener('touchstart',e=>{
    e.preventDefault();
    const t=e.touches[0]; const pt=ptFromEvent(t.clientX,t.clientY);
    if(an.tool==='pen'){
      pushAnnotateUndo(ctx,canvas); drawing=true; lastPt=pt;
      ctx.strokeStyle=an.color; ctx.lineWidth=lineW(); ctx.lineCap='round'; ctx.lineJoin='round';
    }else if(an.tool==='text'){
      placeAnnotateText(t.clientX,t.clientY,pt,canvas,stage,ctx);
    }
  },{passive:false});

  canvas.addEventListener('touchmove',e=>{
    if(!drawing||an.tool!=='pen')return;
    e.preventDefault();
    const t=e.touches[0]; const pt=ptFromEvent(t.clientX,t.clientY);
    ctx.beginPath(); ctx.moveTo(lastPt.x,lastPt.y); ctx.lineTo(pt.x,pt.y); ctx.stroke();
    lastPt=pt;
  },{passive:false});

  canvas.addEventListener('touchend',()=>{ drawing=false; lastPt=null; });
  canvas.addEventListener('touchcancel',()=>{ drawing=false; lastPt=null; });
}

function placeAnnotateText(clientX,clientY,canvasPt,canvas,stage,ctx){
  const existing=stage.querySelector('.a-textinput'); if(existing) existing.remove();
  const r=stage.getBoundingClientRect();
  const dispScale=canvas.getBoundingClientRect().width/canvas.width;
  const fontCanvasPx=Math.max(28,canvas.width*0.045);
  const inp=document.createElement('input');
  inp.type='text'; inp.className='a-textinput';
  inp.style.cssText='position:absolute;left:'+(clientX-r.left)+'px;top:'+(clientY-r.top)+'px;transform:translateY(-50%);'+
    'background:rgba(0,0,0,.5);border:1px dashed '+an.color+';color:'+an.color+';'+
    'font-size:'+Math.round(fontCanvasPx*dispScale)+'px;padding:2px 6px;border-radius:4px;min-width:80px;outline:none;';
  stage.appendChild(inp); inp.focus();
  let done=false;
  const commit=()=>{
    if(done)return; done=true;
    const val=inp.value.trim(); inp.remove();
    if(!val)return;
    pushAnnotateUndo(ctx,canvas);
    ctx.font='700 '+fontCanvasPx+'px system-ui,-apple-system,sans-serif';
    ctx.textBaseline='top';
    ctx.lineWidth=Math.max(3,fontCanvasPx*0.12); ctx.strokeStyle='rgba(0,0,0,.6)';
    ctx.strokeText(val,canvasPt.x,canvasPt.y);
    ctx.fillStyle=an.color; ctx.fillText(val,canvasPt.x,canvasPt.y);
  };
  inp.addEventListener('blur',commit);
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'){ e.preventDefault(); inp.blur(); } });
}

async function saveAnnotation(){
  const canvas=document.getElementById('a-canvas'); if(!canvas)return;
  toast('Saving markup…');
  try{
    const blob=await new Promise(res=>canvas.toBlob(res,'image/jpeg',0.9));
    if(!blob) throw new Error('encode failed');
    const h=houseById(an.houseId); if(!h) throw new Error('no house');
    const newId=uid();
    await photoPut({id:newId,blob,houseId:an.houseId,createdAt:now()});
    h.photos=h.photos||[]; h.photos.push(newId);
    if(!h.cover) h.cover=newId;
    h.updatedAt=now(); persist.houses();
    closeAnnotate();
    if(view.name==='house') render();
    toast('Annotated photo saved');
    openViewer(an.houseId,newId);
  }catch(err){ toast('Could not save markup'); }
}"""
    edits.append((old5, new5, "add photo markup module (pen, text, undo, save-as-new-photo)"))

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
    js_path = Path("/tmp/_notebuilt_chunk6_check.js")
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

    print("\n✅ Chunk 6 applied successfully: photo markup (pen + text + undo + save-as-new-photo).")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
