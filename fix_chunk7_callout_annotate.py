#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 7: Callout tool (circle/box + arrow + note)
Run this from the same folder as your index.html:
    python3 fix_chunk7_callout_annotate.py

Replaces the Chunk 6 Pen + Text tools with a single practical Callout tool:
  - Drag to circle or box the flagged area (toggle shape)
  - Tap where the note should go
  - An arrow auto-draws from your note to the flagged area
  - Type the note text
  - Repeat for as many callouts as you like, then Save
  - Save still creates a NEW photo — your original is never touched

Requires Chunk 6 (fix_chunk6_photo_annotate.py) to already be applied.

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
MARKER = "CHUNK7_CALLOUT_ANNOTATE"  # already-applied guard
PREREQ_MARKER = "CHUNK6_PHOTO_ANNOTATE"

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

    if PREREQ_MARKER not in text:
        fail("Chunk 6 (photo markup) doesn't look applied yet. Run fix_chunk6_photo_annotate.py first.")

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: CSS — add .a-hint + slightly larger glyphs for shape buttons
    # ---------------------------------------------------------------
    old1 = """  .a-swatch.active{border-color:var(--paper)}"""
    new1 = """  .a-swatch.active{border-color:var(--paper)}
  /* CHUNK7_CALLOUT_ANNOTATE */
  .a-shapes .a-tool{font-size:19px}
  #annotate .a-hint{
    text-align:center;font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--paper-faint);padding:8px 12px calc(var(--safe-b) + 10px);flex:none;
  }"""
    edits.append((old1, new1, "CSS: .a-hint + shape button glyph sizing"))

    # ---------------------------------------------------------------
    # Edit 2: replace the whole Pen/Text annotate module with Callout
    # ---------------------------------------------------------------
    old2 = """let an={houseId:null,srcId:null,tool:'pen',color:'#D7A94B'};
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

"""
    new2 = """let an={houseId:null,srcId:null,shape:'circle',color:'#D7A94B'};
let anUndo=[];
let anPending=null; /* {box,shape} once a shape is drawn and we're waiting for the note tap */

async function openAnnotate(){
  const pid=vw.photos[vw.index]; if(!pid)return;
  an={houseId:vw.houseId,srcId:pid,shape:'circle',color:'#D7A94B'};
  anUndo=[]; anPending=null;
  $annotate.classList.remove('hidden');
  await renderAnnotateFrame();
}
function closeAnnotate(){
  $annotate.classList.add('hidden'); $annotate.innerHTML=''; anUndo=[]; anPending=null;
}
function cancelAnnotate(){
  if(anUndo.length){ if(!confirm('Discard this markup?')) return; }
  closeAnnotate();
}

function annotateHintText(){
  return anPending ? 'Tap where the note should go' : 'Drag around the area to flag \\u2014 add as many as you like';
}
function updateAnnotateHint(){
  const el=document.getElementById('a-hint'); if(el) el.textContent=annotateHintText();
}

async function renderAnnotateFrame(){
  $annotate.innerHTML=`
    <div class="a-top">
      <button class="icon-btn" data-a-cancel aria-label="Cancel">${I.x}</button>
      <span class="a-title">Callout</span>
      <button class="btn primary sm" data-a-save>Save</button>
    </div>
    <div class="a-tools">
      <span class="a-shapes">
        <button class="a-tool active" data-a-shape="circle" aria-label="Circle">\u25EF</button>
        <button class="a-tool" data-a-shape="box" aria-label="Box">\u25AD</button>
      </span>
      <span class="a-swatches">
        <button class="a-swatch" data-a-color="#C8654B" style="background:#C8654B" aria-label="Red"></button>
        <button class="a-swatch active" data-a-color="#D7A94B" style="background:#D7A94B" aria-label="Brass"></button>
        <button class="a-swatch" data-a-color="#FFFFFF" style="background:#FFFFFF" aria-label="White"></button>
      </span>
      <button class="icon-btn" data-a-undo aria-label="Undo">${I.undo}</button>
    </div>
    <div class="a-stage" id="a-stage"><canvas id="a-canvas"></canvas></div>
    <div class="a-hint" id="a-hint">${annotateHintText()}</div>`;
  $annotate.querySelector('[data-a-cancel]').onclick=cancelAnnotate;
  $annotate.querySelector('[data-a-save]').onclick=saveAnnotation;
  $annotate.querySelectorAll('[data-a-shape]').forEach(b=>b.onclick=()=>{
    an.shape=b.dataset.aShape;
    $annotate.querySelectorAll('[data-a-shape]').forEach(x=>x.classList.toggle('active',x===b));
  });
  $annotate.querySelectorAll('[data-a-color]').forEach(b=>b.onclick=()=>{
    an.color=b.dataset.aColor;
    $annotate.querySelectorAll('[data-a-color]').forEach(x=>x.classList.toggle('active',x===b));
  });
  $annotate.querySelector('[data-a-undo]').onclick=()=>{ annotateUndo(); updateAnnotateHint(); };

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

function pushAnnotateUndoSnap(snap){
  if(anUndo.length>=15) anUndo.shift();
  anUndo.push(snap);
}
function annotateUndo(){
  const canvas=document.getElementById('a-canvas'); if(!canvas||!anUndo.length)return;
  const ctx=canvas.getContext('2d');
  const snap=anUndo.pop();
  ctx.putImageData(snap,0,0);
  anPending=null;
  const stage=document.getElementById('a-stage');
  const existing=stage&&stage.querySelector('.a-textinput'); if(existing) existing.remove();
}

function shapeBoundsFromPts(p0,p1){
  return { x0:Math.min(p0.x,p1.x), y0:Math.min(p0.y,p1.y), x1:Math.max(p0.x,p1.x), y1:Math.max(p0.y,p1.y) };
}
function drawShapePreview(ctx,base,box,shape,color,lineWidth){
  ctx.putImageData(base,0,0);
  ctx.save();
  ctx.strokeStyle=color; ctx.lineWidth=lineWidth; ctx.lineJoin='round';
  if(shape==='circle'){
    const cx=(box.x0+box.x1)/2, cy=(box.y0+box.y1)/2, rx=(box.x1-box.x0)/2, ry=(box.y1-box.y0)/2;
    ctx.beginPath(); ctx.ellipse(cx,cy,Math.max(rx,4),Math.max(ry,4),0,0,Math.PI*2); ctx.stroke();
  }else{
    ctx.strokeRect(box.x0,box.y0,box.x1-box.x0,box.y1-box.y0);
  }
  ctx.restore();
}
function drawArrowhead(ctx,tipX,tipY,dirAngle,color,size){
  ctx.save();
  ctx.fillStyle=color;
  ctx.beginPath();
  ctx.moveTo(tipX,tipY);
  ctx.lineTo(tipX-size*Math.cos(dirAngle-0.45),tipY-size*Math.sin(dirAngle-0.45));
  ctx.lineTo(tipX-size*Math.cos(dirAngle+0.45),tipY-size*Math.sin(dirAngle+0.45));
  ctx.closePath(); ctx.fill();
  ctx.restore();
}

function bindAnnotateGestures(canvas,stage,ctx){
  let dragging=false, dragStart=null, lastPt=null, preDragSnap=null;
  let rafPending=false;
  const ptFromEvent=(clientX,clientY)=>{
    const r=canvas.getBoundingClientRect();
    return { x:(clientX-r.left)*(canvas.width/r.width), y:(clientY-r.top)*(canvas.height/r.height) };
  };
  const shapeLineW=()=>Math.max(4,canvas.width*0.007);
  const minDragPx=()=>Math.max(18,canvas.width*0.02);

  canvas.addEventListener('touchstart',e=>{
    e.preventDefault();
    const t=e.touches[0]; const pt=ptFromEvent(t.clientX,t.clientY);
    if(anPending){
      placeAnnotateNote(t.clientX,t.clientY,pt,canvas,stage,ctx);
      return;
    }
    dragging=true; dragStart=pt; lastPt=pt;
    preDragSnap=ctx.getImageData(0,0,canvas.width,canvas.height);
  },{passive:false});

  canvas.addEventListener('touchmove',e=>{
    if(!dragging||anPending)return;
    e.preventDefault();
    const t=e.touches[0]; lastPt=ptFromEvent(t.clientX,t.clientY);
    if(!rafPending){
      rafPending=true;
      requestAnimationFrame(()=>{
        rafPending=false;
        if(dragging&&!anPending) drawShapePreview(ctx,preDragSnap,shapeBoundsFromPts(dragStart,lastPt),an.shape,an.color,shapeLineW());
      });
    }
  },{passive:false});

  canvas.addEventListener('touchend',()=>{
    if(!dragging||anPending){ dragging=false; return; }
    dragging=false;
    const dist=Math.hypot(lastPt.x-dragStart.x,lastPt.y-dragStart.y);
    if(dist<minDragPx()){
      ctx.putImageData(preDragSnap,0,0);
      return;
    }
    const box=shapeBoundsFromPts(dragStart,lastPt);
    drawShapePreview(ctx,preDragSnap,box,an.shape,an.color,shapeLineW());
    pushAnnotateUndoSnap(preDragSnap);
    anPending={ box, shape:an.shape };
    updateAnnotateHint();
  });
  canvas.addEventListener('touchcancel',()=>{
    if(dragging&&preDragSnap) ctx.putImageData(preDragSnap,0,0);
    dragging=false;
  });
}

function placeAnnotateNote(clientX,clientY,canvasPt,canvas,stage,ctx){
  const pending=anPending; if(!pending)return;
  const box=pending.box, color=an.color;
  const cx=(box.x0+box.x1)/2, cy=(box.y0+box.y1)/2;
  const halfSpan=Math.max(box.x1-box.x0,box.y1-box.y0)/2;
  const dx=cx-canvasPt.x, dy=cy-canvasPt.y;
  const dist=Math.hypot(dx,dy)||1;
  const reach=Math.min(halfSpan*0.95, dist*0.9);
  const t=Math.max(0,(dist-reach)/dist);
  const tipX=canvasPt.x+dx*t, tipY=canvasPt.y+dy*t;
  const angle=Math.atan2(tipY-canvasPt.y,tipX-canvasPt.x);
  const lineWd=Math.max(3,canvas.width*0.005);
  ctx.save();
  ctx.strokeStyle='rgba(0,0,0,.55)'; ctx.lineWidth=lineWd+3; ctx.lineCap='round';
  ctx.beginPath(); ctx.moveTo(canvasPt.x,canvasPt.y); ctx.lineTo(tipX,tipY); ctx.stroke();
  ctx.strokeStyle=color; ctx.lineWidth=lineWd;
  ctx.beginPath(); ctx.moveTo(canvasPt.x,canvasPt.y); ctx.lineTo(tipX,tipY); ctx.stroke();
  ctx.restore();
  drawArrowhead(ctx,tipX,tipY,angle,color,Math.max(10,canvas.width*0.016));

  const existing=stage.querySelector('.a-textinput'); if(existing) existing.remove();
  const r=stage.getBoundingClientRect();
  const dispScale=canvas.getBoundingClientRect().width/canvas.width;
  const fontCanvasPx=Math.max(26,canvas.width*0.04);
  const inp=document.createElement('input');
  inp.type='text'; inp.className='a-textinput';
  inp.placeholder='Note\\u2026';
  inp.style.cssText='position:absolute;left:'+(clientX-r.left)+'px;top:'+(clientY-r.top)+'px;transform:translateY(-50%);'+
    'background:rgba(0,0,0,.55);border:1px dashed '+color+';color:'+color+';'+
    'font-size:'+Math.round(fontCanvasPx*dispScale)+'px;padding:3px 7px;border-radius:4px;min-width:100px;outline:none;';
  stage.appendChild(inp); inp.focus();
  let done=false;
  const commit=()=>{
    if(done)return; done=true;
    const val=inp.value.trim(); inp.remove();
    if(val){
      ctx.font='700 '+fontCanvasPx+'px system-ui,-apple-system,sans-serif';
      ctx.textBaseline='middle';
      ctx.lineWidth=Math.max(3,fontCanvasPx*0.12); ctx.strokeStyle='rgba(0,0,0,.6)';
      ctx.strokeText(val,canvasPt.x,canvasPt.y);
      ctx.fillStyle=color; ctx.fillText(val,canvasPt.x,canvasPt.y);
    }
    anPending=null;
    updateAnnotateHint();
  };
  inp.addEventListener('blur',commit);
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'){ e.preventDefault(); inp.blur(); } });
}

"""
    edits.append((old2, new2, "replace Pen/Text annotate module with Callout tool"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # mark as applied — stamp the JS module itself so the guard is inspectable in index.html
    if MARKER not in working:
        working = working.replace(
            "let anPending=null; /* {box,shape} once a shape is drawn and we're waiting for the note tap */",
            "let anPending=null; /* {box,shape} once a shape is drawn and we're waiting for the note tap */\n/* " + MARKER + " */",
            1
        )

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
    js_path = Path("/tmp/_notebuilt_chunk7_check.js")
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

    print("\n✅ Chunk 7 applied successfully: Callout tool (circle/box + arrow + note).")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
