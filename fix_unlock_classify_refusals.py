#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the limit message may only appear for an actual limit
Run from the same folder as index.html:
    python3 fix_unlock_classify_refusals.py

INCIDENT #3
-----------
A key showing GRANTED, Usage 0/3, Never Validated in the Polar dashboard
was refused in-app with "This key has already been activated on all of its
devices. You do not need a second one — restoring a Notebuilt backup
carries the unlock across without using a slot."

Every word of that is advice, and all of it was wrong. The key had been
disabled and re-enabled during slot cleanup; whatever the server was
actually saying, the app was not listening.

RULED OUT FIRST, BY READING THE SHIPPED CODE
---------------------------------------------
* **Stale state in the request.** The body is exactly
  `{key, organization_id, label}` — no activation id, nothing carried from
  an earlier attempt, nothing derived from settings.
* **The do-not-tap latch.** `unlockSpent` and the persisted marker only
  drive the warning banner and the `spent` branch, which has its own
  distinct message. The limit copy is reachable only from `kind:'limit'`.
* **The service worker.** Its fetch handler begins
  `if (req.method !== 'GET') return;` — activation is a POST, so the SW
  never sees it and cannot be replaying a cached 403. This mattered because
  "the message persisted across re-enabling the key" is exactly what a
  cached response looks like. It is not one.

THE BUG
-------
    if(res.status===403 || /activation limit|limit reached|already activated/i.test(det))
      return {ok:false, kind:'limit', detail:det};

`res.status===403 ||` — every 403 becomes "limit reached", whatever the
server said. Polar answers 403 NotPermitted for a family of refusals: a
disabled key, a revoked benefit, a key that is not currently active. All of
them arrived wearing the one message the app had for 403, and that message
tells the customer to stop trying and restore a backup instead.

That `||` is mine, from incident #1, written when no real limit response
had been seen and a status was the only thing to hold on to. A real one
WAS seen later in sandbox —

    403 {"error":"NotPermitted","detail":"License key activation limit already reached"}

— and the matcher was never tightened afterwards. Evidence arrived and the
guess stayed.

THE FIX
-------
Classification is driven by what the server SAYS, with the status used only
where it is unambiguous on its own:

  404              -> not recognised
  422              -> the key is not a shape the server can read
  5xx              -> the server is having trouble
  detail says limit-> the limit message, and only here
  detail says revoked/disabled/inactive/expired -> said plainly, quoting it
  any other 4xx    -> refused, with the server's own words shown verbatim

The unknown case no longer invents a reason. It shows the status and the
detail, so the next refusal diagnoses itself instead of costing a round
trip — and so no customer is ever again told what to do about a state
nobody established.

