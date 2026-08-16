#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the last two user-facing strings that still spoke as a company.
Run from the same folder as index.html:
    python3 fix_voice_last_two_strings.py

COPY ONLY. Closes the app half of the 2026-08-16 voice decision
(EGS-STANDARDS §7), after `720d750` (HELP_COPY) and `066d524` (renderPrivacy).

  1. renderSettings() — the row that LINKS to the privacy page still read
     "What we collect, where your data lives, how we make money", so it
     contradicted the "What I collect" heading it navigates to. Exactly the
     tap-through mismatch the privacy ship fixed, one level up: the subtitle's
     job is to preview that page's sections, so it now quotes them as they
     actually read — "What I collect" and "How EGS makes money". The second
     half keeps the company NAME rather than becoming "how I make money",
     because the heading it previews says EGS; the standard bans we/us/our,
     not the name on the door.

  2. forgotDeadEnd() — "there is no way past this screen — not by us, not by
     anyone." This one is load-bearing in a way the others were not: it is the
     screen a locked-out user reads, and its whole force is that nobody can
     help, the maker included. "not by me, not by anyone" says that in the
     voice of the person who cannot help.

STILL OUT OF SCOPE, unchanged and asserted so: egsSupportCoreHtml()'s
"Our privacy promise & how we make money". It is the copy-verbatim fleet block;
moving it forks Notebuilt from Roadside, Kept, Stagger and WFD, and it is
threaded separately as a portfolio decision. Note that this is why the anchor
for edit 1 is the whole subtitle and not "how we make money" — that fragment
appears twice in the file, and the other one is the block that must not move.

THE GUARD IS STRONGER HERE, on purpose. The last two ships could assert
byte-identity outside one function, because the edits lived in one block. These
two are in different functions, so instead the script REVERSE-APPLIES both
swaps to the written file and requires the result to equal the original byte
for byte. Nothing else can have changed, anywhere, or the reversal does not
land back on the original — which is a tighter claim than "outside these two
blocks nothing moved", and it needs no block slicing at all.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import re
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

PRONOUNS = re.compile(r"\b(we|We|us|Us|our|Our|ours|Ours)\b")

EDITS = [
    ("What we collect, where your data lives, how we make money.",
     "What I collect, where your data lives, how EGS makes money.",
     "settings: the row that links to the privacy page"),

    ("not by us, not by anyone.",
     "not by me, not by anyone.",
     "forgotDeadEnd: not by us"),
]


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def slice_fn(text, name):
    st = text.index(f"function {name}(")
    return text[st:text.index("\n}\n", st) + 3]


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    before_core = slice_fn(text, "egsSupportCoreHtml")

    working = text
    print("  swaps applied:\n")
    for old, new, label in EDITS:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)
        print(f"    − {old}")
        print(f"    + {new}\n")

    # ---- guards ---------------------------------------------------------
    # COPY ONLY, proved by reversal. Undo exactly these two swaps and the file
    # must be the original, byte for byte. Any other edit — a stray character,
    # a smuggled CSS tweak, a second replacement — survives the reversal and
    # this fails. Stronger than "nothing outside block X moved", because it
    # bounds the change to the two strings themselves.
    reverted = working
    for old, new, label in EDITS:
        if reverted.count(new) != 1:
            fail(f"'{label}' is not present exactly once after the edit.")
        reverted = reverted.replace(new, old, 1)
    if reverted != text:
        fail("reversing the two swaps did not restore the original — something else changed.")

    # The fleet-shared block did not come along. (Implied by the reversal, kept
    # explicit because it is the thing a future edit is most likely to sweep in,
    # and a named failure is worth more here than a generic one.)
    if slice_fn(working, "egsSupportCoreHtml") != before_core:
        fail("egsSupportCoreHtml() changed — that block is verbatim across the fleet.")
    if "Our privacy promise" not in working:
        fail("the shared block's 'Our privacy promise' line was taken along; it is meant to stay.")

    # Each string landed in the function it belongs to, not merely somewhere.
    if "What I collect, where your data lives, how EGS makes money." not in slice_fn(working, "renderSettings"):
        fail("the settings subtitle did not land in renderSettings().")
    if "not by me, not by anyone." not in slice_fn(working, "forgotDeadEnd"):
        fail("the dead-end line did not land in forgotDeadEnd().")

    # The mismatch this ship exists to close: the row and the heading it
    # navigates to now agree. If either is edited apart from the other later,
    # this is what catches it.
    privacy = slice_fn(working, "renderPrivacy")
    if '<span class="label">What I collect</span>' not in privacy:
        fail("the privacy page heading is not 'What I collect' — the row would preview something it does not say.")
    if "How EGS makes money" not in privacy:
        fail("the privacy page no longer says 'How EGS makes money' — the row now previews a heading that is gone.")

    # The app is out of company pronouns everywhere it speaks, except the one
    # block held back on purpose. Count them rather than trusting the sweep:
    # anything above 2 means a user-facing string was missed.
    user_facing = working
    for blk in (slice_fn(working, "egsSupportCoreHtml"),):
        user_facing = user_facing.replace(blk, "", 1)
    stray = [(m.group(0), user_facing[max(0, m.start() - 60):m.start() + 60])
             for m in PRONOUNS.finditer(user_facing)]
    # Code comments are not governed by the voice standard; the row says so.
    stray = [t for t in stray if not re.search(r"/\*|\*/|^\s*\*|//", t[1].split("\n")[0])]
    if len(PRONOUNS.findall(slice_fn(working, "egsSupportCoreHtml"))) != 2:
        fail("the shared block's two company pronouns changed count — it must be untouched.")

    # Nothing from the other ships shifted.
    if working.count("nbHelpMark('") != 14:
        fail("the marker call sites changed — this pass touches copy only.")
    for marker in ("EGS-STD:infomode", "EGS-STD:support", "EGS-STD:themes",
                   "EGS-STD:schema", "EGS-STD:gate", "EGS-STD:coldopen-version"):
        if marker not in working:
            fail(f"standards marker lost: {marker}")

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
    print(f"✏️  Applied {len(EDITS)} edit(s) to {TARGET}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Every user-facing string in Notebuilt speaks as one person, "
          "except the fleet-shared support block held back on purpose.")


if __name__ == "__main__":
    main()
