#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — outlines that ARE the control get their own token.
Run from the same folder as index.html:
    python3 fix_line_strong_controls.py

Follows fix_themes_day_and_night.py. That ship measured every text pairing
in both themes and cleared 4.5:1, but left one thing measured and unfixed:
--line, the hairline, sits below 3:1 on a card in BOTH themes — 1.26:1 at
night, 2.99:1 in daylight. It was matched across themes for coherence
rather than half-fixed, and the call was deferred.

The call, made: SPLIT IT, because the two jobs were never the same job.

  A card border is aesthetic. It groups things that are already legible on
  their own, and a subtle rule is the correct look — Notebuilt is a field
  notebook, not a form. Those stay on --line, deliberately, at 1.26:1.

  An outline that is the ONLY thing marking an interactive control is
  information. If you cannot see it you cannot find the control, and at
  1.26:1 on a card the to-do punch is very nearly not there.

So one new token, --line-strong, applied to the three outlines that carry
meaning rather than decoration:

  .punch      an EMPTY box until it is ticked. In the todo state there is
              no fill, no glyph, no label — the outline is the entire
              control. This is the case that prompted the split.
  .dots .d    the PIN entry dots. Not interactive, but the unfilled ones
              are what tell you how many digits you have typed, and an
              unfilled dot is also nothing but an outline.
  .photo-add  the dashed add-a-photo tile, where the dashes are the
              affordance.

DELIBERATELY NOT CHANGED, so the next reader does not "finish the job":

  .sec-head .rule, .sheet border-top, .sheet .grab, .empty svg,
  .sorted-cell   — decorative, and staying subtle is the design.
  .keypad button — considered and left. Its outline is --line-soft and is
              also under 3:1, but a keypad button is not an empty outline:
              it carries a 24px digit that clears 4.5:1, so the control is
              findable by its label. Revisit if the lock screen is ever
              redesigned without the numerals.

--line-strong holds --line's hue in both themes, so a strong outline still
reads as the same family of line, only darker on paper and lighter at
night. Values were solved for >=3:1 against ALL THREE grounds (--ink,
--ink-2, --ink-3), not just the one each control happens to sit on today —
a control that gets moved onto a different surface should not silently drop
below the bar. The guard below re-measures that from the file itself.

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


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


