#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 2 of 5: the setup ceremony, the unlock prompt, the Settings section
Run this from the same folder as your index.html:
    python3 fix_vault2_ceremony.py

Requires fix_vault1_core.py to have run first.

The ceremony is four full-screen gates with no skips, because the one thing
that must not happen is somebody protecting a project casually and finding out
six months later that the passphrase is gone:

  1. The warning, in Edwin's words, verbatim.
  2. Passphrase twice, minimum 8 characters, with the hint that a short
     sentence beats P@ss1.
  3. A checkbox that must be ticked before Continue lights up.
  4. The project locks immediately and you have to open it once, right then,
     before any data can go in. If what you wrote down doesn't work, this is
     the moment to find out — not later.

Also adds the unlock sheet (wrong passphrase costs a deliberate one-second
pause before the next attempt — no lockout, no counter), the progress overlay
that encrypt-in-place drives, and a Protected projects section in Settings with
a manual Lock now button.

Backs up first, applies edits with exact-match anchors, aborts atomically
if anything doesn't match, and validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "VAULT_CEREMONY"
REQUIRES = "VAULT_CORE"

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
    if REQUIRES not in text:
        fail(f"{REQUIRES} not found — run fix_vault1_core.py first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: CSS for the ceremony overlay, lock chip and progress overlay
    # ---------------------------------------------------------------
    old1 = r"""  .hidden{display:none!important}
  hr.div{border:none;border-top:1px solid var(--line-soft);margin:14px 0}"""

    new1 = r"""  /* VAULT_CEREMONY */
  #vault{
    position:fixed;inset:0;z-index:110;background:var(--ink);
    display:flex;flex-direction:column;overflow-y:auto;
    padding:calc(var(--safe-t) + 26px) 22px calc(var(--safe-b) + 26px);
    max-width:680px;margin:0 auto;
  }
  #vault .v-mark{display:grid;place-items:center;color:var(--brass);margin-bottom:14px}
  #vault .v-mark svg{width:46px;height:46px}
  #vault h2{font-family:var(--serif);font-size:23px;margin:0 0 14px;text-align:center}
  #vault .v-copy{font-size:15px;line-height:1.62;color:var(--paper-dim);margin-bottom:20px}
  #vault .v-copy b{color:var(--paper)}
  #vault .v-steps{
    font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;
    color:var(--paper-faint);text-align:center;margin-bottom:18px;
  }
  #vault .v-actions{margin-top:auto;padding-top:20px;display:flex;flex-direction:column;gap:10px}
  .v-err{color:var(--danger);font-size:13px;min-height:19px;margin:2px 0 6px}
  .v-check{
    display:flex;align-items:flex-start;gap:12px;cursor:pointer;font-size:14px;line-height:1.5;
    background:var(--ink-2);border:1px solid var(--line-soft);border-radius:var(--radius);padding:14px;
  }
  .v-check input{width:24px;height:24px;flex:none;accent-color:var(--brass);margin-top:1px}
  .btn[disabled]{opacity:.38;pointer-events:none}
  .lock-chip{
    display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:10.5px;
    letter-spacing:.1em;text-transform:uppercase;color:var(--brass);border:1px solid var(--brass);
    border-radius:999px;padding:4px 9px;white-space:nowrap;
  }
  .lock-chip svg{width:12px;height:12px}
  #vault-busy{
    position:fixed;inset:0;z-index:120;background:rgba(10,12,15,.94);display:flex;
    flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:30px;text-align:center;
  }
  #vault-busy .vb-t{font-family:var(--serif);font-size:19px}
  #vault-busy .vb-s{font-family:var(--mono);font-size:12px;color:var(--paper-dim);letter-spacing:.06em}
  #vault-busy .vb-bar{width:min(280px,80vw);height:5px;border-radius:3px;background:var(--ink-3);overflow:hidden}
  #vault-busy .vb-fill{height:100%;background:var(--brass);width:0%;transition:width .18s}

  .hidden{display:none!important}
  hr.div{border:none;border-top:1px solid var(--line-soft);margin:14px 0}"""
    edits.append((old1, new1, "CSS: ceremony overlay, lock chip, progress overlay"))

    # ---------------------------------------------------------------
    # Edit 2: the overlay element
    # ---------------------------------------------------------------
    old2 = r"""<div id="annotate" class="hidden"></div>
<div id="toast"></div>"""
    new2 = r"""<div id="annotate" class="hidden"></div>
<div id="vault" class="hidden"></div>
<div id="toast"></div>"""
    edits.append((old2, new2, "add #vault overlay element"))

    # ---------------------------------------------------------------
    # Edit 3: the ceremony / unlock / progress machinery
    # ---------------------------------------------------------------
    old3 = r"""/* ============================================================
   BOOT
   ============================================================ */"""

    new3 = r"""/* ============================================================
   VAULT_CEREMONY — setup, unlock, and the encrypt/decrypt progress overlay
   ============================================================ */
const $vault=document.getElementById('vault');
function vaultOverlay(html){
  $vault.classList.remove('hidden');
  $vault.innerHTML=html;
  document.body.style.overflow='hidden';
}
function vaultCloseOverlay(){
  $vault.classList.add('hidden'); $vault.innerHTML='';
  document.body.style.overflow='';
}

/* ---------- progress overlay (driven by encrypt/decrypt-in-place) ---------- */
let _vaultBusyEl=null;
function vaultBusy(title, sub, pct){
  if(!_vaultBusyEl){
    _vaultBusyEl=document.createElement('div'); _vaultBusyEl.id='vault-busy';
    _vaultBusyEl.innerHTML='<div class="vb-t"></div><div class="vb-s"></div><div class="vb-bar"><div class="vb-fill"></div></div>';
    document.body.appendChild(_vaultBusyEl);
  }
  _vaultBusyEl.querySelector('.vb-t').textContent=title||'';
  _vaultBusyEl.querySelector('.vb-s').textContent=sub||'';
  const bar=_vaultBusyEl.querySelector('.vb-bar'), fill=_vaultBusyEl.querySelector('.vb-fill');
  if(pct==null) bar.style.display='none';
  else { bar.style.display=''; fill.style.width=Math.max(0,Math.min(100,pct))+'%'; }
  /* Yield so the bar actually paints between records. setTimeout, NOT
     requestAnimationFrame: rAF does not fire while the app is backgrounded, so
     an rAF-based yield stalls a whole encrypt/decrypt pass for as long as the
     app is out of sight. setTimeout keeps firing either way. */
  return new Promise(r=>setTimeout(r,0));
}
function vaultBusyDone(){ if(_vaultBusyEl){ _vaultBusyEl.remove(); _vaultBusyEl=null; } }

/* ---------- the setup ceremony: gates 1-3 ----------
   Resolves true once settings.vault exists and the key is in memory. */
function vaultRunCeremony(){
  return new Promise(resolve=>{
    const cancel=()=>{ vaultCloseOverlay(); resolve(false); };

    /* Gate 1 — the warning. Verbatim. This is the whole point of the ceremony. */
    const gate1=()=>{
      vaultOverlay('<div class="v-steps">Step 1 of 4 &middot; Read this</div>'
        +'<div class="v-mark">'+I.lock+'</div>'
        +'<h2>Before you protect anything</h2>'
        +'<div class="v-copy">This is where you keep your passwords and sensitive data. '
        +'Keep this passphrase in your mind <b>AND</b> written down in a safe place. '
        +'Treat it like your passport, like your gold bars.<br><br>'
        +'There is <b>NO recovery</b>. EGS cannot reset, recover, or bypass this &mdash; '
        +'not won\'t, <b>CAN\'T</b>.</div>'
        +'<div class="v-actions">'
        +'<button class="btn primary block" data-v-next>I understand &mdash; continue</button>'
        +'<button class="btn block" data-v-cancel>Cancel</button></div>');
      $vault.querySelector('[data-v-next]').onclick=()=>gate2();
      $vault.querySelector('[data-v-cancel]').onclick=cancel;
    };

    /* Gate 2 — the passphrase, twice. */
    const gate2=(err)=>{
      vaultOverlay('<div class="v-steps">Step 2 of 4 &middot; Choose a passphrase</div>'
        +'<h2>Your vault passphrase</h2>'
        +'<div class="v-copy">Separate from your app PIN, and not stored anywhere. '
        +'Longer beats clever &mdash; <b>a short sentence beats P@ss1</b>. '
        +'Minimum '+VAULT_MIN_PASS+' characters.</div>'
        +'<div class="field"><label>Passphrase</label><input class="input" type="password" id="v-p1" autocomplete="new-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'
        +'<div class="field"><label>Type it again</label><input class="input" type="password" id="v-p2" autocomplete="new-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'
        +'<div class="v-err">'+esc(err||'')+'</div>'
        +'<div class="v-actions">'
        +'<button class="btn primary block" data-v-next>Continue</button>'
        +'<button class="btn block" data-v-cancel>Cancel</button></div>');
      setTimeout(()=>{ const el=$vault.querySelector('#v-p1'); if(el) el.focus(); },60);
      $vault.querySelector('[data-v-cancel]').onclick=cancel;
      $vault.querySelector('[data-v-next]').onclick=()=>{
        const p1=$vault.querySelector('#v-p1').value, p2=$vault.querySelector('#v-p2').value;
        if(p1.length<VAULT_MIN_PASS){ gate2('Use at least '+VAULT_MIN_PASS+' characters.'); return; }
        if(p1!==p2){ gate2('Those two do not match.'); return; }
        gate3(p1);
      };
    };

    /* Gate 3 — the forced acknowledgement. Continue stays dead until it's ticked. */
    const gate3=(pass)=>{
      vaultOverlay('<div class="v-steps">Step 3 of 4 &middot; Write it down</div>'
        +'<h2>Put it somewhere safe</h2>'
        +'<div class="v-copy">Now, before you go any further. Not in this app &mdash; on paper, '
        +'or wherever you keep the things you cannot afford to lose.</div>'
        +'<label class="v-check"><input type="checkbox" id="v-ack"><span>I have written my '
        +'passphrase down and stored it safely. I understand a lost passphrase means my '
        +'protected data is gone forever.</span></label>'
        +'<div class="v-actions">'
        +'<button class="btn primary block" data-v-next disabled>Continue</button>'
        +'<button class="btn block" data-v-cancel>Cancel</button></div>');
      const ack=$vault.querySelector('#v-ack'), next=$vault.querySelector('[data-v-next]');
      ack.onchange=()=>{ if(ack.checked) next.removeAttribute('disabled'); else next.setAttribute('disabled',''); };
      $vault.querySelector('[data-v-cancel]').onclick=cancel;
      next.onclick=()=>{ if(ack.checked) create(pass); };
    };

    /* Derive the key and store salt + verifier. The passphrase itself is never
       written down anywhere by us — only the ciphertext of a known string. */
    const create=async (pass)=>{
      await vaultBusy('Setting up your vault','Deriving your key — this takes a moment');
      try{
        const salt=b64FromBytes(crypto.getRandomValues(new Uint8Array(16)));
        _vaultKey=await vaultDeriveKey(pass, salt);
        const verifier=await vaultSealText(VAULT_VERIFIER_TEXT);
        settings.vault={ salt, verifier, migration:null };
        persist.settings();
        vaultTouch();
        vaultBusyDone(); vaultCloseOverlay(); resolve(true);
      }catch(e){
        _vaultKey=null; vaultBusyDone();
        gate2('Could not set up the vault — try again.');
      }
    };

    gate1();
  });
}

/* Gate 4 — the project is locked as of right now, and you open it once here
   before anything can go into it. No skip: proving the passphrase works is the
   entire reason this gate exists. */
function vaultVerificationGate(){
  return new Promise(resolve=>{
    vaultRelock(true);
    const draw=(err)=>{
      vaultOverlay('<div class="v-steps">Step 4 of 4 &middot; Prove it works</div>'
        +'<div class="v-mark">'+I.lock+'</div>'
        +'<h2>Unlock it once, now</h2>'
        +'<div class="v-copy">Your project is locked. Open it with the passphrase you just '
        +'wrote down &mdash; before you put anything in it. If what you wrote down doesn\'t '
        +'work, this is the moment to find out.</div>'
        +'<div class="field"><label>Vault passphrase</label><input class="input" type="password" id="v-vp" autocomplete="current-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'
        +'<div class="v-err">'+esc(err||'')+'</div>'
        +'<div class="v-actions"><button class="btn primary block" data-v-go>Unlock</button></div>');
      setTimeout(()=>{ const el=$vault.querySelector('#v-vp'); if(el) el.focus(); },60);
      const go=async()=>{
        const btn=$vault.querySelector('[data-v-go]'), inp=$vault.querySelector('#v-vp');
        const pass=inp.value; if(!pass) return;
        btn.setAttribute('disabled',''); btn.textContent='Unlocking…';
        if(await vaultUnlock(pass)){ vaultCloseOverlay(); resolve(true); return; }
        await new Promise(r=>setTimeout(r,1000));
        draw('That is not the passphrase. Your data is untouched — try again.');
      };
      $vault.querySelector('[data-v-go]').onclick=go;
      $vault.querySelector('#v-vp').addEventListener('keydown',e=>{ if(e.key==='Enter') go(); });
    };
    draw();
  });
}

/* ---------- the everyday unlock ---------- */
function vaultUnlockSheet(opts){
  opts=opts||{};
  const draw=(err)=>{
    sheet('<h2>'+esc(opts.title||'Unlock protected projects')+'</h2>'
      +'<div class="muted" style="font-size:13px;margin-bottom:14px">'
      +esc(opts.body||'Enter your vault passphrase. This is not your app PIN.')+'</div>'
      +'<div class="field"><input class="input" type="password" id="v-up" placeholder="Vault passphrase" autocomplete="current-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'
      +'<div class="v-err">'+esc(err||'')+'</div>'
      +'<button class="btn primary block" id="v-ugo">Unlock</button>');
    setTimeout(()=>{ const el=$mr.querySelector('#v-up'); if(el) el.focus(); },60);
    const go=async()=>{
      const btn=$mr.querySelector('#v-ugo'), inp=$mr.querySelector('#v-up');
      const pass=inp.value; if(!pass) return;
      btn.setAttribute('disabled',''); btn.textContent='Unlocking…';
      if(await vaultUnlock(pass)){
        closeSheet();
        if(opts.onOpen) opts.onOpen(); else render();
        return;
      }
      /* Wrong passphrase costs a deliberate one-second pause. No lockout, no counter. */
      await new Promise(r=>setTimeout(r,1000));
      draw('That passphrase did not open the vault.');
    };
    $mr.querySelector('#v-ugo').onclick=go;
    $mr.querySelector('#v-up').addEventListener('keydown',e=>{ if(e.key==='Enter') go(); });
  };
  draw();
}

function vaultStatusLine(){
  if(!vaultExists()) return 'Not set up — nothing on this device is encrypted yet.';
  return vaultUnlocked()
    ? 'Unlocked. Relocks after 15 minutes idle, or the moment you leave the app.'
    : 'Locked. Your vault passphrase opens it.';
}
function protectedCount(){ return houses.filter(h=>h.protected).length; }

/* TODO — change passphrase: verify the old one, derive a key from the new one,
   then re-encrypt every protected record and rewrite the verifier. Must be
   atomic the same way encrypt-in-place is, or a half-rekeyed vault is
   unopenable by either passphrase. Deliberately not built yet. */

/* ============================================================
   BOOT
   ============================================================ */"""
    edits.append((old3, new3, "ceremony, unlock sheet, progress overlay"))

    # ---------------------------------------------------------------
    # Edit 4: Settings — Protected projects section
    # ---------------------------------------------------------------
    old4 = r"""    ${locked?`<button class="btn danger block sm" data-pin-off style="margin-top:-4px">Turn off app lock</button>`:''}
"""
    new4 = r"""    ${locked?`<button class="btn danger block sm" data-pin-off style="margin-top:-4px">Turn off app lock</button>`:''}

    <div class="sec-head"><span class="label">Protected projects</span><span class="rule"></span></div>
    <div class="card row"><div class="grow"><div>Vault</div><div class="muted" style="font-size:13px">${esc(vaultStatusLine())}</div></div>
      ${vaultUnlocked()?`<button class="btn sm" data-vault-lock>Lock now</button>`:''}</div>
    <div class="card muted" style="font-size:12.5px;line-height:1.6;margin-top:-4px">${
      protectedCount()
        ? `${protectedCount()} project${protectedCount()===1?'':'s'} protected. Turn protection on or off from a project's Edit screen.`
        : `Open a project, tap Edit, and switch on <b style="color:var(--paper)">Protect this project</b> to put its notes, to-dos, specs and photos behind a passphrase of their own.`
    }</div>
"""
    edits.append((old4, new4, "Settings: Protected projects section"))

    # ---------------------------------------------------------------
    # Edit 5: bind the Lock now button
    # ---------------------------------------------------------------
    old5 = r"""  const exp=$app.querySelector('[data-export]'); if(exp) exp.onclick=exportData;"""
    new5 = r"""  const vLock=$app.querySelector('[data-vault-lock]'); if(vLock) vLock.onclick=()=>{ vaultRelock(); toast('Protected projects locked'); };
  const exp=$app.querySelector('[data-export]'); if(exp) exp.onclick=exportData;"""
    edits.append((old5, new5, "bind(): Lock now button"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_vault2_check.js")
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

    print("\n✅ Vault 2/5 applied: setup ceremony, unlock prompt, Settings section.")
    print("   Next: fix_vault3_render.py")

if __name__ == "__main__":
    main()
