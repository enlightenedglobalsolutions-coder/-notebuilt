#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — calculator placeholders stop reading as entered values
Run from the same folder as index.html:
    python3 fix_calc_placeholder.py

Thread th_nb_calc_placeholder. Every empty measurement box drew "0" (ft, in,
frac, m, cm) and Multiply/Divide's number box drew "3", in --paper-faint —
the tertiary TEXT colour, held at 4.5:1 by audit_contrast.py. At that
contrast a placeholder is simply faint text, so an untouched FT box read as
a typed zero and the Times box read as "times 3".

Decided 2026-09-27 (Edwin):
  * wording — ft / in / m / cm boxes are blank (the unit is printed under
    each box already); FRAC keeps a format hint, "3/8…", because 3/8 vs .375
    is a real question; the number box says "how many".
  * dimming — placeholders get their own token, --placeholder, gated by
    audit_contrast.py at >=3:1 on every ground AND <4.5:1 on the input
    ground (--ink-2), so it can never drift back up to text brightness.
    night #7C7A74 (3.81:1 on the input, typed value 11.6:1)
    day   #87847C (3.55:1 on the input, typed value 14.4:1)
  * opacity:1 on ::placeholder — Firefox fades placeholders by default,
    which would put the real colour under the measured one.

CSS and placeholder strings only. A guard strips every placeholder fragment
from the file before and after and requires the remainders byte-identical,
so nothing CALC_STEADY depends on (the input nodes, their handlers,
calcRecompute) can have moved. Mutation-tested: smuggling
`calcRecompute()` -> `render()` into the Times handler aborts before write.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import difflib
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
MARK = "--placeholder:#7C7A74"


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    if MARK in text:
        print("✅ already applied — nothing to do.")
        return
    edits = []

    # ---- tokens: night :root, both day blocks (kept character-identical), pinned
    edits.append((
        "    --paper-faint:#949186;/* tertiary — was #6E6B61, 2.70:1 on a card */\n",
        "    --paper-faint:#949186;/* tertiary — was #6E6B61, 2.70:1 on a card */\n"
        "    --placeholder:#7C7A74;/* hint in an EMPTY box: >=3:1, <4.5:1 — dimmer than any text, see audit_contrast.py */\n",
        "night placeholder token"))
    edits.append((
        "\n      --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C;\n",
        "\n      --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C; --placeholder:#87847C;\n",
        "day placeholder token (media block)"))
    edits.append((
        "\n    --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C;\n",
        "\n    --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C; --placeholder:#87847C;\n",
        "day placeholder token ([data-theme] block)"))
    edits.append((
        "\n    --paper:#ECE6D8; --paper-dim:#A7A294; --paper-faint:#949186;\n",
        "\n    --paper:#ECE6D8; --paper-dim:#A7A294; --paper-faint:#949186; --placeholder:#7C7A74;\n",
        "pinned placeholder token"))

    # ---- the rule
    edits.append((
        "  ::placeholder{color:var(--paper-faint)}\n",
        "  ::placeholder{color:var(--placeholder);opacity:1}   /* th_nb_calc_placeholder: its own token, so a hint never reads as a typed value */\n",
        "::placeholder rule"))

    # ---- the strings
    edits.append(("data-meas-m value=\"'+v.m+'\" placeholder=\"0\">",
                  "data-meas-m value=\"'+v.m+'\" placeholder=\"\">", "m box"))
    edits.append(("data-meas-cm value=\"'+v.cm+'\" placeholder=\"0\">",
                  "data-meas-cm value=\"'+v.cm+'\" placeholder=\"\">", "cm box"))
    edits.append(("data-meas-ft value=\"'+w.ft+'\" placeholder=\"0\">",
                  "data-meas-ft value=\"'+w.ft+'\" placeholder=\"\">", "ft box"))
    edits.append(("data-meas-in value=\"'+w.in+'\" placeholder=\"0\">",
                  "data-meas-in value=\"'+w.in+'\" placeholder=\"\">", "in box"))
    edits.append(("data-meas-frac value=\"'+w.frac+'\" placeholder=\"0\">",
                  "data-meas-frac value=\"'+w.frac+'\" placeholder=\"3/8…\">", "frac box"))
    edits.append(("value=\"'+esc(CALC.num)+'\" placeholder=\"3\" autocomplete=\"off\">",
                  "value=\"'+esc(CALC.num)+'\" placeholder=\"how many\" autocomplete=\"off\">", "number box"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # 1. CSS + placeholder strings only. Strip every placeholder fragment from
    #    both files — the token line, inline tokens, the ::placeholder rule,
    #    every placeholder="…" value — and the remainders must be byte-identical.
    def strip_ph(s):
        s = re.sub(r"(?m)^[ \t]*--placeholder:[^\n]*\n", "", s)
        s = re.sub(r" --placeholder:#[0-9A-Fa-f]{6};", "", s)
        s = re.sub(r"(?m)^[ \t]*::placeholder\{[^}]*\}[^\n]*\n", "", s)
        return re.sub(r'placeholder="[^"]*"', 'placeholder=""', s)
    if strip_ph(text) != strip_ph(working):
        stray = [l for l in difflib.unified_diff(strip_ph(text).splitlines(), strip_ph(working).splitlines(), lineterm="", n=0)
                 if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        fail("something other than a placeholder changed:\n   " + "\n   ".join(stray[:10]))
    changed = [l for l in difflib.unified_diff(text.splitlines(), working.splitlines(), lineterm="", n=0)
               if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    # 2. no numeric placeholder left in the calculator's widgets
    if 'placeholder="0"' in working[working.index("function measWidget("):working.index("function measEcho(")]:
        fail("a measurement box still draws a 0.")
    if 'placeholder="3"' in working:
        fail('the number box still draws "3".')
    # 3. the day blocks must stay character-identical (audit_contrast.py asserts it too)
    if working.count("--paper-faint:#68655C; --placeholder:#87847C;") != 2:
        fail("the two day blocks diverged.")

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
    print(f"✏️  Applied {len(edits)} edit(s) to {TARGET} ({len(changed)} changed lines, all placeholder lines)")

    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Empty calculator boxes draw no digit; placeholders use --placeholder (3:1..<4.5:1), not text colour.")


if __name__ == "__main__":
    main()
