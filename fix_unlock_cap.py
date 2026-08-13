#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the 3-project free cap, and the key that lifts it
Run from the same folder as index.html:
    python3 fix_unlock_cap.py

WHAT THIS BUILDS
----------------
A free tier of 3 projects, and a one-time $29 CAD unlock that removes the
cap. The unlock is a Polar license key: entered once, activated with a
single network call, then never mentioned to anyone again.

WHY THESE SHAPES
----------------
* **Cap governs creation, never data.** The gate sits at the top of
  `openHouseSheet(edit=null)` — the one door every "new project" goes
  through. A restore, a shared-project import and the backup importer all
  push onto `houses` directly and are therefore uncapped by construction,
  not by a flag someone has to remember to check. Getting your own data
  back onto a phone is not a purchase decision.

* **Somebody already past 3 is not a prospect who ignored a limit.**
  `settings.priorProjects` records, once, what this device held the first
  time the capped build ran. If that is more than 3, the pitch opens by
  saying their projects are theirs forever and free, and only then
  mentions that the cap applies to new ones. Their data never locks,
  hides or expires — and the first monetization moment they ever see
  should read as fair rather than as a rug-pull.

* **Unlocked means an activation happened.** Not "a key is present" —
  `unlockIsOn()` requires `activationId`. A key typed while offline
  leaves the app free, which is exactly what makes the retry path safe:
  nothing half-succeeds.

* **The unlock rides the backup on purpose.** `settings` already travels
  whole inside a v3 export, so `settings.unlock` transfers with zero new
  export code, and a restore carries the unlock across WITHOUT burning an
  activation slot. Deliberate for a buy-once product. A v2 file has no
  unlock field, restores locked, and says nothing about it — which is
  correct, because it predates the feature.

* **One call, and the privacy page had to stop lying.** Before this,
  index.html contained zero `fetch(` — and the privacy page said so, in
  those words: "no background calls, no hidden pings." Activation makes
  that sentence false unless it is rewritten, so the privacy page now
  names the one call, when it happens, and that nothing follows it. The
  guard below asserts the file still holds exactly one `fetch(`.

POLAR — VERIFIED AGAINST THE LIVE API, NOT AGAINST MEMORY
---------------------------------------------------------
The customer-portal endpoint is the one designed for client apps:

    POST {API_BASE}/v1/customer-portal/license-keys/activate
    {"key":…, "organization_id":…, "label":…}

Probed 2026-08-13 from this machine:
  * `access-control-allow-origin: *` on both sandbox and production, and
    the OPTIONS preflight answers 200 with POST + content-type allowed.
    So it is callable from the browser.
  * **No Authorization header is involved** — nothing secret ships into
    this public repo. That was the stop-and-report condition; it does not
    apply.
  * A bad key answers `404 {"error":"ResourceNotFound","detail":"Not
    found"}`.

Org and product were read out of the live checkout link:
  organization_id  dd1c6def-7b26-4d7d-86eb-fa3f915074a5
  product          "Notebuilt-Full Unlock", 2900 cad, benefit type
                   license_keys — "Unlocks unlimited projects in Notebuilt"

STILL UNPROVEN, AND HONEST ABOUT IT
------------------------------------
The 200-success body and the activation-limit refusal have not been seen
— that needs a real issued key, which needs a Polar login. Two
consequences are handled defensively rather than guessed at:

  1. `unlockActivate()` treats any non-404 error whose text matches
     /activation limit|limit reached|already activated/ as the
     limit case, and 403 as well, rather than trusting one status code.
     Anything else falls through to a message that shows the server's own
     words instead of inventing them.
  2. `unlockNormalizeKey()` rebuilds the canonical 8-4-4-4-12 shape when
     the typed key has 32 alphanumerics, and otherwise passes the key
     through uppercased with whitespace stripped. Dashes are structural
     in a Polar key, so they are rebuilt, not discarded — "ignore dashes"
     cannot mean "delete them" or a correct key would 404. If the issued
     format turns out to carry a prefix, this is the one function to
     revisit.

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


