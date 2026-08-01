#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 8: write-only vault (envelope encryption), retiring the memory-hold
Run this from the same folder as your index.html:
    python3 fix_vault8_envelope.py

Requires the vault scripts (1-7).

WHY
The memory-hold pattern from Vault 6 is retired. It assumed the page would
survive the camera wait; on real Android hardware the page was evicted during a
2-minute wait and the held photo and its banner died with the context. The
"acceptable failure" was in fact the common one.

WHAT REPLACES IT
Envelope encryption, so capture never needs the vault key at all:

  * At vault setup — and, for vaults that predate this, on the next unlock as a
    migration — an RSA-OAEP 2048 keypair is generated. The PUBLIC key is stored
    in the clear next to the vault block. The PRIVATE key is sealed under the
    vault key like any other secret.
  * Capturing into a protected project generates a fresh random AES-GCM key,
    encrypts the photo with it, and wraps that key with the public key. The
    record is written to IndexedDB the instant it exists.
  * Writing therefore needs only the public half, which is always available.
    Locked, unlocked, mid-grace, or with the page rebuilt a moment ago — no
    difference, and nothing is ever held anywhere waiting for a key.
  * On unlock the private key is unsealed, envelope records are opened and
    resealed under the normal symmetric scheme, so there is one shape at rest.

The public and private halves both travel in backups inside the vault block,
and export/import learned the envelope record shape.

DURABILITY DETAIL
A photo is written to IndexedDB before the project's photo list is saved, so a
death in the gap would leave a record nothing points at. The gap is now a single
localStorage write per photo rather than one at the end of the batch, and a
boot-time sweep re-attaches any record whose houseId names a project that does
not list it. Trade-off worth stating plainly: if a photo delete ever fails to
remove the IndexedDB record while the list write succeeds, that sweep will bring
the photo back. Recovering a lost job-site photo is worth that.

