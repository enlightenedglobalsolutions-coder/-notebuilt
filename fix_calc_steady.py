#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — calculator: stop demolishing the input being typed into
Run from the same folder as index.html:
    python3 fix_calc_steady.py

THE BUG (audit-verified live, HEAD c548bfe)
-------------------------------------------
`calcRecompute()` is bound to `oninput` on every measurement box. For
Board Feet / Area / Square-up it called full `render()`:

    if(m==="bf"||m==="area"||m==="sq"){ render(); return; }

`render()` does `$app.innerHTML = …`, so the input under the user's
finger is destroyed and rebuilt on every keystroke. Measured in all five
modes:

    Add / Subtract ....... input kept, focus kept
    Multiply / Divide .... input kept, focus kept
    Board Feet ........... input DESTROYED, focus -> BODY
    Area ................. input DESTROYED, focus -> BODY
    Square-up ............ input DESTROYED, focus -> BODY

The typed value survives (re-read from CALC and written back by
`measWidget`), the caret and the keyboard do not — so on a phone the
keyboard dismisses after every digit, in the tool tradespeople use most.
Node-identity class, per EGS-DECISIONS 2026-08-12.

WHY IT WAS WRITTEN THAT WAY
---------------------------
Not laziness — a real asymmetry. In tape/md the body always ends with
`calcResult(res)`, so a `.cresult` element always exists and the surgical
`old.replaceWith(...)` path has something to replace. In bf/area/sq the
block is CONDITIONAL:

    +(bf!=null ? '<div class="cresult">…</div>' : '')

Until every field is filled there is no `.cresult` at all, so
`replaceWith` had nothing to work with and the code fell back to a full
render. The fix has to handle the create case, not just the replace case.

THE FIX
-------
1. `calcResultBlock(m)` — one function returning the result HTML for the
   current mode, or '' when the inputs are not all in. Both the full
   render and the surgical repaint call it, so the two can never drift
   apart. This is why the per-mode result formulas move rather than being
   copied: two copies of the board-feet formula is a bug waiting.

2. `calcRecompute()` now creates / replaces / removes that one block in
   place and touches nothing else. No keystroke reaches an input again.

Markup and visible behaviour are unchanged: the result card still appears
only once its fields are complete, and still disappears if a field is
cleared. tape/md keep the exact path they already had — `.cresult` always
exists there, so the replace branch runs and the create branch never
fires.

Deliberately NOT changed: the calculator is not restructured, no mode is
added or removed, no formula's arithmetic is altered.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "CALC_STEADY"


