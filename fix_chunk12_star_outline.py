#!/usr/bin/env python3
"""
Notebuilt — Chunk 12: fix oversized Important star + switch to outline style
Run this from the same folder as your index.html:
    python3 fix_chunk12_star_outline.py

Fixes the sizing bug from Chunk 11 (the star had no explicit width/height,
so it rendered at the browser's default SVG size and filled the whole
card), and swaps the filled star for a small outlined star (Option 5 from
the mockup) — quieter and more classy at 15px.

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
MARKER = "CHUNK12_STAR_OUTLINE"  # already-applied guard

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
    # Edit 1: CSS — explicit sizing for the note-star icon (fixes the bug)
    # ---------------------------------------------------------------
    old1 = """  .empty svg{width:40px;height:40px;color:var(--line);margin-bottom:12px}"""
    new1 = """  .empty svg{width:40px;height:40px;color:var(--line);margin-bottom:12px}
  /* CHUNK12_STAR_OUTLINE */
  .note-star{display:inline-flex;flex:none;vertical-align:-2px}
  .note-star svg{width:15px;height:15px;display:block}"""
    edits.append((old1, new1, "CSS: explicit sizing for .note-star"))

    # ---------------------------------------------------------------
    # Edit 2: icon set — swap filled star for an outlined star
    # ---------------------------------------------------------------
    old2 = """  star:'<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.9 5.8 21.2 7 14.2 2 9.3l7.1-.7L12 2z"/></svg>',"""
    new2 = """  star:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"><path d="M12 2l2.9 6.6L22 9.3l-5 4.9 1.2 7L12 17.9 5.8 21.2 7 14.2 2 9.3l7.1-.7L12 2z"/></svg>',"""
    edits.append((old2, new2, "icon set: I.star becomes outlined instead of filled"))

    # ---------------------------------------------------------------
    # Edit 3: noteCardHtml() — apply the sizing class to the star wrapper
    # ---------------------------------------------------------------
    old3 = """    <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${n.important?`<span style="color:var(--brass)">${I.star}</span> `:''}${esc(n.title||'Untitled')}</div>"""
    new3 = """    <div class="row"><div class="grow"><div style="font-family:var(--serif);font-size:17px">${n.important?`<span class="note-star" style="color:var(--brass)">${I.star}</span> `:''}${esc(n.title||'Untitled')}</div>"""
    edits.append((old3, new3, "noteCardHtml(): apply .note-star sizing class"))

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
    js_path = Path("/tmp/_notebuilt_chunk12_check.js")
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

    print("\n✅ Chunk 12 applied successfully: star icon fixed and now outlined + small.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
