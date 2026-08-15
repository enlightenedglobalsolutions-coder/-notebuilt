#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a Clear control on every calculator mode
Run from the same folder as index.html:
    python3 fix_calc_clear.py

Entering a second measurement meant hand-emptying two or three boxes, each of
which is up to three inputs (ft / in / frac, or m / cm). On a site, in gloves,
that is the difference between using the calculator and not. Clear empties the
ACTIVE mode's boxes and its result in one tap.

WHAT CLEAR DOES NOT TOUCH — mode, the ft/in<->metric toggle, and the operator
choice all survive. Clearing the numbers must not reset how someone works; that
is the same reasoning that gave each mode its own operator slot in
v2026.08.15-1420 (CALC_OP_PER_MODE).

ON THE CONFIRM: the brief asked for a confirm in tape mode IF a running-tape
history exists. It does not. CALC holds scalar slots only (a, b, num, bf_*,
ar_*, sq_*) and "tape" names the tape-measure NOTATION — the Add/Subtract
two-measurement mode — not a running tape. Verified by grep before building:
no history array, no log, nothing accumulated across entries. So there is
nothing to lose and nothing to confirm, and every mode clears instantly. A
confirm guarding nothing is worse than no confirm: it teaches the habit of
tapping through confirms, which is exactly what Tier 1's delete discipline
depends on people NOT having. If a running tape is ever added, the confirm
goes in with it.

PLACEMENT — directly under the mode tab strip, the one position that is
identical in all five modes. Anything below the fields moves: Board Feet has
three fields where the others have two, and bf/area/sq render no result block
until every field is in. Same .btn class as the operator keys, so the target is
the 46px --tap one.

NO FULL RENDER. Clear blanks the values on the EXISTING inputs and repaints
through calcRecompute, the same surgical path a keystroke takes. Calling
render() here would have rebuilt $app and undone the Aug 12 CALC_STEADY work.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import shutil
import sys
import time
from pathlib import Path

