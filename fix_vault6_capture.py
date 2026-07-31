#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 6: camera capture vs. background relock
Run this from the same folder as your index.html:
    python3 fix_vault6_capture.py

Requires the five vault scripts.

THE BUG
Tapping Camera hands control to the system camera app, which backgrounds the
PWA. visibilitychange fires, the background relock wipes the key, and when the
photo comes back there is nothing to seal it with — so it is refused and lost,
on a locked project, on a job site. The relock is doing exactly what it was
told to do. What it lacks is the distinction between "the user left" and "we
sent them out and are expecting them back".

THE FIX
An in-flight-capture flag, set as the photo input is invoked. While it is live
the BACKGROUND trigger is deferred — and only that trigger:

  * Idle relock is untouched. The 15-minute timer keeps running throughout.
  * A hard 2-minute ceiling. Wander off mid-capture and it relocks anyway,
    exactly as if the grace had never applied.
  * Photo returns -> sealed immediately, flag cleared, normal rules resume.
  * Cancel -> flag cleared on return, nothing else changes.

THE EDGE THAT MUST NOT BE DROPPED SILENTLY
If the ceiling fires while the camera is still open and the photo arrives to a
locked vault, the photo is downscaled in memory and HELD there — never written
to IndexedDB, never to localStorage, never in the clear anywhere — and the app
asks for the passphrase. If that sheet is dismissed the photo is still held,
behind a persistent banner, and the only way to lose it is an explicit Discard
behind a confirm. If the app dies in that window the photo is gone; that is the
accepted failure, and it is the same trade the feature already makes elsewhere.

