#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — take ten photos without leaving the camera
Run from the same folder as index.html:
    python3 fix_camera_multishot.py

WHICH PATH ACTUALLY SHOWS THE OK / RETRY CONFIRM
-------------------------------------------------
Established before changing anything, because the brief asks and because
the answer moves the fix:

  * PROTECTED projects -> `data-open-camera` -> the in-app getUserMedia
    viewfinder. Its review screen is Notebuilt's own, captioned "Keep this
    one?", with Retake / Keep. `camKeep()` already ends in `camDrawLive()`
    — "straight back to the viewfinder". This path ALREADY multi-shoots and
    already keeps the stream up between frames.

  * UNPROTECTED projects -> `<input type="file" capture="environment">` ->
    the phone hands over to the Android camera app. The OK / Retry confirm
    is ANDROID'S, drawn by that app, and Notebuilt cannot restyle or loop
    it: OK returns exactly one file and closes the camera app. That is the
    confirm being described, and no amount of work inside the review screen
    would have changed it.

So the multi-shot fix for the reported symptom is not a new confirm — it is
routing the Camera button at the viewfinder that already loops. The new
three-way confirm is built too, because the existing two-way one makes
"done" impossible to express once Keep stops exiting.

WHAT CHANGES
------------
1. **Camera opens the in-app viewfinder for every project**, protected or
   not. Library still uses the file picker, which is correct — that is
   choosing existing files, not capturing. The native camera remains
   reachable, but only where it already was: the explicit "Use the phone
   camera anyway" button on the camera-unavailable screen, with its risk
   stated. This also retires the hand-off that the intro screen already
   describes as where photos go missing.

2. **Three-way review**: "Keep & take another" (primary) / "Keep & done" /
   "Retake". Keeping and continuing redraws the viewfinder from the SAME
   live stream — `camDrawLive()` reassigns `srcObject` and never calls
   `camStart()`, so there is no teardown or re-acquire per shot. The
   teardown on exit, on visibilitychange and on pagehide is untouched.

3. **Nothing is held across shots.** Each kept photo goes down the existing
   `preparePhotoBlob` -> `photoPutFor` -> `persist.houses()` path and is on
   disk before the viewfinder comes back — the same single-shot pipeline,
   enc:1 unlocked and env:1 locked. The only thing that survives a shot is
   an integer counter. The Aug 1 lesson stands: no module-variable photo
   queue, nothing to flush, nothing to lose when Android reclaims the page.

4. **Exactly N records for N shots.** A `cam.saving` latch makes a second
   tap during the write a no-op, and `camShoot` refuses to fire while a
   shot is already under review. That is the double-save shape from the
   flushHeldPhotos bug, closed at the only two doors it can enter by.

