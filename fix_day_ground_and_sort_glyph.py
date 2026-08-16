#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the daylight ground becomes the EGS standard, and the sort
button stops wearing a retired logo.

Run from the same folder as index.html:
    python3 fix_day_ground_and_sort_glyph.py

Four things land here.

1. THE GROUND. Session 1 picked #E9E4D7 for daylight by eye. The decision
   since taken is that the fleet shares one paper, and the paper is PaidUp's
   --bg: #F6F3EC. Read out of apps/paidup/index.html, not assumed — and it
   is NOT what session 1 guessed, so every measured number moved.

   Re-measured (audit_contrast.py, 75 gated pairings): the lighter paper
   raises every daylight pairing rather than lowering any. Worst text
   pairing 4.59:1 -> 5.25:1; --line-strong on the ground 3.07:1 -> 3.52:1.
   Nothing needed re-lifting, so no palette value is touched to chase the
   change — the ground moved and the margins improved.

2. THE ELEVATION LADDER, which the ground move FORCES. Notebuilt's rule is
   that raised surfaces sit further from the ground in the same direction in
   both themes: at night --ink #15181D -> --ink-2 #1C2027 -> --ink-3 #252A33
   climbs toward light. Session 1's daylight ladder climbed the same way,
   from #E9E4D7. On the new ground it cannot be kept: #F2EEE3 is DARKER than
   #F6F3EC, so a card would have sunk below the page and every raised
   surface in daylight would have read as a dent. The ladder is rebuilt to
   climb from the new paper to white.

   White for the card is the metaphor, not a fallback: a spec sheet on a
   job-site table. The table is warm; the page on it is white. Separation is
   carried by the --line-soft border, exactly as at night, where the card
   fill is barely a step off the ground too.

3. --brass-deep GOES. Defined in four scopes, referenced nowhere — it was
   drawn up for a hover state daylight never needed. A token nothing reads
   is a token that drifts out of the palette unnoticed.

4. THE SORT GLYPH. The button right of the Projects title still drew the
   RETIRED L-stroke mark — an axis with three bars, which on a 24px button
   reads as a meaningless "E". The lock-screen redraw replaced that mark in
   four places and missed this one, because here it was not being used as a
   logo at all: it was sitting in the icon set under the name `square`,
   where nothing about the name said "this is the old logo".

   So the name goes with the drawing. It becomes `sort`, holding the
   conventional sort glyph — three bars of decreasing length, in the same
   Feather line language as the rest of the set (1.7 stroke, round caps).
   The retired geometry is then grepped for across the whole file and the
   count must be zero.
