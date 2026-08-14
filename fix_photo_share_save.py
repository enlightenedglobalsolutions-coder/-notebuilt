#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a jobsite photo can reach the apps that need it
Run from the same folder as index.html:
    python3 fix_photo_share_save.py

WHY
---
Photos taken in Notebuilt were reachable by nothing. They live in
IndexedDB, sealed for protected projects, and there was no way to get one
into another app on the phone. The viewer gains Share and Save to device.

WHAT IT DOES
------------
The viewer's action row gains ONE icon, which opens a small sheet with
Share and Save. A sheet rather than two more icons in the top bar: that row
already carries close, a photo count and four actions, and six icon buttons
do not fit a 360px phone. The sheet is also the only honest place to put
the two things that must be said before the photo leaves — where a saved
file actually lands, and what sharing out of a vault means.

  * SHARE — `navigator.share({files:[file]})`, gated on
    `navigator.canShare({files:[file]})` as the brief requires. Where files
    cannot be shared, it falls through to Save rather than failing, and says
    so. An AbortError is the person changing their mind and is silent.

  * SAVE TO DEVICE — an ordinary download. The sheet states, before the
    tap, that it lands in Downloads and not the camera roll, because that is
    the thing people get wrong about Android downloads.

PROTECTED PROJECTS
------------------
`photoBlobFor()` mirrors `photoURL()`'s decryption exactly: enc:1 needs
`_vaultKey`, env:1 (captured while locked, not yet resealed) needs
`_vaultPriv`. Locked, it returns null and the sheet says to unlock first —
the same rule for both shapes, as specified.

Decryption goes to a Blob in memory and to a share payload or a download the
person asked for. Nothing plaintext is written to IndexedDB, to
localStorage, or to a cache. The object URL created for a download is
revoked immediately after.

Leaving the vault is stated in one line before it happens, and confirmed,
because an unprotected copy going out to another app is not recoverable
once it is gone.

