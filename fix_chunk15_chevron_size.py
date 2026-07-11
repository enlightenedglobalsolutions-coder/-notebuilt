#!/usr/bin/env python3
"""
Notebuilt — Chunk 15: fix oversized chevron icon
Run this from the same folder as your index.html:
    python3 fix_chunk15_chevron_size.py

Same class of bug as the star icon (Chunk 12): I.chevronR had no explicit
width/height, so it rendered at the browser's default SVG size and crushed
the "Privacy & how this works" row's text into a single narrow column.
The same unsized chevron is also used on every project's "Site Notes"
header, so this fixes both spots.

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
MARKER = "CHUNK15_CHEVRON_SIZE"  # already-applied guard

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
    # Edit 1: CSS — explicit sizing for the chevron icon
    # ---------------------------------------------------------------
    old1 = """  .note-star svg{width:15px;height:15px;display:block}"""
    new1 = """  .note-star svg{width:15px;height:15px;display:block}
  /* CHUNK15_CHEVRON_SIZE */
  .chev{display:inline-flex;flex:none;color:var(--paper-faint)}
  .chev svg{width:18px;height:18px;display:block}"""
    edits.append((old1, new1, "CSS: .chev sizing"))

    # ---------------------------------------------------------------
    # Edit 2: renderHouse() — Site Notes header chevron
    # ---------------------------------------------------------------
    old2 = """    <div class="sec-head" data-open-house-notes="${h.id}" style="cursor:pointer"><span class="label">Site Notes</span><span class="rule"></span>${I.chevronR}</div>"""
    new2 = """    <div class="sec-head" data-open-house-notes="${h.id}" style="cursor:pointer"><span class="label">Site Notes</span><span class="rule"></span><span class="chev">${I.chevronR}</span></div>"""
    edits.append((old2, new2, "renderHouse(): wrap Site Notes chevron in .chev"))

    # ---------------------------------------------------------------
    # Edit 3: renderSettings() — Privacy row chevron
    # ---------------------------------------------------------------
    old3 = """    <div class="card row" data-go="privacy" style="cursor:pointer"><div class="grow"><div>Privacy & how this works</div><div class="muted" style="font-size:13px">What we collect, where your data lives, how we make money.</div></div>${I.chevronR}</div>"""
    new3 = """    <div class="card row" data-go="privacy" style="cursor:pointer"><div class="grow"><div>Privacy & how this works</div><div class="muted" style="font-size:13px">What we collect, where your data lives, how we make money.</div></div><span class="chev">${I.chevronR}</span></div>"""
    edits.append((old3, new3, "renderSettings(): wrap Privacy row chevron in .chev"))

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
    js_path = Path("/tmp/_notebuilt_chunk15_check.js")
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

    print("\n✅ Chunk 15 applied successfully: chevron icon fixed in both spots.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
