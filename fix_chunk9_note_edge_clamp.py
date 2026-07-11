#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 9: fix callout note text getting cut off near edges
Run this from the same folder as your index.html:
    python3 fix_chunk9_note_edge_clamp.py

Bug: when you tapped near the edge of a photo to place a callout note, the
text drew starting exactly at that point and could run straight off the
edge of the photo (and the floating input box while typing could run off
the visible editor too). This fixes both: the note text now always
repositions itself inward so the whole note stays visible, and the arrow
is drawn to match wherever the text actually ends up.

Requires Chunk 7 (fix_chunk7_callout_annotate.py) to already be applied.

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
MARKER = "CHUNK9_NOTE_EDGE_CLAMP"  # already-applied guard
PREREQ_MARKER = "CHUNK7_CALLOUT_ANNOTATE"

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
        fail("Chunk 7 (Callout tool) doesn't look applied yet. Run fix_chunk7_callout_annotate.py first.")

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: replace placeAnnotateNote() with an edge-aware version
    # ---------------------------------------------------------------
    old1 = """function placeAnnotateNote(clientX,clientY,canvasPt,canvas,stage,ctx){
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
}"""
    new1 = """function placeAnnotateNote(clientX,clientY,canvasPt,canvas,stage,ctx){
  const pending=anPending; if(!pending)return;
  const box=pending.box, color=an.color;

  /* CHUNK9_NOTE_EDGE_CLAMP — the arrow is now drawn at commit time, once we
     know the note text and can keep it fully inside the photo. */
  const existing=stage.querySelector('.a-textinput'); if(existing) existing.remove();
  const r=stage.getBoundingClientRect();
  const dispScale=canvas.getBoundingClientRect().width/canvas.width;
  const fontCanvasPx=Math.max(26,canvas.width*0.04);

  const inp=document.createElement('input');
  inp.type='text'; inp.className='a-textinput';
  inp.placeholder='Note\\u2026';
  const inputW=Math.min(220,Math.round(r.width*0.7));
  let leftPx=clientX-r.left;
  if(leftPx+inputW>r.width-8) leftPx=Math.max(8,r.width-8-inputW);
  const topPx=clientY-r.top;
  inp.style.cssText='position:absolute;left:'+leftPx+'px;top:'+topPx+'px;transform:translateY(-50%);'+
    'width:'+inputW+'px;background:rgba(0,0,0,.55);border:1px dashed '+color+';color:'+color+';'+
    'font-size:'+Math.round(fontCanvasPx*dispScale)+'px;padding:3px 7px;border-radius:4px;outline:none;';
  stage.appendChild(inp); inp.focus();

  let done=false;
  const commit=()=>{
    if(done)return; done=true;
    const val=inp.value.trim(); inp.remove();
    if(!val){ anPending=null; updateAnnotateHint(); return; }

    ctx.font='700 '+fontCanvasPx+'px system-ui,-apple-system,sans-serif';
    ctx.textBaseline='middle'; ctx.textAlign='left';
    const textW=ctx.measureText(val).width;
    const margin=Math.max(10,canvas.width*0.012);
    let tx=canvasPt.x, ty=canvasPt.y;
    if(tx+textW+margin>canvas.width) tx=canvas.width-textW-margin;
    if(tx<margin) tx=margin;
    const halfH=fontCanvasPx*0.6;
    if(ty-halfH<margin) ty=margin+halfH;
    if(ty+halfH>canvas.height-margin) ty=canvas.height-halfH-margin;

    const cx=(box.x0+box.x1)/2, cy=(box.y0+box.y1)/2;
    const halfSpan=Math.max(box.x1-box.x0,box.y1-box.y0)/2;
    const dx=cx-tx, dy=cy-ty;
    const dist=Math.hypot(dx,dy)||1;
    const reach=Math.min(halfSpan*0.95, dist*0.9);
    const t=Math.max(0,(dist-reach)/dist);
    const tipX=tx+dx*t, tipY=ty+dy*t;
    const angle=Math.atan2(tipY-ty,tipX-tx);
    const lineWd=Math.max(3,canvas.width*0.005);
    ctx.save();
    ctx.strokeStyle='rgba(0,0,0,.55)'; ctx.lineWidth=lineWd+3; ctx.lineCap='round';
    ctx.beginPath(); ctx.moveTo(tx,ty); ctx.lineTo(tipX,tipY); ctx.stroke();
    ctx.strokeStyle=color; ctx.lineWidth=lineWd;
    ctx.beginPath(); ctx.moveTo(tx,ty); ctx.lineTo(tipX,tipY); ctx.stroke();
    ctx.restore();
    drawArrowhead(ctx,tipX,tipY,angle,color,Math.max(10,canvas.width*0.016));

    ctx.font='700 '+fontCanvasPx+'px system-ui,-apple-system,sans-serif';
    ctx.textBaseline='middle'; ctx.textAlign='left';
    ctx.lineWidth=Math.max(3,fontCanvasPx*0.12); ctx.strokeStyle='rgba(0,0,0,.6)';
    ctx.strokeText(val,tx,ty);
    ctx.fillStyle=color; ctx.fillText(val,tx,ty);

    anPending=null;
    updateAnnotateHint();
  };
  inp.addEventListener('blur',commit);
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'){ e.preventDefault(); inp.blur(); } });
}"""
    edits.append((old1, new1, "placeAnnotateNote(): keep note text fully inside the photo"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    if MARKER not in working:
        working = working.replace(
            "function placeAnnotateNote(clientX,clientY,canvasPt,canvas,stage,ctx){\n  const pending=anPending; if(!pending)return;\n  const box=pending.box, color=an.color;\n\n  /* CHUNK9_NOTE_EDGE_CLAMP",
            "function placeAnnotateNote(clientX,clientY,canvasPt,canvas,stage,ctx){\n  const pending=anPending; if(!pending)return;\n  const box=pending.box, color=an.color;\n\n  /* CHUNK9_NOTE_EDGE_CLAMP",
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
    js_path = Path("/tmp/_notebuilt_chunk9_check.js")
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

    print("\n✅ Chunk 9 applied successfully: callout notes now stay fully visible near photo edges.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