The vault-locked check is re-run per file rather than once up front, because a
relock can land in the middle of a multi-photo batch.

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
MARKER = "VAULT_CAPTURE"
REQUIRES = ["VAULT_CORE", "VAULT_CEREMONY", "VAULT_RENDER", "VAULT_TOGGLE", "VAULT_BACKUP"]

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
    for req in REQUIRES:
        if req not in text:
            fail(f"{req} not found — run the vault scripts first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: CSS for the held-photo banner
    # ---------------------------------------------------------------
    old = r"""  #backup-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}"""
    new = r"""  #backup-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}

  /* VAULT_CAPTURE — unsaved photo held in memory. Brass edge: this one is a
     data-loss warning, not a nudge, and it does not go away on its own. */
  #photo-hold-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:45;
    background:var(--ink-3);border:1px solid var(--brass);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.45);
  }
  #photo-hold-banner .txt{flex:1;font-size:13px;line-height:1.45;color:var(--paper-dim)}
  #photo-hold-banner .txt b{color:var(--brass);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}"""
    edits.append((old, new, "CSS: held-photo banner"))

    # ---------------------------------------------------------------
    # Edit 2: the capture flag + held-photo machinery
    # ---------------------------------------------------------------
    old = r"""/* VAULT_CORE — the key never survives the app going out of sight. Autosave
   above runs first, so an open protected note is sealed before we drop the key. */
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden') vaultRelock(true);
  else if(view.name==='house' && isProtected(view.param)) render();
});
window.addEventListener('pagehide',()=>vaultRelock(true));"""

    new = r"""/* ============================================================
   VAULT_CAPTURE — the app sending you to the camera is not the app being left
   ------------------------------------------------------------
   Tapping Camera backgrounds the PWA. Without this, the background relock
   wipes the key and the returning photo has nothing to seal it — the photo is
   lost. So a capture WE started defers the background trigger, and only that
   trigger: the idle timer keeps running, and a hard ceiling relocks anyway if
   nobody comes back.
   ============================================================ */
const VAULT_CAPTURE_GRACE_MS = 120000;   /* 2 min ceiling — drop to ~5000 to test */
let _captureAt = 0;        /* 0 = no capture in flight */
let _captureTimer = null;
let _captureSettle = null;

function captureActive(){ return _captureAt !== 0; }
function captureBegin(){
  _captureAt = now();
  clearTimeout(_captureTimer);
  /* Wandered off mid-capture: lock exactly as if the grace had never applied. */
  _captureTimer = setTimeout(()=>{ _captureAt=0; _captureTimer=null; vaultRelock(true); },
                             VAULT_CAPTURE_GRACE_MS);
}
function captureEnd(){
  _captureAt = 0;
  clearTimeout(_captureTimer); _captureTimer = null;
  clearTimeout(_captureSettle); _captureSettle = null;
}

/* ---- a photo we could not seal, held in memory and nowhere else ---- */
let _heldPhotos = null;    /* {houseId, blobs:[Blob]} — never persisted */

function queueHeldPhotos(blobs, houseId){
  if(!blobs || !blobs.length) return;
  if(_heldPhotos && _heldPhotos.houseId===houseId) _heldPhotos.blobs.push(...blobs);
  else _heldPhotos={ houseId, blobs:blobs.slice() };
  showHeldPhotoBanner();
  const h=houseById(houseId), n=_heldPhotos.blobs.length;
  vaultUnlockSheet({
    title: n===1?'Photo waiting to be saved':n+' photos waiting to be saved',
    body: 'The vault locked while the camera was open, so '+(n===1?'it has':'they have')
        +' not been saved yet. '+(n===1?'It is':'They are')+' held in memory only — unlock to '
        +'encrypt '+(n===1?'it':'them')+' into "'+(h?h.name:'that project')+'".',
    onOpen: ()=>{ flushHeldPhotos(); }
  });
}

let _flushingHeld = false;
async function flushHeldPhotos(){
  if(_flushingHeld || !_heldPhotos || !vaultUnlocked()) return;
  _flushingHeld=true;
  /* Claim the queue SYNCHRONOUSLY, before the first await. Unlocking fires this
     from two places — vaultUnlock() and the unlock sheet's onOpen — and without
     claiming it up front both run, both see the same queue, and the photo gets
     saved twice. The re-entrancy flag alone is not enough: the second caller can
     arrive after this one has already yielded on photoPutFor. */
  const houseId=_heldPhotos.houseId, blobs=_heldPhotos.blobs.slice();
  _heldPhotos=null;
  const h=houseById(houseId);
  if(!h){ _flushingHeld=false; dismissHeldPhotoBanner(); return; }
  h.photos=h.photos||[];
  let saved=0; const stillHeld=[];
  for(const blob of blobs){
    try{
      const id=uid();
      await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
      h.photos.push(id); if(!h.cover) h.cover=id; saved++;
    }catch(err){ stillHeld.push(blob); }   /* keep it rather than drop it */
  }
  if(saved){ h.updatedAt=now(); persist.houses(); }
  if(stillHeld.length){
    /* Put back what would not write, merged with anything that arrived while
       we were working. Never overwrite a newer queue. */
    _heldPhotos = (_heldPhotos && _heldPhotos.houseId===houseId)
      ? { houseId, blobs: stillHeld.concat(_heldPhotos.blobs) }
      : { houseId, blobs: stillHeld };
    showHeldPhotoBanner();
  } else if(!_heldPhotos){ dismissHeldPhotoBanner(); }
  _flushingHeld=false;
  render();
  if(saved) toast(saved===1?'Photo saved':saved+' photos saved');
}

function dismissHeldPhotoBanner(){
  const el=document.getElementById('photo-hold-banner'); if(el) el.remove();
}
function showHeldPhotoBanner(){
  dismissHeldPhotoBanner();
  if(!_heldPhotos) return;
  const n=_heldPhotos.blobs.length, h=houseById(_heldPhotos.houseId);
  const it=n===1?'it':'them', isAre=n===1?'It is':'They are';
  const el=document.createElement('div');
  el.id='photo-hold-banner';
  el.innerHTML=`<div class="txt"><b>${n} photo${n===1?'':'s'} not saved yet</b>${isAre} held in memory only, waiting for your vault passphrase. Closing the app loses ${it}.</div>
    <button class="btn primary sm" id="hold-unlock">Save</button>
    <button class="icon-btn" id="hold-discard" aria-label="Discard unsaved photos" style="width:36px;height:36px;flex:none">${I.trash}</button>`;
  document.body.appendChild(el);
  document.getElementById('hold-unlock').onclick=()=>{
    if(vaultUnlocked()){ flushHeldPhotos(); return; }
    vaultUnlockSheet({
      title: n===1?'Unlock to save the photo':'Unlock to save these photos',
      body: 'Your vault passphrase encrypts '+it+' into "'+(h?h.name:'that project')+'".',
      onOpen: ()=>{ flushHeldPhotos(); }
    });
  };
  /* The ONLY way a held photo goes away without being saved. Confirmed, never silent. */
  document.getElementById('hold-discard').onclick=()=>{
    if(!confirm('Discard '+n+' unsaved photo'+(n===1?'':'s')+'?\n\n'+isAre
      +' not saved anywhere, and this cannot be undone.')) return;
    _heldPhotos=null; dismissHeldPhotoBanner();
    toast(n===1?'Photo discarded':'Photos discarded');
  };
}

/* VAULT_CORE — the key never survives the app going out of sight. Autosave
   above runs first, so an open protected note is sealed before we drop the key. */
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden'){
    /* VAULT_CAPTURE — deferred only while a capture we started is in flight. */
    if(!captureActive()) vaultRelock(true);
    return;
  }
  /* Back in the foreground. If a capture was in flight, give the change event a
     moment to land; if nothing arrives it was cancelled, so just clear the flag
     and leave everything else exactly as it was. */
  if(captureActive()){
    clearTimeout(_captureSettle);
    _captureSettle=setTimeout(()=>{ if(captureActive()) captureEnd(); }, 2500);
  }
  if(view.name==='house' && isProtected(view.param)) render();
});
window.addEventListener('pagehide',()=>{ if(!captureActive()) vaultRelock(true); });"""
    edits.append((old, new, "capture flag, held-photo queue, deferred relock"))

    # ---------------------------------------------------------------
    # Edit 3: handlePhoto — hold what cannot be sealed
    # ---------------------------------------------------------------
    old = r"""async function handlePhoto(e,houseId){
  const files=e.target.files?Array.from(e.target.files):[]; if(!files.length)return;
  const multi=files.length>1;
  toast(multi?`Saving ${files.length} photos…`:'Saving photo…');
  const h=houseById(houseId); h.photos=h.photos||[];
  let saved=0, failed=0;
  for(const file of files){
    try{
      const blob=await downscale(file); const id=uid();
      await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
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

    new = r"""async function handlePhoto(e,houseId){
  captureEnd();                                    /* VAULT_CAPTURE — the file landed */
  const files=e.target.files?Array.from(e.target.files):[];
  e.target.value='';
  if(!files.length) return;
  const h=houseById(houseId); if(!h) return;
  const multi=files.length>1;
  toast(multi?`Saving ${files.length} photos…`:'Saving photo…');
  h.photos=h.photos||[];
  let saved=0, failed=0; const held=[];
  for(const file of files){
    let blob=null;
    try{ blob=await downscale(file); }catch(err){ failed++; continue; }
    /* VAULT_CAPTURE — re-checked per file, because a relock can land in the
       middle of a batch. A photo we cannot seal is held in memory; it is never
       written to disk in the clear, and never dropped without saying so. */
    if(h.protected && !vaultUnlocked()){ held.push(blob); continue; }
    try{
      const id=uid();
      await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
      h.photos.push(id);
      if(!h.cover) h.cover=id;
      saved++;
    }catch(err){
      if(h.protected && !vaultUnlocked()) held.push(blob); else failed++;
    }
  }
  h.updatedAt=now(); persist.houses(); render();
  if(held.length) queueHeldPhotos(held, houseId);
  if(saved && failed) toast(`${saved} saved, ${failed} could not be read`);
  else if(failed) toast('Could not read those images');
  else if(saved) toast(multi?`${saved} photos saved`:'Photo saved');
}"""
    edits.append((old, new, "handlePhoto(): hold what cannot be sealed"))

    # ---------------------------------------------------------------
    # Edit 4: flag the capture as the input is invoked
    # ---------------------------------------------------------------
    old = r"""  $app.querySelectorAll('[data-add-photo]').forEach(el=>el.onchange=e=>handlePhoto(e,view.param));"""
    new = r"""  /* VAULT_CAPTURE — this click is about to hand us to the camera or the picker,
     which backgrounds the app. Flag it so the background relock stands down. */
  $app.querySelectorAll('[data-add-photo]').forEach(el=>{
    el.onclick=()=>captureBegin();
    el.onchange=e=>handlePhoto(e,view.param);
  });"""
    edits.append((old, new, "bind(): flag capture on invoke"))

    # ---------------------------------------------------------------
    # Edit 5: a held photo also flushes the moment the vault opens
    # ---------------------------------------------------------------
    old = r"""  vaultResumeMigration();   /* VAULT_TOGGLE — finish anything that was interrupted */
  return true;"""
    new = r"""  vaultResumeMigration();   /* VAULT_TOGGLE — finish anything that was interrupted */
  flushHeldPhotos();        /* VAULT_CAPTURE — seal anything waiting on a key */
  return true;"""
    edits.append((old, new, "vaultUnlock(): flush held photos"))

    # ---------------------------------------------------------------
    # Edit 6: don't stack the softer banners on top of a data-loss warning
    # ---------------------------------------------------------------
    old = r"""  if(document.getElementById('backup-banner')) return;
  if(deferredInstallPrompt) showInstallBanner('android');"""
    new = r"""  if(document.getElementById('backup-banner')||document.getElementById('photo-hold-banner')) return;
  if(deferredInstallPrompt) showInstallBanner('android');"""
    edits.append((old, new, "install prompt: yield to the hold banner"))

    old = r"""  if(document.getElementById('install-banner')||document.getElementById('backup-banner')) return;"""
    new = r"""  if(document.getElementById('install-banner')||document.getElementById('backup-banner')||document.getElementById('photo-hold-banner')) return;"""
    edits.append((old, new, "backup nudge: yield to the hold banner"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_vault6_check.js")
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

    print("\n✅ Vault 6 applied: camera capture no longer trips the background relock.")

if __name__ == "__main__":
    main()
