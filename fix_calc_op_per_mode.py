#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Multiply/Divide stops falling through to division
Run from the same folder as index.html:
    python3 fix_calc_op_per_mode.py

THE BUG (pre-existing, flagged in the Aug 12 calc-focus session, not fixed then)

CALC.op was ONE slot shared by two modes whose operator sets do not overlap:
Add/Subtract uses "+"/"-", Multiply/Divide uses "*"/"/". Both computes then read
that slot through a two-way ternary whose ELSE arm is the fall-through:

    tape:  res = CALC.op==="+" ? A+B : A-B          // not "+"  => subtract
    md:    res = CALC.op==="*" ? A*n : A/n          // not "*"  => DIVIDE

So an operator belonging to the other mode does not fail, it silently picks the
else arm. Cold open leaves CALC.op==="+"; tap Multiply/Divide and that "+" walks
straight into the md compute:

    10" x 3  ->  3 5/16"      (10/3, not 30)
    neither x nor / renders selected
    the number field is labelled "Divide by (number)" under a tab named Multiply

Multiply is unreachable until the user happens to tap x. The mirror runs the
other way: tap x, go back to Add/Subtract, and 10" + 4" reads 6" — a subtraction.

THE FIX (minimal)

Each mode gets its own operator slot — CALC.op stays Add/Subtract, CALC.opmd is
new for Multiply/Divide and defaults to "*", which is what the tab and the first
button already promise. One helper, calcOpFor(m), is the single place the
mode->slot mapping is written, and both computes now NAME their two operators
instead of leaning on an else. An operator from the wrong mode can no longer
reach a compute; if one ever did, the result is null ("—"), not a wrong number.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.

NOTE ON THE SYNTAX GATE: every earlier fix script in this repo checks
scripts[0]. Since the version stamp landed (Aug 15), scripts[0] is a 39-byte
one-liner and the app block is scripts[1] — so those gates have been checking
nothing. This script selects the app block by content and asserts it.
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


def app_block(text):
    """The REAL app block, chosen by content — never by index."""
    blocks = re.findall(r"<script>(.*?)</script>", text, re.S)
    if not blocks:
        fail("no <script> blocks found.")
    block = max(blocks, key=len)
    if not block.lstrip().startswith('"use strict";'):
        fail("the largest <script> block is not the app block.")
    if "function calcResultBlock(" not in block:
        fail("the app block does not contain the calculator.")
    return blocks, block