# The shared checker. One source of truth — if it cannot be imported, that is
# a hard stop, not a reason to continue without a syntax check.
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


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # ---- 1. the Clear row's own rule --------------------------------------
    # .crow makes its buttons flex:1, which would stretch a lone Clear across
    # the full width and give it the weight of a primary action. Its own rule
    # keeps it right-aligned and secondary, at the full .btn tap height.
    old = """  .crow .btn{flex:1;justify-content:center;font-size:20px;padding:8px}
"""
    new = """  .crow .btn{flex:1;justify-content:center;font-size:20px;padding:8px}
  .cclear{display:flex;justify-content:flex-end;margin:0 0 12px}
"""
    edits.append((old, new, "the .cclear rule"))

    # ---- 2. hoist the slot map so Clear and the recompute share it --------
    old = """function calcRecompute(){
  var wrap=$app.querySelector('.wrap'); if(!wrap) return;
  var slotOf={ "c-a":"a","c-b":"b","bf_t":"bf_t","bf_w":"bf_w","bf_l":"bf_l","ar_w":"ar_w","ar_l":"ar_l","sq_a":"sq_a","sq_b":"sq_b" };
  wrap.querySelectorAll('.meas').forEach(function(root){
    var slot=slotOf[root.getAttribute("data-meas")]; if(!slot) return;"""
    new = """/* CALC_STEADY — which CALC slot each measurement widget writes to. ONE map,
   read by the recompute AND by Clear, so a field cannot be added to one and
   forgotten in the other. Same reason calcResultBlock has a single definition:
   the alternative is this table existing twice and drifting. */
var CALC_SLOT_OF={ "c-a":"a","c-b":"b","bf_t":"bf_t","bf_w":"bf_w","bf_l":"bf_l","ar_w":"ar_w","ar_l":"ar_l","sq_a":"sq_a","sq_b":"sq_b" };

function calcRecompute(){
  var wrap=$app.querySelector('.wrap'); if(!wrap) return;
  wrap.querySelectorAll('.meas').forEach(function(root){
    var slot=CALC_SLOT_OF[root.getAttribute("data-meas")]; if(!slot) return;"""
    edits.append((old, new, "hoist the slot map to CALC_SLOT_OF"))

    # ---- 3. calcClear itself ---------------------------------------------
    old = """  var fields=wrap.querySelectorAll('.field');
  if(fields.length) fields[fields.length-1].insertAdjacentElement('afterend', node);
  else wrap.appendChild(node);
}
function renderCalc(){"""
    new = """  var fields=wrap.querySelectorAll('.field');
  if(fields.length) fields[fields.length-1].insertAdjacentElement('afterend', node);
  else wrap.appendChild(node);
}
/* CALC_CLEAR — empty the ACTIVE mode's boxes and its result in one tap.
   Only the active mode's fields are ever in the DOM, so clearing what is
   rendered clears that mode and nothing else — no per-mode list to keep in
   step with renderCalc.
   Left alone on purpose: CALC.mode, the ft/in<->metric toggle, and both
   operator slots. Clearing the numbers must not reset how someone works.
   No confirm, and nothing to confirm: these boxes hold typed input, not saved
   data, and there is no running tape to lose. If one is ever added, its
   confirm goes in with it.
   The values are blanked on the EXISTING inputs and the repaint goes through
   calcRecompute, so a clear takes the same surgical path as a keystroke —
   no full render, and the boxes are never rebuilt. */
function calcClear(){
  var wrap=$app.querySelector('.wrap'); if(!wrap) return;
  wrap.querySelectorAll('.meas').forEach(function(root){
    var slot=CALC_SLOT_OF[root.getAttribute("data-meas")]; if(slot) CALC[slot]=null;
    root.querySelectorAll('input').forEach(function(inp){ inp.value=""; });
  });
  var cnum=wrap.querySelector('#c-num'); if(cnum){ CALC.num=""; cnum.value=""; }
  calcRecompute();
}
function renderCalc(){"""
    edits.append((old, new, "calcClear"))

    # ---- 4. the Clear row, in the one position common to all five modes ---
    old = """  return '<div class="topbar"><div class="grow"><span class="eyebrow">'+esc(APP_NAME)+'</span><h1>Calculator</h1></div>'+unitTog+'</div>'
    +'<div class="wrap"><div style="display:flex;flex-wrap:wrap;margin-bottom:10px">'+tabhtml+'</div>'+body"""
    new = """  /* Clear sits directly under the tab strip — the one position identical in
     all five modes. Anything below the fields moves: Board Feet has three
     fields where the others have two, and bf/area/sq draw no result block
     until every field is in. Plain .btn, the same class as the operator keys,
     so the target is the 46px --tap one and gloves find it by feel. */
  var clearRow='<div class="cclear"><button class="btn" data-calc-clear>Clear</button></div>';
  return '<div class="topbar"><div class="grow"><span class="eyebrow">'+esc(APP_NAME)+'</span><h1>Calculator</h1></div>'+unitTog+'</div>'
    +'<div class="wrap"><div style="display:flex;flex-wrap:wrap;margin-bottom:10px">'+tabhtml+'</div>'+clearRow+body"""
    edits.append((old, new, "the Clear row in renderCalc"))

    # ---- 5. the binding ---------------------------------------------------
    old = """  $app.querySelectorAll('[data-calc-op]').forEach(b=>b.onclick=()=>{ var o=b.dataset.calcOp; if(o==="*"||o==="/") CALC.opmd=o; else CALC.op=o; render(); });"""
    new = """  $app.querySelectorAll('[data-calc-op]').forEach(b=>b.onclick=()=>{ var o=b.dataset.calcOp; if(o==="*"||o==="/") CALC.opmd=o; else CALC.op=o; render(); });
  $app.querySelectorAll('[data-calc-clear]').forEach(b=>b.onclick=()=>calcClear());"""
    edits.append((old, new, "the Clear binding"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)
        print(f"✅ anchor ==1: {label}")

    # ---- guards -----------------------------------------------------------
    # What this edit is FOR:
    for needle, want in (("function calcClear(){", 1),
                         ("data-calc-clear", 2),          # the button, and the binding
                         ("var clearRow=", 1),
                         (".cclear{", 1),
                         ("CALC_SLOT_OF", 3),             # defined once, read by recompute and by Clear
                         ("var slotOf=", 0)):             # the local copy is gone
        got = working.count(needle)
        if got != want:
            fail(f"expected {want} occurrence(s) of {needle!r}, found {got}.")

    # Clear must NOT full-render — that would undo the Aug 12 CALC_STEADY work.
    clear_body = working[working.index("function calcClear(){"):]
    clear_body = clear_body[:clear_body.index("\nfunction renderCalc(){")]
    if "render()" in clear_body.replace("calcRecompute()", ""):
        fail("calcClear calls render() — it must take the surgical path only.")
    if "calcRecompute();" not in clear_body:
        fail("calcClear does not repaint through calcRecompute.")
    # ...and must not reset how the user works.
    for forbidden in ("CALC.mode=", "CALC.op=", "CALC.opmd=", "settings.units"):
        if forbidden in clear_body:
            fail(f"calcClear touches {forbidden!r} — mode, units and operator must survive a clear.")

    # What must not have moved:
    for needle in ("function calcOpFor(m){ return m===\"md\" ? CALC.opmd : CALC.op; }",
                   "var bf=(CALC.bf_t*CALC.bf_w*CALC.bf_l)/144;",
                   "var diag=Math.sqrt(CALC.sq_a*CALC.sq_a+CALC.sq_b*CALC.sq_b);",
                   "if(old){ old.replaceWith(node); return; }",
                   "if(fields.length) fields[fields.length-1].insertAdjacentElement('afterend', node);"):
        if needle not in working:
            fail(f"missing after edit: {needle!r}")
    if working.count("function calcResultBlock(") != 1:
        fail("calcResultBlock is no longer defined exactly once.")

    # ---- backup, then write ----------------------------------------------
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

    # ---- syntax check: EVERY inline block, or restore ---------------------
    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Every mode clears in one tap, and keeps how you were working.")


if __name__ == "__main__":
    main()
