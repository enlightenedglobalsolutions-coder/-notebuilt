#!/usr/bin/env python3
"""
Notebuilt — Chunk 14: in-app Privacy page
Run this from the same folder as your index.html:
    python3 fix_chunk14_privacy_page.py

Adds a self-contained Privacy screen (no external link, works offline)
reached from Settings, written in Notebuilt's own voice: what's collected
(nothing), where data lives (this device only), when the app touches the
internet (loading itself, and Share project via the native share sheet),
how to control your data, and how EGS makes money.

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
MARKER = "CHUNK14_PRIVACY_PAGE"  # already-applied guard

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

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: render dispatch table — add the 'privacy' view
    # ---------------------------------------------------------------
    old1 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch,
            housenotes:renderHouseNotes})[view.name]||renderToday;"""
    new1 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch,
            housenotes:renderHouseNotes,privacy:renderPrivacy})[view.name]||renderToday;"""
    edits.append((old1, new1, "render dispatch: add privacy view"))

    # ---------------------------------------------------------------
    # Edit 2: renderSettings() — add a Privacy row + renderPrivacy() itself
    # ---------------------------------------------------------------
    old2 = """    <label class="btn block" style="margin-top:10px">${I.upload} Restore from backup<input type="file" accept="application/json,.json" hidden data-import></label>

    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    new2 = """    <label class="btn block" style="margin-top:10px">${I.upload} Restore from backup<input type="file" accept="application/json,.json" hidden data-import></label>

    <div class="sec-head"><span class="label">Privacy</span><span class="rule"></span></div>
    <div class="card row" data-go="privacy" style="cursor:pointer"><div class="grow"><div>Privacy & how this works</div><div class="muted" style="font-size:13px">What we collect, where your data lives, how we make money.</div></div>${I.chevronR}</div>

    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    edits.append((old2, new2, "renderSettings(): add Privacy row"))

    # ---------------------------------------------------------------
    # Edit 3: goBack() — privacy returns to Settings + add renderPrivacy()
    # ---------------------------------------------------------------
    old3 = """function goBack(){
  if(view.name==='housenotes'){ go('house', view.param); return; }
  const to = ({house:'houses', note:'notes', search:'today'})[view.name] || 'today';
  go(to);
}"""
    new3 = """function goBack(){
  if(view.name==='housenotes'){ go('house', view.param); return; }
  const to = ({house:'houses', note:'notes', search:'today', privacy:'settings'})[view.name] || 'today';
  go(to);
}

/* CHUNK14_PRIVACY_PAGE */
function renderPrivacy(){
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Privacy</h1></div>
  </div>
  <div class="wrap">
    <div class="sec-head"><span class="label">What we collect</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Nothing. No account, no sign-up, no email. We don't know who you are, and we don't track what you do in this app.</div>

    <div class="sec-head"><span class="label">Where your data lives</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">On this device only — your projects, photos, notes and to-dos are stored in your phone's own storage. We never receive a copy. There's no server for it to go to.</div>

    <div class="sec-head"><span class="label">When this app touches the internet</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">
      Only to load the app itself from GitHub Pages — no data leaves your phone to do that.<br><br>
      If you use <b style="color:var(--paper)">Share project</b>, that hands a file to your phone's own share sheet — you choose where it goes. We're not part of that transfer.<br><br>
      That's the whole list. No analytics, no background calls, no hidden pings.
    </div>

    <div class="sec-head"><span class="label">Your data, your control</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Export a full backup any time — it's a plain file you keep, not something on our servers. Restore it whenever you like. Delete anything, any time; nothing needs our permission.</div>

    <div class="sec-head"><span class="label">How EGS makes money</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">One-time purchase, no subscription. No ads, ever. We can't sell your data because we never have it in the first place.</div>

    <div class="card" style="margin-top:6px;text-align:center;font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--paper-faint)">Enlightened Global Solutions · Built in Canada<br>Read the code · check for yourself</div>
  </div>`;
}"""
    edits.append((old3, new3, "goBack(): privacy->settings mapping + add renderPrivacy()"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk14_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check. Review the diff manually.")
        result = None

    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 14 applied successfully: in-app Privacy page added, linked from Settings.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