# ---------------------------------------------------------------- config
UNLOCK_CONFIG = """  wise: 'WISE_PAYMENT_LINK'
};
/* ============================================================
   UNLOCK_CONFIG — every string and id the paid unlock needs, in one
   place, on purpose.

   PLAY STORE: an Android build may not send buyers to an outside
   checkout (Play Billing policy). Set EXTERNAL_PURCHASE to false and the
   Buy button disappears from the pitch and from Settings; key entry,
   activation and the cap all keep working untouched. Nothing else in the
   file needs editing, and no string lives anywhere but here.

   SANDBOX: point API_BASE at 'https://sandbox-api.polar.sh' and ORG_ID at
   the sandbox organisation. Nothing else changes — the endpoint path and
   payload are identical on both.
   ============================================================ */
const UNLOCK = {
  FREE_PROJECTS: 3,
  PRICE: '$29 CAD',
  EXTERNAL_PURCHASE: true,
  CHECKOUT_URL: 'https://buy.polar.sh/polar_cl_kXuldC4PBwGSgWh8ETQgDD2an3GZcL2qG4UnT2rPI54',
  API_BASE: 'https://api.polar.sh',
  ORG_ID: 'dd1c6def-7b26-4d7d-86eb-fa3f915074a5',
  LABEL: 'Notebuilt'
};
const PAYMENT_TABS = ["""