5. **Max never downgrades silently.** `camShoot` falls back to a canvas
   grab of the preview when `takePhoto()` is unavailable or throws, which
   is viewfinder resolution rather than sensor resolution. That fallback
   was invisible. The shot now records whether Max was asked for and not
   delivered, and the review screen says so above the buttons. The chip
   selection itself persists in `cam.presetKey` across shots — Max stays
   Max — so the only thing being reported is a per-shot capability, which
   is exactly what the brief asked to surface rather than hide.

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

    # 1 — every project's Camera button opens the viewfinder that loops
    old_btn = """      ${h.protected
        ? `<button class="photo-add" data-open-camera="${h.id}" aria-label="Take photo">${I.camera}<span>Camera</span></button>`
        : `<label class="photo-add" aria-label="Take photo">${I.camera}<span>Camera</span><input type="file" accept="image/*" capture="environment" hidden data-add-photo></label>`}"""
    new_btn = """      <!-- CAM_MULTISHOT — the in-app viewfinder for every project, not just
           protected ones. Handing an unprotected project to the phone's
           camera app meant Android drew the confirm, Android closed the
           camera after one frame, and a jobsite visit cost ten round trips.
           It is also the hand-off the intro screen already names as where
           photos get lost. Library still uses the file picker: that is
           choosing files that already exist, not capturing. -->
      <button class="photo-add" data-open-camera="${h.id}" aria-label="Take photo">${I.camera}<span>Camera</span></button>"""
    edits.append((old_btn, new_btn, "photo grid: viewfinder for every project"))

    # 2 — record when Max was asked for and not delivered
    old_shoot = """async function camShoot(){
  const btn=$camera.querySelector('[data-cam-shoot]'); if(btn) btn.setAttribute('disabled','');
  let blob=null;
  if(cam.presetKey==='max' && cam.imageCapture){
    /* full sensor resolution where the browser offers it */
    try{ blob=await cam.imageCapture.takePhoto(); }catch(e){ blob=null; }
  }
  if(!blob) blob=await camGrabFrame();"""
    new_shoot = """async function camShoot(){
  /* CAM_MULTISHOT — one shot in flight at a time. Without this a second tap
     while the still is being prepared produces a second record for a frame
     the person only took once. */
  if(cam.saving || cam.shot) return;
  const btn=$camera.querySelector('[data-cam-shoot]'); if(btn) btn.setAttribute('disabled','');
  let blob=null;
  const wantedMax=(cam.presetKey==='max');
  let gotMax=false;
  if(wantedMax && cam.imageCapture){
    /* full sensor resolution where the browser offers it */
    try{ blob=await cam.imageCapture.takePhoto(); gotMax=!!blob; }catch(e){ blob=null; }
  }
  /* The fallback is a canvas grab of the PREVIEW — viewfinder resolution,
     not sensor resolution. It used to happen silently, so Max could quietly
     deliver a Standard-sized frame. The review screen now says so. */
  if(!blob) blob=await camGrabFrame();"""
    edits.append((old_shoot, new_shoot, "camShoot(): re-entry guard + Max fallback flag"))

    old_shot_rec = """  cam.shot={ blob, url, w:dims.w, h:dims.h };
  camDrawReview();"""
    new_shot_rec = """  cam.shot={ blob, url, w:dims.w, h:dims.h, maxMissed:(wantedMax && !gotMax) };
  camDrawReview();"""
    edits.append((old_shot_rec, new_shot_rec, "camShoot(): carry the flag onto the shot"))

    # 3 — the three-way review
    old_review = """    +'<div class="cam-controls">'
    +'<div class="cam-hint" style="padding-bottom:10px">'
    +esc(cam.shot.w+' × '+cam.shot.h+' · '+PHOTO_PRESETS[cam.presetKey].label)+'</div>'
    +'<div class="row" style="gap:10px">'
    +'<button class="btn" style="flex:1" data-cam-retake>Retake</button>'
    +'<button class="btn primary" style="flex:1" data-cam-keep>Keep</button></div></div>';
  camBind();"""
    new_review = """    +'<div class="cam-controls">'
    +'<div class="cam-hint" style="padding-bottom:10px">'
    +esc(cam.shot.w+' × '+cam.shot.h+' · '+PHOTO_PRESETS[cam.presetKey].label)
    +(cam.kept?' · '+cam.kept+' saved so far':'')+'</div>'
    /* Said, not swallowed: Max asked the sensor and the sensor declined, so
       this frame is the preview's size. The chip stays on Max for the next
       one, which may well succeed. */
    +(cam.shot.maxMissed
        ? '<div class="cam-warn" style="margin-bottom:10px">Max was not available for this shot, so it was taken at viewfinder resolution. Max is still selected for the next one.</div>'
        : '')
    +'<button class="btn primary block" data-cam-keep-more>Keep &amp; take another</button>'
    +'<div class="row" style="gap:10px;margin-top:10px">'
    +'<button class="btn" style="flex:1" data-cam-retake>Retake</button>'
    +'<button class="btn" style="flex:1" data-cam-keep-done>Keep &amp; done</button></div></div>';
  camBind();"""
    edits.append((old_review, new_review, "camDrawReview(): three-way confirm"))

    # 4 — keep, then either carry on or leave
    old_keep = """async function camKeep(){
  if(!cam.shot) return;
  const houseId=cam.houseId, h=houseById(houseId);
  if(!h){ camClose(); return; }
  const keepBtn=$camera.querySelector('[data-cam-keep]');
  if(keepBtn){ keepBtn.setAttribute('disabled',''); keepBtn.textContent='Saving…'; }
  try{
    const blob=await preparePhotoBlob(cam.shot.blob, cam.presetKey, true);
    const id=uid();
    await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
    h.photos=h.photos||[]; h.photos.push(id);
    if(!h.cover) h.cover=id;
    h.updatedAt=now(); persist.houses();
    if(cam.shot.url){ try{ URL.revokeObjectURL(cam.shot.url); }catch(e){} }
    cam.shot=null;
    toast('Photo saved');
    camDrawLive();                       /* straight back to the viewfinder */
  }catch(err){
    if(keepBtn){ keepBtn.removeAttribute('disabled'); keepBtn.textContent='Keep'; }
    toast(String(err&&err.message)==='no capture key'
      ? 'Unlock the vault once to turn on locked capture'
      : 'Could not save that photo');
  }
}"""
    new_keep = """async function camKeep(andAnother){
  /* CAM_MULTISHOT — the latch, not the button state, is what guarantees one
     record per shot. Disabling the buttons is cosmetic; a second call that
     arrives anyway finds cam.saving already true and does nothing. */
  if(!cam.shot || cam.saving) return;
  const houseId=cam.houseId, h=houseById(houseId);
  if(!h){ camClose(); return; }
  cam.saving=true;
  $camera.querySelectorAll('[data-cam-keep-more],[data-cam-keep-done],[data-cam-retake]')
         .forEach(b=>b.setAttribute('disabled',''));
  const pressed=$camera.querySelector(andAnother?'[data-cam-keep-more]':'[data-cam-keep-done]');
  if(pressed) pressed.textContent='Saving\\u2026';
  try{
    /* Unchanged from single-shot: sealed symmetrically when unlocked,
       enveloped when not, and the list persisted before anything else
       happens. On disk before the viewfinder returns — nothing is carried. */
    const blob=await preparePhotoBlob(cam.shot.blob, cam.presetKey, true);
    const id=uid();
    await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
    h.photos=h.photos||[]; h.photos.push(id);
    if(!h.cover) h.cover=id;
    h.updatedAt=now(); persist.houses();
    if(cam.shot.url){ try{ URL.revokeObjectURL(cam.shot.url); }catch(e){} }
    cam.shot=null; cam.saving=false;
    cam.kept=(cam.kept||0)+1;            /* a count, never the photos */
    if(andAnother){
      toast(cam.kept===1?'Photo saved':cam.kept+' photos saved');
      camDrawLive();                     /* same stream, no re-acquire */
    } else {
      camClose();                        /* teardown on exit, as before */
    }
  }catch(err){
    /* Redraw rather than hand-restore labels: the shot is still here, and
       the review screen is the one true description of that state. */
    cam.saving=false;
    camDrawReview();
    toast(String(err&&err.message)==='no capture key'
      ? 'Unlock the vault once to turn on locked capture'
      : 'Could not save that photo');
  }
}"""
    edits.append((old_keep, new_keep, "camKeep(): keep-and-continue or keep-and-exit"))

    # 5 — bind the two, without handing the click event in as the flag
    old_bind = """  const keep=$camera.querySelector('[data-cam-keep]'); if(keep) keep.onclick=camKeep;"""
    new_bind = """  /* Arrows, not bare references: `onclick=camKeep` would pass the click
     event as andAnother, and an event object is truthy. */
  const keepMore=$camera.querySelector('[data-cam-keep-more]'); if(keepMore) keepMore.onclick=()=>camKeep(true);
  const keepDone=$camera.querySelector('[data-cam-keep-done]'); if(keepDone) keepDone.onclick=()=>camKeep(false);"""
    edits.append((old_bind, new_bind, "camBind(): the two keep buttons"))

    # 6 — the running count where the shutter is
    old_hint = """    +'<div class="cam-hint">'+(multi?'Pick a lens · ':'')+'Tap Max for full resolution</div>'"""
    new_hint = """    +'<div class="cam-hint">'+(cam.kept?cam.kept+(cam.kept===1?' photo':' photos')+' saved · ':'')
    +(multi?'Pick a lens · ':'')+'Tap Max for full resolution</div>'"""
    edits.append((old_hint, new_hint, "camDrawLive(): running count"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # Nothing may accumulate photos across shots.
    for stray, why in [
        ("heldPhotos", "a photo queue would reintroduce the Aug 1 memory-hold bug"),
        ("flushHeldPhotos", "the double-save shape must not return"),
        ("data-cam-keep>", "the old single Keep button survived"),
    ]:
        if stray in working:
            fail(f"{why} — found {stray!r}")
    # The keep path must still write through the one pipeline, once.
    keep_body = working[working.find("async function camKeep"):working.find("function camBind")]
    if keep_body.count("photoPutFor(") != 1:
        fail("camKeep must write exactly once per shot.")
    if "cam.saving" not in keep_body:
        fail("the one-save latch is missing from camKeep.")
    if "camStart(" in keep_body:
        fail("camKeep re-acquires the stream — the viewfinder must stay live.")
    # Exit teardown must be untouched.
    for needed in ["window.addEventListener('pagehide'", "camStop();", "function camClose()"]:
        if needed not in working:
            fail(f"exit teardown changed — {needed!r} missing.")
    # The native capture hand-off may survive ONLY on the explicit error screen.
    if working.count('capture="environment"') != 1:
        fail(f"expected exactly 1 native capture input (the error-screen opt-in), "
             f"found {working.count('capture=\"environment\"')}.")
    if "data-cam-native" not in working:
        fail("the explicit native fallback was removed from the error screen.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: one write per shot, one save latch, no photo queue")
    print("✅ guard: stream never re-acquired between shots; exit teardown intact")
    print("✅ guard: native capture remains only as the explicit error-screen opt-in")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_multishot_check.js")
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

    print("\n✅ ten photos, one camera session, ten records.")


if __name__ == "__main__":
    main()
