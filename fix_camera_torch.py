#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — flash in the in-app viewfinder, and never left on
Run from the same folder as index.html:
    python3 fix_camera_torch.py

WHY THE TEARDOWN IS THE INTERESTING PART
-----------------------------------------
Turning a torch on is three lines. The failure that matters is leaving a
phone's lamp burning after the person has walked away from the camera, so
the off-switch is placed where it cannot be missed rather than at each exit.

`camStop()` is the single choke point every teardown already routes through:

    camClose()            -> camStop()      (Keep & done, Cancel, the X)
    camStart()            -> camStop()      (lens switch, before re-acquire)
    visibilitychange hidden-> camStop()     (backgrounded, incl. relock)
    pagehide              -> camStop()      (the page going away)

So the torch is extinguished in `camStop()`, once, and every path inherits
it. `applyConstraints` is fired without awaiting because `camStop` is
synchronous and `pagehide` gives nothing to await in; `t.stop()` immediately
after is the hard guarantee, since a stopped track releases the lamp. Belt
and braces, in that order.

PER-LENS, NOT PER-DEVICE
------------------------
`track.getCapabilities().torch` is read from the ACTIVE track each time one
is acquired. Front cameras and several rear lenses have no lamp, and the
button is absent for them rather than greyed — a disabled flash button
invites a tap that can never work.

SURVIVING A LENS SWITCH
-----------------------
A new track does not carry the old constraint. `camStart` remembers the
desired state BEFORE `camStop` clears it, then reapplies it on the new track
if that lens has a lamp. Where it does not, the state stays off and the
button disappears — the button always describes the track that exists, never
an intention.

Backgrounding is deliberately NOT covered by that: `camStop` clears the flag
before the page is hidden, so returning finds the torch off, which is what
the brief requires.

