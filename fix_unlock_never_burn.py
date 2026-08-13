#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — INCIDENT: a spent activation could be thrown away silently
Run from the same folder as index.html:
    python3 fix_unlock_never_burn.py

WHAT HAPPENED
-------------
On 2026.08.13-1011, a real production key activated successfully on
Polar's side — all three slots were consumed — while the app never
recorded the unlock and kept inviting another attempt. Settings stayed on
"Free". Three paid activations were spent for nothing.

WHAT IT WAS NOT
---------------
The production response shape. Checked before touching anything:
  * both environments report `polar-version: 2026-04`
  * production's own OpenAPI declares 200 -> LicenseKeyActivationRead with
    `id` REQUIRED at the top level — identical to what sandbox returned

So `body.id` was there to be found, and the sandbox proof that passed this
exact flow was not passing for a reason production could invalidate.

WHERE IT ACTUALLY BREAKS
------------------------
Between "the server said yes" and "the app wrote it down" the shipped code
had exactly two statements and no protection on either:

    settings.unlock={ key:key, activationId:body.id, activatedAt:now() };
    persist.settings();                    // <-- uncaught

`persist.settings()` is `localStorage.setItem(...)`. When that throws —
quota reached on a device with a lot of data, a storage policy refusing
the write — the exception leaves `unlockActivate`, rejects the promise the
click handler is awaiting, and every line after the await is skipped. The
button never re-enables, never shows a message, and sits there reading
"Activating…". A dead-looking tap is exactly what makes a person close the
sheet, reopen it, and spend another activation.

The same silence covers a second family: any 2xx whose body the app fails
to recognise falls through to "Could not activate just now (error 200)" —
which advises a retry that can only ever burn another slot.

Both are the same underlying mistake: the app decided whether an
activation had happened by looking at its own bookkeeping instead of at
the fact that the server had already spent one.

THE FIX
-------
1. **A 2xx IS the activation.** Success is decided on the status code, and
   the activation id is dug out afterwards, best-effort (`id`,
   `activation_id`, `activation.id`). A missing field can no longer discard
   a paid activation — the record is written either way and flagged.

2. **Write, then read it back.** `unlockPersistVerified()` persists and
   then re-reads localStorage to confirm the unlock actually landed. A
   write that throws, or that silently fails to stick, can no longer pass
   for a recorded purchase.

3. **A spent activation never re-arms the button.** If the server said yes
   and the device could not keep it, the button is retired — disabled and
   relabelled — and the message says plainly that the activation was used,
   not to tap again, and what to do instead. A refusal that never reached
   a successful activation (404, 403, offline) is still safe to retry, and
   still offers retry: the distinction is now explicit.

4. **Nothing throws its way out of the click handler.** The await is
   wrapped, and so is the post-success `render()` — a render error can no
   longer make a stored, paid unlock look like nothing happened.

The in-memory unlock is kept even when the write fails, so the session the
customer paid for works immediately; they are told it may not survive a
restart rather than being silently downgraded.