None of these spend an activation, so every one of them leaves the button
armed. Only a 2xx latches.

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

    # 1 — classify from what the server said
    old_cls = """  const det=unlockErrorDetail(body);
  if(res.status===404) return {ok:false, kind:'unknown'};
  /* The exact status for an exhausted key has not been seen from a real
     one. Match on what it says as well as what it returns, so the clear
     message survives either answer. */
  if(res.status===403 || /activation limit|limit reached|already activated/i.test(det))
    return {ok:false, kind:'limit', detail:det};
  return {ok:false, kind:'other', detail:det, status:res.status};
}"""
    new_cls = """  const det=unlockErrorDetail(body);
  const t=det.toLowerCase();
  /* Status only where it means one thing on its own. */
  if(res.status===404) return {ok:false, kind:'unknown'};
  if(res.status===422) return {ok:false, kind:'malformed', detail:det};
  if(res.status>=500)  return {ok:false, kind:'server', detail:det, status:res.status};
  /* Polar answers 403 NotPermitted for a whole family of refusals — a spent
     key, a disabled one, a revoked benefit. Reading the status alone told a
     customer with a GRANTED 0/3 key that they were out of devices, and told
     them to stop trying. So the limit message is reachable only when the
     server actually says limit. */
  if(/activation limit|limit already reached|limit reached/.test(t))
    return {ok:false, kind:'limit', detail:det};
  if(/revoked|disabled|not active|inactive|no longer valid|expired/.test(t))
    return {ok:false, kind:'inactive', detail:det};
  /* Refused for a reason we have not learned to name. Say so, and show what
     was said, rather than reaching for the nearest message that fits. */
  return {ok:false, kind:'refused', detail:det, status:res.status};
}"""
    edits.append((old_cls, new_cls, "unlockActivate(): classify from the server's words"))

    # 2 — an honest message per state, none of them advice-shaped without proof
    old_txt = """  if(r.kind==='unknown') return 'That key was not recognised. Copy the whole line out of the email, dashes and all.';"""
    new_txt = """  if(r.kind==='unknown') return 'That key was not recognised. Copy the whole line out of the email, dashes and all.';
  if(r.kind==='malformed') return 'The server could not read that as a key. Copy the whole line out of the email — it should look like '+((UNLOCK.KEY_PREFIX?UNLOCK.KEY_PREFIX+'-':'')+'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX')+'. Nothing was used up.';
  if(r.kind==='server')   return 'The activation server is having trouble right now (error '+(r.status||'5xx')+')'+(r.detail?' — '+r.detail:'')+'. Nothing was used up. Try again in a minute.';
  if(r.kind==='inactive') return 'The server says this key is not currently active'+(r.detail?' \\u2014 \\u201c'+r.detail+'\\u201d':'')+'. Nothing was used up. If it was just re-enabled, give it a moment and tap again; if it stays this way, contact EGS with the email you bought it with.';
  if(r.kind==='refused')  return 'The server refused the activation'+(r.status?' (error '+r.status+')':'')+(r.detail?' \\u2014 \\u201c'+r.detail+'\\u201d':'')+'. Nothing was used up. Tap again if you like; if it keeps saying this, send that message to EGS and it will be diagnosed from it.';"""
    edits.append((old_txt, new_txt, "unlockErrorText(): a message per proven state"))

    # 3 — the old catch-all is now unreachable; keep it honest anyway
    old_other = """  return 'Could not activate just now'+(r.detail?' — '+r.detail:(r.status?' (error '+r.status+')':''))+'. Your key is still here; try again in a moment.';"""
    new_other = """  /* Nothing routes here any more — every refusal is named above — but a
     future kind must not inherit a reassuring sentence by accident. */
  return 'Could not activate just now'+(r.detail?' — '+r.detail:(r.status?' (error '+r.status+')':''))+'. Nothing was used up; your key is still here.';"""
    edits.append((old_other, new_other, "unlockErrorText(): honest fallback"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if "res.status===403 ||" in working:
        fail("a bare 403 can still be classified as the limit.")
    act = working[working.find("async function unlockActivate"):working.find("function unlockErrorText")]
    if "kind:'limit'" not in act:
        fail("the limit classification vanished entirely.")
    # The limit branch must be guarded by the message text, never by a status.
    # The condition contains parentheses of its own (`.test(t)`), so take the
    # text between the last `if(` and the limit return rather than trying to
    # balance them with a character class.
    lim = act.find("return {ok:false, kind:'limit'")
    cond = act[act.rfind("if(", 0, lim):lim]
    if not cond:
        fail("could not isolate the limit branch to check its condition.")
    if "res.status" in cond:
        fail("the limit branch still keys on a status code.")
    # The advice sentence may live only in the limit message.
    for kind_msg in ["kind==='inactive'", "kind==='refused'", "kind==='server'", "kind==='malformed'"]:
        seg = working[working.find(kind_msg):working.find(kind_msg) + 600]
        if "do not need a second one" in seg or "restoring a Notebuilt backup" in seg:
            fail(f"advice-shaped copy leaked into {kind_msg}")
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: the limit branch keys on the server's words, not on a status")
    print("✅ guard: no advice-shaped copy outside the proven limit case")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_classify_check.js")
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

    print("\n✅ every refusal now says what the server said, and only a real limit says limit.")


if __name__ == "__main__":
    main()
