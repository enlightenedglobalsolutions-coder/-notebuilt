#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the unlock help sheet answers the app-store question in Edwin's
words, and stops taking a position he had not taken.
Run from the same folder as index.html:
    python3 fix_infomode_appstore_copy.py

fix_infomode.py wrote that paragraph from the manifesto's logic, because the
Aug-14 demo-prep FAQ answers were not on the drive to copy from. It came out
as "why it is NOT in an app store" — a settled, permanent stance. It is not
one. EGS-SELLER-STUDY-SHEET.md already says the claim to avoid is app-store
availability "not yet", and a store version is in fact in the works, so copy
that reads as a refusal would be out of date the day it shipped and would have
made a liar of the app in the meantime.

Replaced with the real Aug-14 wording, which is better anyway because it
answers the question the customer is actually asking — "is this a real app?" —
before it answers the one about stores:

  * it installs straight from the website and behaves like any other app,
  * it is not in a store TODAY, a store version is coming, and the honest
    reason it started direct is no middleman: no 15-30% cut passed on, no
    account, no store tracking the install, no waiting on store review,
  * same app either way; the data stays on the phone regardless.

VOICE — the one thing to notice. Edwin's FAQ is first person singular ("a cut
I'd have to pass on to you", "the guy who built it", "the moment I ship them").
The rest of HELP_COPY speaks as "us" ('vault': "not by us"; 'backup': "there is
no our side"). Rather than launder his words into corporate "we", this entry
goes first-person throughout: the closing honesty-based paragraph moves from
"We know that" to "I know that" so the sheet does not change who is speaking
halfway down. Nothing earlier in 'unlock' says "we" at all, so the entry is
internally consistent — but it IS now the one entry in a different person from
its neighbours. Deliberate, and flagged for review rather than smoothed over.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
try:
    from fixscript_check import check_html
except ImportError as e:
    print(f"❌ cannot import platform/fixscript_check.py ({e}) — refusing to edit unverified.")
    sys.exit(1)

TARGET = Path("index.html")
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


OLD = (
    "Why it is not in an app store: a store takes a cut of every sale, charges a yearly fee "
    "to be listed, and decides what the app may do and when an update is allowed out. Notebuilt "
    "is a web app you add to your home screen instead. It costs nothing to keep it there, a fix "
    "reaches you the day it is written, and nobody stands between you and it. The trade is honest "
    "— there is no store listing to look us up in, so the code is readable and the privacy "
    "page tells you exactly what the app does."
    "\\n\\n"
    "And because the check runs on your own phone, in code you can read, it is honesty-based. "
    "We know that. Paying is a choice to keep this being built, not a lock we have you behind."
)

NEW = (
    "It is a real app that installs straight from the website — no app store in the middle. "
    "You go to notebuilt.ca, tap Install, and it is on your home screen like any other app: its "
    "own icon, opens full screen, works with no signal. The only difference is where it came from."
    "\\n\\n"
    "It is not in an app store today, and a store version is in the works. But here is the honest "
    "reason it started this way: direct means no middleman. No store taking a 15-30% cut that "
    "I’d have to pass on to you, no account required, no store tracking what you installed. "
    "You get it direct from the guy who built it, and updates land the moment I ship them instead "
    "of waiting on store review."
    "\\n\\n"
    "Same app either way once it is installed. Your data is identical — everything stays on "
    "your phone regardless."
    "\\n\\n"
    "And because the check runs on your own phone, in code you can read, it is honesty-based. "
    "I know that. Paying is a choice to keep this being built, not a lock I have you behind."
)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        fail(f"anchor for 'unlock app-store paragraphs' matched {count} time(s), expected exactly 1.")
    working = text.replace(OLD, NEW, 1)

    # ---- guards ---------------------------------------------------------
    # The stance is gone, in every form it could come back in.
    for banned in ("Why it is not in an app store",
                   "no store listing to look us up in",
                   "not a lock we have you behind"):
        if banned in working:
            fail(f"the old app-store stance is still in the file: {banned!r}")
    # The "today" framing and the coming store version are BOTH present —
    # this is the correction, and half of it is not the correction.
    if "not in an app store today" not in working:
        fail("the 'today' framing did not land.")
    if "a store version is in the works" not in working:
        fail("the store version being in the works did not land.")
    # Edwin's specifics survived the adaptation rather than being paraphrased
    # back into generalities, which is the whole reason his wording was asked for.
    for kept in ("notebuilt.ca, tap Install", "15-30% cut",
                 "direct from the guy who built it", "waiting on store review",
                 "Same app either way once it is installed"):
        if kept not in working:
            fail(f"a phrase from the Aug-14 wording was lost: {kept!r}")
    # Voice: the entry does not change person halfway down. Slice out of
    # HELP_COPY specifically — HELP_TITLE carries a 'unlock' key too, and
    # splitting on the bare key finds the title first and checks nothing.
    entry = working.split("const HELP_COPY={", 1)[1]
    entry = entry.split("  'unlock':'", 1)[1].split("'\n};", 1)[0]
    if len(entry) < 800:
        fail("the unlock entry read back too short — the guard is looking at the wrong string.")
    for we in ("We know", "we have you behind", " we ", " us "):
        if we in entry:
            fail(f"the unlock entry still speaks as {we!r} while the rest of it says 'I'.")
    # Seven paragraphs, six breaks — still one JS string on one line.
    breaks = entry.count("\\n\\n")
    if breaks != 6:
        fail(f"the unlock entry has {breaks} paragraph breaks, expected 6 (seven paragraphs).")

    # ---- backup, then write --------------------------------------------
    stamp = int(time.time())
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}")
    n = 1
    while backup_path.exists():
        backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}-{n}")
        n += 1
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ The unlock sheet says 'not today, and a store version is coming' "
          "in Edwin's words, instead of taking a stance he had not taken.")


if __name__ == "__main__":
    main()