DIAGNOSTIC VALUE
----------------
The failure reason is surfaced verbatim (`QuotaExceededError`, or "it did
not persist"). Whichever of the two families caused this incident, the
next occurrence names itself in one line instead of costing three slots to
narrow down.

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

    # 1 — decide on the status, verify the write, never lose a spent slot
    old_act = """  let body=null; try{ body=await res.json(); }catch(e){}
  if(res.ok && body && body.id){
    settings.unlock={ key:key, activationId:body.id, activatedAt:now() };
    persist.settings();
    return {ok:true};
  }"""
    new_act = """  let body=null; try{ const raw=await res.text(); body=raw?JSON.parse(raw):null; }catch(e){}
  /* A 2xx means the server has already spent one of the activations. That
     is the fact that matters and it is true whatever the body turns out to
     look like, so success is decided on the status and the id is dug out
     afterwards, best effort. Deciding it on a field name instead is how a
     paid activation gets discarded and the customer invited to buy the
     next one with another slot. */
  if(res.ok){
    const id=(body && (body.id || body.activation_id || (body.activation && body.activation.id))) || null;
    settings.unlock={ key:key, activationId:(id || 'unrecorded-'+now()), activatedAt:now() };
    if(!id) settings.unlock.idMissing=true;
    /* Kept in memory above whatever happens below: the session was paid
       for and works now, even if this device refuses to remember it. */
    const wrote=unlockPersistVerified();
    if(!wrote.ok) return {ok:false, kind:'unstored', why:wrote.why};
    return {ok:true, idMissing:!id};
  }"""
    edits.append((old_act, new_act, "unlockActivate(): status decides, write is verified"))

    # 2 — the verified write itself
    old_helper = """/* THE ONLY NETWORK CALL IN THIS APP."""
    new_helper = """/* Write it, then read it straight back. A settings write that throws, or
   that silently fails to land, must never pass for a recorded purchase:
   the activation behind it is already spent and cannot be spent twice. The
   reason is carried out verbatim, because "it did not save" is a support
   ticket and "QuotaExceededError" is a fix. */
function unlockPersistVerified(){
  try{ persist.settings(); }
  catch(e){ return {ok:false, why:(e&&e.name)||'the write failed'}; }
  try{
    const back=JSON.parse(localStorage.getItem(K.settings)||'null');
    if(!(back && back.unlock && back.unlock.activationId)) return {ok:false, why:'it did not persist'};
  }catch(e){ return {ok:false, why:(e&&e.name)||'it could not be read back'}; }
  return {ok:true};
}

/* THE ONLY NETWORK CALL IN THIS APP."""
    edits.append((old_helper, new_helper, "unlockPersistVerified()"))

    # 3 — the handler: nothing escapes it, and a spent slot never re-arms
    old_click = """  go.onclick=async()=>{
    err.textContent='';
    go.disabled=true; go.textContent='Activating\\u2026';
    const r=await unlockActivate(inp.value);
    if(r.ok){ closeSheet(); render(); unlockThanks(resume); return; }
    /* The typed key stays in the field. Losing it to an error message is
       how a person gives up on a thing they have already paid for. */
    go.disabled=false; go.textContent=(r.kind==='offline')?'Try again':'Activate';
    err.textContent=unlockErrorText(r);
    inp.focus();
  };"""
    new_click = """  go.onclick=async()=>{
    err.textContent='';
    go.disabled=true; go.textContent='Activating\\u2026';
    /* Nothing below may throw its way out of this handler. An exception
       here leaves the button stuck mid-spin with no message, which reads as
       a dead tap — and a dead tap is what makes a person close the sheet
       and spend another activation. */
    let r;
    try{ r=await unlockActivate(inp.value); }
    catch(e){ r={ok:false, kind:'crashed', detail:(e&&(e.name||e.message))||'unexpected error'}; }
    if(r.ok){
      /* A render fault must not make a stored, paid unlock look like
         nothing happened. */
      try{ closeSheet(); render(); }catch(e){}
      unlockThanks(resume,r);
      return;
    }
    /* A refusal that never reached a successful activation is safe to
       retry, and still offers it. One that did is not: the slot is already
       spent, so the button is retired instead of re-armed. */
    if(r.kind==='unstored' || r.kind==='crashed'){
      go.disabled=true; go.textContent='Do not tap again';
      err.textContent=unlockErrorText(r);
      return;
    }
    /* The typed key stays in the field. Losing it to an error message is
       how a person gives up on a thing they have already paid for. */
    go.disabled=false; go.textContent=(r.kind==='offline')?'Try again':'Activate';
    err.textContent=unlockErrorText(r);
    inp.focus();
  };"""
    edits.append((old_click, new_click, "unlockKeySheet(): no escape, no blind re-arm"))

    # 4 — words for the two states that must never invite a retry
    old_txt = """  if(r.kind==='limit')   return 'This key has already been activated on all of its devices."""
    new_txt = """  if(r.kind==='unstored') return 'Your key worked — the server accepted it and this device is unlocked now. But it could not be saved here ('+(r.why||'unknown reason')+'), so it may not survive closing the app. Do NOT tap Activate again: that would spend another activation for nothing. Write your key down, then reopen and check Settings — if it still says Free, contact EGS before trying again.';
  if(r.kind==='crashed')  return 'Something went wrong after the request was sent, so it is not certain whether an activation was used'+(r.detail?' ('+r.detail+')':'')+'. Do not tap again yet. Close this, open Settings, and look at the Unlock row — if it says Unlocked, you are done.';
  if(r.kind==='limit')   return 'This key has already been activated on all of its devices."""
    edits.append((old_txt, new_txt, "unlockErrorText(): unstored + crashed"))

    # 5 — say it when the server gave us nothing to hold on to
    old_thanks = """function unlockThanks(resume){
  sheet('<h2>Unlocked</h2>'"""
    new_thanks = """function unlockThanks(resume,info){
  /* Recorded, working, and honest about the one thing that was odd. */
  const quirk=(info&&info.idMissing)
    ? '<br><br>Recorded on this device, though the server did not send back an activation reference. Worth mentioning to EGS if you ever need support.'
    : '';
  sheet('<h2>Unlocked</h2>'"""
    edits.append((old_thanks, new_thanks, "unlockThanks(): carry the quirk"))

    old_thanks_body = """      +'Thank you — this is what keeps EGS building.'
    +'</div>'"""
    new_thanks_body = """      +'Thank you — this is what keeps EGS building.'+quirk
    +'</div>'"""
    edits.append((old_thanks_body, new_thanks_body, "unlockThanks(): render the quirk"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    if "if(res.ok && body && body.id)" in working:
        fail("the field-name success test survived.")
    # The only persist of an unlock must be the verified one.
    act_start = working.find("async function unlockActivate")
    act_end = working.find("function unlockErrorText")
    if act_start < 0 or act_end < 0 or act_end <= act_start:
        fail("could not isolate unlockActivate to check its writes.")
    body_act = working[act_start:act_end]
    if "persist.settings();" in body_act:
        fail("unlockActivate still writes settings directly instead of via the verified path.")
    if "unlockPersistVerified()" not in body_act:
        fail("unlockActivate does not use the verified write.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")
    for stray in ["19004685-5905-41a6-bd1f-acbd5b8abb6d", "CFC46983"]:
        if stray in working:
            fail(f"sandbox material would ship — found {stray!r}")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: success decided on status, not on a field name")
    print("✅ guard: unlockActivate writes only through the verified path")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_never_burn_check.js")
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

    print("\n✅ a spent activation is now recorded or reported — never discarded, never retried blind.")


if __name__ == "__main__":
    main()
