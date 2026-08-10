#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Backup v3: close the export gap (th_nb_export_gap)
Run from the same folder as index.html:
    python3 fix_backup_v3.py

THE GAP
-------
exportData() wrote { app, version:2, exportedAt, houses, tasks, notes,
photos, vault } and nothing else. notebuilt.categories was never in the
file; notebuilt.settings was never in the file beyond its .vault slice.
importData() restores only what the dump carries, so every restore made
until now silently landed on default settings with no custom categories —
and nothing in the file revealed the gap. Per-photo `cropped` was dropped
too. IndexedDB was never affected: photos is the only store and export
already covered 100% of it, all three shapes.

WHAT THIS ADDS
--------------
1. exportData -> version 3: adds `categories`, the ENTIRE `settings`
   object, per-photo `cropped`, and a `contents` manifest (counts +
   booleans) so a backup file states what it holds in its own words.

2. importData accepts v2 AND v3. v3 fields are optional, so a real v2
   file restores exactly as it does today. The confirm dialog shows the
   manifest first; for a v2 file it names what the file does NOT contain.

3. Vault passphrase gate. If the file carries a vault block, the
   passphrase is verified against the BACKUP's own salt/verifier before
   one byte is committed. Fail -> retry or cancel, nothing touched.

4. Re-seal. If the device's vault uses a different passphrase, the
   restore can be re-sealed under the device's current one. See the
   note below — this is NOT the keypair re-wrap the brief described.

5. settings.lastBackupAt = the file's exportedAt. Never verbatim from
   the restored settings, never stamped "now".

6. App PIN: the DEVICE's PIN wins when one is set; the backup's PIN is
   taken only on a fresh install. A PIN is not cryptographic and belongs
   to the phone in your hand, not to the file.

NOTE ON RE-SEAL — deviation from the brief, deliberate
------------------------------------------------------
The brief specified: "unwrap the backup's private key with the backup
key, re-wrap under the current vault key." That is not sufficient and
would have shipped a restore that cannot be read.

In this app the RSA keypair covers ONE case only: an envelope capture
(env:1) taken while the vault was locked. Everything else — every
sealed text field, and every enc:1 photo — is AES-GCM directly under
PBKDF2(passphrase, salt). Re-wrapping the private key changes none of
it. The current passphrase would still open nothing.

So the re-seal here opens every sealed value with the backup's key and
seals it again under the device's key, normalising env:1 captures to the
ordinary enc:1 shape as it goes — exactly what an unlock on the source
device would have done. It runs on the PARSED FILE IN MEMORY, before any
commit: if a single record fails, the whole restore is abandoned and the
device is left untouched. No partial restore, as specified.