def fail(msg):
    print(f"\n❌ ABORTED — no changes were made.\n   Reason: {msg}\n")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found in this folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ Already applied — nothing to do.")
        return

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: calcRecompute -> surgical, plus the shared result builder.
    # ---------------------------------------------------------------
    old1 = """function calcRecompute(){
  var wrap=$app.querySelector('.wrap'); if(!wrap) return;
  var slotOf={ "c-a":"a","c-b":"b","bf_t":"bf_t","bf_w":"bf_w","bf_l":"bf_l","ar_w":"ar_w","ar_l":"ar_l","sq_a":"sq_a","sq_b":"sq_b" };
  wrap.querySelectorAll('.meas').forEach(function(root){
    var slot=slotOf[root.getAttribute("data-meas")]; if(!slot) return;
    var echo=root.parentNode.querySelector('.cecho'); if(echo){ var v=CALC[slot]; echo.textContent=(v!=null)?measEcho(v,measMode()):""; }
  });
  var old=wrap.querySelector('.cresult'); var m=CALC.mode;
  // board-feet / area / square-up: value blocks depend on the result; simplest correct path is a full render
  if(m==="bf"||m==="area"||m==="sq"){ render(); return; }
  if(!old) { render(); return; }
  var res=null;
  if(m==="tape"){ if(CALC.a!=null&&CALC.b!=null) res=CALC.op==="+"?CALC.a+CALC.b:CALC.a-CALC.b; }
  else if(m==="md"){ if(CALC.a!=null){ var n=parseFloat(CALC.num); if(!isNaN(n)&&String(CALC.num).trim()!==""){ res=CALC.op==="*"?CALC.a*n:(n!==0?CALC.a/n:null); } } }
  var tmp=document.createElement('div'); tmp.innerHTML=calcResult(res); old.replaceWith(tmp.firstChild);
}"""

    new1 = """/* CALC_STEADY — the result block for a mode, as HTML, or '' when the fields are
   not all in yet. ONE definition, called by the full render AND by the surgical
   repaint below, so the two can never drift. That matters more than it looks:
   the alternative is the board-feet formula existing in two places. */
function calcResultBlock(m){
  var mode=measMode();
  if(m==="tape"||m==="md"){
    var A=CALC.a, res=null;
    if(A!=null){
      if(m==="tape"){ if(CALC.b!=null) res = CALC.op==="+"?A+CALC.b:A-CALC.b; }
      else { var n=parseFloat(CALC.num); if(!isNaN(n)&&String(CALC.num).trim()!==""){ res = CALC.op==="*"?A*n:(n!==0?A/n:null); } }
    }
    return calcResult(res);          /* always present: reads "\\u2014" when empty */
  }
  if(m==="bf"){
    if(CALC.bf_t==null||CALC.bf_w==null||CALC.bf_l==null) return '';
    var bf=(CALC.bf_t*CALC.bf_w*CALC.bf_l)/144;
    return '<div class="cresult"><div class="muted">Board feet</div><div class="cbig">'+(Math.round(bf*100)/100)+' bf</div></div>';
  }
  if(m==="area"){
    if(CALC.ar_w==null||CALC.ar_l==null) return '';
    var sqin=CALC.ar_w*CALC.ar_l, sqft=sqin/144, sqm=sqin*0.00064516;
    return '<div class="cresult"><div class="muted">Area</div><div class="cbig">'+(mode==="metric"?(Math.round(sqm*100)/100)+' m\\u00b2':(Math.round(sqft*100)/100)+' sq ft')+'</div><div class="muted" style="margin-top:4px">'+(mode==="metric"?(Math.round(sqft*100)/100)+' sq ft':(Math.round(sqm*100)/100)+' m\\u00b2')+'</div></div>';
  }
  if(m==="sq"){
    if(CALC.sq_a==null||CALC.sq_b==null) return '';
    var diag=Math.sqrt(CALC.sq_a*CALC.sq_a+CALC.sq_b*CALC.sq_b);
    return '<div class="cresult"><div class="muted">Diagonal</div><div class="cbig">'+calcShow(diag)+'</div></div>';
  }
  return '';
}

function calcRecompute(){
  var wrap=$app.querySelector('.wrap'); if(!wrap) return;
  var slotOf={ "c-a":"a","c-b":"b","bf_t":"bf_t","bf_w":"bf_w","bf_l":"bf_l","ar_w":"ar_w","ar_l":"ar_l","sq_a":"sq_a","sq_b":"sq_b" };
  wrap.querySelectorAll('.meas').forEach(function(root){
    var slot=slotOf[root.getAttribute("data-meas")]; if(!slot) return;
    var echo=root.parentNode.querySelector('.cecho'); if(echo){ var v=CALC[slot]; echo.textContent=(v!=null)?measEcho(v,measMode()):""; }
  });
  /* CALC_STEADY — repaint ONLY the result block.
     This used to call render() for bf/area/sq, because in those modes .cresult
     is absent until every field is filled and there was nothing to replaceWith.
     A full render rebuilds $app, which demolished the input under the user's
     finger: focus fell to <body> and the phone keyboard dismissed on every
     digit. Create, replace or remove the one block in place and the boxes are
     never touched. */
  var m=CALC.mode, html=calcResultBlock(m), old=wrap.querySelector('.cresult');
  if(!html){ if(old) old.remove(); return; }
  var tmp=document.createElement('div'); tmp.innerHTML=html;
  var node=tmp.firstChild;
  if(old){ old.replaceWith(node); return; }
  /* First moment it can be shown: it belongs after the last measurement field,
     ahead of the trailing hint that closes .wrap. */
  var fields=wrap.querySelectorAll('.field');
  if(fields.length) fields[fields.length-1].insertAdjacentElement('afterend', node);
  else wrap.appendChild(node);
}"""
    edits.append((old1, new1, "calcRecompute(): surgical repaint + shared calcResultBlock()"))

    # ---------------------------------------------------------------
    # Edit 2: tape / md — use the shared builder.
    # ---------------------------------------------------------------
    old2 = """    var A=CALC.a, res=null;
    if(A!=null){
      if(m==="tape"){ if(CALC.b!=null) res = CALC.op==="+"?A+CALC.b:A-CALC.b; }
      else { var n=parseFloat(CALC.num); if(!isNaN(n)&&CALC.num.trim()!==""){ res = CALC.op==="*"?A*n:(n!==0?A/n:null); } }
    }
    body=''"""
    new2 = """    body=''"""
    edits.append((old2, new2, "renderCalc(): drop tape/md duplicate result maths"))

    old3 = """    +calcResult(res);
  } else if(m==="bf"){
    var bf=null;
    if(CALC.bf_t!=null&&CALC.bf_w!=null&&CALC.bf_l!=null) bf=(CALC.bf_t*CALC.bf_w*CALC.bf_l)/144;
    body=''"""
    new3 = """    +calcResultBlock(m);
  } else if(m==="bf"){
    body=''"""
    edits.append((old3, new3, "renderCalc(): tape/md + bf head -> shared builder"))

    old4 = """    +calcMField("bf_l","Length",CALC.bf_l,mode)
    +(bf!=null?'<div class="cresult"><div class="muted">Board feet</div><div class="cbig">'+(Math.round(bf*100)/100)+' bf</div></div>':'');
  } else if(m==="area"){
    var sqft=null,sqin=null,sqm=null;
    if(CALC.ar_w!=null&&CALC.ar_l!=null){ sqin=CALC.ar_w*CALC.ar_l; sqft=sqin/144; sqm=sqin*0.00064516; }
    body=''"""
    new4 = """    +calcMField("bf_l","Length",CALC.bf_l,mode)
    +calcResultBlock("bf");
  } else if(m==="area"){
    body=''"""
    edits.append((old4, new4, "renderCalc(): bf result + area head -> shared builder"))

    old5 = """    +calcMField("ar_l","Length",CALC.ar_l,mode)
    +(sqft!=null?'<div class="cresult"><div class="muted">Area</div><div class="cbig">'+(mode==="metric"?(Math.round(sqm*100)/100)+' m\\u00b2':(Math.round(sqft*100)/100)+' sq ft')+'</div><div class="muted" style="margin-top:4px">'+(mode==="metric"?(Math.round(sqft*100)/100)+' sq ft':(Math.round(sqm*100)/100)+' m\\u00b2')+'</div></div>':'');
  } else if(m==="sq"){
    var diag=null;
    if(CALC.sq_a!=null&&CALC.sq_b!=null) diag=Math.sqrt(CALC.sq_a*CALC.sq_a+CALC.sq_b*CALC.sq_b);
    body=''"""
    new5 = """    +calcMField("ar_l","Length",CALC.ar_l,mode)
    +calcResultBlock("area");
  } else if(m==="sq"){
    body=''"""
    edits.append((old5, new5, "renderCalc(): area result + sq head -> shared builder"))

    old6 = """    +calcMField("sq_b","Side B",CALC.sq_b,mode)
    +(diag!=null?'<div class="cresult"><div class="muted">Diagonal</div><div class="cbig">'+calcShow(diag)+'</div></div>':'');
  }"""
    new6 = """    +calcMField("sq_b","Side B",CALC.sq_b,mode)
    +calcResultBlock("sq");
  }"""
    edits.append((old6, new6, "renderCalc(): sq result -> shared builder"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # Mutation guard: the render() call that caused the bug must be gone from
    # calcRecompute, and no per-mode result formula may survive in renderCalc.
    def strip_comments(s):
        s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
        return re.sub(r"^\s*//.*$", "", s, flags=re.M)

    seg = strip_comments(working[working.index("function calcRecompute(){"):working.index("function renderCalc(){")])
    if "render()" in seg:
        fail("calcRecompute still calls render() — the bug would survive the fix.")
    rc = strip_comments(working[working.index("function renderCalc(){"):working.index("function calcMField(")])
    for stray in ["/144", "0.00064516", "Math.sqrt("]:
        if stray in rc:
            fail(f"renderCalc still carries a result formula ({stray}) — it must come from calcResultBlock().")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: calcRecompute() no longer calls render()")
    print("✅ guard: renderCalc() carries no result formula of its own")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_calc_steady_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ CALC_STEADY applied: a keystroke repaints one result block, nothing else.")
    print("   Gate: before.el === after.el AND activeElement survives, 6 rapid")
    print("   keystrokes, all five modes.")


if __name__ == "__main__":
    main()
