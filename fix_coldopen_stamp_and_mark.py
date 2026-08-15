#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a version you can read on the first screen, and the real mark on it
Run from the same folder as index.html:
    python3 fix_coldopen_stamp_and_mark.py

WHAT CHANGES
------------
Two things a person meets before they have done anything at all: the version
stamp, and the mark above it.

1 · COLD-OPEN VERSION STAMP  (EGS-STD:coldopen-version)
-------------------------------------------------------
`window.EGS_VERSION` has been in the file since the stamp was introduced, but
it was rendered in exactly one place — `renderSettings()`. A fresh visitor
lands on the to-do list (`view={name:'todo'}`) or, with a PIN set, on the
keypad; neither drew it. "Is the update actually on the phone?" was a question
you could only answer by navigating into Settings, which is not what the
standard asks for: it asks for the FIRST screen, before setup, before any PIN.

So the stamp now renders from one helper, `versionStamp()`, in three places
that between them cover every way in:

  * `lockGate()`     — under the keypad, before a digit is entered
  * `lockPrompt()`   — the three "forgot PIN" screens share one shape
  * `render()`       — appended to whatever view was drawn, first one included

The hand-rolled copy inside `renderSettings()` is removed in the same breath.
Two renderers of one value is how they drift; there is now one, and Settings
gets its footer from the same helper as everything else.

`window.EGS_VERSION` itself is untouched — `egs-deploy.sh` stamps that line and
must keep matching it.

2 · THE IN-APP MARK
-------------------
The shipped icons (192 / 512 / maskable / 180) are the ruled-plank N in the
gold Vitruvian seal. `MARK` — the SVG the app draws at four render sites, all
of them lock screens — was something else entirely: an L-stroke and three
bars, no seal, and at 58px it read as an E. It was the first thing a locked-out
user saw, and it did not match the icon they had tapped to get there.

MARK is redrawn from the shipped PNG, measured off `icons/icon-512.png` and
divided by eight into a 64-unit viewBox:

  seal        two rings (r 186.5 / 168) + a square 109.5→403 with a dot at
              each corner, all #D6A84B
  posts       two serif columns, 50 wide with 76-wide caps, ruled every 28
  plank       a 52.9 x 323 slab at 30.4 degrees off vertical, lighter stock,
              ruled across its width, a nail head near each end

The icons are NOT generated from this and must not be — `icons/*.png` stay the
source of truth for the home screen. This is the same drawing, by hand, for
the one place a PNG cannot go.

Backs up first, exact-match anchors asserted ==1, node --check on the real
script block, atomic.
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


