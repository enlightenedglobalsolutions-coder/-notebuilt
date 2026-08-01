#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — visible version stamp
Run this from the same folder as your index.html:
    python3 fix_version_stamp.py

window.EGS_VERSION printed at the bottom of Settings: small, dim, one line.
egs-deploy.sh already stamps that value into index.html on every deploy, so
this just surfaces what is already there — which is what makes it useful when
someone says "it still looks stale" and you need to know what they are actually
running before you start guessing.

Family-standard candidate; here it is only Notebuilt.

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
MARKER = "VERSION_STAMP"

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

    old = r"""      Enlightened Global Solutions · on-device · one-time, no subscription.
    </div>
  </div>`;
}"""
    new = r"""      Enlightened Global Solutions · on-device · one-time, no subscription.
    </div>

    <!-- VERSION_STAMP — what egs-deploy.sh stamped, shown so "is it actually
         updated?" is a question you can answer by looking. -->
    <div class="mono" style="text-align:center;font-size:10.5px;letter-spacing:.12em;color:var(--paper-faint);margin:20px 0 4px">${esc(window.EGS_VERSION||'dev build')}</div>
  </div>`;
}"""
    edits.append((old, new, "Settings: version stamp"))

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
    js_path = Path("/tmp/_notebuilt_version_check.js")
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

    print("\n✅ Version stamp applied: bottom of Settings.")

if __name__ == "__main__":
    main()
