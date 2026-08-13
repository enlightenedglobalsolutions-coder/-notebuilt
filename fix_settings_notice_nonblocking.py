#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the unreadable-settings notice must not be a modal at launch
Run from the same folder as index.html:
    python3 fix_settings_notice_nonblocking.py

WHY
---
fix_settings_never_self_destruct.py announced the emergency with an
`alert()` on a timer. Testing it froze the renderer outright, which is the
same thing it would do to a person opening the app: a modal fires before
anything is on screen, blocks the whole page until it is dismissed, and on
an installed PWA is a genuinely alarming way to be greeted.

It is also the wrong shape for the message. This state persists — every
settings write stays blocked until a backup is restored — so it needs a
surface that persists with it, not one that is dismissed once and gone.

THE NOTICE
----------
* a toast shortly after launch, so it is noticed at all
* a permanent card at the top of Settings, in the danger style, stating
  what is affected, what is safe, and what to do

Both are non-blocking. Nothing about the guarantee changes: the damaged
file is still preserved untouched and every settings write is still
refused. Only the way it is said changes.

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

    old_alert = """if(settingsUnreadable){
  setTimeout(()=>{ try{
    alert('Notebuilt could not read your saved settings.\\n\\n'
      +'Your projects, notes and photos are safe and untouched. What is affected is your app lock, your vault passphrase record and your unlock.\\n\\n'
      +'Nothing has been overwritten — the file is being left exactly as it is. Restore your most recent backup to put it right.');
  }catch(e){} }, 1500);
}"""
    new_alert = """if(settingsUnreadable){
  /* Noticed at all, without blocking the app the way a modal at launch
     would. The lasting surface is the card in Settings below — this state
     does not go away until a backup is restored, so the notice should not
     either. */
  setTimeout(()=>{ try{ toast('Saved settings could not be read \\u2014 see Settings'); }catch(e){} }, 1800);
}"""
    edits.append((old_alert, new_alert, "non-blocking launch notice"))

    old_head = """  return `<div class="topbar"><div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Settings</h1></div></div>
  <div class="wrap">"""
    new_head = """  return `<div class="topbar"><div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Settings</h1></div></div>
  <div class="wrap">
    ${settingsUnreadable?`<div class="card" style="border:1px solid var(--danger,#b5453b);margin-bottom:14px">
      <div style="font-weight:600;margin-bottom:6px">Your saved settings could not be read</div>
      <div class="muted" style="font-size:13px;line-height:1.6">Your projects, notes, to-dos and photos are safe and untouched. What is in that file is your app lock, your vault passphrase record, your recovery code and your unlock.<br><br>
      Nothing has been overwritten — the damaged file is being left exactly as it is, and Notebuilt has stopped saving settings so it stays that way. Restore your most recent backup to put it right.<br><br>
      Until then, changes on this screen will not be remembered.</div>
    </div>`:''}"""
    edits.append((old_head, new_head, "renderSettings(): the lasting notice"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "alert('Notebuilt could not read" in working:
        fail("the blocking launch alert survived.")
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    if "if(settingsUnreadable) return;" not in working:
        fail("the write block was lost.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: no blocking dialog at launch; write block intact")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_notice_check.js")
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

    print("\n✅ the emergency is announced without freezing the app that is reporting it.")


if __name__ == "__main__":
    main()