THE GRACE PERIOD survives but is demoted to session convenience — it only saves
you retyping a passphrase. No photo's survival depends on it, on a timer, or on
the page staying alive.

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
MARKER = "VAULT_ENVELOPE"
REQUIRES = ["VAULT_CORE", "VAULT_CAPTURE"]
# Identifiers that must not survive: the entire memory-hold pattern.
MUST_BE_GONE = ["_heldPhotos", "_flushingHeld", "queueHeldPhotos", "flushHeldPhotos",
                "showHeldPhotoBanner", "dismissHeldPhotoBanner", "photo-hold-banner"]

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
            fail(f"{req} not found — run the earlier vault scripts first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: drop the held-photo banner CSS
    # ---------------------------------------------------------------
    old = r"""
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
    new = r""""""
    edits.append((old, new, "remove held-photo banner CSS"))

    # ---------------------------------------------------------------
    # Edit 2: the envelope scheme
    # ---------------------------------------------------------------
    old = r"""async function photoPutFor(houseId, rec){
  const stale=_objUrls.get(rec.id);
  if(stale){ URL.revokeObjectURL(stale); _objUrls.delete(rec.id); _vaultUrlIds.delete(rec.id); }
  const h=houseById(houseId);
  if(h && h.protected){
    if(!vaultUnlocked()) throw new Error('vault locked');
    const sealed=await vaultSealBytes(new Uint8Array(await rec.blob.arrayBuffer()));
    const out={ id:rec.id, enc:1, iv:sealed.iv, ct:sealed.ct,
                type:(rec.blob.type||'image/jpeg'),
                houseId:rec.houseId, createdAt:rec.createdAt };
    if(rec.cropped) out.cropped=true;
    return photoPut(out);
  }
  return photoPut(rec);
}"""

    new = r"""/* ============================================================
   VAULT_ENVELOPE — a write-only vault
   ------------------------------------------------------------
   A photo taken into a protected project has to be written the instant it
   exists, because the page may not survive the next second — Android evicts
   it during a long camera wait, and anything held in memory dies with it.
   So capture is made not to need the vault key at all.

   A random AES-GCM key encrypts the photo; that key is wrapped with an
   RSA-OAEP public key kept in the clear. Writing needs only the public half,
   which is always there. Reading needs the private half, which is sealed under
   the vault passphrase like everything else. Locked, unlocked, mid-grace, or
   freshly rebuilt: no difference, and nothing is ever held waiting for a key.
   ============================================================ */
const VAULT_RSA_GEN    = { name:'RSA-OAEP', modulusLength:2048,
                           publicExponent:new Uint8Array([1,0,1]), hash:'SHA-256' };
const VAULT_RSA_IMPORT = { name:'RSA-OAEP', hash:'SHA-256' };
let _vaultPriv = null;      /* CryptoKey — memory only, dropped on relock */
let _resealing = false;

function isEnvPhoto(rec){ return !!rec && rec.env===1 && !!rec.ct && typeof rec.ek==='string'; }

/* Usages are wrapKey/unwrapKey, NOT encrypt/decrypt: WebCrypto refuses
   wrapKey() on a key imported for 'encrypt' with InvalidAccessError. */
async function vaultImportPub(b64){
  return crypto.subtle.importKey('spki', bytesFromB64(b64), VAULT_RSA_IMPORT, false, ['wrapKey']);
}
async function vaultImportPriv(b64){
  return crypto.subtle.importKey('pkcs8', bytesFromB64(b64), VAULT_RSA_IMPORT, false, ['unwrapKey']);
}

/* Fresh data key per photo, wrapped to the public key. Textbook envelope. */
async function vaultEnvelopeSeal(bytes, pubB64){
  const pub = await vaultImportPub(pubB64);
  const dek = await crypto.subtle.generateKey({name:'AES-GCM',length:256}, true, ['encrypt','decrypt']);
  const iv  = crypto.getRandomValues(new Uint8Array(12));
  const ct  = await crypto.subtle.encrypt({name:'AES-GCM', iv}, dek, bytes);
  const ek  = await crypto.subtle.wrapKey('raw', dek, pub, {name:'RSA-OAEP'});
  return { ek:b64FromBytes(ek), iv:b64FromBytes(iv), ct };
}
async function vaultEnvelopeOpen(rec){
  if(!_vaultPriv) throw new Error('vault locked');
  const dek = await crypto.subtle.unwrapKey('raw', bytesFromB64(rec.ek), _vaultPriv,
                {name:'RSA-OAEP'}, {name:'AES-GCM',length:256}, false, ['decrypt']);
  return crypto.subtle.decrypt({name:'AES-GCM', iv:bytesFromB64(rec.iv)}, dek, rec.ct);
}

/* Vaults created before the envelope existed get their keypair on the next
   unlock — the only moment we hold the key needed to seal the private half. */
async function vaultEnsureEnvelopeKeys(){
  if(!vaultUnlocked() || !settings.vault) return false;
  if(settings.vault.pub && settings.vault.priv){
    if(!_vaultPriv){
      try{ _vaultPriv = await vaultImportPriv(await vaultOpenText(settings.vault.priv)); }
      catch(e){ return false; }
    }
    return true;
  }
  const pair = await crypto.subtle.generateKey(VAULT_RSA_GEN, true, ['wrapKey','unwrapKey']);
  const pubB64  = b64FromBytes(await crypto.subtle.exportKey('spki',  pair.publicKey));
  const privB64 = b64FromBytes(await crypto.subtle.exportKey('pkcs8', pair.privateKey));
  settings.vault.pub  = pubB64;
  settings.vault.priv = await vaultSealText(privB64);
  persist.settings();
  _vaultPriv = await vaultImportPriv(privB64);
  return true;
}

/* Envelope records are already safe; this converts them to the ordinary
   symmetric shape so there is one form at rest. Per record and idempotent, so
   an interruption just leaves a mix — and both shapes read fine. */
async function vaultResealEnvelopes(){
  if(!vaultUnlocked() || !_vaultPriv || _resealing) return 0;
  _resealing = true;
  let converted = 0;
  try{
    for(const rec of await photoAll()){
      if(!isEnvPhoto(rec)) continue;
      try{
        const pt = await vaultEnvelopeOpen(rec);
        const sealed = await vaultSealBytes(new Uint8Array(pt));
        const out = { id:rec.id, enc:1, iv:sealed.iv, ct:sealed.ct,
                      type:rec.type||'image/jpeg', houseId:rec.houseId, createdAt:rec.createdAt };
        if(rec.cropped) out.cropped = true;
        await photoPut(out);
        const stale=_objUrls.get(rec.id);
        if(stale){ URL.revokeObjectURL(stale); _objUrls.delete(rec.id); _vaultUrlIds.delete(rec.id); }
        converted++;
      }catch(e){ /* leave it as an envelope — still readable, still safe */ }
    }
  } finally { _resealing = false; }
  if(converted) render();
  return converted;
}

async function vaultAfterUnlock(){
  try{
    if(await vaultEnsureEnvelopeKeys()) await vaultResealEnvelopes();
  }catch(e){}
}

/* A photo reaches IndexedDB before the project's photo list is saved, so a
   death in that gap leaves a record nothing points at. The record knows which
   project it belongs to, so re-attach it rather than orphan it. */
async function recoverOrphanPhotos(){
  let re=0;
  try{
    for(const rec of await photoAll()){
      if(!rec.houseId) continue;
      const h=houseById(rec.houseId); if(!h) continue;
      h.photos=h.photos||[];
      if(h.photos.indexOf(rec.id)>=0) continue;
      h.photos.push(rec.id);
      if(!h.cover) h.cover=rec.id;
      re++;
    }
  }catch(e){ return 0; }
  if(re){ persist.houses(); try{ render(); }catch(e){} }
  return re;
}

/* The ONE photo write path. Never throws for want of a key: protected and
   unlocked seals symmetrically, protected and locked envelopes it, and either
   way the bytes are on disk before this returns. */
async function photoPutFor(houseId, rec){
  const stale=_objUrls.get(rec.id);
  if(stale){ URL.revokeObjectURL(stale); _objUrls.delete(rec.id); _vaultUrlIds.delete(rec.id); }
  const h=houseById(houseId);
  if(!(h && h.protected)) return photoPut(rec);
  const bytes=new Uint8Array(await rec.blob.arrayBuffer());
  const type=(rec.blob.type||'image/jpeg');
  if(vaultUnlocked()){
    const sealed=await vaultSealBytes(bytes);
    const out={ id:rec.id, enc:1, iv:sealed.iv, ct:sealed.ct, type,
                houseId:rec.houseId, createdAt:rec.createdAt };
    if(rec.cropped) out.cropped=true;
    return photoPut(out);
  }
  if(!(settings.vault && settings.vault.pub)) throw new Error('no capture key');
  const env=await vaultEnvelopeSeal(bytes, settings.vault.pub);
  const out={ id:rec.id, env:1, ek:env.ek, iv:env.iv, ct:env.ct, type,
              houseId:rec.houseId, createdAt:rec.createdAt };
  if(rec.cropped) out.cropped=true;
  return photoPut(out);
}"""
    edits.append((old, new, "envelope scheme + photoPutFor rewrite"))

    # ---------------------------------------------------------------
    # Edit 3: photoURL reads envelope records too
    # ---------------------------------------------------------------
    old = r"""  if(isEncPhoto(rec)){
    if(!_vaultKey) return '';                 /* locked: no pixels reach the screen */
    try{
      const pt=await vaultOpenBytes(rec.iv, rec.ct);
      blob=new Blob([pt],{type:rec.type||'image/jpeg'});
    }catch(e){ return ''; }
    _vaultUrlIds.add(id);
  }"""
    new = r"""  if(isEncPhoto(rec)){
    if(!_vaultKey) return '';                 /* locked: no pixels reach the screen */
    try{
      const pt=await vaultOpenBytes(rec.iv, rec.ct);
      blob=new Blob([pt],{type:rec.type||'image/jpeg'});
    }catch(e){ return ''; }
    _vaultUrlIds.add(id);
  } else if(isEnvPhoto(rec)){
    /* VAULT_ENVELOPE — captured while locked and not yet resealed. */
    if(!_vaultPriv) return '';
    try{
      const pt=await vaultEnvelopeOpen(rec);
      blob=new Blob([pt],{type:rec.type||'image/jpeg'});
    }catch(e){ return ''; }
    _vaultUrlIds.add(id);
  }"""
    edits.append((old, new, "photoURL(): read envelope records"))

    # ---------------------------------------------------------------
    # Edit 4: relock drops the private key too
    # ---------------------------------------------------------------
    old = r"""  const wasOpen = !!_vaultKey;
  _vaultKey=null; _vaultCache.clear(); _vaultLoading=null;"""
    new = r"""  const wasOpen = !!_vaultKey;
  _vaultKey=null; _vaultPriv=null; _vaultCache.clear(); _vaultLoading=null;"""
    edits.append((old, new, "vaultRelock(): drop the private key"))

    # ---------------------------------------------------------------
    # Edit 5: unlock bootstraps keys and reseals, instead of flushing a queue
    # ---------------------------------------------------------------
    old = r"""  vaultResumeMigration();   /* VAULT_TOGGLE — finish anything that was interrupted */
  flushHeldPhotos();        /* VAULT_CAPTURE — seal anything waiting on a key */
  return true;"""
    new = r"""  vaultResumeMigration();   /* VAULT_TOGGLE — finish anything that was interrupted */
  vaultAfterUnlock();       /* VAULT_ENVELOPE — bootstrap keys, then reseal captures */
  return true;"""
    edits.append((old, new, "vaultUnlock(): envelope bootstrap + reseal"))

    # ---------------------------------------------------------------
    # Edit 6: new vaults get their keypair at setup
    # ---------------------------------------------------------------
    old = r"""        settings.vault={ salt, verifier, migration:null };
        persist.settings();
        vaultTouch();"""
    new = r"""        settings.vault={ salt, verifier, migration:null };
        persist.settings();
        /* VAULT_ENVELOPE — the capture keypair exists from the very first
           moment the vault does, so a locked capture is never unsupported. */
        await vaultEnsureEnvelopeKeys();
        vaultTouch();"""
    edits.append((old, new, "ceremony: generate the capture keypair"))

    # ---------------------------------------------------------------
    # Edit 7: retire the whole memory-hold block
    # ---------------------------------------------------------------
    old = r"""/* ---- a photo we could not seal, held in memory and nowhere else ---- */
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

/* VAULT_CORE"""
    new = r"""/* VAULT_ENVELOPE — the memory-hold that used to live here is gone. Nothing is
   ever kept in memory awaiting a key: photoPutFor() writes every capture the
   moment it exists, envelope-sealed when the vault is shut. */

/* VAULT_CORE"""
    edits.append((old, new, "retire the memory-hold pattern"))

    # ---------------------------------------------------------------
    # Edit 8: the grace period is now convenience only
    # ---------------------------------------------------------------
    old = r"""const VAULT_CAPTURE_GRACE_MS = 120000;   /* 2 min ceiling — drop to ~5000 to test */"""
    new = r"""/* VAULT_ENVELOPE — demoted to convenience. It saves you retyping a passphrase
   after taking a photo, and nothing more: no photo's survival depends on this
   window, on this timer, or on the page still being alive when you get back. */
const VAULT_CAPTURE_GRACE_MS = 120000;   /* 2 min ceiling — drop to ~5000 to test */"""
    edits.append((old, new, "demote the grace period"))

    # ---------------------------------------------------------------
    # Edit 9: handlePhoto — write every photo, hold nothing
    # ---------------------------------------------------------------
    old = r"""  let saved=0, failed=0; const held=[];
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

    new = r"""  let saved=0, failed=0, needKey=0;
  for(const file of files){
    let blob=null;
    try{ blob=await downscale(file); }catch(err){ failed++; continue; }
    try{
      const id=uid();
      /* VAULT_ENVELOPE — written the instant it exists, whatever the lock
         state. Then the list is persisted immediately rather than at the end of
         the batch, so a death mid-batch strands at most one record — and the
         boot sweep re-attaches even that. */
      await photoPutFor(houseId,{id,blob,houseId,createdAt:now()});
      h.photos.push(id);
      if(!h.cover) h.cover=id;
      h.updatedAt=now(); persist.houses();
      saved++;
    }catch(err){
      if(String(err&&err.message)==='no capture key') needKey++; else failed++;
    }
  }
  render();
  if(needKey) toast('Unlock the vault once to turn on locked capture');
  else if(saved && failed) toast(`${saved} saved, ${failed} could not be read`);
  else if(failed) toast('Could not read those images');
  else if(saved) toast(multi?`${saved} photos saved`:'Photo saved');
}"""
    edits.append((old, new, "handlePhoto(): write everything, hold nothing"))

    # ---------------------------------------------------------------
    # Edit 10-11: banner guards revert
    # ---------------------------------------------------------------
    old = r"""  if(document.getElementById('backup-banner')||document.getElementById('photo-hold-banner')) return;"""
    new = r"""  if(document.getElementById('backup-banner')) return;"""
    edits.append((old, new, "install prompt guard revert"))

    old = r"""  if(document.getElementById('install-banner')||document.getElementById('backup-banner')||document.getElementById('photo-hold-banner')) return;"""
    new = r"""  if(document.getElementById('install-banner')||document.getElementById('backup-banner')) return;"""
    edits.append((old, new, "backup nudge guard revert"))

    # ---------------------------------------------------------------
    # Edit 12: export understands envelope records
    # ---------------------------------------------------------------
    old = r"""    if(isEncPhoto(p)) photoData[p.id]={ enc:1, iv:p.iv, type:p.type||'image/jpeg',
                                        houseId:p.houseId, createdAt:p.createdAt, b64:b64FromBytes(p.ct) };
    else photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)};"""
    new = r"""    if(isEncPhoto(p)) photoData[p.id]={ enc:1, iv:p.iv, type:p.type||'image/jpeg',
                                        houseId:p.houseId, createdAt:p.createdAt, b64:b64FromBytes(p.ct) };
    /* VAULT_ENVELOPE — a capture taken while locked and not yet resealed. It
       travels as it sits, wrapped key and all; the vault block carries the
       private half that opens it. */
    else if(isEnvPhoto(p)) photoData[p.id]={ env:1, ek:p.ek, iv:p.iv, type:p.type||'image/jpeg',
                                        houseId:p.houseId, createdAt:p.createdAt, b64:b64FromBytes(p.ct) };
    else photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)};"""
    edits.append((old, new, "exportData(): envelope records"))

    # ---------------------------------------------------------------
    # Edit 13: restore understands envelope records
    # ---------------------------------------------------------------
    old = r"""      if(p.enc===1) await photoPut({id, enc:1, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                                    type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt});
      else await photoPut({id,blob:b64ToBlob(p.b64),houseId:p.houseId,createdAt:p.createdAt});"""
    new = r"""      if(p.enc===1) await photoPut({id, enc:1, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                                    type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt});
      else if(p.env===1) await photoPut({id, env:1, ek:p.ek, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                                    type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt});
      else await photoPut({id,blob:b64ToBlob(p.b64),houseId:p.houseId,createdAt:p.createdAt});"""
    edits.append((old, new, "importData(): envelope records"))

    # ---------------------------------------------------------------
    # Edit 14: boot-time orphan sweep
    # ---------------------------------------------------------------
    old = r"""lockGate();"""
    new = r"""lockGate();
/* VAULT_ENVELOPE — re-attach any capture that reached IndexedDB while the page
   died before its project's photo list was written. */
recoverOrphanPhotos();"""
    edits.append((old, new, "boot: orphan photo sweep"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # Assertion: the memory-hold pattern must be entirely gone.
    survivors = [n for n in MUST_BE_GONE if n in working]
    if survivors:
        fail("memory-hold identifiers still present after edits: " + ", ".join(survivors))
    print("✅ assertion: no memory-hold identifiers remain (" + ", ".join(MUST_BE_GONE) + ")")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_vault8_check.js")
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

    print("\n✅ Vault 8 applied: write-only vault. Capture no longer needs the vault key.")

if __name__ == "__main__":
    main()
