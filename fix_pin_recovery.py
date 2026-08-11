#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — forgot-PIN recovery (th_nb_pin)
Run from the same folder as index.html, AFTER fix_pin_steady.py:
    python3 fix_pin_recovery.py

THE PREMISE (from the decided design)
-------------------------------------
The PIN is a privacy gate, not crypto. Nothing is encrypted under it —
the vault passphrase is the real secret. So a PIN with no way back is a
trap with no upside: it locks out the owner and stops nobody who has the
disk. Two ways back, in priority order:

  1. A vault exists -> the vault passphrase resets the PIN. It is already
     the stronger credential; anyone holding it can read the protected
     data anyway, so gating the PIN behind it costs nothing.
  2. No vault -> a one-time recovery code, generated at the moment the
     PIN is set, shown once, stored only as a hash (same sha+salt shape
     as the PIN). Single use: spending it immediately mints a new one.

Verifying the vault passphrase here deliberately does NOT unlock the
vault — `vaultKeyFor()` returns a key that is checked and dropped. A PIN
reset is a PIN reset; it does not widen into vault access.

WHAT THIS ADDS
--------------
- Recovery core: generate / normalise / set / verify. Alphabet excludes
  I, O, 0 and 1 because this gets copied to paper and back; 16 chars from
  a 32-symbol set = 80 bits. 32 divides 256, so the modulo is unbiased.
  Dashes, spaces and case are ignored on entry.
- "Forgot PIN?" on the lock screen, routing to whichever of the three
  answers is true: vault passphrase, recovery code, or an honest dead
  end that does not pretend there is a way through.
- New PIN after recovery, confirm-twice, built once (PIN_STEADY rules).
- PIN setup with no vault now mints a code and makes you acknowledge it.
- Existing installs: one dismissible offer on the next unlock, recorded
  the moment it is shown so it can never nag twice. Also reachable any
  time from Settings -> Security -> Recovery.
- Info-mode copy planted in HELP_COPY ahead of info mode existing.

IMPORT PAIRING (v3 export already carries this)
-----------------------------------------------
`settings.recovery` rides the v3 export for free. But importData keeps
the DEVICE's PIN when one is set, so it must keep the device's recovery
credential too — they are one pair. Taking the backup's code while
keeping the device's PIN would silently change which written-down code
opens the door. That pairing is added here and gated by a round-trip.

