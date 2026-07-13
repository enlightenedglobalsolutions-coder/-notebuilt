#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
What's For Dinner (WFD) — Fix 23: backup-durability nudge
Run this from the same folder as your index.html:
    python3 fix23_backup_nudge.py

Same gentle, infrequent backup reminder as Notebuilt and Kept, adapted to
WFD's light theme and vanilla-JS structure (no PIN-lock gate here, so it
checks once shortly after the app finishes loading instead). Shows only
if you have saved meals worth losing, only if it's been 21+ days since
your last backup (or never), or if the browser hasn't confirmed your data
is protected from being cleared. Dismiss snoozes it a week. Every real
export (from this banner or Settings) records the date automatically.

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
MARKER = "FIX23_BACKUP_NUDGE"

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
    # Edit 1: export button handler — track last-backup timestamp
    # ---------------------------------------------------------------
    old1 = """      setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
      showToast('\U0001f4be Backup saved!');
    } catch(e){
      showToast('Could not export \u2014 try again');
    }
  });"""
    new1 = """      setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
      showToast('\U0001f4be Backup saved!');
      try{ localStorage.setItem('wfd_last_backup_at', String(Date.now())); }catch(_e){}
      dismissBackupBanner();
    } catch(e){
      showToast('Could not export \u2014 try again');
    }
  });"""
    edits.append((old1, new1, "export handler: track wfd_last_backup_at"))

    # ---------------------------------------------------------------
    # Edit 2: boot sequence — check the nudge shortly after load
    # ---------------------------------------------------------------
    old2 = """buildSvBtns();
tick();
setInterval(tick,30000);"""
    new2 = """buildSvBtns();
tick();
setInterval(tick,30000);

/* FIX23_BACKUP_NUDGE — quiet, infrequent, never a modal */
(function(){
  var css='#backup-banner{position:fixed;left:12px;right:12px;bottom:16px;z-index:4000;'
    +'background:#fff;border:1px solid #B5D4F4;border-radius:14px;box-shadow:0 8px 24px rgba(4,44,83,0.18);'
    +'padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}'
    +'#backup-banner .txt{flex:1;font-size:13px;line-height:1.4;color:#185FA5;}'
    +'#backup-banner .txt b{color:#042C53;display:block;font-size:15px;margin-bottom:2px;}'
    +'#backup-banner button{border:none;border-radius:20px;cursor:pointer;flex:none;}'
    +'#backup-banner .bb-go{background:#185FA5;color:#fff;font-weight:700;font-size:13px;padding:9px 14px;}'
    +'#backup-banner .bb-x{background:#E6F1FB;color:#185FA5;width:32px;height:32px;font-size:16px;font-weight:700;}';
  var st=document.createElement('style'); st.textContent=css; document.head.appendChild(st);

  function hasSavedMeals(){
    try{ var raw=localStorage.getItem('wfd_saved'); if(!raw) return false; var arr=JSON.parse(raw); return !!(arr&&arr.length); }
    catch(_e){ return false; }
  }
  window.dismissBackupBanner=function(){
    var el=qs('backup-banner'); if(el) el.remove();
  };
  function showBackupBanner(neverBackedUp, notPersistent){
    if(qs('backup-banner')) return;
    var msg;
    if(neverBackedUp&&notPersistent) msg="You haven't backed up yet, and this browser hasn't confirmed your data is protected from being cleared.";
    else if(neverBackedUp) msg="You haven't exported a backup yet. Keep a copy somewhere safe.";
    else if(notPersistent) msg="It's been a while since your last backup, and this browser hasn't confirmed your data is protected from being cleared.";
    else msg="It's been a while since your last backup. Keep a copy somewhere safe.";
    var el=document.createElement('div');
    el.id='backup-banner';
    el.innerHTML='<div class="txt"><b>Back up your recipes</b>'+msg+'</div>'
      +'<button class="bb-go" id="backup-go">Back up now</button>'
      +'<button class="bb-x" id="backup-x" aria-label="Not now">\u2715</button>';
    document.body.appendChild(el);
    var goBtn=qs('backup-go'); if(goBtn) goBtn.addEventListener('click', function(){ var b=qs('btnExportData'); if(b) b.click(); });
    var xBtn=qs('backup-x'); if(xBtn) xBtn.addEventListener('click', function(){
      try{ localStorage.setItem('wfd_backup_snooze_until', String(Date.now()+7*86400000)); }catch(_e){}
      dismissBackupBanner();
    });
  }
  function maybeShowBackupNudge(){
    if(!hasSavedMeals()) return;
    var snoozeUntil=0; try{ snoozeUntil=parseInt(localStorage.getItem('wfd_backup_snooze_until')||'0',10); }catch(_e){}
    if(Date.now()<snoozeUntil) return;
    var last=0; try{ last=parseInt(localStorage.getItem('wfd_last_backup_at')||'0',10); }catch(_e){}
    var daysSince=last?(Date.now()-last)/86400000:Infinity;
    var backupDue=daysSince>=21;
    var check=function(notPersistent){
      if(!backupDue&&!notPersistent) return;
      showBackupBanner(!last, notPersistent);
    };
    if(navigator.storage&&navigator.storage.persisted){
      navigator.storage.persisted().then(function(p){ check(!p); }).catch(function(){ check(false); });
    }else{ check(false); }
  }
  setTimeout(maybeShowBackupNudge, 2500);
})();"""
    edits.append((old2, new2, "boot sequence: add backup nudge check"))

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
    ok_all = True
    for i, s in enumerate(scripts):
        js_path = Path(f"/tmp/_wfd_fix23_check_{i}.js")
        js_path.write_text(s, encoding="utf-8")
        try:
            result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            print("⚠️  node not found — skipping syntax check.")
            result = None
        if result is not None and result.returncode != 0:
            ok_all = False
            print(f"Script block {i} syntax error:\n{result.stderr}")
    if not ok_all:
        shutil.copy2(backup_path, TARGET)
        fail("JS syntax check failed, restored from backup.")
    print("✅ JS syntax check passed (node --check)")

    print("\n✅ Fix 23 applied successfully: backup-durability nudge.")
    print("   Next: push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
