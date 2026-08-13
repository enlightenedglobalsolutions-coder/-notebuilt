#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the privacy scan must list only hosts the app can reach
Run from the same folder as index.html:
    python3 fix_unlock_sandbox_comment.py

egs-deploy.sh --full reports third-party hosts with

    grep -oE 'https://[a-z0-9.-]+' index.html

which is a text scan, so it cannot tell a live endpoint from a URL sitting
in a comment. The UNLOCK_CONFIG block explains how to switch to the
sandbox and named the host as a full URL, so the privacy report listed

    https://sandbox-api.polar.sh

as an external host — for a build that can never contact it. A privacy
report whose job is "verify each host is intended" loses exactly that job
when it names hosts the app does not use, because the reader starts
discounting the list.

The instruction is worth keeping, so only the scheme goes. The host is
still named, the switch is still documented, and the report now lists the
two hosts this build can actually reach: api.polar.sh (activation) and
buy.polar.sh (the checkout link a person taps).

Backs up first, exact-match anchor asserted ==1, node --check, atomic.
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

    old = """   SANDBOX: point API_BASE at 'https://sandbox-api.polar.sh' and ORG_ID at
   the sandbox organisation. Nothing else changes — the endpoint path and
   payload are identical on both."""
    new = """   SANDBOX: point API_BASE at the sandbox-api.polar.sh host (same scheme,
   same path) and ORG_ID at the sandbox organisation. Nothing else changes
   — the endpoint path and payload are identical on both. The scheme is
   left off deliberately: the deploy privacy scan greps this file for
   https:// URLs, and a host named here but never contacted would show up
   in that report as though the app talked to it."""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    hosts = sorted(set(re.findall(r"https://[a-z0-9.-]+", working)))
    polar_hosts = [h for h in hosts if "polar" in h]
    if sorted(polar_hosts) != ["https://api.polar.sh", "https://buy.polar.sh"]:
        fail(f"unexpected polar hosts remain as URLs: {polar_hosts}")
    if "sandbox-api.polar.sh" not in working:
        fail("the sandbox switching instruction was lost entirely.")
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not set to production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")
    print(f"✅ guard: polar hosts reachable as URLs are exactly {polar_hosts}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_unlock_comment_check.js")
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

    print("\n✅ the privacy report now lists only hosts this build can reach.")


if __name__ == "__main__":
    main()
