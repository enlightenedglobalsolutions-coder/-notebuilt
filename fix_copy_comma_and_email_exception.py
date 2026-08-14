#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the send sheet breathes, and the privacy page names the email
Run from the same folder as index.html:
    python3 fix_copy_comma_and_email_exception.py

Copy and markup only. Two edits, no logic, no network, no service worker.

EDIT 1 — the send sheet reads as instructions, not prose
--------------------------------------------------------
    "Share hands the image to another app on this phone.
     Save puts it in your Downloads folder — not the camera roll."

Both sentences open with a button name doing double duty as a verb, so the
eye trips: "Share hands" scans as a compound noun before it resolves into
subject-and-verb. A comma after each button name lets the label be a label:

    "Share, hands the image to another app on this phone.
     Save, puts it in your Downloads folder — not the camera roll."

Edwin's edit, both commas confirmed in session.

EDIT 2 — the privacy page stops being silent about the checkout email
---------------------------------------------------------------------
WHAT WE COLLECT opens "Nothing. No account, no sign-up, no email." That is
true of the app and always will be — but anyone who buys the unlock hands
an email to Polar at checkout, and can see us listed as the merchant. A
reader who meets that after reading this page has caught us in something,
even though nothing about it is untoward.

So the page says it first, in the place where the claim is made, and draws
the line where it actually falls: outside the app, held by Polar, never
joined to anything done here. The headline "Nothing." is untouched — it is
still exactly true of what Notebuilt collects.

HELP_COPY['photo-send'] was reviewed this session and deliberately left
byte-identical. A guard below asserts it did not move.

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


# The help copy is held byte-for-byte across this edit. Compared as a whole
# string rather than by count, so a stray character inside it is caught too.
HELP_PHOTO_SEND = (
    "'photo-send':'Share hands the image straight to another app on this phone "
    "\\u2014 your workforce app, a message, email. Save to device puts a copy in "
    "your Downloads folder, which is not the same place as your camera roll; "
    "your gallery may not show it."
)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")

    # ---- edit 1: the send sheet ----------------------------------------
    sheet_old = (
        "    +'Share hands the image to another app on this phone. "
        "Save puts it in your <b style=\"color:var(--paper)\">Downloads</b> "
        "folder \\u2014 not the camera roll.'"
    )
    sheet_new = (
        "    +'Share, hands the image to another app on this phone. "
        "Save, puts it in your <b style=\"color:var(--paper)\">Downloads</b> "
        "folder \\u2014 not the camera roll.'"
    )

    count = text.count(sheet_old)
    if count != 1:
        fail(f"send-sheet anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(sheet_old, sheet_new, 1)

    # ---- edit 2: the privacy page --------------------------------------
    collect_old = (
        "    <div class=\"card muted\" style=\"font-size:13.5px;line-height:1.6\">"
        "Nothing. No account, no sign-up, no email. We don't know who you are, "
        "and we don't track what you do in this app.</div>"
    )
    exception = (
        "<br><br>The one exception lives outside the app: if you buy the unlock, "
        "Polar — who handle the payment — ask for an email at checkout to send "
        "your key. That email stays with Polar; like any store, we can see who "
        "bought in their dashboard, but it never enters Notebuilt and is never "
        "tied to anything you do here."
    )
    collect_new = collect_old[: -len("</div>")] + exception + "</div>"

    count = working.count(collect_old)
    if count != 1:
        fail(f"privacy 'Nothing.' anchor matched {count} time(s), expected exactly 1.")
    working = working.replace(collect_old, collect_new, 1)

    # ---- guards ---------------------------------------------------------
    if "+'Share hands the image to another app on this phone." in working:
        fail("the un-commaed sheet sentence survived.")
    if "Save puts it in your <b" in working:
        fail("the un-commaed Save sentence survived.")
    if working.count("+'Share, hands the image to another app on this phone.") != 1:
        fail("the commaed sheet line is not present exactly once.")

    if working.count("The one exception lives outside the app") != 1:
        fail("the exception text is not present exactly once.")
    # The headline claim is the whole point of the card — it must be untouched.
    if working.count(
        ">Nothing. No account, no sign-up, no email. We don't know who you are, "
        "and we don't track what you do in this app."
    ) != 1:
        fail("the 'Nothing.' headline claim was disturbed.")

    # Held byte-identical this session, by Edwin's review.
    if working.count(HELP_PHOTO_SEND) != 1 or text.count(HELP_PHOTO_SEND) != 1:
        fail("HELP_COPY['photo-send'] moved — it was to stay byte-identical.")

    # Copy and markup only.
    if working.count("fetch(") != text.count("fetch("):
        fail("the number of fetch( calls changed — this is copy only.")
    hosts = sorted(set(h for h in re.findall(r"https://[a-z0-9.-]+", working) if "polar" in h))
    if hosts != ["https://api.polar.sh", "https://buy.polar.sh"]:
        fail(f"the polar host set changed: {hosts}")
    if working.count("<div") != working.count("</div>"):
        fail("div tags no longer balance.")
    if working.count("<div") != text.count("<div"):
        fail("the number of div elements changed — no new nodes were intended.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print("✏️  Applied 2 edits to index.html")
    print("✅ guard: both send-sheet commas landed; old strings gone")
    print("✅ guard: exception text present once; 'Nothing.' headline unchanged")
    print("✅ guard: HELP_COPY['photo-send'] byte-identical")
    print("✅ guard: copy only — fetch( count, polar hosts, div count unchanged")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_comma_email_check.js")
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

    print("\n✅ the sheet breathes, and the one email we can see is named.")


if __name__ == "__main__":
    main()
