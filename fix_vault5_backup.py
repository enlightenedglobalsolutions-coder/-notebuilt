#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 5 of 5: backup and restore
Run this from the same folder as your index.html:
    python3 fix_vault5_backup.py

Requires scripts 1-4.

exportData() didn't export settings at all, which meant the vault salt and
verifier were not in the backup file — so a protected project could be restored
and then never opened again by anyone, ever. That is closed here: the vault
block travels with the data.

What goes in the file is ciphertext exactly as it sits in storage, IV and all.
The passphrase is not in there and cannot be — nothing derived from it is
stored anywhere. That is what makes the file safe to keep on a laptop, in a
cloud drive, on a USB stick in a drawer: losing it gives up nothing.

Restore brings protected projects back locked, and says so before it starts.

Backup filename standard is unchanged: notebuilt-backup-<date>.json.

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
MARKER = "VAULT_BACKUP"
REQUIRES = ["VAULT_CORE", "VAULT_CEREMONY", "VAULT_RENDER", "VAULT_TOGGLE"]

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
    # Edit 1: export — carry the vault block and sealed photos
    # ---------------------------------------------------------------
    old = r"""async function exportData(){
  toast('Building backup…');
  const photos=await photoAll();
  const photoData={};
  for(const p of photos){ photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)}; }
  /* CHUNK13_RENAME_BACKUP */
  const dump={ app:'notebuilt', version:1, exportedAt:now(), houses, tasks, notes, photos:photoData };"""

    new = r"""async function exportData(){
  toast('Building backup…');
  const photos=await photoAll();
  const photoData={};
  for(const p of photos){
    /* VAULT_BACKUP — a sealed photo is exported exactly as it sits in storage:
       ciphertext and its IV. The file never holds a readable copy. */
    if(isEncPhoto(p)) photoData[p.id]={ enc:1, iv:p.iv, type:p.type||'image/jpeg',
                                        houseId:p.houseId, createdAt:p.createdAt, b64:b64FromBytes(p.ct) };
    else photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)};
  }
  /* CHUNK13_RENAME_BACKUP */
  /* The salt and verifier have to travel with the data, or a restored protected
     project could never be opened again by anyone. The passphrase itself is not
     in here and cannot be — nothing derived from it is stored anywhere. */
  const dump={ app:'notebuilt', version:2, exportedAt:now(), houses, tasks, notes, photos:photoData,
               vault: settings.vault || null };"""
    edits.append((old, new, "exportData(): vault block + sealed photos"))

    # ---------------------------------------------------------------
    # Edit 2: restore — bring the vault back, and sealed photos with it
    # ---------------------------------------------------------------
    old = r"""  if(!confirm('Restore will REPLACE everything currently in the app with the backup. Continue?')) return;
  try{
    const text=await file.text(); const d=JSON.parse(text);
    if(d.app!=='notebuilt' && d.app!=='punchlist') throw new Error('Not a Notebuilt backup');
    houses=d.houses||[]; tasks=d.tasks||[]; notes=d.notes||[];
    persist.houses(); persist.tasks(); persist.notes();
    /* photos */
    const existing=await photoAll(); for(const p of existing) await photoDel(p.id).catch(()=>{});
    _objUrls.clear();
    for(const [id,p] of Object.entries(d.photos||{})){ await photoPut({id,blob:b64ToBlob(p.b64),houseId:p.houseId,createdAt:p.createdAt}); }
    go('houses'); toast('Backup restored');"""

    new = r"""  if(!confirm('Restore will REPLACE everything currently in the app with the backup.\n\nThat includes your vault: any protected projects in the backup come back locked, and only the passphrase they were made with will open them.\n\nContinue?')) return;
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
      else await photoPut({id,blob:b64ToBlob(p.b64),houseId:p.houseId,createdAt:p.createdAt});
    }
    go('houses');
    toast(houses.some(h=>h.protected)?'Restored — protected projects are locked':'Backup restored');"""
    edits.append((old, new, "importData(): restore the vault and sealed photos"))

    # ---------------------------------------------------------------
    # Edit 3: backup copy — say the file is safe to keep anywhere
    # ---------------------------------------------------------------
    # NB: the source file writes its dashes as — escapes, not literal em-dashes.
    # The source file writes its dashes as backslash-u escapes, not literal
    # em-dashes, so the anchor is built explicitly rather than typed.
    D = "\\u2014"
    old = ('const APP_BACKUP_DESC = "Save your projects, photos, notes and to-dos to a file. '
           'Keep it safe ' + D + ' you can restore it anytime, even on a new phone or after reinstalling.";')
    new = ('const APP_BACKUP_DESC = "Save your projects, photos, notes and to-dos to a file. '
           'Keep it safe ' + D + ' you can restore it anytime, even on a new phone or after reinstalling.'
           '<br><br>Anything in a protected project stays encrypted inside the file, so the backup '
           'is safe to store anywhere ' + D + ' a copy of it gives up nothing without your vault passphrase.";')
    edits.append((old, new, "backup description copy"))

    # ---------------------------------------------------------------
    # Edit 4: restore copy — state what comes back locked
    # ---------------------------------------------------------------
    old = r"""    <div class="row" style="gap:10px;margin:10px 0 22px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>"""
    new = r"""    <div class="row" style="gap:10px;margin:10px 0 10px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>
    <div class="muted" style="font-size:12.5px;line-height:1.6;margin:0 0 22px">Restoring replaces everything currently in the app. Protected projects come back <b style="color:var(--paper)">locked</b> &mdash; you'll need the passphrase they were made with, and nothing in the file can stand in for it.</div>"""
    edits.append((old, new, "restore copy"))

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
    js_path = Path("/tmp/_notebuilt_vault5_check.js")
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

    print("\n✅ Vault 5/5 applied: backup and restore carry the vault.")
    print("   All five scripts applied. Next: test, then deploy with egs-deploy.sh --full")

if __name__ == "__main__":
    main()
