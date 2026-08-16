#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the help copy speaks as one person, not a company.
Run from the same folder as index.html:
    python3 fix_infomode_voice_first_person.py

COPY ONLY. No logic, no markers, no CSS — asserted below by rebuilding the
file with the HELP_COPY block removed and requiring it to be byte-identical
before and after.

WHY. The info-mode ship (v2026.08.16-0919) wrote sixteen HELP_COPY entries in
"we/us/our", because that is how the rest of the app talks. The next ship then
replaced the app-store answer with Edwin's own Aug-14 FAQ wording, which is
first person singular — "a cut I'd have to pass on to you", "the guy who built
it", "the moment I ship them". That left one entry saying I and four saying we,
which is worse than either alone: the unlock sheet reads as a person and the
vault sheet beside it reads as a company, in an app whose whole pitch is that
it is one guy and not a company. Decision (Edwin, 2026-08-16): I/me/my
everywhere. This closes the four.

Four are plain pronoun swaps. The fifth is not, and that is the one worth
reading twice: "There is no copy on our side, because there is no our side"
lands because "our side" is a noun phrase you can negate. "my side" is not —
"there is no my side" is not English. Swapping the pronoun would have quietly
broken the best line in the backup sheet, which is exactly the kind of damage a
find-and-replace does and a guard does not catch. Rewritten to keep the shape:
"There is no copy on my end, because there is no other end."

STILL OPEN, deliberately out of scope. 24 occurrences of we/us/our remain
outside HELP_COPY — ten of them in renderPrivacy(), which the unlock help sheet
links straight into, so a reader who taps through still crosses from I to we.
Two more are in egsSupportCoreHtml(), the block marked "copy verbatim into
every new EGS app, do not edit the copy", so changing them here would fork
Notebuilt from Roadside, Kept, Stagger and WFD — a fleet decision, not this
app's. Neither is touched here; both are recorded in §7.

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

# The company pronouns, as whole words. Used to prove the pass is complete
# rather than merely applied — five swaps that leave a sixth behind would look
# exactly like success.
PRONOUNS = re.compile(r"\b(we|We|us|Us|our|Our|ours|Ours)\b")

EDITS = [
    # 1 — share / entry 08
    ("We are not in the middle of that transfer, and it cannot be taken back.",
     "I am not in the middle of that transfer, and it cannot be taken back.",
     "share: We are not -> I am not"),
    # 2 — applock / entry 10
    ("off the device — us included.",
     "off the device — me included.",
     "applock: us included -> me included"),
    # 3 — vault / entry 11
    ("not by Notebuilt, not by us.",
     "not by Notebuilt, not by me.",
     "vault: not by us -> not by me"),
    # 4 — vault / entry 11
    ("and we would rather say it plainly than sell you something softer.",
     "and I would rather say it plainly than sell you something softer.",
     "vault: we would -> I would"),
    # 5 — backup / entry 16. NOT a pronoun swap; see the header.
    ("There is no copy on our side, because there is no our side.",
     "There is no copy on my end, because there is no other end.",
     "backup: no our side -> no other end"),
]


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def help_copy_block(text):
    """The HELP_COPY object literal, and the file with it cut out."""
    start = text.index("const HELP_COPY={")
    end = text.index("\n};", start)
    return text[start:end], text[:start] + text[end:]


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    working = text
    for old, new, label in EDITS:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    before_block, before_rest = help_copy_block(text)
    after_block, after_rest = help_copy_block(working)

    # COPY ONLY. Everything that is not HELP_COPY must be byte-identical.
    # This is the guard that makes the docstring's first line checkable rather
    # than a promise: logic, markers, CSS and every other string are outside
    # this block, so if any of them moved, this fails.
    if before_rest != after_rest:
        fail("something outside HELP_COPY changed — this pass is copy only.")

    # The pass is complete, not merely applied.
    left = sorted(set(PRONOUNS.findall(after_block)))
    if left:
        fail(f"HELP_COPY still speaks as a company: {left}")
    # ...and it was not complete before, or there was nothing to do.
    if not PRONOUNS.search(before_block):
        fail("HELP_COPY had no company pronouns to begin with — nothing to fix, so this script is stale.")

    # Each replacement actually landed, in the entry it belongs to.
    for _, new, label in EDITS:
        if new not in after_block:
            fail(f"'{label}' did not land inside HELP_COPY.")

    # #5 is the one a careless swap would have broken. Assert the ungrammatical
    # form it would have produced is nowhere in the file.
    if "there is no my side" in working or "no copy on my side" in working:
        fail("the backup line was pronoun-swapped instead of rewritten — 'there is no my side' is not English.")

    # First person is present, so the entries did not simply lose the person.
    for token in ("not by me.", "me included.", "I am not in the middle",
                  "I would rather say it plainly", "no other end."):
        if token not in after_block:
            fail(f"expected first-person phrasing missing: {token!r}")

    # The shipped structure is untouched: same entries, same titles, and the
    # info-mode machinery exactly as it was.
    keys = set(re.findall(r"^  '([a-z-]+)':", after_block, re.M))
    titles = set(re.findall(r"^  '([a-z-]+)':",
                 working.split("const HELP_TITLE={", 1)[1].split("\n};", 1)[0], re.M))
    if len(keys) != 16 or keys != titles:
        fail(f"HELP_COPY/HELP_TITLE drifted: {len(keys)} entries, symmetric={keys == titles}")
    if working.count(':root[data-guide="off"] .help-i{display:none}') != 1:
        fail("the one rule that hides every marker moved.")
    # 14 call sites. The definition reads `function nbHelpMark(key){` and
    # carries no quote, so it is deliberately not in this count.
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

    print("\n✅ All 16 help entries speak as one person. Nothing outside HELP_COPY moved.")


if __name__ == "__main__":
    main()
