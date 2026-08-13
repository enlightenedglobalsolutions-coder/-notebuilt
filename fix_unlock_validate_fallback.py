#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a key without activation limits is validated, not activated
Run from the same folder as index.html:
    python3 fix_unlock_validate_fallback.py

THE EVIDENCE (production validate, no slot spent, captured today)
------------------------------------------------------------------
    "status":            "granted"
    "limit_activations":  null        <-- activation is NOT enabled
    "usage":              0
    "limit_usage":        3           <-- the "3" is a USAGE limit
    "activation":         null

The dashboard's "0/3" is usage against `limit_usage`, not activations
against `limit_activations`. The sandbox key every earlier proof ran
against had `limit_activations: 3`, so the sandbox chain exercised a code
path the production product does not have. That is the whole
production-vs-sandbox difference, and it is a product configuration
difference rather than an API one.

Polar's own guidance: activation "is only required if you've configured
activation limits". Call `/activate` for a key that has none and it is
refused — which is what the customer hit, and what the previous build
mistranslated into "you have used all your devices".

THE FIX
-------
When `/activate` is refused for any reason OTHER than a proven activation
limit, the app asks `/validate` — the endpoint that fits a key with no
activation limit — and unlocks only if the server itself answers
`status: "granted"`.

This is self-correcting rather than trusting:

  * activation not enabled -> validate says granted   -> unlocked, correctly
  * disabled / revoked key -> validate says otherwise -> stays locked, and
                                                         the refusal message
                                                         from that branch is
                                                         what gets shown
  * genuine activation limit reached -> never reaches the fallback at all,
                                        so the device limit still means
                                        something wherever one is configured

`increment_usage` is deliberately NOT sent: consuming the usage allowance
is not what this call is for, and a key with `limit_usage: 3` would
otherwise be spent down by three unlocks.

ON "ONE NETWORK CALL"
---------------------
The privacy promise is that nothing is sent before the key is entered and
nothing ever again afterwards. That is unchanged. What changes is that a
refused activation may be followed by one validation, at the same moment,
still only because a person tapped Activate. Both are at entry time; the
count after activation is still zero, forever. The privacy page says "your
key" and "once", which stays accurate, and the guard below still holds the
file to exactly the two Polar hosts.

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

    # 1 — the validation probe, used only after a non-limit refusal
    old_helper = """/* Set the moment the server returns a 2xx, and never cleared."""
    new_helper = """/* The endpoint that fits a key carrying no activation limit. Polar refuses
   /activate outright for such a key, and validation is what its own docs
   point at instead. Returns the license record only when the server states
   the key is granted, so nothing here is taken on trust: a disabled or
   revoked key answers with some other status and unlocks nothing.
   increment_usage is deliberately absent — a key with a usage allowance
   must not have it spent down by unlocking. */
async function unlockValidate(key){
  let res;
  try{
    res=await fetch(UNLOCK.API_BASE+'/v1/customer-portal/license-keys/validate',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ key:key, organization_id:UNLOCK.ORG_ID })
    });
  }catch(e){ return null; }
  if(!res.ok) return null;
  let b=null; try{ b=await res.json(); }catch(e){}
  if(b && b.status==='granted') return b;
  return null;
}

/* Set the moment the server returns a 2xx, and never cleared."""
    edits.append((old_helper, new_helper, "unlockValidate()"))

    # 2 — fall back to it for every refusal except a proven limit
    old_tail = """  if(/revoked|disabled|not active|inactive|no longer valid|expired/.test(t))
    return {ok:false, kind:'inactive', detail:det};
  /* Refused for a reason we have not learned to name. Say so, and show what
     was said, rather than reaching for the nearest message that fits. */
  return {ok:false, kind:'refused', detail:det, status:res.status};
}"""
    new_tail = """  /* Not a limit. The most likely reason by far is that this key carries no
     activation limit at all, in which case /activate was never the right
     call and validation is. Ask the server directly rather than guessing
     from the wording: it unlocks only if it answers "granted", so a
     disabled or revoked key falls through to the honest message below. */
  const lic=await unlockValidate(key);
  if(lic){
    settings.unlock={ key:key, activationId:'validated-'+(lic.id||now()),
                      activatedAt:now(), viaValidation:true };
    const wrote=unlockPersistVerified();
    if(!wrote.ok) return {ok:false, kind:'unstored', why:wrote.why};
    return {ok:true, viaValidation:true};
  }
  if(/revoked|disabled|not active|inactive|no longer valid|expired/.test(t))
    return {ok:false, kind:'inactive', detail:det};
  /* Refused for a reason we have not learned to name. Say so, and show what
     was said, rather than reaching for the nearest message that fits. */
  return {ok:false, kind:'refused', detail:det, status:res.status};
}"""
    edits.append((old_tail, new_tail, "unlockActivate(): validate fallback"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 2:
        fail(f"expected exactly 2 fetch( (activate + validate), found {working.count('fetch(')}.")
    # The comment explaining its absence mentions it by name, so match the
    # property form — the only shape that would actually put it in a request.
    if re.search(r"increment_usage\s*:", working):
        fail("increment_usage must never be sent — it spends the usage allowance.")
    hosts = sorted(set(h for h in re.findall(r"https://[a-z0-9.-]+", working) if "polar" in h))
    if hosts != ["https://api.polar.sh", "https://buy.polar.sh"]:
        fail(f"unexpected polar hosts: {hosts}")
    act = working[working.find("async function unlockActivate"):working.find("function unlockErrorText")]
    # A proven limit must never reach the fallback, or the device cap is a lie
    # wherever one is actually configured.
    if act.index("kind:'limit'") > act.index("unlockValidate(key)"):
        fail("the limit branch no longer short-circuits the validation fallback.")
    if "b.status==='granted'" not in working:
        fail("the fallback does not require the server to confirm the key is granted.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: limit short-circuits the fallback; unlock requires a 'granted' answer")
    print("✅ guard: increment_usage never sent; hosts still api/buy.polar.sh only")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_validate_fallback_check.js")
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

    print("\n✅ a key with no activation limit now unlocks the way its own product is configured.")


if __name__ == "__main__":
    main()