# --------------------------------------------------------------- runtime
UNLOCK_RUNTIME = """                  categories:()=>save(K.categories,categories) };

/* ============================================================
   UNLOCK — the free cap, and the key that lifts it.
   Strings and ids live in UNLOCK (search UNLOCK_CONFIG). This is the
   behaviour, and it is the only part of the app that touches a network.
   ============================================================ */

/* Unlocked means an activation completed — not that a key is present.
   A key typed with no signal leaves the app free, which is what makes the
   retry path safe: there is no half-unlocked state to get stuck in. */
function unlockIsOn(){ return !!(settings.unlock && settings.unlock.activationId); }

/* What this device held the first time the capped build ran, written
   once and never again. Someone already past the cap did not ignore a
   limit — the app changed under them, and the pitch owes them different
   words than a new user gets. Riding settings, it travels in a backup,
   so their standing survives a restore onto a new phone. */
function unlockPriorProjects(){
  if(typeof settings.priorProjects==='number') return settings.priorProjects;
  settings.priorProjects=houses.length; persist.settings();
  return settings.priorProjects;
}

/* Creation only. A restore, a backup import and a shared project all push
   onto houses directly without ever routing through openHouseSheet, so
   they are uncapped by construction rather than by a flag someone has to
   remember. Getting your own data back is not a purchase decision. */
function unlockCanCreateProject(){ return unlockIsOn() || houses.length < UNLOCK.FREE_PROJECTS; }

function unlockActivatedOn(){
  const t=settings.unlock&&settings.unlock.activatedAt;
  if(!t) return '';
  try{ return new Date(t).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}); }
  catch(e){ return ''; }
}

/* Forgiving the way the recovery code is forgiving: case and spacing are
   how a human copies something off a screen, and neither counts. Dashes
   are the exception — they are part of the key, so they are rebuilt into
   the canonical shape rather than dropped. Stripping them would turn a
   correct key into a 404. One request goes out, never a fan of guesses. */
function unlockNormalizeKey(s){
  const up=String(s==null?'':s).toUpperCase().replace(/\\s+/g,'');
  const core=up.replace(/[^A-Z0-9]/g,'');
  if(core.length===32) return core.replace(/^(.{8})(.{4})(.{4})(.{4})(.{12})$/,'$1-$2-$3-$4-$5');
  return up;
}

function unlockErrorDetail(b){
  if(!b) return '';
  if(typeof b.detail==='string') return b.detail;
  if(Array.isArray(b.detail)&&b.detail.length&&b.detail[0]&&b.detail[0].msg) return String(b.detail[0].msg);
  return typeof b.error==='string'?b.error:'';
}

/* THE ONLY NETWORK CALL IN THIS APP. It happens when a person taps
   Activate, and at no other moment — not at launch, not on a timer, not
   to re-check afterwards. Nothing about the person or their data is sent:
   the body is the key, the organisation id, and a fixed label. */
async function unlockActivate(rawKey){
  const key=unlockNormalizeKey(rawKey);
  if(!key) return {ok:false, kind:'empty'};
  /* Asked while plainly offline, say so without a doomed request first. */
  if(navigator.onLine===false) return {ok:false, kind:'offline'};
  let res;
  try{
    res=await fetch(UNLOCK.API_BASE+'/v1/customer-portal/license-keys/activate',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ key:key, organization_id:UNLOCK.ORG_ID, label:UNLOCK.LABEL })
    });
  }catch(e){ return {ok:false, kind:'offline'}; }
  let body=null; try{ body=await res.json(); }catch(e){}
  if(res.ok && body && body.id){
    settings.unlock={ key:key, activationId:body.id, activatedAt:now() };
    persist.settings();
    return {ok:true};
  }
  const det=unlockErrorDetail(body);
  if(res.status===404) return {ok:false, kind:'unknown'};
  /* The exact status for an exhausted key has not been seen from a real
     one. Match on what it says as well as what it returns, so the clear
     message survives either answer. */
  if(res.status===403 || /activation limit|limit reached|already activated/i.test(det))
    return {ok:false, kind:'limit', detail:det};
  return {ok:false, kind:'other', detail:det, status:res.status};
}

function unlockErrorText(r){
  if(r.kind==='empty')   return 'Enter the key from your email.';
  if(r.kind==='offline') return 'Activating needs the internet for a moment — the one time Notebuilt ever asks. Your key is still here: tap Try again once you are back online.';
  if(r.kind==='unknown') return 'That key was not recognised. Copy the whole line out of the email, dashes and all.';
  if(r.kind==='limit')   return 'This key has already been activated on all of its devices. You do not need a second one — restoring a Notebuilt backup carries the unlock across without using a slot.';
  return 'Could not activate just now'+(r.detail?' — '+r.detail:(r.status?' (error '+r.status+')':''))+'. Your key is still here; try again in a moment.';
}

/* resume=true means they were stopped mid-action at the cap, so finishing
   the unlock should hand back the thing they were trying to do. */
function unlockPitch(resume){
  const free=UNLOCK.FREE_PROJECTS;
  const grand=unlockPriorProjects()>free;
  const head=grand?'Your projects are yours — free, forever':'Unlock unlimited projects';
  const lead=grand
    ? 'You have <b style="color:var(--paper)">'+houses.length+' projects</b>, from before Notebuilt had a limit. They stay yours forever, free — nothing here locks, hides or expires.<br><br>'
      +'Unlocking removes the '+free+'-project cap on new ones.'
    : 'Notebuilt is free for '+free+' projects, and you are using all '+free+'.<br><br>'
      +'Unlocking gives you as many as you like. Everything else — photos, the vault, backups, the calculator — is already yours and always was.';
  sheet('<h2>'+head+'</h2>'
    +'<div class="muted" style="font-size:13.5px;line-height:1.62">'+lead+'<br><br>'
      +'<b style="color:var(--paper)">'+esc(UNLOCK.PRICE)+', once.</b> No subscription, no account, no email address needed.<br><br>'
      +'Activating asks the internet for a moment, one time. After that Notebuilt never contacts anything again — it is not re-checked at launch, or ever.<br><br>'
      +'Your key is kept in your settings, so it travels inside your backup. Restore that onto your next phone and it is still unlocked.'
    +'</div>'
    +(UNLOCK.EXTERNAL_PURCHASE
        ? '<a class="btn primary block" style="margin-top:14px" href="'+esc(UNLOCK.CHECKOUT_URL)+'" target="_blank" rel="noopener noreferrer">Unlock — '+esc(UNLOCK.PRICE)+'</a>'
        : '')
    +'<button class="btn block" data-unlock-key style="margin-top:10px">I already have a key</button>'
    +'<button class="btn block" data-unlock-later style="margin-top:10px">Not now</button>');
  $mr.querySelector('[data-unlock-key]').onclick=()=>unlockKeySheet('',resume);
  $mr.querySelector('[data-unlock-later]').onclick=()=>closeSheet();
}

function unlockKeySheet(prefill,resume){
  sheet('<h2>Enter your key</h2>'
    +'<div class="muted" style="font-size:13px;line-height:1.6;margin-bottom:12px">It arrives by email as soon as you buy. Capitals, spaces and dashes do not matter.</div>'
    +'<div class="field"><input class="input" id="u-key" placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX" autocomplete="off" autocapitalize="characters" autocorrect="off" spellcheck="false" value="'+esc(prefill||'')+'"></div>'
    +'<div class="err" id="u-err"></div>'
    +'<button class="btn primary block" id="u-go" style="margin-top:12px">Activate</button>'
    +'<button class="btn block" id="u-back" style="margin-top:10px">Back</button>');
  const inp=$mr.querySelector('#u-key'), err=$mr.querySelector('#u-err'), go=$mr.querySelector('#u-go');
  setTimeout(()=>inp.focus(),50);
  $mr.querySelector('#u-back').onclick=()=>unlockPitch(resume);
  go.onclick=async()=>{
    err.textContent='';
    go.disabled=true; go.textContent='Activating\\u2026';
    const r=await unlockActivate(inp.value);
    if(r.ok){ closeSheet(); render(); unlockThanks(resume); return; }
    /* The typed key stays in the field. Losing it to an error message is
       how a person gives up on a thing they have already paid for. */
    go.disabled=false; go.textContent=(r.kind==='offline')?'Try again':'Activate';
    err.textContent=unlockErrorText(r);
    inp.focus();
  };
}

function unlockThanks(resume){
  sheet('<h2>Unlocked</h2>'
    +'<div class="muted" style="font-size:13.5px;line-height:1.62">'
      +'Unlimited projects, from now on.<br><br>'
      +'That was the only time Notebuilt will contact anything. It will not check again — not at launch, not ever.<br><br>'
      +'Your key sits in your settings, so your next backup carries it. Restore that onto a new phone and it stays unlocked, without spending an activation.<br><br>'
      +'Thank you — this is what keeps EGS building.'
    +'</div>'
    +'<button class="btn primary block" id="u-done" style="margin-top:14px">'+(resume?'New project':'Done')+'</button>');
  $mr.querySelector('#u-done').onclick=()=>{ closeSheet(); if(resume) openHouseSheet(); };
}

/* Recorded on the first run of the capped build, before anything can ask. */
unlockPriorProjects();"""