Backs up first, applies edits with exact-match anchors (each asserted to
match exactly once), aborts atomically if anything doesn't match, and
validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "BACKUP_V3"


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
    # Edit 1: key-parameterised seal/open helpers.
    # A restore reasons about TWO vault keys at once and must not
    # disturb _vaultKey, so the in-memory-key primitives are not enough.
    # ---------------------------------------------------------------
    old1 = """async function vaultSealField(v){ return isEnc(v) ? v : vaultSealText(v==null?'':String(v)); }
async function vaultOpenField(v){ return isEnc(v) ? vaultOpenText(v) : (v==null?'':String(v)); }"""
    new1 = """async function vaultSealField(v){ return isEnc(v) ? v : vaultSealText(v==null?'':String(v)); }
async function vaultOpenField(v){ return isEnc(v) ? vaultOpenText(v) : (v==null?'':String(v)); }

/* BACKUP_V3 — the same seal and open, against a key handed in rather than the
   one in memory. A restore has to hold TWO vault keys at once — the backup
   file's and this device's — and neither may disturb _vaultKey, because what
   is on screen still belongs to the data set being replaced. */
async function vaultOpenTextWith(key, rec){
  const pt = await crypto.subtle.decrypt({name:'AES-GCM', iv:bytesFromB64(rec.iv)}, key, bytesFromB64(rec.ct));
  return new TextDecoder().decode(pt);
}
async function vaultSealTextWith(key, str){
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv}, key,
                new TextEncoder().encode(str==null?'':String(str)));
  return { enc:1, iv:b64FromBytes(iv), ct:b64FromBytes(ct) };
}
/* Resolves to a CryptoKey iff the passphrase opens THAT vault block — the
   backup's or the device's, whichever is passed. A wrong passphrase is an
   answer, not an exception. */
async function vaultKeyFor(pass, block){
  if(!block || !block.salt || !block.verifier) return null;
  try{
    const k = await vaultDeriveKey(pass, block.salt);
    if(await vaultOpenTextWith(k, block.verifier) !== VAULT_VERIFIER_TEXT) return null;
    return k;
  }catch(e){ return null; }
}"""
    edits.append((old1, new1, "vault core: key-parameterised seal/open + vaultKeyFor()"))

    # ---------------------------------------------------------------
    # Edit 2: export carries the per-photo cropped flag.
    # ---------------------------------------------------------------
    old2 = """    else photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)};
  }"""
    new2 = """    else photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)};
    /* BACKUP_V3 — the cover-crop flag is part of the photo, and every backup
       written before now dropped it on the floor. */
    if(p.cropped) photoData[p.id].cropped=true;
  }"""
    edits.append((old2, new2, "exportData(): carry per-photo cropped flag"))

    # ---------------------------------------------------------------
    # Edit 3: the dump itself -> version 3.
    # ---------------------------------------------------------------
    old3 = """  const dump={ app:'notebuilt', version:2, exportedAt:now(), houses, tasks, notes, photos:photoData,
               vault: settings.vault || null };"""
    new3 = """  /* BACKUP_V3 — categories and the whole settings object travel too. Until
     version 3 they did not, so every restore quietly landed on defaults with
     none of your custom categories, and the file said nothing about it. The
     contents block is that missing sentence: what this file holds, in its own
     words, readable without running anything. */
  const dump={ app:'notebuilt', version:3, exportedAt:now(), houses, tasks, notes, photos:photoData,
               vault: settings.vault || null,
               categories: categories,
               settings: settings,
               contents:{ projects:houses.length, tasks:tasks.length, notes:notes.length,
                          photos:Object.keys(photoData).length,
                          categories:(categories||[]).length,
                          settings:true, vault:!!settings.vault } };"""
    edits.append((old3, new3, "exportData(): version 3 + categories + settings + contents manifest"))

    # ---------------------------------------------------------------
    # Edit 4: importData -> manifest, passphrase gate, re-seal, v2/v3.
    # Anchored on the entire existing function, replaced wholesale.
    # ---------------------------------------------------------------
    old4 = """async function importData(e){
  const file=e.target.files&&e.target.files[0]; if(!file)return;
  if(!confirm('Restore will REPLACE everything currently in the app with the backup.\\n\\nThat includes your vault: any protected projects in the backup come back locked, and only the passphrase they were made with will open them.\\n\\nContinue?')) return;
  try{
    const text=await file.text(); const d=JSON.parse(text);
    if(d.app!=='notebuilt' && d.app!=='punchlist') throw new Error('Not a Notebuilt backup');
    houses=d.houses||[]; tasks=d.tasks||[]; notes=d.notes||[];
    /* VAULT_BACKUP — the salt and verifier come back with the data, and the key
       in memory goes: whatever is on screen belongs to the old data set. */
    vaultRelock(true);
    settings.vault = d.vault || null;
    persist.houses(); persist.tasks(); persist.notes(); persist.settings();
    /* photos */
    const existing=await photoAll(); for(const p of existing) await photoDel(p.id).catch(()=>{});
    _objUrls.clear(); _vaultUrlIds.clear(); _vaultCache.clear();
    for(const [id,p] of Object.entries(d.photos||{})){
      if(p.enc===1) await photoPut({id, enc:1, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                                    type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt});
      else if(p.env===1) await photoPut({id, env:1, ek:p.ek, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                                    type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt});
      else await photoPut({id,blob:b64ToBlob(p.b64),houseId:p.houseId,createdAt:p.createdAt});
    }
    go('houses');
    toast(houses.some(h=>h.protected)?'Restored — protected projects are locked':'Backup restored');
  }catch(err){ alert('Could not restore: '+err.message); }
}"""

    new4 = """/* BACKUP_V3 — what the file says it holds. A version 3 file carries its own
   manifest; anything older is counted from the arrays, and the difference
   between the two is exactly what the reader needs to be told about. */
function backupManifest(d){
  const c = d.contents || {};
  const num = (v, fallback)=> (typeof v==='number' ? v : fallback);
  return {
    version:    d.version || 1,
    projects:   num(c.projects, (d.houses||[]).length),
    tasks:      num(c.tasks,    (d.tasks||[]).length),
    notes:      num(c.notes,    (d.notes||[]).length),
    photos:     num(c.photos,   Object.keys(d.photos||{}).length),
    categories: Array.isArray(d.categories) ? d.categories.length : 0,
    hasCategories: Array.isArray(d.categories) && d.categories.length>0,
    hasSettings:   !!(d.settings && typeof d.settings==='object'),
    hasVault:      !!(d.vault && d.vault.salt && d.vault.verifier)
  };
}
function backupManifestText(m){
  const n=(count,word)=> '  \\u2022 '+count+' '+word+(count===1?'':'s')+'\\n';
  const missing=[];
  if(!m.hasCategories) missing.push('your custom categories');
  if(!m.hasSettings)   missing.push('your app settings');
  return 'This backup contains:\\n'
    + n(m.projects,'project') + n(m.tasks,'to-do') + n(m.notes,'note') + n(m.photos,'photo')
    + (m.hasCategories ? '  \\u2022 '+m.categories+' custom categor'+(m.categories===1?'y':'ies')+'\\n' : '')
    + (m.hasSettings   ? '  \\u2022 your app settings\\n' : '')
    + (m.hasVault      ? '  \\u2022 a vault \\u2014 protected projects, still encrypted\\n' : '')
    + (missing.length
        ? '\\nIt does NOT contain '+missing.join(' or ')+'.\\nThis is an older backup (version '
          +m.version+'), written before those were included. What is on this device stays as it is.\\n'
        : '');
}

/* BACKUP_V3 — prove the backup can be opened BEFORE this device is touched.
   A restore that lands data nobody can read is worse than no restore at all,
   because by then the readable copy is gone. */
function backupAskPass(opts){
  return new Promise(resolve=>{
    const draw=(err)=>{
      vaultOverlay('<div class="v-steps">'+esc(opts.step||'')+'</div>'
        +'<div class="v-mark">'+I.lock+'</div>'
        +'<h2>'+esc(opts.title)+'</h2>'
        +'<div class="v-copy">'+opts.body+'</div>'
        +'<div class="field"><label>Vault passphrase</label>'+pwField('b-vp','','current-password')+'</div>'
        +'<div class="v-err">'+esc(err||'')+'</div>'
        +'<div class="v-actions"><button class="btn primary block" data-b-go>Continue</button>'
        +'<button class="btn block" data-b-cancel>Cancel restore</button></div>');
      bindPwEyes($vault);
      setTimeout(()=>{ const el=$vault.querySelector('#b-vp'); if(el) el.focus(); },60);
      const go=async()=>{
        const btn=$vault.querySelector('[data-b-go]'), inp=$vault.querySelector('#b-vp');
        const pass=inp.value; if(!pass) return;
        btn.setAttribute('disabled',''); btn.textContent='Checking\\u2026';
        const key=await vaultKeyFor(pass, opts.block);
        if(key){ vaultCloseOverlay(); resolve({key:key, pass:pass}); return; }
        /* Same deliberate one-second cost as every other wrong passphrase. */
        await new Promise(r=>setTimeout(r,1000));
        draw(opts.err||'That passphrase does not open this vault \\u2014 retry or cancel.');
      };
      $vault.querySelector('[data-b-go]').onclick=go;
      $vault.querySelector('[data-b-cancel]').onclick=()=>{ vaultCloseOverlay(); resolve(null); };
      $vault.querySelector('#b-vp').addEventListener('keydown',e=>{ if(e.key==='Enter') go(); });
    };
    draw();
  });
}

/* BACKUP_V3 — RE-SEAL.
   Every protected value in a backup — text field and photo alike — is AES-GCM
   directly under PBKDF2(that backup's passphrase, that backup's salt). The RSA
   keypair covers one case only: a capture taken while the vault was locked. So
   re-wrapping the keypair would change nothing; the only honest re-seal is to
   open every sealed value with the backup's key and seal it again with this
   device's, normalising envelope captures to the ordinary sealed shape on the
   way through — exactly what an unlock on the source device would have done.

   This runs on the parsed file, in memory, BEFORE anything is committed. One
   record that will not open aborts the whole restore and the device is left
   exactly as it was. There is no half-re-sealed state to be stranded in. */
async function backupReseal(d, fromKey, toKey){
  const photoIds = Object.keys(d.photos||{});
  const total = (d.houses||[]).length + (d.tasks||[]).length + (d.notes||[]).length + photoIds.length;
  let done = 0;
  const tick = async ()=>{
    done++;
    if(done%4===0 || done===total)
      await vaultBusy('Re-sealing the restore','under this device\\u2019s passphrase',
                      total ? Math.round(done/total*100) : 100);
  };
  const move = async v => isEnc(v) ? vaultSealTextWith(toKey, await vaultOpenTextWith(fromKey, v)) : v;

  for(const h of d.houses||[]){
    h.address = await move(h.address);
    h.notes   = await move(h.notes);
    for(const s of h.specs||[]){
      s.room  = await move(s.room);  s.label = await move(s.label);
      s.value = await move(s.value); s.note  = await move(s.note);
    }
    await tick();
  }
  for(const t of d.tasks||[]){ t.text=await move(t.text); await tick(); }
  for(const nt of d.notes||[]){ nt.title=await move(nt.title); nt.body=await move(nt.body); await tick(); }

  let priv=null;
  for(const id of photoIds){
    const p=d.photos[id];
    if(p.enc===1){
      const pt = await crypto.subtle.decrypt({name:'AES-GCM', iv:bytesFromB64(p.iv)}, fromKey, bytesFromB64(p.b64));
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv}, toKey, pt);
      p.iv=b64FromBytes(iv); p.b64=b64FromBytes(ct);
    } else if(p.env===1){
      if(!priv){
        if(!(d.vault && d.vault.priv)) throw new Error('this backup holds a photo that only its own vault could open');
        priv = await vaultImportPriv(await vaultOpenTextWith(fromKey, d.vault.priv));
      }
      const dek = await crypto.subtle.unwrapKey('raw', bytesFromB64(p.ek), priv,
                    {name:'RSA-OAEP'}, {name:'AES-GCM',length:256}, false, ['decrypt']);
      const pt  = await crypto.subtle.decrypt({name:'AES-GCM', iv:bytesFromB64(p.iv)}, dek, bytesFromB64(p.b64));
      const iv  = crypto.getRandomValues(new Uint8Array(12));
      const ct  = await crypto.subtle.encrypt({name:'AES-GCM', iv}, toKey, pt);
      delete p.env; delete p.ek;
      p.enc=1; p.iv=b64FromBytes(iv); p.b64=b64FromBytes(ct);
    }
    await tick();
  }
}

async function importData(e){
  const file=e.target.files&&e.target.files[0]; if(!file)return;
  const reset=()=>{ try{ e.target.value=''; }catch(err){} };

  /* Read and understand the file first. Nothing is replaced until the person
     doing it has been told, in counts, what they are replacing it with. */
  let d;
  try{
    d=JSON.parse(await file.text());
    if(d.app!=='notebuilt' && d.app!=='punchlist') throw new Error('Not a Notebuilt backup');
  }catch(err){ reset(); alert('Could not restore: '+err.message); return; }

  const m=backupManifest(d);
  if(!confirm(backupManifestText(m)
      +'\\nRestore REPLACES everything currently in the app with what is listed above.\\n'
      +(m.hasVault
          ? '\\nThe backup carries a vault. You will be asked for its passphrase before anything here is replaced.\\n'
          : (vaultExists()
              ? '\\nThis device has a vault and this backup does not. Restoring removes it, along with everything it protected.\\n'
              : ''))
      +'\\nContinue?')){ reset(); return; }

  /* ---- the gate: the backup's own salt and verifier, before any commit ---- */
  let keepVault=null;
  if(m.hasVault){
    const got=await backupAskPass({
      step:'Restore \\u00b7 the backup\\u2019s vault',
      title:'The backup\\u2019s passphrase',
      body:'This backup contains protected projects. Enter the vault passphrase '
          +'<b>the backup was made with</b>. It is checked against the file itself \\u2014 '
          +'nothing on this device is touched until it opens.',
      block:d.vault,
      err:'This backup uses a different passphrase \\u2014 retry or cancel.'});
    if(!got){ reset(); toast('Restore cancelled \\u2014 nothing changed'); return; }

    /* Would that same passphrase also open the vault already on this device?
       If not, restoring as-is leaves the device answering to the backup's
       passphrase instead of the one in daily use. Offer the swap. */
    if(vaultExists() && !(await vaultKeyFor(got.pass, settings.vault))){
      if(confirm('This device\\u2019s vault uses a different passphrase than the backup.\\n\\n'
        +'OK \\u2014 RE-SEAL: everything is re-encrypted under this device\\u2019s current '
        +'passphrase, and that is the one that opens it afterwards.\\n\\n'
        +'Cancel \\u2014 restore as-is: the backup\\u2019s passphrase becomes the one that opens the vault.')){
        const cur=await backupAskPass({
          step:'Restore \\u00b7 this device\\u2019s vault',
          title:'This device\\u2019s passphrase',
          body:'The one you use on this phone now. Everything in the backup is re-sealed '
              +'under it in memory, before the restore commits \\u2014 if any part of it will '
              +'not open, nothing is restored and this device is left as it is.',
          block:settings.vault,
          err:'That is not this device\\u2019s vault passphrase \\u2014 retry or cancel.'});
        if(!cur){ reset(); toast('Restore cancelled \\u2014 nothing changed'); return; }
        keepVault=settings.vault;
        try{
          await vaultBusy('Re-sealing the restore','reading the backup',0);
          await backupReseal(d, got.key, cur.key);
          vaultBusyDone();
        }catch(err){
          vaultBusyDone(); reset();
          alert('Re-seal failed, so nothing was restored and this device is untouched:\\n\\n'
                +(err.message||err));
          return;
        }
      }
    }
  }

  try{
    /* VAULT_BACKUP — the salt and verifier come back with the data, and the key
       in memory goes: whatever is on screen belongs to the old data set. */
    vaultRelock(true);
    houses=d.houses||[]; tasks=d.tasks||[]; notes=d.notes||[];
    persist.houses(); persist.tasks(); persist.notes();

    /* BACKUP_V3 — a version 3 file carries these; a version 2 file does not,
       and what is on this device is then left exactly where it is. */
    if(Array.isArray(d.categories) && d.categories.length){ categories=d.categories; persist.categories(); }
    const vaultBlock = keepVault || d.vault || null;
    if(d.settings && typeof d.settings==='object'){
      const next=Object.assign({}, d.settings);
      /* The PIN is not cryptographic and belongs to the phone in your hand,
         not to the file. Keep the one already set here; take the backup's only
         on a device that has none. */
      if(settings.pinHash){ next.pinHash=settings.pinHash; next.pinSalt=settings.pinSalt; }
      settings=next;
    }
    settings.vault=vaultBlock;
    if(!settings.sortHouses) settings.sortHouses='updated';
    if(!settings.units) settings.units='imperial';
    /* The data is as old as the moment the file was written, and the backup
       nudge should say so. Never the restored value, never now(). */
    settings.lastBackupAt=d.exportedAt||now();
    persist.settings();

    /* photos */
    const existing=await photoAll(); for(const p of existing) await photoDel(p.id).catch(()=>{});
    _objUrls.clear(); _vaultUrlIds.clear(); _vaultCache.clear();
    for(const [id,p] of Object.entries(d.photos||{})){
      let rec;
      if(p.enc===1) rec={id, enc:1, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                         type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt};
      else if(p.env===1) rec={id, env:1, ek:p.ek, iv:p.iv, ct:bytesFromB64(p.b64).buffer,
                         type:p.type||'image/jpeg', houseId:p.houseId, createdAt:p.createdAt};
      else rec={id, blob:b64ToBlob(p.b64), houseId:p.houseId, createdAt:p.createdAt};
      if(p.cropped) rec.cropped=true;
      await photoPut(rec);
    }
    reset();
    go('houses');
    toast(houses.some(h=>h.protected)?'Restored — protected projects are locked':'Backup restored');
  }catch(err){ reset(); alert('Could not restore: '+err.message); }
}"""
    edits.append((old4, new4, "importData(): manifest + passphrase gate + re-seal + v2/v3"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_backup_v3_check.js")
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

    print("\n✅ Backup v3 applied: exports now carry categories, settings, cropped")
    print("   flags and a contents manifest; restores gate on the vault passphrase")
    print("   and can re-seal under this device's.")
    print("   Next: run the round-trip harness, then egs-deploy.sh --full.")
    print("   Then make a fresh export — every backup made before this is incomplete.")


if __name__ == "__main__":
    main()
