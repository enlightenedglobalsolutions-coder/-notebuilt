#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a spend that outlived its session must still be visible
Run from the same folder as index.html:
    python3 fix_unlock_spend_marker.py

THE REMAINING HOLE
------------------
`unlockSpent` is a session latch, so it resets on reload. On the device
this incident happened to — one that accepts the activation but cannot
save it — the sequence is:

    activate -> succeeds -> cannot be stored -> told not to retry
    close the app
    reopen -> latch cleared, no record of anything -> tap -> slot 2 gone

Which is the original trap with an extra step. Three slots went this way.

THE MARKER
----------
On any 2xx a tiny record is written to its own key,
`notebuilt.unlockSpent` — a timestamp, nothing else. It is attempted
BEFORE the settings write and wrapped in its own try/catch, because it is
the thing most likely to fit when the large write is what failed: it is
~30 bytes, and it is not in the durability guard's CRIT list, so unlike
settings it is not silently duplicated into a `_bak` twin.

On a device whose quota is genuinely exhausted even this will fail. That
case cannot be solved by writing something, and this does not pretend to.

WHY A WARNING AND NOT A BLOCK
------------------------------
If the marker hard-blocked activation, anyone who legitimately buys a
second key — or activates again after deactivating a slot in the Polar
dashboard, which is exactly the recovery path — would be locked out by
their own history with no way through.

So the marker warns instead. The key sheet opens with the date an
activation was already spent and what tapping again will cost, and the
button stays armed. "Never burn a slot blind" is satisfied by removing the
blindness, not the choice.

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

    # 1 — read the marker; its own key, deliberately outside CRIT
    old_dec = """/* Set the moment the server returns a 2xx, and never cleared."""
    new_dec = """/* A spend that outlived its session. Its own tiny key: settings is the
   write that fails first under pressure, and the durability guard mirrors
   every CRIT key into a `_bak` twin, so putting this there would double
   exactly the cost that is already too high. */
const UNLOCK_SPENT_KEY='notebuilt.unlockSpent';
function unlockSpentBefore(){
  try{ const v=JSON.parse(localStorage.getItem(UNLOCK_SPENT_KEY)||'null'); return (v&&v.at)?v:null; }
  catch(e){ return null; }
}

/* Set the moment the server returns a 2xx, and never cleared."""
    edits.append((old_dec, new_dec, "unlockSpentBefore() + marker key"))

    # 2 — write it first, on its own, before the write that is known to fail
    old_latch = """    unlockSpent=true;
    const id=(body && (body.id || body.activation_id || (body.activation && body.activation.id))) || null;"""
    new_latch = """    unlockSpent=true;
    /* Before the settings write, and independent of whether that survives:
       this is the record that stops the next launch spending another. */
    try{ localStorage.setItem(UNLOCK_SPENT_KEY, JSON.stringify({at:now()})); }catch(e){}
    const id=(body && (body.id || body.activation_id || (body.activation && body.activation.id))) || null;"""
    edits.append((old_latch, new_latch, "unlockActivate(): persist the spend marker"))

    # 3 — say it, at the top of the sheet, before a finger is anywhere near
    old_sheet = """  sheet('<h2>Enter your key</h2>'
    +'<div class="muted" style="font-size:13px;line-height:1.6;margin-bottom:12px">It arrives by email as soon as you buy. Capitals, spaces and dashes do not matter.</div>'"""
    new_sheet = """  /* An activation already went out from this device and was never recorded.
     Say so before the tap, not after it. */
  const spent=(!unlockIsOn() && unlockSpentBefore());
  let spentOn='';
  if(spent){ try{ spentOn=new Date(spent.at).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}); }catch(e){} }
  sheet('<h2>Enter your key</h2>'
    +(spent?'<div class="card" style="background:var(--ink-2);margin-bottom:12px"><div class="muted" style="font-size:13px;line-height:1.6">An activation was already used from this device'+(spentOn?' on '+esc(spentOn):'')+', but it was never saved here. Your key has a limited number of activations, and tapping Activate will spend another one.<br><br>If Settings still shows <b style="color:var(--paper)">Free</b>, contact EGS before spending it — the used one can be released instead.</div></div>':'')
    +'<div class="muted" style="font-size:13px;line-height:1.6;margin-bottom:12px">It arrives by email as soon as you buy. Capitals, spaces and dashes do not matter.</div>'"""
    edits.append((old_sheet, new_sheet, "unlockKeySheet(): warn about a prior spend"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    act = working[working.find("async function unlockActivate"):working.find("function unlockErrorText")]
    if "UNLOCK_SPENT_KEY" not in act:
        fail("the marker is never written on success.")
    if act.index("UNLOCK_SPENT_KEY") > act.index("unlockPersistVerified()"):
        fail("the marker is written after the settings write — the order that fails.")
    # The marker must never be in the durability guard's CRIT list, or it gets
    # a _bak twin and doubles the cost of the write most likely to fail.
    crit = re.search(r"const CRIT = \[([^\]]*)\]", working)
    if not crit:
        fail("could not find the durability CRIT list to check.")
    if "unlockSpent" in crit.group(1):
        fail("the spend marker was added to CRIT — that doubles its write cost.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: marker written before the settings write, and outside CRIT")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_spend_marker_check.js")
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

    print("\n✅ a spend now survives the session that made it, and says so before the next tap.")


if __name__ == "__main__":
    main()
