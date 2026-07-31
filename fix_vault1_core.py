#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 1 of 5: crypto core + the photo choke point
Run this from the same folder as your index.html:
    python3 fix_vault1_core.py

Lays the foundation for Protected Projects. Nothing is visible to the user
after this script alone — it adds the machinery the next four scripts use.

What goes in:
  * PBKDF2-SHA256 (600,000 rounds) -> 256-bit AES-GCM key, derived from a
    vault passphrase that is NOT the app PIN. The key lives in one
    module-scoped variable and is never written to disk. Relock wipes it.
  * A verifier: AES-GCM of the fixed string "notebuilt-vault-ok". Unlocking
    means deriving the key and trying to decrypt that. No passphrase hash is
    ever stored, so there is nothing to crack offline but the data itself.
  * vt() + an IV-keyed plaintext cache, so the app's synchronous renderers can
    show decrypted text without being rewritten as async.
  * photoAllowedFor() / photosFor() / coverFor() — the ONE shared filter every
    photo enumeration routes through. A protected project's photos never appear
    outside that project, locked or unlocked. No per-screen judgment calls.
  * photoPutFor() — the ONE write path, which encrypts iff the project is
    protected. There is only one blob per photo in this app (downscale() caps
    it at 1000px and the same blob serves the grid thumbnail, the cover and the
    full-screen view), so encrypting it leaves no unencrypted thumbnail behind.
  * Relock on idle (15 min), on visibilitychange, and on pagehide.

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
MARKER = "VAULT_CORE"

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

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: replace the photo object-URL helper with the vault core
    #         plus a photoURL() that can decrypt.
    # ---------------------------------------------------------------
    old1 = r"""const _objUrls=new Map();
async function photoURL(id){
  if(_objUrls.has(id)) return _objUrls.get(id);
  const rec=await photoGet(id); if(!rec) return '';
  const u=URL.createObjectURL(rec.blob); _objUrls.set(id,u); return u;
}"""

    new1 = r"""const _objUrls=new Map();

/* ============================================================
   VAULT_CORE — Protected Projects
   A protected project's contents are encrypted at rest under a passphrase
   that is NOT the app PIN. The key exists only in memory, only while the
   vault is unlocked. There is no recovery and no backdoor — by design.
   ============================================================ */
const VAULT_ITER = 600000;                          /* PBKDF2 rounds */
const VAULT_VERIFIER_TEXT = 'notebuilt-vault-ok';
const VAULT_IDLE_MS = 15*60*1000;                   /* idle auto-relock */
const VAULT_MIN_PASS = 8;

let _vaultKey = null;             /* CryptoKey — memory only, never persisted */
let _vaultCache = new Map();      /* iv -> plaintext. Wiped on relock. */
let _vaultUrlIds = new Set();     /* photo ids whose object URL came from ciphertext */
let _vaultIdleTimer = null;
let _vaultLoading = null;

/* ---------- base64 <-> bytes (chunked: a 1000px JPEG blows the arg limit) ---------- */
function b64FromBytes(buf){
  const b = (buf instanceof Uint8Array) ? buf : new Uint8Array(buf);
  let s='';
  for(let i=0;i<b.length;i+=8192) s += String.fromCharCode.apply(null, b.subarray(i,i+8192));
  return btoa(s);
}
function bytesFromB64(s){
  const bin=atob(s); const a=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) a[i]=bin.charCodeAt(i);
  return a;
}

/* An encrypted value is an OBJECT where a STRING used to be. That makes the
   test unambiguous, and it makes a half-migrated project self-describing —
   which is what lets an interrupted encrypt-in-place simply be re-run. */
function isEnc(v){ return !!v && typeof v==='object' && v.enc===1 && typeof v.iv==='string'; }
function isEncPhoto(rec){ return !!rec && rec.enc===1 && !!rec.ct; }

function vaultUnlocked(){ return !!_vaultKey; }
function vaultExists(){ return !!(settings.vault && settings.vault.salt && settings.vault.verifier); }
function isProtected(houseId){ const h=houseById(houseId); return !!(h && h.protected); }

async function vaultDeriveKey(pass, saltB64){
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pass), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey(
    { name:'PBKDF2', salt:bytesFromB64(saltB64), iterations:VAULT_ITER, hash:'SHA-256' },
    base, { name:'AES-GCM', length:256 }, false, ['encrypt','decrypt']);
}

/* A fresh random IV on EVERY write. Never reused. */
async function vaultSealBytes(bytes){
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv}, _vaultKey, bytes);
  return { iv:b64FromBytes(iv), ct };
}
async function vaultOpenBytes(ivB64, ct){
  return crypto.subtle.decrypt({name:'AES-GCM', iv:bytesFromB64(ivB64)}, _vaultKey, ct);
}
async function vaultSealText(str){
  const r = await vaultSealBytes(new TextEncoder().encode(str==null?'':String(str)));
  return { enc:1, iv:r.iv, ct:b64FromBytes(r.ct) };
}
async function vaultOpenText(rec){
  return new TextDecoder().decode(await vaultOpenBytes(rec.iv, bytesFromB64(rec.ct)));
}
/* Seal only what isn't sealed already — the idempotence that makes resume safe. */
async function vaultSealField(v){ return isEnc(v) ? v : vaultSealText(v==null?'':String(v)); }
async function vaultOpenField(v){ return isEnc(v) ? vaultOpenText(v) : (v==null?'':String(v)); }

/* ---------- reading encrypted text from synchronous renderers ----------
   The renderers are synchronous string builders; decryption is not. Rather
   than rewrite them, warm a cache for one project and re-render — the same
   shape hydratePhotos() already uses. Keyed by IV, which is unique per record
   per write, so the cache self-invalidates the moment a value is re-encrypted. */
function vt(v){
  if(!isEnc(v)) return v==null?'':v;
  const hit=_vaultCache.get(v.iv);
  return hit==null?'':hit;
}
function vaultNeeds(v){ return isEnc(v) && !_vaultCache.has(v.iv); }
function vaultPendingFor(houseId){
  const h=houseById(houseId); if(!h) return false;
  return vaultNeeds(h.address) || vaultNeeds(h.notes)
    || (h.specs||[]).some(s=>vaultNeeds(s.room)||vaultNeeds(s.label)||vaultNeeds(s.value)||vaultNeeds(s.note))
    || notes.some(n=>n.houseId===houseId && (vaultNeeds(n.title)||vaultNeeds(n.body)))
    || tasks.some(t=>t.houseId===houseId && vaultNeeds(t.text));
}
/* Decrypt ONE project's text on demand. Never a bulk decrypt of the vault. */
async function vaultLoadProject(houseId){
  if(!vaultUnlocked()) return;
  const h=houseById(houseId); if(!h) return;
  const vals=[];
  const collect=v=>{ if(vaultNeeds(v)) vals.push(v); };
  collect(h.address); collect(h.notes);
  (h.specs||[]).forEach(s=>{ collect(s.room); collect(s.label); collect(s.value); collect(s.note); });
  notes.forEach(n=>{ if(n.houseId===houseId){ collect(n.title); collect(n.body); } });
  tasks.forEach(t=>{ if(t.houseId===houseId) collect(t.text); });
  for(const v of vals){
    try{ _vaultCache.set(v.iv, await vaultOpenText(v)); }
    catch(e){ _vaultCache.set(v.iv, ''); }
  }
}
/* Safe to call on every render: warms the screen we're about to paint, then repaints. */
function vaultEnsureProject(houseId){
  if(!vaultUnlocked() || !isProtected(houseId)) return;
  if(_vaultLoading===houseId || !vaultPendingFor(houseId)) return;
  _vaultLoading=houseId;
  vaultLoadProject(houseId).then(()=>{ _vaultLoading=null; render(); })
                           .catch(()=>{ _vaultLoading=null; });
}

/* ---------- lock / unlock lifecycle ---------- */
async function vaultUnlock(pass){
  if(!vaultExists()) return false;
  const prev=_vaultKey;
  try{
    _vaultKey = await vaultDeriveKey(pass, settings.vault.salt);
    if(await vaultOpenText(settings.vault.verifier) !== VAULT_VERIFIER_TEXT) throw new Error('bad passphrase');
  }catch(e){ _vaultKey=prev; return false; }
  vaultTouch();
  return true;
}
function vaultRelock(silent){
  const wasOpen = !!_vaultKey;
  _vaultKey=null; _vaultCache.clear(); _vaultLoading=null;
  clearTimeout(_vaultIdleTimer); _vaultIdleTimer=null;
  /* Revoke every object URL built from ciphertext — otherwise a decrypted
     image stays reachable in memory after the vault is locked. */
  for(const id of _vaultUrlIds){
    const u=_objUrls.get(id);
    if(u){ URL.revokeObjectURL(u); _objUrls.delete(id); }
  }
  _vaultUrlIds.clear();
  if(!wasOpen) return;
  try{ if(vw && vw.houseId && isProtected(vw.houseId)) closeViewer(); }catch(e){}
  try{ if(an && an.houseId && isProtected(an.houseId)) closeAnnotate(); }catch(e){}
  try{ if($mr && $mr.innerHTML) closeSheet(); }catch(e){}
  if(!silent){ try{ render(); }catch(e){} }
}
function vaultTouch(){
  if(!_vaultKey) return;
  clearTimeout(_vaultIdleTimer);
  _vaultIdleTimer=setTimeout(()=>{ vaultRelock(); toast('Protected projects locked'); }, VAULT_IDLE_MS);
}

/* ============================================================
   THE photo choke point — decoy-proof rule, one place only.
   Every enumeration of photo ids in this app goes through these.
   scopeHouseId is the project whose OWN screen is being painted; pass null
   for any cross-project surface (project list, pickers, search, exports).
   ============================================================ */
function photoAllowedFor(houseId, scopeHouseId){
  const h=houseById(houseId);
  if(!h || !h.protected) return true;         /* not protected: unchanged, zero cost */
  if(scopeHouseId !== houseId) return false;  /* never outside its own project. ever. */
  return vaultUnlocked();
}
function photosFor(houseId, scopeHouseId){
  const h=houseById(houseId); if(!h) return [];
  return photoAllowedFor(houseId, scopeHouseId) ? (h.photos||[]) : [];
}
function coverFor(houseId, scopeHouseId){
  const h=houseById(houseId); if(!h || !h.cover) return null;
  return photoAllowedFor(houseId, scopeHouseId) ? h.cover : null;
}

/* The ONE photo write path: encrypts iff the project is protected. */
async function photoPutFor(houseId, rec){
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
}

async function photoURL(id){
  if(_objUrls.has(id)) return _objUrls.get(id);
  const rec=await photoGet(id); if(!rec) return '';
  let blob=rec.blob;
  if(isEncPhoto(rec)){
    if(!_vaultKey) return '';                 /* locked: no pixels reach the screen */
    try{
      const pt=await vaultOpenBytes(rec.iv, rec.ct);
      blob=new Blob([pt],{type:rec.type||'image/jpeg'});
    }catch(e){ return ''; }
    _vaultUrlIds.add(id);
  }
  if(!blob) return '';
  const u=URL.createObjectURL(blob); _objUrls.set(id,u); return u;
}"""
    edits.append((old1, new1, "insert vault core + decrypting photoURL()"))

    # ---------------------------------------------------------------
    # Edit 2: relock rules — idle, backgrounded, page hidden
    # ---------------------------------------------------------------
    old2 = r"""/* Auto-save an open note when the screen is hidden (lock/switch) or unloaded. */
document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='hidden'){ _leavingView={name:view.name,param:view.param}; autosaveOpenNote(); } });
window.addEventListener('pagehide',()=>{ _leavingView={name:view.name,param:view.param}; autosaveOpenNote(); });"""

    new2 = r"""/* Auto-save an open note when the screen is hidden (lock/switch) or unloaded. */
document.addEventListener('visibilitychange',()=>{ if(document.visibilityState==='hidden'){ _leavingView={name:view.name,param:view.param}; autosaveOpenNote(); } });
window.addEventListener('pagehide',()=>{ _leavingView={name:view.name,param:view.param}; autosaveOpenNote(); });

/* VAULT_CORE — the key never survives the app going out of sight. Autosave
   above runs first, so an open protected note is sealed before we drop the key. */
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='hidden') vaultRelock(true);
  else if(view.name==='house' && isProtected(view.param)) render();
});
window.addEventListener('pagehide',()=>vaultRelock(true));
['pointerdown','keydown','touchstart'].forEach(ev=>
  document.addEventListener(ev,()=>{ if(_vaultKey) vaultTouch(); },{passive:true}));"""
    edits.append((old2, new2, "relock on idle / background / pagehide"))

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
    js_path = Path("/tmp/_notebuilt_vault1_check.js")
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

    print("\n✅ Vault 1/5 applied: crypto core + photo choke point.")
    print("   No user-visible change yet. Next: fix_vault2_ceremony.py")

if __name__ == "__main__":
    main()
