#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Vault 7: show-passphrase toggle
Run this from the same folder as your index.html:
    python3 fix_vault7_showpass.py

Requires the vault scripts.

A standard eye toggle on every passphrase field, default hidden, each field
independent. The setup pair is the reason this exists: with no recovery, a
double-typo made behind dots at creation time is the single worst outcome the
whole feature can produce — you would not find out until the day you needed the
data, and by then nothing can be done. Being able to look at what you typed
before you commit to it is the cheapest possible defence against that.

There are FOUR fields, not three: setup, confirm, the step-4 verification gate,
and the everyday unlock sheet. The verification gate is an unlock field, so it
gets the same treatment — leaving it out would be the one place you cannot check
your typing at exactly the moment you are proving the passphrase works.

Colours are pinned to the app's own tokens (--paper-dim resting, --brass when
revealed) rather than to system or inherited colours, so the pressed and resting
states stay a deliberate contrast pair.

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
MARKER = "VAULT_EYE"
REQUIRES = ["VAULT_CEREMONY"]

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
    for req in REQUIRES:
        if req not in text:
            fail(f"{req} not found — run the vault scripts first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: eye icons
    # ---------------------------------------------------------------
    old = r"""  lock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',"""
    new = r"""  lock:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',
  /* VAULT_EYE */
  eye:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="2.8"/></svg>',
  eyeOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M10.6 6.6A9.9 9.9 0 0 1 12 5.5c6.4 0 10 6.5 10 6.5a18 18 0 0 1-3.1 3.9M6.2 8.1A18 18 0 0 0 2 12s3.6 6.5 10 6.5a9.8 9.8 0 0 0 3.5-.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><path d="M3 3l18 18"/></svg>',"""
    edits.append((old, new, "eye / eyeOff icons"))

    # ---------------------------------------------------------------
    # Edit 2: CSS
    # ---------------------------------------------------------------
    old = r"""  .v-check input{width:24px;height:24px;flex:none;accent-color:var(--brass);margin-top:1px}"""
    new = r"""  .v-check input{width:24px;height:24px;flex:none;accent-color:var(--brass);margin-top:1px}
  /* VAULT_EYE — resting and revealed are a deliberate contrast pair, pinned to
     the app's own tokens rather than to inherited or system colours. */
  .pw-wrap{position:relative;display:block}
  .pw-wrap .input{padding-right:52px}
  .pw-eye{
    position:absolute;right:3px;top:50%;transform:translateY(-50%);
    width:44px;height:44px;border-radius:10px;display:grid;place-items:center;
    background:none;color:var(--paper-dim);
  }
  .pw-eye:active{background:var(--ink-3)}
  .pw-eye svg{width:20px;height:20px;display:block}
  .pw-eye[aria-pressed="true"]{color:var(--brass)}"""
    edits.append((old, new, "CSS: eye toggle"))

    # ---------------------------------------------------------------
    # Edit 3: the field builder + binder
    # ---------------------------------------------------------------
    old = r"""const $vault=document.getElementById('vault');"""
    new = r"""const $vault=document.getElementById('vault');

/* VAULT_EYE — every passphrase field can be revealed. Default hidden, one
   toggle per field, no global "show all". A hidden double-typo at creation is
   the worst thing this feature can do to someone, because there is no recovery
   and no way to find out until it is far too late. */
function pwField(id, placeholder, autocomplete){
  return '<span class="pw-wrap">'
    +'<input class="input" type="password" id="'+id+'"'
    +(placeholder?' placeholder="'+esc(placeholder)+'"':'')
    +' autocomplete="'+(autocomplete||'current-password')+'"'
    +' autocapitalize="off" autocorrect="off" spellcheck="false">'
    +'<button type="button" class="pw-eye" data-pw-eye="'+id+'"'
    +' aria-label="Show passphrase" aria-pressed="false">'+I.eye+'</button>'
    +'</span>';
}
function bindPwEyes(scope){
  scope.querySelectorAll('[data-pw-eye]').forEach(b=>b.onclick=()=>{
    const inp=scope.querySelector('#'+b.getAttribute('data-pw-eye')); if(!inp) return;
    const reveal = inp.type==='password';
    inp.type = reveal ? 'text' : 'password';
    b.setAttribute('aria-pressed', reveal?'true':'false');
    b.setAttribute('aria-label', reveal?'Hide passphrase':'Show passphrase');
    b.innerHTML = reveal ? I.eyeOff : I.eye;
    /* keep the caret where it was — retyping from scratch is the thing we are
       trying to avoid */
    const v=inp.value; inp.focus(); try{ inp.setSelectionRange(v.length,v.length); }catch(e){}
  });
}"""
    edits.append((old, new, "pwField() + bindPwEyes()"))

    # ---------------------------------------------------------------
    # Edit 4: setup pair (gate 2)
    # ---------------------------------------------------------------
    old = r"""        +'<div class="field"><label>Passphrase</label><input class="input" type="password" id="v-p1" autocomplete="new-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'
        +'<div class="field"><label>Type it again</label><input class="input" type="password" id="v-p2" autocomplete="new-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'"""
    new = r"""        +'<div class="field"><label>Passphrase</label>'+pwField('v-p1','','new-password')+'</div>'
        +'<div class="field"><label>Type it again</label>'+pwField('v-p2','','new-password')+'</div>'"""
    edits.append((old, new, "gate 2: setup + confirm fields"))

    old = r"""      setTimeout(()=>{ const el=$vault.querySelector('#v-p1'); if(el) el.focus(); },60);"""
    new = r"""      bindPwEyes($vault);
      setTimeout(()=>{ const el=$vault.querySelector('#v-p1'); if(el) el.focus(); },60);"""
    edits.append((old, new, "gate 2: bind eyes"))

    # ---------------------------------------------------------------
    # Edit 5: verification gate (gate 4)
    # ---------------------------------------------------------------
    old = r"""        +'<div class="field"><label>Vault passphrase</label><input class="input" type="password" id="v-vp" autocomplete="current-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'"""
    new = r"""        +'<div class="field"><label>Vault passphrase</label>'+pwField('v-vp','','current-password')+'</div>'"""
    edits.append((old, new, "gate 4: verification field"))

    old = r"""      setTimeout(()=>{ const el=$vault.querySelector('#v-vp'); if(el) el.focus(); },60);"""
    new = r"""      bindPwEyes($vault);
      setTimeout(()=>{ const el=$vault.querySelector('#v-vp'); if(el) el.focus(); },60);"""
    edits.append((old, new, "gate 4: bind eyes"))

    # ---------------------------------------------------------------
    # Edit 6: the everyday unlock sheet
    # ---------------------------------------------------------------
    old = r"""      +'<div class="field"><input class="input" type="password" id="v-up" placeholder="Vault passphrase" autocomplete="current-password" autocapitalize="off" autocorrect="off" spellcheck="false"></div>'"""
    new = r"""      +'<div class="field">'+pwField('v-up','Vault passphrase','current-password')+'</div>'"""
    edits.append((old, new, "unlock sheet: field"))

    old = r"""    setTimeout(()=>{ const el=$mr.querySelector('#v-up'); if(el) el.focus(); },60);"""
    new = r"""    bindPwEyes($mr);
    setTimeout(()=>{ const el=$mr.querySelector('#v-up'); if(el) el.focus(); },60);"""
    edits.append((old, new, "unlock sheet: bind eyes"))

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
    js_path = Path("/tmp/_notebuilt_vault7_check.js")
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

    print("\n✅ Vault 7 applied: show-passphrase toggle on all four passphrase fields.")

if __name__ == "__main__":
    main()
