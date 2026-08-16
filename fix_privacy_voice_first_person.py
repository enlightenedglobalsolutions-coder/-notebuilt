#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the privacy page speaks as one person too.
Run from the same folder as index.html:
    python3 fix_privacy_voice_first_person.py

COPY ONLY, and the last piece of the 2026-08-16 voice decision (EGS-STANDARDS
§7, "App voice: first person singular"). `720d750` put all sixteen HELP_COPY
entries in first person; this does renderPrivacy(), which was the sharp half of
what that ship left open — the `unlock` help sheet links directly into this
page, so a reader tapping through went from "a cut I'd have to pass on to you"
straight into "we don't know who you are", in one tap, on the page whose whole
job is being believed.

Ten occurrences, six edits (two sentences carry two each). Minimal rewording:
every claim keeps its exact meaning, and nothing but the person changes.

NOT TOUCHED, on purpose: egsSupportCoreHtml() still says "Our privacy promise
& how we make money". That block is marked "copy this block verbatim into every
new EGS app, do not edit the copy below", so changing it here would fork
Notebuilt from Roadside, Kept, Stagger and WFD. It is threaded separately as a
portfolio decision; Notebuilt lives with the one "Our" it did not write until
the fleet moves. A guard below asserts that block is byte-identical, so this
script cannot quietly take it along.

The one worth reading twice is edit 5. "not something on our servers" becomes
"not something on my servers", and the swap is safe here — unlike the backup
sheet's "there is no our side", which could not take a pronoun and needed a
rewrite (see §7). Checked, not assumed: EGS has no servers either way, so the
sentence negates the same thing in both persons and the claim is unchanged.

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
    ('<span class="label">What we collect</span>',
     '<span class="label">What I collect</span>',
     "heading: What we collect"),

    ("We don't know who you are, and we don't track what you do in this app.",
     "I don't know who you are, and I don't track what you do in this app.",
     "what I collect: We don't know / we don't track"),

    ("like any store, we can see who bought in their dashboard",
     "like any store, I can see who bought in their dashboard",
     "polar checkout: we can see"),

    ("We never receive a copy.",
     "I never receive a copy.",
     "where your data lives: We never receive"),

    ("We're not part of that transfer.",
     "I'm not part of that transfer.",
     "share project: We're not part"),

    ("not something on our servers. Restore it whenever you like. Delete anything, any time; nothing needs our permission.",
     "not something on my servers. Restore it whenever you like. Delete anything, any time; nothing needs my permission.",
     "your data your control: our servers / our permission"),

    ("We can't sell your data because we never have it in the first place.",
     "I can't sell your data because I never have it in the first place.",
     "how EGS makes money: We can't sell / we never have"),
]


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def slice_fn(text, name, end="\n}\n"):
    """The whole body of a top-level function, by name.

    Matched on `function <name>(` rather than `function <name>(){` — the
    shared support block takes a `tabs` argument, and assuming the empty
    signature made this abort before it read a single anchor.
    """
    st = text.index(f"function {name}(")
    return text[st:text.index(end, st) + len(end)]


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    before_privacy = slice_fn(text, "renderPrivacy")
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
    after_privacy = slice_fn(working, "renderPrivacy")
    after_core = slice_fn(working, "egsSupportCoreHtml")

    # COPY ONLY, and confined to this one view. Cut renderPrivacy out of both
    # files and the remainder must be byte-identical — that is what makes the
    # docstring's first line checkable instead of a promise.
    if text.replace(before_privacy, "", 1) != working.replace(after_privacy, "", 1):
        fail("something outside renderPrivacy() changed — this pass is copy only.")

    # The fleet-shared block is explicitly out of scope, so prove it did not move.
    if before_core != after_core:
        fail("egsSupportCoreHtml() changed — that block is verbatim across the fleet and is threaded separately.")
    if "Our privacy promise" not in after_core:
        fail("the shared block's 'Our privacy promise' line was taken along; it is meant to stay.")

    # The pass is complete, not merely applied.
    left = sorted(set(PRONOUNS.findall(after_privacy)))
    if left:
        fail(f"renderPrivacy() still speaks as a company: {left}")
    if not PRONOUNS.search(before_privacy):
        fail("renderPrivacy() had no company pronouns to begin with — this script is stale.")

    # First person is present, so the page did not simply lose its person.
    for token in ("What I collect", "I don't know who you are", "I never receive a copy.",
                  "I'm not part of that transfer.", "on my servers", "nothing needs my permission",
                  "I can't sell your data"):
        if token not in after_privacy:
            fail(f"expected first-person phrasing missing: {token!r}")

    # Every claim the page makes must survive the rewording untouched. These are
    # the load-bearing promises; a voice pass that softened one would be a lie
    # shipped on the page that exists to be believed.
    for claim in ("No account, no sign-up, no email",
                  "There's no server for it to go to.",
                  "That's the whole list. No analytics, no background calls, no hidden pings.",
                  "One-time purchase, no subscription. No ads, ever.",
                  "the unlock is never re-checked, at launch or ever."
                  if "the unlock is never re-checked, at launch or ever." in before_privacy
                  else "once it succeeds the unlock is never re-checked"):
        if claim not in after_privacy:
            fail(f"a privacy claim did not survive the rewording: {claim!r}")

    # Structure untouched: same number of sections, same links out.
    if before_privacy.count('class="sec-head"') != after_privacy.count('class="sec-head"'):
        fail("a privacy section was added or lost.")
    if after_privacy.count('data-go="support"') != 1:
        fail("the link to Support & Backup moved.")

    # Nothing from the other ships shifted.
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
    print(f"✏️  Applied {len(EDITS)} edit(s), {len(PRONOUNS.findall(before_privacy))} occurrence(s), to {TARGET}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ The privacy page speaks as one person. The fleet-shared support block is untouched.")


if __name__ == "__main__":
    main()
