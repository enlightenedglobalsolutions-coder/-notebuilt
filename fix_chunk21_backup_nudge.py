#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Chunk 21: backup-durability nudge
Run this from the same folder as your index.html:
    python3 fix_chunk21_backup_nudge.py

Same gentle, infrequent backup reminder built for Kept, ported here: shows
only if there are actual projects, only if it's been 21+ days since your
last backup (or you've never backed up), or if the browser hasn't
confirmed your data is protected from being cleared. Dismiss snoozes it a
week. Never stacks with the install-prompt banner. Every real export
(from this banner or Settings) records the date automatically.

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
MARKER = "CHUNK21_BACKUP_NUDGE"

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
    # Edit 1: CSS — matching #backup-banner styles
    # ---------------------------------------------------------------
    old1 = """  #install-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}"""
    new1 = """  #install-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}

  /* CHUNK21_BACKUP_NUDGE */
  #backup-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
  }
  #backup-banner .txt{flex:1;font-size:13px;line-height:1.4;color:var(--paper-dim)}
  #backup-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}"""
    edits.append((old1, new1, "CSS: #backup-banner styles"))

    # ---------------------------------------------------------------
    # Edit 2: exportData() — track lastBackupAt
    # ---------------------------------------------------------------
    old2 = """async function exportData(){
  toast('Building backup…');
  const photos=await photoAll();
  const photoData={};
  for(const p of photos){ photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)}; }
  /* CHUNK13_RENAME_BACKUP */
  const dump={ app:'notebuilt', version:1, exportedAt:now(), houses, tasks, notes, photos:photoData };
  const blob=new Blob([JSON.stringify(dump)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download=`notebuilt-backup-${todayKey()}.json`; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000); toast('Backup downloaded');
}"""
    new2 = """async function exportData(){
  toast('Building backup…');
  const photos=await photoAll();
  const photoData={};
  for(const p of photos){ photoData[p.id]={houseId:p.houseId,createdAt:p.createdAt,b64:await blobToB64(p.blob)}; }
  /* CHUNK13_RENAME_BACKUP */
  const dump={ app:'notebuilt', version:1, exportedAt:now(), houses, tasks, notes, photos:photoData };
  const blob=new Blob([JSON.stringify(dump)],{type:'application/json'});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download=`notebuilt-backup-${todayKey()}.json`; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href),1000); toast('Backup downloaded');
  settings.lastBackupAt=now(); persist.settings();
}"""
    edits.append((old2, new2, "exportData(): track lastBackupAt"))

    # ---------------------------------------------------------------
    # Edit 3 & 4: hook the nudge check into both unlock success paths
    # ---------------------------------------------------------------
    old3 = """  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); return; }"""
    new3 = """  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); return; }"""
    edits.append((old3, new3, "lockGate(): hook nudge on no-PIN unlock"))

    old4 = """        if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); }"""
    new4 = """        if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); }"""
    edits.append((old4, new4, "lockGate(): hook nudge on correct-PIN unlock"))

    # ---------------------------------------------------------------
    # Edit 5: mutual exclusion + the full nudge module
    # ---------------------------------------------------------------
    old5 = """function maybeShowInstallPrompt(){
  if(installPromptShown||isStandaloneApp()||localStorage.getItem('installPromptDismissed')||!appUnlocked()) return;
  if(deferredInstallPrompt) showInstallBanner('android');
  else if(isIOSDevice()) showInstallBanner('ios');
}"""
    new5 = """function maybeShowInstallPrompt(){
  if(installPromptShown||isStandaloneApp()||localStorage.getItem('installPromptDismissed')||!appUnlocked()) return;
  if(document.getElementById('backup-banner')) return;
  if(deferredInstallPrompt) showInstallBanner('android');
  else if(isIOSDevice()) showInstallBanner('ios');
}

/* CHUNK21_BACKUP_NUDGE — quiet, infrequent, never a modal */
async function maybeShowDataSafetyNudge(){
  if(!appUnlocked()) return;
  if(document.getElementById('install-banner')||document.getElementById('backup-banner')) return;
  if(!houses.length) return;
  const snoozeUntil=parseInt(localStorage.getItem('backupNudgeSnoozeUntil')||'0',10);
  if(Date.now()<snoozeUntil) return;

  const last=settings.lastBackupAt||0;
  const daysSince=last?(Date.now()-last)/86400000:Infinity;
  const backupDue=daysSince>=21;

  let notPersistent=false;
  if(navigator.storage&&navigator.storage.persisted){
    try{ notPersistent=!(await navigator.storage.persisted()); }catch(e){}
  }

  if(!backupDue&&!notPersistent) return;
  showDataSafetyBanner(!last, notPersistent);
}
function showDataSafetyBanner(neverBackedUp, notPersistent){
  if(document.getElementById('backup-banner')||document.getElementById('install-banner')) return;
  let msg;
  if(neverBackedUp&&notPersistent) msg="You haven't backed up yet, and this browser hasn't confirmed your data is protected from being cleared.";
  else if(neverBackedUp) msg="You haven't exported a backup yet. Keep a copy somewhere safe.";
  else if(notPersistent) msg="It's been a while since your last backup, and this browser hasn't confirmed your data is protected from being cleared.";
  else msg="It's been a while since your last backup. Keep a copy somewhere safe.";
  const el=document.createElement('div');
  el.id='backup-banner';
  el.innerHTML=`<div class="txt"><b>Back up your projects</b>${msg}</div>
    <button class="btn primary sm" id="backup-go">Back up now</button>
    <button class="icon-btn" id="backup-x" aria-label="Not now" style="width:36px;height:36px;flex:none">${I.x}</button>`;
  document.body.appendChild(el);
  document.getElementById('backup-go').onclick=async()=>{
    await exportData();
    dismissBackupBanner();
  };
  document.getElementById('backup-x').onclick=()=>{
    localStorage.setItem('backupNudgeSnoozeUntil', String(Date.now()+7*86400000));
    dismissBackupBanner();
  };
}
function dismissBackupBanner(){
  const el=document.getElementById('backup-banner'); if(el) el.remove();
}"""
    edits.append((old5, new5, "add data-safety nudge module + mutual exclusion"))

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
        fail("no <script> block found after edit.")
    js_path = Path("/tmp/_notebuilt_chunk21_check.js")
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

    print("\n✅ Chunk 21 applied successfully: backup-durability nudge.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