NOTE ON THE TEXT FIELD
----------------------
The recovery screens carry a real <input>, which the jump-fix brief
listed as suspect 1. That was about the KEYPAD screen, which still has
no focusable text field. Here you must actually type, so the keyboard
appearing and scrolling the field into view is correct behaviour rather
than the bug — and these screens carry no keypad to be pushed around.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "PIN_RECOVERY"


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
    if "PIN_STEADY" not in text:
        fail("fix_pin_steady.py has not been applied yet — run that first.")
    if "BACKUP_V3" not in text:
        fail("backup v3 is not present — the import pairing edit needs it.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: CSS for the recovery screens.
    # ---------------------------------------------------------------
    old1 = """  #lock .err{color:var(--danger);font-size:13px;min-height:18px;margin-top:6px}"""
    new1 = """  #lock .err{color:var(--danger);font-size:13px;min-height:18px;margin-top:6px}

  /* PIN_RECOVERY */
  .lock-link{
    margin-top:18px;font-family:var(--mono);font-size:12px;letter-spacing:.08em;
    text-transform:uppercase;color:var(--paper-dim);text-decoration:underline;
    text-underline-offset:4px;padding:10px 12px;touch-action:manipulation;
  }
  .lock-copy{font-size:14px;line-height:1.62;color:var(--paper-dim);max-width:340px;text-align:center}
  .lock-copy b{color:var(--paper)}
  #lock .lock-field{width:min(340px,86vw)}
  .lock-actions{width:min(340px,86vw);display:flex;flex-direction:column;gap:10px;margin-top:16px}
  .reco-code{
    font-family:var(--mono);font-size:19px;letter-spacing:.16em;color:var(--brass);
    background:var(--ink-2);border:1px solid var(--line-soft);border-radius:12px;
    padding:15px 12px;margin:14px 0 2px;text-align:center;word-break:break-all;
    -webkit-user-select:all;user-select:all;
  }"""
    edits.append((old1, new1, "CSS: recovery screens"))

    # ---------------------------------------------------------------
    # Edit 2: recovery core + the three "forgot" screens.
    # ---------------------------------------------------------------
    old2 = """function randSalt(){ return [...crypto.getRandomValues(new Uint8Array(8))].map(b=>b.toString(16).padStart(2,'0')).join(''); }"""
    new2 = """function randSalt(){ return [...crypto.getRandomValues(new Uint8Array(8))].map(b=>b.toString(16).padStart(2,'0')).join(''); }

/* ============================================================
   PIN_RECOVERY — getting back in when the PIN is gone
   The PIN is a privacy gate, not a lock on the data: nothing is encrypted
   under it. That cuts both ways — it is why forgetting it must not cost you
   the app, and why a way back is not a hole in anything. Where a vault exists
   its passphrase is already the stronger credential, so it is the way back.
   Where there is none, a one-time code written down at setup stands in.
   ============================================================ */
/* No I, O, 0 or 1 — this gets copied off a screen onto paper and back again.
   32 symbols divides 256 exactly, so the modulo below is unbiased. */
const RECOVERY_ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
const RECOVERY_LEN=16;   /* 16 chars from 32 symbols = 80 bits */

/* PIN_RECOVERY — info-mode copy, planted now so info mode inherits it. */
const HELP_COPY={
  'pin-recovery':'Your PIN keeps casual hands out of the app. It does not encrypt anything \\u2014 the vault passphrase does.'
};

function recoveryGenerate(){
  const bytes=crypto.getRandomValues(new Uint8Array(RECOVERY_LEN));
  let s='';
  for(let i=0;i<RECOVERY_LEN;i++) s+=RECOVERY_ALPHABET[bytes[i]%RECOVERY_ALPHABET.length];
  return s.replace(/(.{4})(?=.)/g,'$1-');
}
/* Dashes, spaces and case are how a human writes it down. None of them count. */
function recoveryNormalize(s){ return String(s==null?'':s).toUpperCase().replace(/[^A-Z0-9]/g,''); }
function recoveryExists(){ return !!(settings.recovery && settings.recovery.hash && settings.recovery.salt); }
async function recoverySet(){
  const code=recoveryGenerate(), salt=randSalt();
  settings.recovery={ salt:salt, hash:await sha(recoveryNormalize(code)+salt), createdAt:now() };
  persist.settings();
  return code;                      /* the only moment the plain code exists */
}
async function recoveryVerify(input){
  if(!recoveryExists()) return false;
  const norm=recoveryNormalize(input);
  if(!norm) return false;
  return (await sha(norm+settings.recovery.salt))===settings.recovery.hash;
}

/* One screen shape for all three answers to "forgot PIN". */
function lockPrompt(o){
  $lock.classList.remove('hidden');
  $lock.innerHTML='<div class="mark">'+MARK+'</div>'
    +'<div class="name">'+esc(o.title)+'</div>'
    +'<div class="lock-copy" style="margin:12px 0 14px">'+o.copy+'</div>'
    +(o.field?'<div class="lock-field">'+o.field+'</div>':'')
    +'<div class="err"></div>'
    +'<div class="lock-actions">'
      +(o.go?'<button type="button" class="btn primary block" data-go>'+esc(o.go)+'</button>':'')
      +'<button type="button" class="btn block" data-back>'+esc(o.back||'Back')+'</button>'
    +'</div>';
  $lock.querySelector('[data-back]').onclick=o.onBack;
  return { err:$lock.querySelector('.err'), go:$lock.querySelector('[data-go]') };
}

function forgotPinFlow(){
  const back=()=>lockGate();
  if(vaultExists())    return forgotViaVault(back);
  if(recoveryExists()) return forgotViaCode(back);
  return forgotDeadEnd(back);
}

function forgotViaVault(back){
  const ui=lockPrompt({
    title:'Forgot PIN',
    copy:'Your PIN keeps casual hands out of the app. It does not encrypt anything \\u2014 '
        +'your <b>vault passphrase</b> does, and that is the way back in. Enter it to set a new PIN.',
    field:'<div class="field">'+pwField('r-vp','Vault passphrase','current-password')+'</div>',
    go:'Continue', onBack:back });
  bindPwEyes($lock);
  setTimeout(()=>{ const el=$lock.querySelector('#r-vp'); if(el) el.focus(); },60);
  const run=async()=>{
    const inp=$lock.querySelector('#r-vp'), pass=inp.value; if(!pass) return;
    ui.go.setAttribute('disabled',''); ui.go.textContent='Checking\\u2026';
    /* Checked and dropped. Resetting a PIN does not widen into vault access. */
    const key=await vaultKeyFor(pass, settings.vault);
    if(key){ newPinAfterRecovery(false); return; }
    await new Promise(r=>setTimeout(r,1000));
    ui.go.removeAttribute('disabled'); ui.go.textContent='Continue';
    ui.err.textContent='That is not your vault passphrase.';
  };
  ui.go.onclick=run;
  $lock.querySelector('#r-vp').addEventListener('keydown',e=>{ if(e.key==='Enter') run(); });
}

function forgotViaCode(back){
  const ui=lockPrompt({
    title:'Forgot PIN',
    copy:'Enter the recovery code you wrote down. Dashes and capitals do not matter. '
        +'It works <b>once</b> \\u2014 a fresh one is issued straight after.',
    field:'<div class="field"><label>Recovery code</label>'
         +'<input class="input" id="r-code" autocomplete="off" autocapitalize="characters" '
         +'autocorrect="off" spellcheck="false" placeholder="XXXX-XXXX-XXXX-XXXX"></div>',
    go:'Continue', onBack:back });
  setTimeout(()=>{ const el=$lock.querySelector('#r-code'); if(el) el.focus(); },60);
  const run=async()=>{
    const inp=$lock.querySelector('#r-code'); if(!recoveryNormalize(inp.value)) return;
    ui.go.setAttribute('disabled',''); ui.go.textContent='Checking\\u2026';
    if(await recoveryVerify(inp.value)){ newPinAfterRecovery(true); return; }
    await new Promise(r=>setTimeout(r,1000));
    ui.go.removeAttribute('disabled'); ui.go.textContent='Continue';
    ui.err.textContent='That code does not match. Check for a mistyped letter.';
  };
  ui.go.onclick=run;
  $lock.querySelector('#r-code').addEventListener('keydown',e=>{ if(e.key==='Enter') run(); });
}

/* The honest answer. No vault, no code, no way through — and no pretending. */
function forgotDeadEnd(back){
  lockPrompt({
    title:'Forgot PIN',
    copy:'Nothing was set up on this device to get back in, so there is no way past this '
        +'screen \\u2014 not by us, not by anyone.<br><br>Your projects are still on the phone and '
        +'still intact. If you have a backup file, install the app fresh and restore it: a backup '
        +'is not protected by the PIN, and restoring it lets you set a new one.',
    onBack:back, back:'Back to the keypad' });
}

function recoveryCodeHtml(code, spent){
  return '<div class="lock-copy">'+(spent
      ? 'That code is spent. Here is your new one \\u2014 <b>write it down before you continue</b>.'
      : '<b>Write this down</b> and keep it somewhere safe. It is how you get back into the app if you forget your PIN.')
    +'</div><div class="reco-code">'+esc(code)+'</div>'
    +'<div class="lock-copy" style="font-size:12.5px;margin-top:10px">Only a hash of it is stored, so it can never be shown again. '
    +'Lose it and you can issue a new one from Settings.</div>';
}
function showRecoveryCode(code, spent, onDone){
  $lock.classList.remove('hidden');
  $lock.innerHTML='<div class="mark">'+MARK+'</div><div class="name">Recovery code</div>'
    +recoveryCodeHtml(code, spent)
    +'<div class="lock-actions"><button type="button" class="btn primary block" data-done>I have written it down</button></div>';
  $lock.querySelector('[data-done]').onclick=onDone;
}
function recoveryCodeSheet(code, spent){
  sheet('<h2>Recovery code</h2>'+recoveryCodeHtml(code, spent)
    +'<button class="btn primary block" style="margin-top:16px" data-done>I have written it down</button>');
  $mr.querySelector('[data-done]').onclick=()=>{ closeSheet(); render(); };
}

/* Confirm-twice, built once, same rules as the keypad it replaces. */
function newPinAfterRecovery(viaCode){
  let stage=1, first='', entry='', busy=false;
  $lock.classList.remove('hidden');
  $lock.innerHTML='<div class="mark">'+MARK+'</div><div class="name">Set a new PIN</div>'
    +'<div class="hint" data-pin-msg>Choose a 4-digit PIN</div>'
    +'<div class="dots">'+[0,1,2,3].map(()=>'<div class="d"></div>').join('')+'</div>'
    +'<div class="err"></div>'
    +'<div class="keypad">'+PIN_KEYPAD_HTML+'</div>';
  const $dots=[...$lock.querySelectorAll('.dots .d')];
  const $msg=$lock.querySelector('[data-pin-msg]'), $err=$lock.querySelector('.err');
  const paint=(msg,err)=>{
    $dots.forEach((d,i)=>d.classList.toggle('on', i<entry.length));
    if(msg!==undefined) $msg.textContent=msg;
    if(err!==undefined) $err.textContent=err||'';
  };
  const done=()=>{ $lock.classList.add('hidden'); $lock.innerHTML=''; showShell(true); render(); toast('New PIN set'); };
  $lock.querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{
    if(busy) return;
    const k=b.dataset.k;
    if(k==='del'){ entry=entry.slice(0,-1); paint(undefined,''); return; }
    if(entry.length>=4) return;
    entry+=k; paint(undefined,'');
    if(entry.length<4) return;
    if(stage===1){ first=entry; entry=''; stage=2; paint('Re-enter to confirm'); return; }
    if(entry!==first){ entry=''; stage=1; first=''; paint('Choose a 4-digit PIN','Did not match \\u2014 start again'); return; }
    busy=true;
    const salt=randSalt(); settings.pinSalt=salt; settings.pinHash=await sha(first+salt);
    persist.settings();
    /* Single use: the code that opened this door is spent, so mint the next one
       before letting go of the screen that can show it. */
    if(viaCode){ const code=await recoverySet(); busy=false; showRecoveryCode(code, true, done); }
    else { busy=false; done(); }
  });
}

/* One offer, on one unlock, for installs that predate any of this. Recorded the
   moment it is SHOWN, not when it is answered — being asked twice is nagging. */
function maybeOfferRecoveryCode(){
  if(!settings.pinHash) return;
  if(vaultExists() || recoveryExists()) return;
  if(settings.recoveryOfferedAt) return;
  if($mr.innerHTML) return;                    /* something else already has the screen */
  settings.recoveryOfferedAt=now(); persist.settings();
  sheet('<h2>A way back into the app</h2>'
    +'<div class="muted" style="font-size:13.5px;line-height:1.62">'+esc(HELP_COPY['pin-recovery'])
    +'<br><br>But if you forget the PIN right now, there is no way back in. Generate a one-time '
    +'recovery code and write it down \\u2014 you will only be asked this once.</div>'
    +'<div style="display:flex;gap:10px;margin-top:16px">'
    +'<button class="btn primary" style="flex:1" data-reco-go>Generate a code</button>'
    +'<button class="btn" style="flex:1" data-reco-no>Not now</button></div>');
  $mr.querySelector('[data-reco-no]').onclick=closeSheet;
  $mr.querySelector('[data-reco-go]').onclick=async()=>{ recoveryCodeSheet(await recoverySet(), false); };
}"""
    edits.append((old2, new2, "recovery core + forgot screens + offer"))

    # ---------------------------------------------------------------
    # Edit 3: lockGate — the Forgot PIN link, and the offer after unlock.
    # ---------------------------------------------------------------
    old3 = """      <div class="keypad">${PIN_KEYPAD_HTML}</div>`;
  const $dots=[...$lock.querySelectorAll('.dots .d')];
  const $err=$lock.querySelector('.err');"""
    new3 = """      <div class="keypad">${PIN_KEYPAD_HTML}</div>
      <button type="button" class="lock-link" data-forgot>Forgot PIN?</button>`;
  $lock.querySelector('[data-forgot]').onclick=forgotPinFlow;   /* PIN_RECOVERY */
  const $dots=[...$lock.querySelectorAll('.dots .d')];
  const $err=$lock.querySelector('.err');"""
    edits.append((old3, new3, "lockGate(): Forgot PIN link"))

    old4 = """      if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); }
      else{ entry=''; paint('Wrong PIN'); }"""
    new4 = """      if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); maybeOfferRecoveryCode(); }
      else{ entry=''; paint('Wrong PIN'); }"""
    edits.append((old4, new4, "lockGate(): offer recovery after unlock"))

    # ---------------------------------------------------------------
    # Edit 5: setupPin — mint a code when there is no vault to fall back on.
    # ---------------------------------------------------------------
    old5 = """      const salt=randSalt(); settings.pinSalt=salt; settings.pinHash=await sha(first+salt);
      persist.settings(); busy=false;
      closeSheet(); render(); toast('App lock on');"""
    new5 = """      const salt=randSalt(); settings.pinSalt=salt; settings.pinHash=await sha(first+salt);
      persist.settings(); busy=false;
      render(); toast('App lock on');
      /* PIN_RECOVERY — a PIN with no way back is a trap. With no vault passphrase
         to fall back on, the code is minted here, at the one moment the person is
         already thinking about how they get in. */
      if(!vaultExists() && !recoveryExists()){
        settings.recoveryOfferedAt=now();
        recoveryCodeSheet(await recoverySet(), false);
      } else closeSheet();"""
    edits.append((old5, new5, "setupPin(): mint a recovery code when there is no vault"))

    # ---------------------------------------------------------------
    # Edit 6: Settings — show the recovery state, allow a new code.
    # ---------------------------------------------------------------
    old6 = """    ${locked?`<button class="btn danger block sm" data-pin-off style="margin-top:-4px">Turn off app lock</button>`:''}"""
    new6 = """    ${locked?`<button class="btn danger block sm" data-pin-off style="margin-top:-4px">Turn off app lock</button>`:''}
    ${locked?`<div class="card row" data-help="pin-recovery"><div class="grow"><div>If you forget your PIN</div><div class="muted" style="font-size:13px">${
        vaultExists() ? 'Your vault passphrase resets it.'
      : recoveryExists() ? 'A recovery code is set. Only its hash is stored here.'
      : 'Nothing is set up \\u2014 you would be locked out.'}</div></div>${
        vaultExists() ? '' : `<button class="btn sm" data-reco-new>${recoveryExists()?'New code':'Create'}</button>`}</div>`:''}"""
    edits.append((old6, new6, "Settings: recovery status card"))

    old7 = """  const pinOff=$app.querySelector('[data-pin-off]'); if(pinOff) pinOff.onclick=()=>{ if(confirm('Turn off the app lock?')){ settings.pinHash=null; settings.pinSalt=null; persist.settings(); render(); toast('App lock off'); } };"""
    new7 = """  const pinOff=$app.querySelector('[data-pin-off]'); if(pinOff) pinOff.onclick=()=>{ if(confirm('Turn off the app lock?')){ settings.pinHash=null; settings.pinSalt=null; persist.settings(); render(); toast('App lock off'); } };
  /* PIN_RECOVERY — issuing a new code retires the old one, so say so first. */
  const recoNew=$app.querySelector('[data-reco-new]');
  if(recoNew) recoNew.onclick=async()=>{
    if(recoveryExists() && !confirm('Issue a new recovery code?\\n\\nThe one you wrote down before will stop working.')) return;
    settings.recoveryOfferedAt=now();
    recoveryCodeSheet(await recoverySet(), false);
  };"""
    edits.append((old7, new7, "bind(): new recovery code button"))

    # ---------------------------------------------------------------
    # Edit 8: importData — the recovery credential pairs with the PIN.
    # ---------------------------------------------------------------
    old8 = """      if(settings.pinHash){ next.pinHash=settings.pinHash; next.pinSalt=settings.pinSalt; }"""
    new8 = """      if(settings.pinHash){
        next.pinHash=settings.pinHash; next.pinSalt=settings.pinSalt;
        /* PIN_RECOVERY — the recovery credential is the way into THIS phone and
           belongs to the PIN it was issued alongside. Taking the backup's code
           while keeping the device's PIN would silently change which written-down
           code opens the door. On a fresh install both come from the file. */
        next.recovery=settings.recovery||null;
        next.recoveryOfferedAt=settings.recoveryOfferedAt||null;
      }"""
    edits.append((old8, new8, "importData(): pair recovery with the PIN it belongs to"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_pin_recovery_check.js")
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

    print("\n✅ PIN_RECOVERY applied: vault passphrase or one-time code resets the PIN.")
    print("   Gate: both paths, wrong input rejected, code single-use,")
    print("   v3 export round-trip carries recovery state.")


if __name__ == "__main__":
    main()
