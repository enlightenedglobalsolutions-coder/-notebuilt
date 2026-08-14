#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the activation sentence, made accurate about counts
Run from the same folder as index.html:
    python3 fix_privacy_activation_sentence.py

Copy only. One line of the privacy page.

WHAT WAS OFF
------------
The paragraph predates the validate fallback and counts REQUESTS in two
places, both of which the fallback made untrue:

    "...sends your key once to Polar..."      <- the key goes with the
                                                 follow-up request too
    "That single moment is the only time."    <- reads as "one request",
                                                 and there may be two

The sentence added in the last sweep says the honest thing straight after
("If that first request is refused, Notebuilt asks the server one follow-up
question"), which left the page contradicting itself a line apart.

THE FIX
-------
Stop counting requests and count MOMENTS, which is the claim that is both
true and the one a reader actually cares about:

    "...sends your key to Polar, who handle the payment, to register it.
     That is the only moment Notebuilt ever reaches out."

"once" simply goes — the following sentences already establish that nothing
precedes the key and nothing follows the unlock, which is the guarantee. The
number of requests inside that single moment is then described exactly, by
the sentence underneath it.

Nothing else on the page changes, and no behaviour anywhere does.

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

    old = """      If you unlock the app, tapping <b style="color:var(--paper)">Activate</b> sends your key once to Polar, who handle the payment, to register it. That single moment is the only time. Nothing of yours goes with it"""
    new = """      If you unlock the app, tapping <b style="color:var(--paper)">Activate</b> sends your key to Polar, who handle the payment, to register it. That is the only moment Notebuilt ever reaches out. Nothing of yours goes with it"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "sends your key once to Polar" in working:
        fail("the request-counting 'once' survived.")
    if "That single moment is the only time" in working:
        fail("the old single-request claim survived.")
    if "That is the only moment Notebuilt ever reaches out." not in working:
        fail("the replacement sentence did not land.")
    # The sentence that describes the follow-up must still be there — it is
    # what makes the new wording precise rather than merely vaguer.
    if "asks the server one follow-up question" not in working:
        fail("the follow-up sentence is missing — the new wording relies on it.")
    # Copy only.
    if working.count("fetch(") != text.count("fetch("):
        fail("the number of fetch( calls changed — this is copy only.")
    hosts = sorted(set(h for h in re.findall(r"https://[a-z0-9.-]+", working) if "polar" in h))
    if hosts != ["https://api.polar.sh", "https://buy.polar.sh"]:
        fail(f"the polar host set changed: {hosts}")
    if working.count("'photo-send':") != text.count("'photo-send':"):
        fail("HELP_COPY['photo-send'] was disturbed — it is still held.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print("✏️  Applied 1 edit to index.html")
    print("✅ guard: no request-counting claims remain; follow-up sentence intact")
    print("✅ guard: copy only — fetch( count and host set unchanged")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_activation_sentence_check.js")
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

    print("\n✅ the page counts moments, not requests — and both are now true.")


if __name__ == "__main__":
    main()