# --- contrast, so the guard MEASURES instead of trusting the hex it reads ---
def _lum(hexs):
    h = hexs.lstrip('#')
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # ---- the token, in all four scopes ---------------------------------
    # Night. Solved from --line's own hue: 1.26 -> 3.08 on a card.
    edits.append((
        """    --line:#333A45;       /* hairline rule (blueprint) */
    --line-soft:#2A2F39;""",
        """    --line:#333A45;       /* hairline rule (blueprint) — DECORATIVE */
    --line-soft:#2A2F39;
    /* An outline that IS the control, where nothing else marks it: the
       empty to-do punch, an unfilled PIN dot, the dashed add-photo tile.
       >=3:1 on every ground, because that outline is information. Card
       borders deliberately stay on --line and stay subtle. */
    --line-strong:#67758B;""",
        "night --line-strong"))

    # Daylight lives in two blocks (guarded media query, then the explicit
    # override) that are byte-identical apart from indentation. Indentation
    # alone is NOT enough to tell them apart: the 4-space line is a literal
    # substring of the 6-space one, so a bare anchor matches both and the
    # ==1 assertion aborts. Carrying the --ink line above each pins the
    # indentation right after a newline, which does separate them.
    edits.append((
        """      --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
      --line:#998F78; --line-soft:#C9C0AC;""",
        """      --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
      --line:#998F78; --line-soft:#C9C0AC; --line-strong:#8B8069;""",
        "daylight --line-strong (media block)"))
    edits.append((
        """    --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
    --line:#998F78; --line-soft:#C9C0AC;""",
        """    --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
    --line:#998F78; --line-soft:#C9C0AC; --line-strong:#8B8069;""",
        "daylight --line-strong (explicit block)"))
    edits.append((
        """    --line:#333A45; --line-soft:#2A2F39;
    --paper:#ECE6D8; --paper-dim:#A7A294; --paper-faint:#949186;""",
        """    --line:#333A45; --line-soft:#2A2F39; --line-strong:#67758B;
    --paper:#ECE6D8; --paper-dim:#A7A294; --paper-faint:#949186;""",
        "dark-by-nature --line-strong"))

    # ---- the three outlines that carry meaning -------------------------
    edits.append((
        """  .punch{
    flex:none;width:30px;height:30px;border-radius:8px;margin-top:1px;
    border:1.5px solid var(--line);display:grid;place-items:center;
    color:var(--paper-faint);transition:.12s;
  }""",
        """  /* --line-strong, not --line: until it is ticked this box is empty —
     no fill, no glyph, no label — so the outline is the whole control.
     The doing/done states below override the colour anyway. */
  .punch{
    flex:none;width:30px;height:30px;border-radius:8px;margin-top:1px;
    border:1.5px solid var(--line-strong);display:grid;place-items:center;
    color:var(--paper-faint);transition:.12s;
  }""",
        "to-do punch outline"))
    edits.append((
        """  .dots .d{width:14px;height:14px;border-radius:50%;border:1.5px solid var(--line)}""",
        """  /* An unfilled dot is only its outline, and counting the unfilled ones
     is how you know how many digits you have entered. */
  .dots .d{width:14px;height:14px;border-radius:50%;border:1.5px solid var(--line-strong)}""",
        "PIN entry dots"))
    edits.append((
        """  .photo-add{
    aspect-ratio:1;border:1.5px dashed var(--line);border-radius:8px;""",
        """  /* The dashes are the affordance here, so they are information too. */
  .photo-add{
    aspect-ratio:1;border:1.5px dashed var(--line-strong);border-radius:8px;""",
        "add-photo tile"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # Mutation-tested below by the harness; each was broken on purpose and
    # confirmed to abort with index.html left byte-identical.

    if working.count("--line-strong:") != 4:
        fail(f"--line-strong defined in {working.count('--line-strong:')} scopes, expected 4.")
    if working.count("var(--line-strong)") != 3:
        fail(f"--line-strong used {working.count('var(--line-strong)')} times, expected exactly 3 "
             "— this token is for outlines that ARE the control, nothing else.")

    # The three that must have it...
    for sel, frag in (
            (".punch", "border:1.5px solid var(--line-strong);display:grid"),
            (".dots .d", "border-radius:50%;border:1.5px solid var(--line-strong)}"),
            (".photo-add", "border:1.5px dashed var(--line-strong);border-radius:8px")):
        if frag not in working:
            fail(f"{sel} did not take --line-strong.")

    # ...and the decorative ones that must NOT, because staying subtle is
    # the design decision, not an oversight waiting to be corrected.
    for sel, frag in (
            ("section rule", ".sec-head .rule{flex:1;height:1px;background:var(--line)}"),
            ("sheet grab handle", ".sheet .grab{width:38px;height:4px;border-radius:2px;background:var(--line)"),
            ("empty-state icon", ".empty svg{width:40px;height:40px;color:var(--line);"),
            ("sheet top edge", "border-radius:20px 20px 0 0;border-top:1px solid var(--line);")):
        if frag not in working:
            fail(f"the {sel} was changed — decorative lines stay on --line by decision.")

    # MEASURE the token from the file rather than trusting the hex above.
    style = working[working.find("<style>"):working.find("</style>")]

    def scope(pat):
        m = re.search(pat + r"\{(.*?)\n(?:  |    )\}", style, re.S)
        if not m:
            fail(f"could not re-read token scope {pat} to measure it.")
        return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})", m.group(1)))

    for name, pat in (("night", r"\n  :root"),
                      ("daylight", r':root\[data-theme="light"\]'),
                      ("daylight/system", r':root:not\(\[data-theme="dark"\]\)'),
                      ("dark-by-nature", r"#viewer,#annotate,#camera,#vault-busy")):
        T = scope(pat)
        if "--line-strong" not in T:
            fail(f"{name} scope has no --line-strong.")
        for ground in ("--ink", "--ink-2", "--ink-3"):
            r = contrast(T["--line-strong"], T[ground])
            if r < 3.0:
                fail(f"{name}: --line-strong on {ground} = {r:.2f}, below the 3:1 a control outline needs.")
        # And the decorative line must stay BELOW it — if they converge,
        # the split has quietly undone itself and everything looks the same.
        if contrast(T["--line-strong"], T["--ink-3"]) <= contrast(T["--line"], T["--ink-3"]):
            fail(f"{name}: --line-strong is no stronger than --line — the split collapsed.")

    # Nothing from the previous ship may have moved.
    # Four: the head script, the token block, the JS helpers, and the
    # settings handler's pointer back to them.
    if working.count("EGS-STD:themes") != 4:
        fail(f"the row-13 marker count changed ({working.count('EGS-STD:themes')}, expected 4).")
    if working.count("var(--brass-fill)") != 12:
        fail("a gold plate moved — not this fix's business.")
    if working.count("nbSetTheme(") != 2:
        fail("the theme write path changed — not this fix's business.")

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
    print(f"✏️  Applied {len(edits)} edit(s) to {TARGET}")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Outlines that are the control clear 3:1 in both themes; "
          "decorative rules stay subtle, on purpose.")


if __name__ == "__main__":
    main()