THE PAYLOAD IS THE IMAGE
------------------------
`{files:[file]}` and nothing else — no `title`, no `text`, no `url`, and a
filename built only from a timestamp. No project name, no project id, no
photo id, no storage key. Guarded below, the same way the app-share payload
is.

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

    # 1 — the decrypted blob, by the same rules photoURL already follows
    old_helper = """/* ---------- helpers ---------- */
function toast(msg){"""
    new_helper = """/* PHOTO_SHARE — the bytes, decrypted in memory, for a share payload or a
   download the person has asked for. Deliberately NOT routed through
   photoURL()'s object-URL cache: this hands the plaintext to another app,
   so it is written out explicitly here rather than borrowing a handle that
   exists for putting pixels on screen. Same lock rules as photoURL: a
   sealed photo needs the vault open, and a photo captured while locked and
   not yet resealed needs the envelope key. Nothing plaintext is persisted
   anywhere by this function. */
async function photoBlobFor(id){
  const rec=await photoGet(id); if(!rec) return null;
  if(isEncPhoto(rec)){
    if(!_vaultKey) return null;
    try{ const pt=await vaultOpenBytes(rec.iv, rec.ct);
         return new Blob([pt],{type:rec.type||'image/jpeg'}); }catch(e){ return null; }
  }
  if(isEnvPhoto(rec)){
    if(!_vaultPriv) return null;
    try{ const pt=await vaultEnvelopeOpen(rec);
         return new Blob([pt],{type:rec.type||'image/jpeg'}); }catch(e){ return null; }
  }
  return rec.blob||null;
}

/* A name carrying a timestamp and nothing else. Not the project, not the
   photo id, not a storage key — a filename travels with the file. */
function photoOutName(){
  const d=new Date();
  const p=n=>String(n).padStart(2,'0');
  return 'notebuilt-'+d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())
         +'-'+p(d.getHours())+p(d.getMinutes())+p(d.getSeconds())+'.jpg';
}

/* ---------- helpers ---------- */
function toast(msg){"""
    edits.append((old_helper, new_helper, "photoBlobFor() + photoOutName()"))

    # 2 — the sheet, and the two ways out
    old_del = """async function deleteViewerPhoto(){"""
    new_del = """/* PHOTO_SHARE — one sheet, because the two sentences that have to be read
   before a photo leaves the app need somewhere to live, and because six
   icon buttons do not fit the viewer's top row on a phone. */
function openPhotoSendSheet(){
  const pid=vw.photos[vw.index]; if(!pid) return;
  const h=houseById(vw.houseId);
  const prot=!!(h && h.protected);
  sheet('<h2>Send this photo</h2>'
    +(prot?'<div class="card" style="background:var(--ink-2);margin-bottom:12px"><div class="muted" style="font-size:13px;line-height:1.6">'
        +'This project is protected. Sharing or saving sends an <b style="color:var(--paper)">unprotected copy out of the vault</b> \\u2014 whatever receives it holds a plain photo that Notebuilt no longer controls.'
        +'</div></div>':'')
    +'<div class="muted" style="font-size:13px;line-height:1.6;margin-bottom:12px">'
    +'Share hands the image to another app on this phone. Save puts it in your <b style="color:var(--paper)">Downloads</b> folder \\u2014 not the camera roll.'
    +'</div>'
    +'<button class="btn primary block" data-ph-share>'+I.share+' Share\\u2026</button>'
    +'<button class="btn block" style="margin-top:10px" data-ph-save>'+I.download+' Save to device</button>'
    +'<button class="btn block" style="margin-top:10px" data-ph-cancel>Cancel</button>');
  $mr.querySelector('[data-ph-cancel]').onclick=closeSheet;
  $mr.querySelector('[data-ph-share]').onclick=()=>sendViewerPhoto(true);
  $mr.querySelector('[data-ph-save]').onclick=()=>sendViewerPhoto(false);
}

async function sendViewerPhoto(wantShare){
  const pid=vw.photos[vw.index]; if(!pid) return;
  const h=houseById(vw.houseId);
  const prot=!!(h && h.protected);
  /* Said once, plainly, and confirmed — an unprotected copy in another app
     cannot be called back. */
  if(prot && !confirm('Send an unprotected copy out of the vault?\\n\\n'
      +'The photo leaves encrypted storage as an ordinary image. Whatever receives it keeps it.')) return;
  const blob=await photoBlobFor(pid);
  if(!blob){
    closeSheet();
    toast(prot?'Unlock the vault to send this photo':'Could not read that photo');
    return;
  }
  const file=new File([blob], photoOutName(), {type:blob.type||'image/jpeg'});
  if(wantShare && navigator.canShare && navigator.share){
    let ok=false;
    try{ ok=navigator.canShare({files:[file]}); }catch(e){ ok=false; }
    if(ok){
      closeSheet();
      /* SHARE_PAYLOAD — the image and nothing else. No title, no text, no
         url: none of them are the photo, and all of them would carry
         something about where it came from. */
      try{ await navigator.share({files:[file]}); }
      catch(err){ if(!(err && err.name==='AbortError')) toast('Could not share that photo'); }
      return;
    }
    toast('Sharing files is not available here \\u2014 saving instead');
  }
  closeSheet();
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob); a.download=file.name; a.click();
  setTimeout(()=>{ try{ URL.revokeObjectURL(a.href); }catch(e){} },1000);
  toast('Saved to your Downloads folder');
}

async function deleteViewerPhoto(){"""
    edits.append((old_del, new_del, "openPhotoSendSheet() + sendViewerPhoto()"))

    # 3 — one new icon in the viewer, and its binding
    old_actions = """        <button class="icon-btn" data-v-markup aria-label="Add markup">${I.edit}</button>"""
    new_actions = """        <button class="icon-btn" data-v-markup aria-label="Add markup">${I.edit}</button>
        <button class="icon-btn" data-v-send aria-label="Share or save photo">${I.share}</button>"""
    edits.append((old_actions, new_actions, "viewer: the send icon"))

    old_bindv = """  $viewer.querySelector('[data-v-cover]').onclick=setViewerCover;"""
    new_bindv = """  $viewer.querySelector('[data-v-cover]').onclick=setViewerCover;
  $viewer.querySelector('[data-v-send]').onclick=openPhotoSendSheet;"""
    edits.append((old_bindv, new_bindv, "viewer: bind the send icon"))

    # 4 — info-mode copy (the brief's list was cut off mid-sentence; written
    #     to the spec's own stated points)
    old_help = """  'unlock':'Free covers three projects,"""
    new_help = """  'photo-send':'Share hands the image straight to another app on this phone \\u2014 your workforce app, a message, email. Save to device puts a copy in your Downloads folder, which is not the same place as your camera roll; your gallery may not show it. Only the picture is sent: no project name, no address, nothing about where it was taken. From a protected project, both of these take the photo out of the vault as an ordinary unprotected image, and whatever receives it keeps it \\u2014 which is why it asks first, and why it needs the vault open to do it at all.',
  'unlock':'Free covers three projects,"""
    edits.append((old_help, new_help, "HELP_COPY: photo-send"))

    # Hooked on the sheet's own copy — the place the explanation belongs —
    # rather than on the image stage. Anchors text introduced by edit 2 above,
    # which is already in `working` by the time this one runs.
    old_helpattr = """    +'<div class="muted" style="font-size:13px;line-height:1.6;margin-bottom:12px">'
    +'Share hands the image to another app on this phone."""
    new_helpattr = """    +'<div class="muted" data-help="photo-send" style="font-size:13px;line-height:1.6;margin-bottom:12px">'
    +'Share hands the image to another app on this phone."""
    edits.append((old_helpattr, new_helpattr, "send sheet: info-mode hook"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    send = working[working.find("async function sendViewerPhoto"):working.find("async function deleteViewerPhoto")]
    # The payload is the image. Nothing that names where it came from.
    m = re.search(r"navigator\.share\(\{([^}]*)\}\)", send)
    if not m:
        fail("could not isolate the share payload.")
    payload = m.group(1)
    if payload.strip() != "files:[file]":
        fail(f"the share payload carries more than the image: {payload!r}")
    for leak in ["h.name", "vw.houseId", "houseId:", "pid", "project"]:
        if leak in payload:
            fail(f"the share payload leaks {leak!r}")
    # canShare must actually gate the share.
    if "navigator.canShare" not in send:
        fail("share is not gated on canShare({files}).")
    # No plaintext may be persisted by the send path.
    for stray, why in [
        ("photoPut(", "the send path must never write a photo record"),
        ("localStorage.setItem", "the send path must never write to storage"),
        ("_objUrls.set", "the send path must not populate the display cache"),
    ]:
        if stray in send:
            fail(f"{why} — found {stray!r}")
    if "URL.revokeObjectURL" not in send:
        fail("the download object URL is never revoked.")
    # Locked vault must block both shapes.
    blobfn = working[working.find("async function photoBlobFor"):working.find("function photoOutName")]
    if "_vaultKey" not in blobfn or "_vaultPriv" not in blobfn:
        fail("photoBlobFor does not enforce both lock shapes.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: share payload is exactly {files:[file]} — nothing about origin")
    print("✅ guard: send path persists nothing; both lock shapes enforced")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_share_check.js")
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

    print("\n✅ a photo can now reach another app — and says what that costs first.")


if __name__ == "__main__":
    main()
