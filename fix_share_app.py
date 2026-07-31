#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Share the app
Run this from the same folder as your index.html:
    python3 fix_share_app.py

A "Share Notebuilt" button on the Support & Backup page — the Contribute page,
and the natural home for it, because passing the app on is a form of support
that costs nothing.

navigator.share with title, one-line description and the app URL. Where share
is unavailable (most desktop browsers), it falls back to copying the line to the
clipboard with a toast; if the clipboard is refused too, it opens a sheet with
the text selectable, so there is always a way through.

ZERO vault interaction by construction. This function reads no project, no
photo, no note, no setting. The only thing it can ever send is the app's own
public URL, computed from location — there is no code path from here to user
data, which is the property worth keeping true if this is ever extended.

NOTE ON PLACEMENT: egsSupportCoreHtml() carries a "copy this verbatim into every
EGS app, do not edit" banner, so the button is added to renderSupport() — the
app-specific block above it — rather than inside the shared core.

The share line is a single const at the top of the app-specific block, flagged
for Edwin's veto:
    "Notebuilt — the field notebook for construction crews. Private, offline, yours."

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
MARKER = "SHARE_APP"

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
    # Edit 1: the share line + the share function
    # ---------------------------------------------------------------
    old = r"""function renderSupport(){"""
    new = r"""/* ============================================================
   SHARE_APP — passing the app on, as a form of support.
   Sends the public app link and nothing else. No project, no photo, no note,
   no setting, no vault. There is deliberately no code path from here to user
   data, and that is the property to keep true if this is ever extended.
   ============================================================ */
/* The share line. One string, easy to veto or rewrite. */
const SHARE_APP_LINE = 'Notebuilt — the field notebook for construction crews. Private, offline, yours.';

function appShareUrl(){
  /* the app's own directory URL, never a deep link into any state */
  return location.origin + location.pathname.replace(/[^/]*$/, '');
}
async function doShareApp(){
  const url=appShareUrl();
  if(navigator.share){
    try{
      await navigator.share({ title:APP_NAME, text:SHARE_APP_LINE, url });
      return;                                     /* the OS sheet said its piece */
    }catch(err){
      if(err && err.name==='AbortError') return;  /* user backed out — say nothing */
      /* anything else: fall through to the clipboard */
    }
  }
  try{
    await navigator.clipboard.writeText(SHARE_APP_LINE+' '+url);
    toast('Link copied');
  }catch(e){
    /* clipboard refused (insecure context, permissions) — show it instead of
       swallowing it, so there is always a way to get the link out */
    sheet('<h2>Share '+esc(APP_NAME)+'</h2>'
      +'<div class="muted" style="font-size:13px;margin-bottom:10px">Copy this and send it on:</div>'
      +'<div class="card mono" style="font-size:12.5px;word-break:break-all;line-height:1.6">'
      +esc(SHARE_APP_LINE+' '+url)+'</div>'
      +'<button class="btn primary block" data-copy="'+esc(SHARE_APP_LINE+' '+url)+'" style="margin-top:10px">Copy</button>');
    bindCopyButtons($mr);
  }
}

function renderSupport(){"""
    edits.append((old, new, "share line + doShareApp()"))

    # ---------------------------------------------------------------
    # Edit 2: the button on the Support & Backup page
    # ---------------------------------------------------------------
    old = r"""    ${egsSupportCoreHtml(tabs)}"""
    new = r"""    <div class="sec-head"><span class="label">Share ${esc(APP_NAME)}</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Know a crew who'd use this? Passing it on is its own kind of support, and it costs nothing. This sends the app's public link and nothing else &mdash; none of your projects, photos or notes go with it.</div>
    <button class="btn block" data-share-app style="margin:10px 0 22px;display:flex;align-items:center;justify-content:center;gap:8px">${I.share} Share ${esc(APP_NAME)}</button>

    ${egsSupportCoreHtml(tabs)}"""
    edits.append((old, new, "Support page: Share button"))

    # ---------------------------------------------------------------
    # Edit 3: wire it
    # ---------------------------------------------------------------
    old = r"""  $app.querySelectorAll('[data-pay-tab]').forEach(b=>b.onclick=()=>{"""
    new = r"""  const shareAppBtn=$app.querySelector('[data-share-app]'); if(shareAppBtn) shareAppBtn.onclick=doShareApp;
  $app.querySelectorAll('[data-pay-tab]').forEach(b=>b.onclick=()=>{"""
    edits.append((old, new, "bind(): Share button"))

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

    print("\n✅ Share Notebuilt applied: button on the Support & Backup page.")

if __name__ == "__main__":
    main()