# The mark, measured off icons/icon-512.png and divided by 8.
NEW_MARK = (
    "const MARK = '<svg viewBox=\"0 0 64 64\" fill=\"none\" aria-hidden=\"true\">'\n"
    " /* the plaque, in the icon's own ground colour */\n"
    " +'<rect x=\"2\" y=\"2\" width=\"60\" height=\"60\" rx=\"15\" fill=\"#1A1E25\" stroke=\"#333A45\"/>'\n"
    " /* the seal: two rings and a square, a dot at each corner */\n"
    " +'<g stroke=\"#D6A84B\" fill=\"none\">'\n"
    "   +'<circle cx=\"32\" cy=\"32\" r=\"23.34\" stroke-width=\".69\"/>'\n"
    "   +'<circle cx=\"32\" cy=\"32\" r=\"21\" stroke-width=\".28\"/>'\n"
    "   +'<rect x=\"13.66\" y=\"13.66\" width=\"36.69\" height=\"36.69\" stroke-width=\".44\"/>'\n"
    " +'</g>'\n"
    " +'<g fill=\"#D6A84B\"><circle cx=\"13.66\" cy=\"13.66\" r=\".5\"/><circle cx=\"50.35\" cy=\"13.66\" r=\".5\"/>'\n"
    "   +'<circle cx=\"50.35\" cy=\"50.35\" r=\".5\"/><circle cx=\"13.66\" cy=\"50.35\" r=\".5\"/></g>'\n"
    " /* the two serif posts */\n"
    " +'<g fill=\"#C89F47\" stroke=\"#0D1016\" stroke-width=\".5\" stroke-linejoin=\"round\">'\n"
    "   +'<path d=\"M18.75 14.88H28.5V17.88H26.75V46.13H28.5V49.13H18.75V46.13H20.5V17.88H18.75Z\"/>'\n"
    "   +'<path d=\"M35.5 14.88H45.25V17.88H43.5V46.13H45.25V49.13H35.5V46.13H37.25V17.88H35.5Z\"/></g>'\n"
    " /* ruled like the pad they are cut from */\n"
    " +'<g stroke=\"#92753B\" stroke-width=\".42\">'\n"
    "   +'<path d=\"M20.5 21.81H26.75M20.5 25.31H26.75M20.5 28.81H26.75M20.5 32.31H26.75M20.5 35.81H26.75M20.5 39.31H26.75M20.5 42.81H26.75\"/>'\n"
    "   +'<path d=\"M37.25 21.81H43.5M37.25 25.31H43.5M37.25 28.81H43.5M37.25 32.31H43.5M37.25 35.81H43.5M37.25 39.31H43.5M37.25 42.81H43.5\"/></g>'\n"
    " /* the diagonal plank, over both posts, crossing the frame at each end */\n"
    " +'<path d=\"M24.61 12.85L45.01 47.59L39.53 50.96L18.95 16.28Z\" fill=\"#F5CC74\" stroke=\"#0D1016\" stroke-width=\".5\" stroke-linejoin=\"round\"/>'\n"
    "   +'<path d=\"M28.77 20.05L23.35 23.23M30.86 23.61L25.44 26.79M32.91 27.12L27.49 30.3M34.97 30.62L29.55 33.8M37.02 34.12L31.6 37.3M39.08 37.64L33.66 40.82M41.13 41.14L35.71 44.32\" stroke=\"#8D7037\" stroke-width=\".42\"/>'\n"
    "   +'<g fill=\"#0E1016\"><circle cx=\"23.79\" cy=\"17.76\" r=\".55\"/><circle cx=\"40.37\" cy=\"46.06\" r=\".55\"/></g>'\n"
    " +'</svg>';"
)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — the marker, so `egs-deploy.sh --full` can grep row 2 on this app
    old_ver = """<script>window.EGS_VERSION = '2026.08.14-1606';</script>"""
    new_ver = """<!-- EGS-STD:coldopen-version -->
<script>window.EGS_VERSION = '2026.08.14-1606';</script>"""
    edits.append((old_ver, new_ver, "marker: EGS-STD:coldopen-version"))

    # 2 — one class for the stamp, so the three render sites cannot drift apart
    old_mono = """  .mono{font-family:var(--mono)}"""
    new_mono = """  .mono{font-family:var(--mono)}
  /* EGS-STD:coldopen-version — one look for the stamp, wherever it is drawn. */
  .ver-stamp{font-family:var(--mono);text-align:center;font-size:10.5px;letter-spacing:.12em;
    color:var(--paper-faint);margin:20px 0 4px}
  #lock .ver-stamp{margin:18px 0 0}"""
    edits.append((old_mono, new_mono, "CSS: .ver-stamp"))

    # 3 — the mark, redrawn from the shipped icon
    old_mark_start = "const MARK = '<svg viewBox=\"0 0 64 64\" fill=\"none\">"
    m = re.search(r"const MARK = '<svg viewBox=\"0 0 64 64\" fill=\"none\">.*?</svg>';", text, re.S)
    if not m:
        fail("could not find the MARK const to replace.")
    if text.count(old_mark_start) != 1:
        fail("MARK const is not unique.")
    old_mark = m.group(0)
    new_mark = (
        "/* MARK — the shipped app icon, redrawn as vector for the four lock screens.\n"
        "   Geometry is icons/icon-512.png divided by 8, so the mark above the keypad\n"
        "   and the mark on the home screen are the same drawing. The PNGs are NOT\n"
        "   generated from this and must not be; they remain the source for the icon. */\n"
        + NEW_MARK
    )
    edits.append((old_mark, new_mark, "MARK: the ruled-plank N in its seal"))

    # 4 — one renderer for the stamp
    old_render = """function render(){
  autosaveOpenNote();                              // save the screen we're leaving"""
    new_render = """/* EGS-STD:coldopen-version — one source (window.EGS_VERSION), one renderer.
   The stamp used to exist only inside renderSettings(), so a fresh visitor —
   who lands on the to-do list, or on the keypad — could not answer "is this
   the update?" without navigating into Settings first. That is not the first
   screen, which is what the standard asks for. */
function versionStamp(){
  return '<div class="ver-stamp">'+esc(window.EGS_VERSION||'dev build')+'</div>';
}

function render(){
  autosaveOpenNote();                              // save the screen we're leaving"""
    edits.append((old_render, new_render, "versionStamp()"))

    # 5 — every view carries it, the first one included
    old_paint = """  $app.innerHTML=r(view.param);"""
    new_paint = """  $app.innerHTML=r(view.param)+versionStamp();   /* cold open lands here */"""
    edits.append((old_paint, new_paint, "render(): stamp every view"))

    # 6 — and Settings stops rolling its own
    old_settings = """
    <!-- VERSION_STAMP — what egs-deploy.sh stamped, shown so "is it actually
         updated?" is a question you can answer by looking. -->
    <div class="mono" style="text-align:center;font-size:10.5px;letter-spacing:.12em;color:var(--paper-faint);margin:20px 0 4px">${esc(window.EGS_VERSION||'dev build')}</div>
  </div>`;"""
    new_settings = """
    <!-- VERSION_STAMP — drawn by render() now, from the one shared helper,
         like every other screen. Settings kept a second copy; it does not. -->
  </div>`;"""
    edits.append((old_settings, new_settings, "renderSettings(): drop the duplicate"))

    # 7 — the keypad, before a digit is entered
    old_gate = """      <button type="button" class="lock-link" data-forgot>Forgot PIN?</button>`;"""
    new_gate = """      <button type="button" class="lock-link" data-forgot>Forgot PIN?</button>
      ${versionStamp()}`;"""
    edits.append((old_gate, new_gate, "lockGate(): stamp under the keypad"))

    # 8 — and the three forgot-PIN screens, which share one shape
    old_prompt = """      +(o.go?'<button type="button" class="btn primary block" data-go>'+esc(o.go)+'</button>':'')
      +'<button type="button" class="btn block" data-back>'+esc(o.back||'Back')+'</button>'
    +'</div>';"""
    new_prompt = """      +(o.go?'<button type="button" class="btn primary block" data-go>'+esc(o.go)+'</button>':'')
      +'<button type="button" class="btn block" data-back>'+esc(o.back||'Back')+'</button>'
    +'</div>'
    +versionStamp();"""
    edits.append((old_prompt, new_prompt, "lockPrompt(): stamp on the way back in"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # One source, and the deploy script can still stamp it.
    if not re.search(r"window\.EGS_VERSION = '[^']*'", working):
        fail("the line egs-deploy.sh stamps no longer matches its sed.")
    if working.count("window.EGS_VERSION||'dev build'") != 1:
        fail("window.EGS_VERSION is read in more than one place — that is how stamps drift.")
    if working.count("versionStamp()") != 4:      # 1 definition + 3 call sites
        fail(f"expected 1 definition and 3 call sites for versionStamp(), found {working.count('versionStamp()')}.")

    # Both cold-open paths draw it. No-PIN: lockGate falls through to render().
    gate = working[working.find("function lockGate(){"):working.find("function setupPin(){")]
    if "showShell(true); render();" not in gate:
        fail("the no-PIN branch of lockGate no longer routes through render() — the stamp would not be drawn.")
    if "${versionStamp()}" not in gate:
        fail("the PIN keypad does not draw the stamp.")
    if "+versionStamp();" not in working[working.find("function lockPrompt(o){"):working.find("function forgotPinFlow(){")]:
        fail("the forgot-PIN screens do not draw the stamp.")
    body = working[working.find("function render(){"):working.find("function renderNav(){")]
    if "+versionStamp()" not in body:
        fail("render() does not append the stamp to the view it just drew.")

    # The mark is the icon's mark, not the old L-and-bars.
    mark = re.search(r"const MARK = '.*?</svg>';", working, re.S).group(0)
    for shape, why in [('circle cx="32" cy="32" r="23.34"', "the seal's outer ring is missing"),
                       ('rect x="13.66"', "the seal's square is missing"),
                       ("M24.61 12.85L45.01 47.59", "the diagonal plank is missing"),
                       ('fill="#F5CC74"', "the plank is not cut from the lighter stock")]:
        if shape not in mark:
            fail(f"MARK is not the shipped mark: {why}.")
    if "M20 16v28h28" in working:
        fail("the old L-stroke path is still in the file.")
    if working.count("const MARK = ") != 1:
        fail("MARK is defined more than once.")

    # Nothing here may touch the icons the home screen uses.
    if "icons/icon-180.png" not in working:
        fail("index.html's apple-touch-icon reference was lost.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: one EGS_VERSION reader, three render sites, deploy sed still matches")
    print("✅ guard: both cold-open paths (no-PIN → render, PIN → keypad) draw the stamp")
    print("✅ guard: MARK carries the seal, the square and the ruled plank; old path gone")

    # node --check the app's script block — the biggest one, not the first,
    # which is the one-line EGS_VERSION stamp.
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_coldopen_check.js")
    js_path.write_text(max(scripts, key=len), encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check, on the app's script block)")

    print("\n✅ the version reads on the first screen, under the mark that is actually the app's.")


if __name__ == "__main__":
    main()