# ------------------------------------------------------------------ main
def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — config block, next to the payment config it belongs beside
    old_cfg = """  wise: 'WISE_PAYMENT_LINK'
};
const PAYMENT_TABS = ["""
    edits.append((old_cfg, UNLOCK_CONFIG, "UNLOCK_CONFIG block"))

    # 2 — the runtime, right after persist (which its stamp call needs)
    old_rt = """                  categories:()=>save(K.categories,categories) };"""
    edits.append((old_rt, UNLOCK_RUNTIME, "unlock runtime + prior-projects stamp"))

    # 3 — the cap, on the one door every new project goes through
    old_gate = """function openHouseSheet(edit=null){
  const h=edit||{};"""
    new_gate = """function openHouseSheet(edit=null){
  /* UNLOCK — creation only, and only when this is not an edit. Every other
     way a project appears (restore, backup import, shared file) bypasses
     this function entirely and stays uncapped. */
  if(!edit && !unlockCanCreateProject()){ unlockPitch(true); return; }
  const h=edit||{};"""
    edits.append((old_gate, new_gate, "openHouseSheet(): cap gate on create"))

    # 4 — the Settings row
    old_about = """    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    new_about = """    <div class="sec-head"><span class="label">Unlock</span><span class="rule"></span></div>
    <div class="card row" data-help="unlock"><div class="grow"><div>${unlockIsOn()?'Unlocked \\u2713':'Free \\u2014 '+UNLOCK.FREE_PROJECTS+' projects'}</div>
      <div class="muted" style="font-size:13px">${unlockIsOn()
        ? 'Unlimited projects. Activated '+esc(unlockActivatedOn())+', and never re-checked since.'
        : houses.length>UNLOCK.FREE_PROJECTS
          ? houses.length+' projects, all yours to keep. '+esc(UNLOCK.PRICE)+' once to add more.'
          : houses.length+' of '+UNLOCK.FREE_PROJECTS+' used. '+esc(UNLOCK.PRICE)+' once, for unlimited projects.'}</div></div>
      ${unlockIsOn()?'':'<button class="btn sm" data-unlock-open>Unlock</button>'}</div>

    <div class="sec-head"><span class="label">About</span><span class="rule"></span></div>"""
    edits.append((old_about, new_about, "renderSettings(): Unlock row"))

    # 5 — bind it
    old_bind = """  const vLock=$app.querySelector('[data-vault-lock]'); if(vLock) vLock.onclick=()=>{ vaultRelock(); toast('Protected projects locked'); };"""
    new_bind = """  const vLock=$app.querySelector('[data-vault-lock]'); if(vLock) vLock.onclick=()=>{ vaultRelock(); toast('Protected projects locked'); };
  const unlockOpen=$app.querySelector('[data-unlock-open]'); if(unlockOpen) unlockOpen.onclick=()=>unlockPitch(false);"""
    edits.append((old_bind, new_bind, "settings binding: Unlock button"))

    # 6 — info copy
    old_help = """const HELP_COPY={
  'pin-recovery':'Your PIN keeps casual hands out of the app. It does not encrypt anything \\u2014 the vault passphrase does.'
};"""
    new_help = """const HELP_COPY={
  'pin-recovery':'Your PIN keeps casual hands out of the app. It does not encrypt anything \\u2014 the vault passphrase does.',
  'unlock':'Free covers three projects, with every feature switched on \\u2014 photos, the vault, backups, the calculator. Unlocking lifts the limit on how many projects you keep, once, for one payment. Entering your key sends it to our payment provider a single time to activate it; after that Notebuilt never contacts anything again, and the unlock is never re-checked. The key is stored in your settings, so your backup carries it to your next phone.'
};"""
    edits.append((old_help, new_help, "HELP_COPY: unlock"))

    # 7 — the privacy page can no longer claim there are no calls at all
    old_priv = """      If you use <b style="color:var(--paper)">Share project</b>, that hands a file to your phone's own share sheet — you choose where it goes. We're not part of that transfer.<br><br>
      That's the whole list. No analytics, no background calls, no hidden pings."""
    new_priv = """      If you use <b style="color:var(--paper)">Share project</b>, that hands a file to your phone's own share sheet — you choose where it goes. We're not part of that transfer.<br><br>
      If you unlock the app, tapping <b style="color:var(--paper)">Activate</b> sends your key once to Polar, who handle the payment, to register it. That single moment is the only time. Nothing of yours goes with it — no projects, no photos, no identifier for you — and once it succeeds the unlock is never re-checked, at launch or ever.<br><br>
      That's the whole list. No analytics, no background calls, no hidden pings."""
    edits.append((old_priv, new_priv, "renderPrivacy(): name the one activation call"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- mutation guards -------------------------------------------------
    # Exactly one network call may exist in this file, and it must be the
    # activation one. This is the claim the privacy page now makes in print.
    n_fetch = working.count("fetch(")
    if n_fetch != 1:
        fail(f"expected exactly 1 fetch( in the file, found {n_fetch}.")
    if "customer-portal/license-keys/activate" not in working:
        fail("the activation endpoint is missing.")
    for token, why in [
        ("Authorization", "an auth header must never appear — this repo is public"),
        ("POLAR_API_KEY", "no Polar secret may ship"),
        ("polar_oat_", "an org access token must never ship"),
    ]:
        if token in working:
            fail(f"{why} — found {token!r}")
    if "if(!edit && !unlockCanCreateProject())" not in working:
        fail("the cap gate did not land.")
    # The importers must stay uncapped: neither may have grown a gate.
    for fn in ["async function importData(e){", "async function importSharedProject(e){"]:
        idx = working.find(fn)
        if idx < 0:
            fail(f"could not find {fn!r} to check it stayed uncapped.")
        if "unlockCanCreateProject" in working[idx:idx + 4000]:
            fail(f"{fn!r} appears to have been capped — import must never be blocked.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: exactly one fetch( in the file, and it is the activation call")
    print("✅ guard: no token, key or Authorization header anywhere")
    print("✅ guard: cap gate present; both import paths still uncapped")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_unlock_cap_check.js")
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

    print("\n✅ UNLOCK applied: free at 3 projects, key lifts it, one call and never again.")


if __name__ == "__main__":
    main()
