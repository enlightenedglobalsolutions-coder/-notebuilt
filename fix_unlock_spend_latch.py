#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — one activation per session, enforced where it is spent
Run from the same folder as index.html:
    python3 fix_unlock_spend_latch.py

WHY, ON TOP OF THE BUTTON BEING DISABLED
-----------------------------------------
After a successful-but-unstorable activation the button is disabled and
relabelled, and a real tap cannot get through — a disabled button does not
fire click events. Proven in a browser.

That is a UI property, though, and the thing it protects is a customer's
money. `disabled` is one careless future edit away from being removed, and
it does nothing against any path that reaches the handler another way.

So the rule moves to the only place an activation can actually be spent:
`unlockActivate` itself latches once the server has returned a 2xx, and
refuses to issue a second request for the rest of the session no matter
who asks or how. The UI can be wrong; the spend cannot happen twice.

The latch is set ONLY on a 2xx — the moment a slot is known to be gone. A
404 (wrong key) or a 403 (limit reached) spends nothing, so those stay
freely retryable, which is what a person mistyping a key needs.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
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


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — the latch, declared beside the thing it guards
    old_dec = """/* Write it, then read it straight back."""
    new_dec = """/* Set the moment the server returns a 2xx, and never cleared. One
   activation can be spent per session; the UI may be wrong about what
   happened, but the money cannot be spent twice on account of it. */
let unlockSpent=false;

/* Write it, then read it straight back."""
    edits.append((old_dec, new_dec, "unlockSpent latch declaration"))

    # 2 — refuse before the request, latch the instant one is known spent
    old_guard = """  if(!key) return {ok:false, kind:'empty'};
  /* Asked while plainly offline, say so without a doomed request first. */
  if(navigator.onLine===false) return {ok:false, kind:'offline'};"""
    new_guard = """  if(!key) return {ok:false, kind:'empty'};
  /* An activation has already been spent in this session. Whatever the
     screen says, another request can only spend another one. */
  if(unlockSpent) return {ok:false, kind:'spent'};
  /* Asked while plainly offline, say so without a doomed request first. */
  if(navigator.onLine===false) return {ok:false, kind:'offline'};"""
    edits.append((old_guard, new_guard, "unlockActivate(): refuse a second spend"))

    old_latch = """  if(res.ok){
    const id=(body && (body.id || body.activation_id || (body.activation && body.activation.id))) || null;"""
    new_latch = """  if(res.ok){
    /* Latched before anything below can throw, because from here a slot is
       gone whether or not the rest of this function succeeds. */
    unlockSpent=true;
    const id=(body && (body.id || body.activation_id || (body.activation && body.activation.id))) || null;"""
    edits.append((old_latch, new_latch, "unlockActivate(): latch on 2xx"))

    # 3 — words for it, and treat it as terminal in the sheet
    old_txt = """  if(r.kind==='unstored') return"""
    new_txt = """  if(r.kind==='spent')    return 'An activation was already used a moment ago, so Notebuilt will not send another — that would spend a second one for nothing. Close the app, reopen it, and look at Settings: if the Unlock row says Unlocked, you are done. If it still says Free, write your key down and contact EGS.';
  if(r.kind==='unstored') return"""
    edits.append((old_txt, new_txt, "unlockErrorText(): spent"))

    old_term = """    if(r.kind==='unstored' || r.kind==='crashed'){"""
    new_term = """    if(r.kind==='unstored' || r.kind==='crashed' || r.kind==='spent'){"""
    edits.append((old_term, new_term, "unlockKeySheet(): spent is terminal too"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    # The latch must be read before the request and written on success.
    act = working[working.find("async function unlockActivate"):working.find("function unlockErrorText")]
    if "if(unlockSpent) return" not in act:
        fail("the latch is not checked before the request.")
    if "unlockSpent=true;" not in act:
        fail("the latch is never set.")
    if act.index("if(unlockSpent) return") > act.index("await fetch("):
        fail("the latch is checked after the request — too late to prevent a spend.")
    if act.index("unlockSpent=true;") > act.index("unlockPersistVerified()"):
        fail("the latch is set after the write — a throw in between would leave it unset.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: latch read before the request, set on 2xx before any write")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_spend_latch_check.js")
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

    print("\n✅ a second activation cannot be issued in a session, whatever the UI does.")


if __name__ == "__main__":
    main()