"""
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
from fixscript_check import check_html  # noqa: E402

TARGET = Path(__file__).with_name("index.html")
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv

# The EGS daylight ground. Source of truth: apps/paidup/index.html --bg.
DAY_GROUND = "#F6F3EC"
DAY_RAISED = "#FBF9F3"
DAY_CARD = "#FFFFFF"
DAY_NAV = "rgba(251,249,243,.92)"

# The retired mark, by geometry rather than by name — the name is exactly
# what let it survive the last sweep.
RETIRED_MARK_PATHS = ["M5 4v15h15", "M5 4h6M5 9h4M5 14h4"]


def fail(msg):
    print(f"\n❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found — run this from the repo folder.")
    original = TARGET.read_text(encoding="utf-8")
    working = original
    edits = []

    def sub(old, new, what, count=1):
        nonlocal working
        n = working.count(old)
        if n != count:
            fail(f"{what}: expected {count} occurrence(s) of\n    {old[:110]}\n"
                 f"  found {n}. The file is not the shape this fix was written for.")
        working = working.replace(old, new)
        edits.append(what)

    # ---- 1 + 2: the ground, and the ladder it forces --------------------
    # Both daylight blocks are edited with the same replacement so they stay
    # character-identical; audit_contrast.py asserts that they do.
    sub("--ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;",
        f"--ink:{DAY_GROUND}; --ink-2:{DAY_RAISED}; --ink-3:{DAY_CARD};",
        "daylight ground + elevation ladder", count=2)

    sub("--nav-bg:rgba(243,239,229,.92);",
        f"--nav-bg:{DAY_NAV};",
        "daylight nav bar follows the new raised surface", count=2)

    # The status bar cannot come from CSS, so it is stated twice on purpose:
    # once in <head> for the first frame, once as the updater's fallback.
    # Both must move, or the notch keeps painting the old paper.
    sub("window.NB_THEME_BAR={dark:'#15181D',light:'#E9E4D7'};",
        f"window.NB_THEME_BAR={{dark:'#15181D',light:'{DAY_GROUND}'}};",
        "status-bar colour, first frame")
    sub("const bar=window.NB_THEME_BAR||{dark:'#15181D',light:'#E9E4D7'};",
        f"const bar=window.NB_THEME_BAR||{{dark:'#15181D',light:'{DAY_GROUND}'}};",
        "status-bar colour, updater fallback")

    # ---- 3: the token nothing reads -------------------------------------
    sub("    --brass-deep:#9A6E27;\n", "", "drop --brass-deep (night)")
    sub("      --brass-deep:#6B4A0C;\n", "", "drop --brass-deep (daylight, media)")
    sub("    --brass-deep:#6B4A0C;\n", "", "drop --brass-deep (daylight, explicit)")

    # ---- 4: the sort glyph ----------------------------------------------
    sub("""  square:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4v15h15"/><path d="M5 4h6M5 9h4M5 14h4"/></svg>',""",
        """  /* Three bars, longest first — the conventional sort mark. This slot
     used to hold the RETIRED app logo under the name `square`, which is
     how it survived the lock-screen redraw: nothing about the name said
     it was a logo. Named for what it draws now. */
  sort:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 6.5h16M4 12h10.5M4 17.5h5"/></svg>',""",
        "sort glyph replaces the retired mark")

    sub("${I.square}</button>", "${I.sort}</button>",
        "the Projects sort button draws the sort glyph")

    # ---- guards ----------------------------------------------------------
    # The rider's gate: zero surviving occurrences of the retired geometry,
    # searched by path data across the whole file, not by icon name.
    for p in RETIRED_MARK_PATHS:
        if p in working:
            fail(f"the retired mark survives somewhere else: {p!r}")
    if "I.square" in working or "  square:" in working:
        fail("something still reaches for I.square.")
    if working.count("I.sort") != 1 or working.count("  sort:'") != 1:
        fail("the sort glyph is not defined once and used once.")

    # The ground is the standard now — it must appear in exactly the places
    # that state it, and the old paper must be gone from all of them.
    if "#E9E4D7" in working:
        fail("the old daylight ground survives somewhere.")
    if working.count(DAY_GROUND) != 4:
        fail(f"{working.count(DAY_GROUND)} references to the ground, expected 4 "
             "(two token blocks, two status-bar statements).")
    if "--brass-deep" in working:
        fail("--brass-deep survives.")

    # Session 1's invariants, re-asserted: this fix must not have disturbed
    # any of them. The ordering one is the trap — equal specificity means
    # source order is the ONLY thing making an explicit Day choice win.
    media_light = working.find("@media (prefers-color-scheme: light)")
    explicit_light = working.find(':root[data-theme="light"]{')
    if media_light < 0 or explicit_light < 0:
        fail("a theme block is missing — light would not render.")
    if explicit_light < media_light:
        fail("[data-theme=\"light\"] precedes the media block; Day would lose "
             "to a night phone.")
    if ':root:not([data-theme="dark"])' not in working:
        fail("the media block is unguarded.")
    if "#viewer,#annotate,#camera,#vault-busy{" not in working:
        fail("the dark-by-nature scope is gone.")

    # Every gold plate still carries its own ink.
    style_txt = working[working.find("<style>"):working.find("</style>")]
    plates = 0
    for m in re.finditer(r"\{([^{}]*)\}", style_txt):
        body = m.group(1)
        if "var(--brass-fill)" in body:
            plates += 1
            if "var(--on-brass)" not in body:
                fail(f"a gold plate carries no --on-brass ink: {body.strip()[:70]}")
    if plates != 8:
        fail(f"{plates} gold plates found, expected 8.")

    # The startup-write law.
    if working.count("nbSetTheme(") != 2:
        fail("nbSetTheme is reached from somewhere new — startup must never "
             "write the theme.")
    if working.count("localStorage.setItem(NB_THEME_KEY") != 1:
        fail("more than one writer for the theme key.")

    # Markers this fix has no business touching.
    for marker, n in (("EGS-STD:coldopen-version", 3), ("EGS-STD:schema", 1),
                      ("EGS-STD:gate", 1), ("EGS-STD:themes", 4)):
        if working.count(marker) != n:
            fail(f"{marker} count changed ({working.count(marker)}, expected {n}).")
    if working.count("window.EGS_VERSION") != 3:
        fail("the version stamp moved.")

    # ---- backup, then write ---------------------------------------------
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

    # ---- syntax check: EVERY inline block, or restore --------------------
    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print(f"\n✅ Daylight stands on the EGS ground ({DAY_GROUND}), the ladder "
          "climbs to white, and the sort button draws a sort glyph.")
    print("   Next: python3 audit_contrast.py")


if __name__ == "__main__":
    main()
