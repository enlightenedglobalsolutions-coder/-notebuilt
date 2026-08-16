#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the theme row stops saying the opposite of what it means.

Run from the same folder as index.html:
    python3 fix_theme_copy_says_what_it_means.py

Found on the daylight sweep of Settings. With Day selected, the row read:

    Theme
    Daylight, whatever your phone is set to.        [Day] Night  Auto

The intent is "daylight REGARDLESS of the phone". What it actually reads as
is "daylight — which is whatever your phone is set to", i.e. the Auto
behaviour, described under the button that specifically does NOT do that.
The Auto line one branch above says "Following your phone", so the two
options describe themselves with almost the same words while doing opposite
things — which is the reading that makes a user tap Auto expecting Day.

Replaced with a sentence that names the phone as the thing being overridden
rather than the thing being followed. Copy only; no behaviour, no tokens.
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
from fixscript_check import check_html  # noqa: E402

TARGET = Path(__file__).with_name("index.html")
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv


def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found — run this from the repo folder.")
    working = TARGET.read_text(encoding="utf-8")
    edits = []

    def sub(old, new, what):
        nonlocal working
        n = working.count(old)
        if n != 1:
            fail(f"{what}: expected 1 occurrence of\n    {old}\n  found {n}.")
        working = working.replace(old, new)
        edits.append(what)

    sub("'Daylight, whatever your phone is set to.'",
        "'Always daylight, even when your phone is set to night.'",
        "the Day line names the phone as overridden, not followed")
    sub("'Night, whatever your phone is set to.'",
        "'Always night, even when your phone is set to day.'",
        "the Night line, the same way round")

    # The Auto branch is the one that DOES follow the phone, and it must keep
    # saying so — otherwise this fix has just moved the ambiguity.
    if "'Following your phone \\u2014 '" not in working:
        fail("the Auto line changed shape — it is the only one that should "
             "claim to follow the phone.")
    if "whatever your phone is set to." in working.split("'theme':")[0]:
        fail("a settings line still uses the ambiguous phrasing.")

    stamp = int(time.time())
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}")
    n = 1
    while backup_path.exists():
        backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}-{n}")
        n += 1
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edit(s) to {TARGET}")
    for e in edits:
        print(f"     · {e}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Day and Night say they override the phone; Auto still says it "
          "follows it.")


if __name__ == "__main__":
    main()