# ---- edits: (description, old, new) ---------------------------------------
EDITS = [
    (
        "operator slot per mode + the one mapping helper",
        '''var CALC={mode:"tape", a:null, b:null, op:"+", num:"", bf_t:null, bf_w:null, bf_l:null, ar_w:null, ar_l:null, sq_a:null, sq_b:null};''',
        '''/* CALC_OP_PER_MODE — Add/Subtract and Multiply/Divide keep SEPARATE operator
   slots. They shared one, and because each compute read it through a two-way
   ternary, an operator from the other mode did not fail — it took the else arm.
   Cold open leaves op "+", so tapping Multiply/Divide and entering 10" x 3 read
   3 5/16": a division, with neither button lit and the field labelled "Divide
   by" under a tab named Multiply. The mirror ran the other way, a "*" reaching
   tape and quietly subtracting. One slot per mode, and both computes below name
   their two operators outright rather than treating "not this one" as the other. */
var CALC={mode:"tape", a:null, b:null, op:"+", opmd:"*", num:"", bf_t:null, bf_w:null, bf_l:null, ar_w:null, ar_l:null, sq_a:null, sq_b:null};
/* The operator in force for a mode — the ONE place that mapping is written, so
   the compute, the button highlight and the field label cannot disagree. */
function calcOpFor(m){ return m==="md" ? CALC.opmd : CALC.op; }''',
    ),
    (
        "both computes name their operators (no else fall-through)",
        '''      if(m==="tape"){ if(CALC.b!=null) res = CALC.op==="+"?A+CALC.b:A-CALC.b; }
      else { var n=parseFloat(CALC.num); if(!isNaN(n)&&String(CALC.num).trim()!==""){ res = CALC.op==="*"?A*n:(n!==0?A/n:null); } }''',
        '''      var op=calcOpFor(m);
      if(m==="tape"){ if(CALC.b!=null){ if(op==="+") res=A+CALC.b; else if(op==="-") res=A-CALC.b; } }
      else { var n=parseFloat(CALC.num); if(!isNaN(n)&&String(CALC.num).trim()!==""){ if(op==="*") res=A*n; else if(op==="/") res=(n!==0?A/n:null); } }''',
    ),
    (
        "the selected op button reads from the mode's own slot",
        """    +'<div class="crow">'+ops.map(function(o){return '<button class="btn '+(CALC.op===o[1]?'primary':'')+'" data-calc-op="'+o[1]+'">'+o[0]+'</button>';}).join("")+'</div>'""",
        """    +'<div class="crow">'+ops.map(function(o){return '<button class="btn '+(calcOpFor(m)===o[1]?'primary':'')+'" data-calc-op="'+o[1]+'">'+o[0]+'</button>';}).join("")+'</div>'""",
    ),
    (
        "the number field label reads from the mode's own slot",
        """       : '<div class="field"><label>'+(CALC.op==="*"?"Times (number)":"Divide by (number)")+'</label>""",
        """       : '<div class="field"><label>'+(calcOpFor(m)==="*"?"Times (number)":"Divide by (number)")+'</label>""",
    ),
    (
        "the op button writes to the mode's own slot",
        '''  $app.querySelectorAll('[data-calc-op]').forEach(b=>b.onclick=()=>{ CALC.op=b.dataset.calcOp; render(); });''',
        '''  $app.querySelectorAll('[data-calc-op]').forEach(b=>b.onclick=()=>{ var o=b.dataset.calcOp; if(o==="*"||o==="/") CALC.opmd=o; else CALC.op=o; render(); });''',
    ),
]


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    before_blocks, before_app = app_block(text)
    print(f"\U0001f4c4 app block located: {len(before_app)} chars "
          f"(block {before_blocks.index(before_app)} of {len(before_blocks)})")

    working = text
    for desc, old, new in EDITS:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for {desc!r} matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)
        print(f"✅ anchor ==1: {desc}")

    # ---- guards ---------------------------------------------------------
    if working == text:
        fail("nothing changed.")

    # the shared-slot reads are gone from the calculator
    for gone in ('res = CALC.op==="+"?A+CALC.b:A-CALC.b',
                 'res = CALC.op==="*"?A*n:(n!==0?A/n:null)',
                 "(CALC.op===o[1]?'primary':'')",
                 'CALC.op==="*"?"Times (number)"',
                 "CALC.op=b.dataset.calcOp;"):
        if gone in working:
            fail(f"a shared-slot read survived the edit: {gone!r}")

    # the new shape is present, and singular
    for needle, want in ((' opmd:"*",', 1),
                         ("function calcOpFor(m){", 1),
                         ("calcOpFor(m)", 4),  # the definition, the compute, the highlight, the label
                         ("CALC.opmd=o;", 1)):
        got = working.count(needle)
        if got != want:
            fail(f"expected {want} occurrence(s) of {needle!r}, found {got}.")

    # the rest of the calculator is untouched
    for needle in ('var bf=(CALC.bf_t*CALC.bf_w*CALC.bf_l)/144;',
                   'var sqin=CALC.ar_w*CALC.ar_l, sqft=sqin/144, sqm=sqin*0.00064516;',
                   'var diag=Math.sqrt(CALC.sq_a*CALC.sq_a+CALC.sq_b*CALC.sq_b);',
                   'CALC.mode=b.dataset.calcMode;',
                   'var m=CALC.mode, html=calcResultBlock(m), old=wrap.querySelector(\'.cresult\');',
                   "if(old){ old.replaceWith(node); return; }"):
        if needle not in working:
            fail(f"missing after edit: {needle!r}")

    after_blocks, after_app = app_block(working)
    if len(before_blocks) != len(after_blocks):
        fail("script block count changed.")

    # ---- backup, write, syntax check ------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Patched {TARGET}")

    js_path = Path("/tmp/_notebuilt_calc_op_check.js")
    js_path.write_text(after_app, encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)],
                                capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        shutil.copy2(backup_path, TARGET)
        fail("node not found — restored from backup. The syntax gate is not optional here.")
    if result.returncode != 0:
        shutil.copy2(backup_path, TARGET)
        fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
    print(f"✅ JS syntax check passed (node --check on the app block, {len(after_app)} chars)")

    print("\n✅ Multiply multiplies. Each mode holds its own operator.")


if __name__ == "__main__":
    main()
