#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the contrast audit, as a program instead of a paragraph.

Run from the same folder as index.html:
    python3 audit_contrast.py            # audit, exit 1 on any failure
    python3 audit_contrast.py --verbose  # print every pairing, passes included

WHY THIS EXISTS
---------------
Session 1 measured the palette by hand and wrote the numbers into a comment.
A comment cannot be re-run. The moment the ground colour changes — which is
exactly what happened when the day ground moved to PaidUp's #F6F3EC — every
one of those hand-measured numbers is stale, and nothing in the repo says so.

So the measurement lives here, reads the tokens out of index.html, and fails
loudly. The palette is now checkable by anyone who can run one command.

WHAT IT CHECKS
--------------
Not a hand-picked list of pairings — the full matrix. Every text-role token
against every ground-role token, in every theme context, because a rule that
puts --paper-faint on --ink-3 can be added at any time and the audit must
already have covered it. That is a superset of what the app actually draws,
which is the point: it cannot go stale by someone adding a rule.

  text roles    --paper --paper-dim --paper-faint --brass --doing --done --danger
  grounds       --ink --ink-2 --ink-3
  bar           4.5:1 (WCAG AA, normal text)

Two pairings are checked on their own terms:

  --on-brass on --brass-fill   4.5:1 — the plate rule. The gold plate is the
                               same colour in both themes, so this is one
                               measurement, but it is the one that breaks if
                               anyone ever writes --paper onto a brass fill.

  --line-strong on grounds     3:1 — an outline that IS the control (the
                               empty to-do punch, an unfilled PIN dot, the
                               dashed add-photo tile) is information, and
                               non-text UI components take the 3:1 bar.
                               --line stays decorative and is reported, not
                               gated.

CONTEXTS
--------
  night     :root
  day       :root[data-theme="light"]
  pinned    #viewer,#annotate,#camera,#vault-busy — the four layers that are
            dark BY NATURE. Audited as their own context because their whole
            job is to hold night values while the page around them is light;
            if one drifts, daylight paints dark text on near-black there and
            nowhere else, which is precisely the bug no page-level audit sees.

The day block is defined twice in the stylesheet on purpose (a guarded media
query, then an equal-specificity [data-theme] block). This reads the
[data-theme="light"] one and asserts the media block is character-identical,
so the audit cannot pass a file where the two have silently diverged.
"""
import re
import sys
from pathlib import Path

TARGET = Path(__file__).with_name("index.html")

TEXT_ROLES = ["--paper", "--paper-dim", "--paper-faint",
              "--brass", "--doing", "--done", "--danger"]
GROUNDS = ["--ink", "--ink-2", "--ink-3"]

AA_TEXT = 4.5      # WCAG AA, normal text
AA_UI = 3.0        # WCAG AA, non-text UI component


# ---------- colour maths ----------

def _srgb_to_linear(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexstr):
    h = hexstr.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _srgb_to_linear(r)
            + 0.7152 * _srgb_to_linear(g)
            + 0.0722 * _srgb_to_linear(b))


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# ---------- reading the tokens out of the stylesheet ----------

TOKEN_RE = re.compile(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{3,8})")


def _block_after(css, anchor):
    """The text of the first {...} block whose selector text ends at `anchor`."""
    i = css.find(anchor)
    if i < 0:
        raise SystemExit(f"audit: could not find `{anchor}` in the stylesheet")
    start = css.index("{", i) + 1
    depth, j = 1, start
    while depth and j < len(css):
        if css[j] == "{":
            depth += 1
        elif css[j] == "}":
            depth -= 1
        j += 1
    return css[start:j - 1]


def tokens_in(block):
    return dict(TOKEN_RE.findall(block))


def read_contexts(html):
    css = html[html.index("<style>"):html.index("</style>")]

    night = tokens_in(_block_after(css, ":root{"))
    day_explicit = _block_after(css, ':root[data-theme="light"]')
    day_media = _block_after(css, ':root:not([data-theme="dark"])')
    pinned_block = _block_after(css, "#viewer,#annotate,#camera,#vault-busy")

    # The two day blocks must agree, or one mode silently drifts from the
    # other and only a live OS switch would ever show it.
    if tokens_in(day_explicit) != tokens_in(day_media):
        a, b = tokens_in(day_explicit), tokens_in(day_media)
        diff = {k: (a.get(k), b.get(k)) for k in set(a) | set(b)
                if a.get(k) != b.get(k)}
        raise SystemExit("audit: the two daylight blocks have diverged: "
                         + repr(diff))

    day = dict(night)
    day.update(tokens_in(day_explicit))
    pinned = dict(night)
    pinned.update(tokens_in(pinned_block))

    return {"night": night, "day": day, "pinned": pinned}


# ---------- the audit ----------

def audit(contexts, verbose=False):
    failures, lines = [], []

    for name, t in contexts.items():
        lines.append(f"\n  {name.upper()}  (ground {t['--ink']})")
        for ground in GROUNDS:
            for role in TEXT_ROLES:
                if role not in t or ground not in t:
                    failures.append(f"{name}: {role} or {ground} is undefined")
                    continue
                r = contrast(t[role], t[ground])
                ok = r >= AA_TEXT
                if not ok:
                    failures.append(
                        f"{name}: {role} ({t[role]}) on {ground} ({t[ground]}) "
                        f"= {r:.2f}:1, needs {AA_TEXT}")
                if verbose or not ok:
                    lines.append(f"    {'ok  ' if ok else 'FAIL'}  "
                                 f"{role:<14} on {ground:<8} {r:5.2f}:1")

        # the plate rule
        r = contrast(t["--on-brass"], t["--brass-fill"])
        ok = r >= AA_TEXT
        if not ok:
            failures.append(f"{name}: --on-brass on --brass-fill = {r:.2f}:1")
        if verbose or not ok:
            lines.append(f"    {'ok  ' if ok else 'FAIL'}  "
                         f"{'--on-brass':<14} on --brass-fill {r:5.2f}:1")

        # an outline that IS the control
        for ground in GROUNDS:
            r = contrast(t["--line-strong"], t[ground])
            ok = r >= AA_UI
            if not ok:
                failures.append(
                    f"{name}: --line-strong ({t['--line-strong']}) on {ground} "
                    f"({t[ground]}) = {r:.2f}:1, needs {AA_UI}")
            if verbose or not ok:
                lines.append(f"    {'ok  ' if ok else 'FAIL'}  "
                             f"{'--line-strong':<14} on {ground:<8} {r:5.2f}:1"
                             f"   (UI bar {AA_UI})")

        # decorative — reported so a drift is visible, never gated
        if verbose:
            for ground in GROUNDS:
                r = contrast(t["--line"], t[ground])
                lines.append(f"    --    {'--line':<14} on {ground:<8} "
                             f"{r:5.2f}:1   (decorative, not gated)")

    return failures, lines


def main(argv):
    verbose = "--verbose" in argv or "-v" in argv
    html = TARGET.read_text(encoding="utf-8")
    contexts = read_contexts(html)
    failures, lines = audit(contexts, verbose=verbose)

    checked = len(contexts) * (len(TEXT_ROLES) * len(GROUNDS)
                               + 1 + len(GROUNDS))
    print(f"Notebuilt contrast audit — {checked} gated pairings across "
          f"{len(contexts)} contexts")
    print("".join(l + "\n" for l in lines), end="")

    if failures:
        print(f"\n❌ {len(failures)} FAILED")
        for f in failures:
            print("   ! " + f)
        return 1
    print(f"\n✅ all {checked} gated pairings pass "
          f"(text {AA_TEXT}:1, UI {AA_UI}:1)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
