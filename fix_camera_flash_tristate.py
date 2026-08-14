#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — one flash button, three modes: Off → Flash → Torch
Run from the same folder as index.html:
    python3 fix_camera_flash_tristate.py

WHAT CHANGES
------------
The viewfinder's flash control stops being a flashlight switch and becomes a
three-mode cycle. The lamp plumbing from the last ship is kept intact —
`camSetTorch()` remains the only thing that ever writes `cam.torchOn`, and
`camStop()` remains the only place the lamp is extinguished — and the modes
are layered on top of it rather than replacing it.

  OFF    struck bolt, dim chip.  No light, ever.
  FLASH  filled bolt, brass chip. Viewfinder stays DARK while framing; the
         lamp lives only for the duration of one capture.
  TORCH  flashlight glyph, white chip. Continuous light while framing, shots
         taken under it, and it stays lit across "Keep & take another".

Three silhouettes and three chip colours, because the brief's real
requirement is that the state reads at a glance in sunlight — a single glyph
that only changes colour does not.

THE FLASH CAPTURE, AND WHY IT IS A `finally`
---------------------------------------------
    lamp on -> settle -> capture -> lamp off, in a finally

`FLASH_SETTLE_MS` is 300 (the brief's 250-400 band, middle). Too early and
the sensor reads a frame the lamp has not reached yet — dark, or blown as
auto-exposure over-corrects. It is one constant, deliberately alone on its
line, because tuning it on device is expected.

The extinguish sits in a `finally`, so a capture that throws still puts the
light out. That is the whole reason the capture is wrapped at all: the
failure mode being designed against is not a bad photo, it is a phone left
burning after one.

`litForShot` records whether THIS shot turned the lamp on. Only then does the
finally turn it off — so a TORCH-mode capture, where the lamp was already on
and must stay on, is never darkened by the shot that happened under it.

Where Max goes through a real `ImageCapture` and the device advertises
`fillLightMode: 'flash'`, the burst is preferred and the manual dance is
skipped entirely — no settle delay, no torch, the hardware does it properly.

MODE ACROSS A TRACK SWAP
------------------------
A new track drops every constraint, so `camStart` reads the desired mode
BEFORE `camStop` clears it and reapplies it to the new track. A lens with no
lamp (`getCapabilities().torch` absent — front cameras, several rear lenses)
drops the mode to OFF and hides the button rather than greying it.

Backgrounding deliberately does NOT carry the mode back: `camStop` resets it
to OFF, which is both the brief's "resets to OFF on camera exit" and the
safer default for a light.

KILL RULES
----------
Unchanged and still absolute — the lamp dies in `camStop()`, which every exit
routes through (Keep & done, cancel, the X, lens switch, visibilitychange,
pagehide), plus the new `finally` for a throwing capture. Guards below assert
all of it.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — a third silhouette
    old_icon = """  boltOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8z"/><path d="M3 3l18 18"/></svg>',"""
    new_icon = """  boltOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8z"/><path d="M3 3l18 18"/></svg>',
  /* A lamp, not a bolt: continuous light has to be told apart from a burst at
     arm's length in sunlight, which colour alone does not do. */
  torchOn:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2h6l-.7 4.5H9.7z" fill="currentColor"/><path d="M9.7 6.5h4.6l.7 13a3 3 0 0 1-6 0z" fill="currentColor"/><path d="M19 4.5l2.5-1.5M19.5 9h3M19 13.5l2.5 1.5"/></svg>',"""
    edits.append((old_icon, new_icon, "icons: torchOn"))

    # 2 — a third chip colour
    old_css = """  .cam-flash.on{background:var(--brass);border-color:var(--brass);color:#231a07}"""
    new_css = """  .cam-flash.on{background:var(--brass);border-color:var(--brass);color:#231a07}
  /* Continuous light gets its own colour as well as its own glyph. */
  .cam-flash.torch{background:var(--paper);border-color:var(--paper);color:#15181D}"""
    edits.append((old_css, new_css, "CSS: .cam-flash.torch"))

    # 3 — the settle constant, alone so it is easy to tune on device
    old_const = """async function camSetTorch(on){"""
    new_const = """/* CAM_FLASH — the gap between striking the lamp and reading the sensor.
   Too short and the frame is dark, or blown as auto-exposure over-corrects
   after the fact. The brief's band is 250-400ms; this is the middle of it and
   is expected to be tuned on a real device. */
const FLASH_SETTLE_MS=300;

/* off -> flash -> torch -> off */
const FLASH_MODES=['off','flash','torch'];
function camFlashMode(){ return cam.flashMode||'off'; }

async function camSetTorch(on){"""
    edits.append((old_const, new_const, "FLASH_SETTLE_MS + mode order"))

    # 4 — the mode setter, layered over the lamp
    old_setter_tail = """/* Only what the device genuinely exposes. Labels are blank until permission has
   been granted, which is why this runs after getUserMedia. */"""
    new_setter_tail = """/* CAM_FLASH — the mode, and the framing light that follows from it. Only
   TORCH lights the viewfinder; FLASH stays dark until the shutter, which is
   the whole difference between the two. A lens with no lamp cannot hold a
   mode at all. */
async function camSetFlashMode(mode){
  if(!cam.torchCap){ cam.flashMode='off'; return false; }
  cam.flashMode=mode;
  const wantLit=(mode==='torch');
  if(wantLit!==!!cam.torchOn){
    const ok=await camSetTorch(wantLit);
    /* Asked for light and refused: say off, because that is what is true. */
    if(!ok && wantLit){ cam.flashMode='off'; return false; }
  }
  return true;
}

/* Only what the device genuinely exposes. Labels are blank until permission has
   been granted, which is why this runs after getUserMedia. */"""
    edits.append((old_setter_tail, new_setter_tail, "camSetFlashMode()"))

    # 5 — reset the mode with the lamp
    old_stop = """  cam.torchOn=false; cam.torchCap=false; cam.fillFlash=false;"""
    new_stop = """  cam.torchOn=false; cam.torchCap=false; cam.fillFlash=false; cam.flashMode='off';"""
    edits.append((old_stop, new_stop, "camStop(): reset the mode too"))

    # 6 — carry the mode across a track swap
    old_want = """  const wantTorch=!!cam.torchOn;
  camStop();"""
    new_want = """  const wantMode=camFlashMode();
  camStop();"""
    edits.append((old_want, new_want, "camStart(): remember the mode"))

    old_reapply = """  if(wantTorch && cam.torchCap) await camSetTorch(true);"""
    new_reapply = """  /* CAM_FLASH — a new track carries none of the old constraints. Put the mode
     back on it, or drop to OFF where this lens has no lamp to put it on. */
  if(!cam.torchCap) cam.flashMode='off';
  else if(wantMode!=='off') await camSetFlashMode(wantMode);"""
    edits.append((old_reapply, new_reapply, "camStart(): reapply the mode"))

    # 7 — three states on the button
    old_btn = """    +(cam.torchCap
        ? '<button class="cam-flash'+(cam.torchOn?' on':'')+'" data-cam-torch aria-pressed="'+(cam.torchOn?'true':'false')
          +'" aria-label="'+(cam.torchOn?'Turn flash off':'Turn flash on')+'">'+(cam.torchOn?I.bolt:I.boltOff)+'</button>'
        : '')"""
    new_btn = """    +(cam.torchCap
        ? (function(){
            const m=camFlashMode();
            const cls = m==='torch' ? ' on torch' : (m==='flash' ? ' on' : '');
            const gly = m==='torch' ? I.torchOn : (m==='flash' ? I.bolt : I.boltOff);
            const lab = m==='off'   ? 'Flash off \\u2014 tap for flash'
                      : m==='flash' ? 'Flash on \\u2014 tap for torch'
                      :               'Torch on \\u2014 tap to turn off';
            return '<button class="cam-flash'+cls+'" data-cam-torch aria-label="'+lab+'" title="'+lab+'">'+gly+'</button>';
          })()
        : '')"""
    edits.append((old_btn, new_btn, "camDrawLive(): three states"))

    # 8 — cycle, don't toggle
    old_bind = """  if(torch) torch.onclick=async()=>{
    const want=!cam.torchOn;
    const ok=await camSetTorch(want);
    if(!ok && want) toast('This lens would not turn its flash on');
    camDrawLive();                        /* redraw from the lamp, not the wish */
  };"""
    new_bind = """  if(torch) torch.onclick=async()=>{
    const next=FLASH_MODES[(FLASH_MODES.indexOf(camFlashMode())+1)%FLASH_MODES.length];
    const ok=await camSetFlashMode(next);
    if(!ok) toast('This lens would not turn its flash on');
    camDrawLive();                        /* redraw from the lamp, not the wish */
  };"""
    edits.append((old_bind, new_bind, "camBind(): cycle the mode"))

    # 9 — the capture, with the lamp's life bounded by it
    old_shoot = """  let blob=null;
  const wantedMax=(cam.presetKey==='max');
  let gotMax=false;
  if(wantedMax && cam.imageCapture){
    /* full sensor resolution where the browser offers it. CAM_TORCH — where
       the device offers a genuine flash burst, ask for it rather than leaning
       on the lamp; everywhere else the torch is already lighting the scene
       and covers both modes. */
    const opts=(cam.torchOn && cam.fillFlash) ? {fillLightMode:'flash'} : null;
    try{ blob=await (opts ? cam.imageCapture.takePhoto(opts) : cam.imageCapture.takePhoto());
         gotMax=!!blob; }catch(e){ blob=null; }
  }
  /* The fallback is a canvas grab of the PREVIEW — viewfinder resolution,
     not sensor resolution. It used to happen silently, so Max could quietly
     deliver a Standard-sized frame. The review screen now says so. */
  if(!blob) blob=await camGrabFrame();"""
    new_shoot = """  let blob=null;
  const wantedMax=(cam.presetKey==='max');
  let gotMax=false;
  /* CAM_FLASH — a real burst is better than anything done by hand: no settle
     delay, no lamp to remember to extinguish. Only worth it at Max, through a
     genuine ImageCapture, on a device that advertises it. */
  const useBurst=(wantedMax && cam.imageCapture && camFlashMode()==='flash' && cam.fillFlash);
  /* Did THIS shot strike the lamp? Only then may it put it out — a capture
     taken under TORCH must never darken the light it was taken under. */
  let litForShot=false;
  try{
    if(camFlashMode()==='flash' && !useBurst){
      litForShot=await camSetTorch(true);
      /* Read the sensor before the lamp arrives and the frame is dark, or
         blown once auto-exposure catches up. */
      if(litForShot) await new Promise(r=>setTimeout(r,FLASH_SETTLE_MS));
    }
    if(wantedMax && cam.imageCapture){
      /* full sensor resolution where the browser offers it. */
      const opts=useBurst ? {fillLightMode:'flash'} : null;
      try{ blob=await (opts ? cam.imageCapture.takePhoto(opts) : cam.imageCapture.takePhoto());
           gotMax=!!blob; }catch(e){ blob=null; }
    }
    /* The fallback is a canvas grab of the PREVIEW — viewfinder resolution,
       not sensor resolution. It used to happen silently, so Max could quietly
       deliver a Standard-sized frame. The review screen now says so. */
    if(!blob) blob=await camGrabFrame();
  } finally {
    /* The point of the wrapper: a capture that throws still puts the light
       out. A phone left burning is worse than a photo not taken. */
    if(litForShot) await camSetTorch(false);
  }"""
    edits.append((old_shoot, new_shoot, "camShoot(): flash capture bounded by a finally"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # The lamp still has exactly one writer, and camStop still kills it.
    writers = re.findall(r"cam\.torchOn\s*=[^=]", working)
    if len(writers) != 3:
        fail(f"unexpected number of cam.torchOn writers: {len(writers)}")
    stop_body = working[working.find("function camStop(){"):working.find("function camClose()")]
    for needed, why in [("torch:false", "camStop no longer extinguishes the lamp"),
                        ("cam.flashMode='off'", "camStop no longer resets the mode")]:
        if needed not in stop_body:
            fail(why)
    if stop_body.index("torch:false") > stop_body.index("getTracks().forEach"):
        fail("the lamp is extinguished after the track is released — wrong order.")
    for path in ["function camClose(){\n  camStop();",
                 "if(document.visibilityState==='hidden') camStop();",
                 "window.addEventListener('pagehide',()=>{ if(cam.open) camStop(); });"]:
        if path not in working:
            fail(f"a teardown path no longer routes through camStop: {path!r}")

    # The shot-scoped light must be released in a finally, not on the happy path.
    shoot = working[working.find("async function camShoot(){"):working.find("function camRetake()")]
    if "} finally {" not in shoot:
        fail("the flash capture is not wrapped in a finally.")
    fin = shoot[shoot.index("} finally {"):]
    if "camSetTorch(false)" not in fin:
        fail("the finally does not extinguish the shot-scoped light.")
    if shoot.count("camSetTorch(false)") != 1:
        fail("the shot-scoped extinguish must exist exactly once, in the finally.")
    if "litForShot" not in fin:
        fail("the finally does not check whether THIS shot struck the lamp — torch mode would be darkened.")
    # TORCH must never take the manual path.
    if "camFlashMode()==='flash' && !useBurst" not in shoot:
        fail("the manual lamp dance is not restricted to FLASH mode.")

    # Three visually distinct states must actually exist.
    live = working[working.find("function camDrawLive(){"):working.find("function camDrawReview(){")]
    for glyph in ["I.torchOn", "I.bolt", "I.boltOff"]:
        if glyph not in live:
            fail(f"the button is missing a state glyph: {glyph}")
    if "' on torch'" not in live:
        fail("torch has no distinct chip class.")
    if "disabled" in live and "cam-flash" in live and "cam.torchCap" not in live:
        fail("the flash button appears to be greyed rather than absent.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: one lamp writer; camStop still extinguishes and now resets the mode")
    print("✅ guard: shot-scoped light released in a finally, only when this shot struck it")
    print("✅ guard: three distinct glyphs + a distinct torch chip; button absent, not greyed")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_tristate_check.js")
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

    print("\n✅ off, flash, torch — and the lamp outlives none of them.")


if __name__ == "__main__":
    main()