MAX
---
Where Max goes through `ImageCapture` and the device advertises
`fillLightMode: 'flash'`, the Max shot asks for a real burst instead of
relying on the lamp. `getPhotoCapabilities()` is raced against a 800ms
timeout: a promise that neither resolves nor rejects is exactly how
2026.08.12-1407 hung this app's launch, and a capability probe is not worth
a viewfinder that never opens. Anywhere the burst is unavailable, the torch
already lights the scene and covers both modes.

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

    # 1 — two glyphs, lit and unlit
    old_icon = """  lock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',"""
    new_icon = """  lock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',
  /* CAM_TORCH — filled when the lamp is on, outline with a slash when off. */
  bolt:'<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8z"/></svg>',
  boltOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M13 2 5 14h5l-1 8 8-12h-5l1-8z"/><path d="M3 3l18 18"/></svg>',"""
    edits.append((old_icon, new_icon, "icons: bolt / boltOff"))

    # 2 — the control, sized to sit beside the shutter
    old_css = """  .cam-chip.on{background:var(--brass);border-color:var(--brass);color:#231a07}"""
    new_css = """  .cam-chip.on{background:var(--brass);border-color:var(--brass);color:#231a07}
  /* CAM_TORCH — same footprint as the spacer opposite it, so the shutter
     stays centred whether or not this lens has a lamp. */
  .cam-flash{
    width:46px;height:46px;border-radius:50%;display:grid;place-items:center;flex:none;
    border:1px solid var(--line);background:rgba(255,255,255,.06);color:var(--paper-dim);
  }
  .cam-flash.on{background:var(--brass);border-color:var(--brass);color:#231a07}
  .cam-flash svg{width:22px;height:22px}"""
    edits.append((old_css, new_css, "CSS: .cam-flash"))

    # 3 — off in the one place every teardown already goes through
    old_stop = """function camStop(){
  /* Complete teardown: tracks stopped, srcObject cleared, references dropped.
     A live indicator light after leaving the viewfinder is not acceptable. */
  try{ if(cam.stream) cam.stream.getTracks().forEach(t=>{ try{ t.stop(); }catch(e){} }); }catch(e){}"""
    new_stop = """function camStop(){
  /* Complete teardown: tracks stopped, srcObject cleared, references dropped.
     A live indicator light after leaving the viewfinder is not acceptable. */
  /* CAM_TORCH — the lamp goes out here, and therefore on every exit: close,
     cancel, lens switch, backgrounding and pagehide all arrive through this
     function. Not awaited, because this is synchronous and pagehide gives
     nothing to wait in; the t.stop() below is the hard guarantee, since a
     released track releases the lamp with it. */
  try{
    const _t=cam.stream && cam.stream.getVideoTracks && cam.stream.getVideoTracks()[0];
    if(_t && cam.torchOn){ try{ _t.applyConstraints({advanced:[{torch:false}]}); }catch(e){} }
  }catch(e){}
  cam.torchOn=false; cam.torchCap=false; cam.fillFlash=false;
  try{ if(cam.stream) cam.stream.getTracks().forEach(t=>{ try{ t.stop(); }catch(e){} }); }catch(e){}"""
    edits.append((old_stop, new_stop, "camStop(): extinguish, then release"))

    # 4 — detect on the new track, and carry a lens switch across
    old_start = """async function camStart(deviceId){
  camStop();"""
    new_start = """async function camStart(deviceId){
  /* CAM_TORCH — read the wish before camStop() clears it, so switching lens
     can carry the lamp over. Backgrounding deliberately does not: camStop
     runs on its own there, the flag is already false by the time we return,
     and the torch comes back off. */
  const wantTorch=!!cam.torchOn;
  camStop();"""
    edits.append((old_start, new_start, "camStart(): remember the wish"))

    old_after = """  cam.imageCapture=null;
  try{ if(window.ImageCapture && track) cam.imageCapture=new ImageCapture(track); }catch(e){}
  await camListDevices();
  camDrawLive();"""
    new_after = """  cam.imageCapture=null;
  try{ if(window.ImageCapture && track) cam.imageCapture=new ImageCapture(track); }catch(e){}
  /* CAM_TORCH — capability belongs to THIS track. Front cameras and several
     rear lenses have no lamp; the button is absent for those rather than
     greyed, because a disabled flash button invites a tap that cannot work. */
  cam.torchCap=false; cam.fillFlash=false;
  try{ const caps=(track && track.getCapabilities) ? track.getCapabilities() : null;
       cam.torchCap=!!(caps && caps.torch); }catch(e){}
  /* A capability probe is not worth a viewfinder that never opens: raced,
     because a promise that neither resolves nor rejects is exactly how
     2026.08.12-1407 hung this app on launch. */
  try{
    if(cam.imageCapture && cam.imageCapture.getPhotoCapabilities){
      const pc=await Promise.race([
        cam.imageCapture.getPhotoCapabilities().catch(()=>null),
        new Promise(r=>setTimeout(()=>r(null),800))
      ]);
      const modes=pc && pc.fillLightMode;
      cam.fillFlash=!!(modes && modes.indexOf && modes.indexOf('flash')>=0);
    }
  }catch(e){ cam.fillFlash=false; }
  if(wantTorch && cam.torchCap) await camSetTorch(true);
  await camListDevices();
  camDrawLive();"""
    edits.append((old_after, new_after, "camStart(): detect + reapply"))

    # 5 — the toggle itself
    old_list = """/* Only what the device genuinely exposes. Labels are blank until permission has
   been granted, which is why this runs after getUserMedia. */"""
    new_list = """/* CAM_TORCH — the only writer of cam.torchOn while a track is live. A refusal
   leaves the flag false, so the button always describes the lamp rather than
   the request. */
async function camSetTorch(on){
  const track=cam.stream && cam.stream.getVideoTracks ? cam.stream.getVideoTracks()[0] : null;
  if(!track || !cam.torchCap) return false;
  try{
    await track.applyConstraints({advanced:[{torch:!!on}]});
    cam.torchOn=!!on;
    return true;
  }catch(e){
    cam.torchOn=false;
    return false;
  }
}

/* Only what the device genuinely exposes. Labels are blank until permission has
   been granted, which is why this runs after getUserMedia. */"""
    edits.append((old_list, new_list, "camSetTorch()"))

    # 6 — beside the shutter, with a spacer keeping it centred
    old_shutter = """    +'<div class="cam-shutter-row"><button class="cam-shutter" data-cam-shoot aria-label="Take photo"></button></div>'"""
    new_shutter = """    +'<div class="cam-shutter-row">'
    +(cam.torchCap
        ? '<button class="cam-flash'+(cam.torchOn?' on':'')+'" data-cam-torch aria-pressed="'+(cam.torchOn?'true':'false')
          +'" aria-label="'+(cam.torchOn?'Turn flash off':'Turn flash on')+'">'+(cam.torchOn?I.bolt:I.boltOff)+'</button>'
        : '')
    +'<button class="cam-shutter" data-cam-shoot aria-label="Take photo"></button>'
    +(cam.torchCap?'<span style="width:46px;flex:none"></span>':'')
    +'</div>'"""
    edits.append((old_shutter, new_shutter, "camDrawLive(): the flash button"))

    # 7 — bind it
    old_bind = """  const shoot=$camera.querySelector('[data-cam-shoot]'); if(shoot) shoot.onclick=camShoot;"""
    new_bind = """  const shoot=$camera.querySelector('[data-cam-shoot]'); if(shoot) shoot.onclick=camShoot;
  const torch=$camera.querySelector('[data-cam-torch]');
  if(torch) torch.onclick=async()=>{
    const want=!cam.torchOn;
    const ok=await camSetTorch(want);
    if(!ok && want) toast('This lens would not turn its flash on');
    camDrawLive();                        /* redraw from the lamp, not the wish */
  };"""
    edits.append((old_bind, new_bind, "camBind(): the flash toggle"))

    # 8 — prefer a real burst for the Max shot where one exists
    old_max = """  if(wantedMax && cam.imageCapture){
    /* full sensor resolution where the browser offers it */
    try{ blob=await cam.imageCapture.takePhoto(); gotMax=!!blob; }catch(e){ blob=null; }
  }"""
    new_max = """  if(wantedMax && cam.imageCapture){
    /* full sensor resolution where the browser offers it. CAM_TORCH — where
       the device offers a genuine flash burst, ask for it rather than leaning
       on the lamp; everywhere else the torch is already lighting the scene
       and covers both modes. */
    const opts=(cam.torchOn && cam.fillFlash) ? {fillLightMode:'flash'} : null;
    try{ blob=await (opts ? cam.imageCapture.takePhoto(opts) : cam.imageCapture.takePhoto());
         gotMax=!!blob; }catch(e){ blob=null; }
  }"""
    edits.append((old_max, new_max, "camShoot(): fillLightMode for Max"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    stop_body = working[working.find("function camStop(){"):working.find("function camClose()")]
    if "torch:false" not in stop_body:
        fail("camStop does not extinguish the torch.")
    if "cam.torchOn=false" not in stop_body:
        fail("camStop does not clear the torch flag.")
    # Compare against the actual release call, not the prose above it — the
    # comment explaining the ordering also contains the words "t.stop()".
    if stop_body.index("torch:false") > stop_body.index("getTracks().forEach"):
        fail("the torch is extinguished after the track is stopped — wrong order.")
    # Every teardown path must still route through camStop.
    for path in ["function camClose(){\n  camStop();",
                 "if(document.visibilityState==='hidden') camStop();",
                 "window.addEventListener('pagehide',()=>{ if(cam.open) camStop(); });"]:
        if path not in working:
            fail(f"a teardown path no longer routes through camStop: {path!r}")
    # camSetTorch must be the only writer of torchOn while live.
    # Exactly three assignments: the reset in camStop, and the success and
    # failure paths in camSetTorch. camStart only READS the flag (to carry a
    # lens switch), so it must not appear here — if this count grows, some new
    # code is claiming the lamp is on without having asked the track.
    writers = re.findall(r"cam\.torchOn\s*=[^=]", working)
    if len(writers) != 3:
        fail(f"unexpected number of cam.torchOn writers: {len(writers)}")
    # The button may only exist where the lamp does.
    live = working[working.find("function camDrawLive(){"):working.find("function camDrawReview(){")]
    if "cam.torchCap" not in live:
        fail("the flash button is not gated on the active track's capability.")
    if "disabled" in live and "cam-flash" in live and "cam-flash'+(cam.torchOn?' on':'')" not in live:
        fail("the flash button appears to be greyed rather than absent.")
    if "getCapabilities" not in working:
        fail("torch capability is never read from the track.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: torch extinguished in camStop, before the track is released")
    print("✅ guard: every teardown path still routes through camStop")
    print("✅ guard: button gated on the active track's capability, absent not greyed")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_torch_check.js")
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

    print("\n✅ flash where the lens has one, and out before you leave.")


if __name__ == "__main__":
    main()
