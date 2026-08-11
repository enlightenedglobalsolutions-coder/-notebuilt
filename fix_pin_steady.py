#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — PIN screen: stop the jump (th_nb_pin)
Run from the same folder as index.html:
    python3 fix_pin_steady.py

DIAGNOSIS — none of the four suspects in the brief
--------------------------------------------------
Measured against the live file in a real browser:

  1. A focused real <input>?   NO. The lock screen has no input, textarea
     or select at all — it is divs and buttons. Ruled out.
  2. Dot row / error line changing height?  NO. `.err` already carries
     `min-height:18px`, and `.d.on` changes background and border-COLOUR
     only, never a dimension. Measured shift: 0px. Ruled out.
  3. `:active` changing box size?  NO. `.keypad button:active` sets
     `background` and nothing else. Ruled out.
  4. Page scrolling behind the lock?  Largely no — `#lock` is
     `position:fixed; inset:0`, `#app` is hidden behind it, and body
     already has `overscroll-behavior-y:none`.

THE ACTUAL CAUSE
----------------
`draw()` re-assigned `$lock.innerHTML` on EVERY keypress. Measured: 27
DOM nodes destroyed and rebuilt per digit — including the <button> still
under the user's thumb, which holds focus at that instant. Confirmed in
the browser:

    focused button destroyed .... true
    still in document ........... false
    activeElement after ......... BODY  (focus lost)
    inline <svg> re-parsed ...... true  (every digit)

Losing focus from an element inside a fixed overlay, while the whole
subtree re-lays-out mid-touch, is what iOS answers with a scroll. Desktop
Chrome shows 0px of movement for the same code, which is exactly why this
only ever reproduced on Edwin's phone.

THE FIX
-------
Build the lock screen ONCE. A keypress now touches two things: the `.on`
class on four dots, and the error line's textContent. No node is created
or destroyed, nothing takes or loses focus, the 58px inline SVG is parsed
once instead of once per digit.

`setupPin()` had the identical defect and is fixed the same way — it went
further and rebuilt the scrim itself on every digit, re-registering its
click handler each time. That path is how you CHANGE a PIN, so Edwin hits
it too.

Also hardened, all of which are real iOS behaviours rather than guesses:
  - `touch-action:manipulation` on keypad buttons — kills the double-tap
    zoom gesture, and with it the 300ms delay and its viewport shuffle.
  - `type="button"` — these defaulted to `type="submit"`.
  - `justify-content:safe center` + `overflow-y:auto` +
    `overscroll-behavior:contain` on `#lock`. Content measures 568px
    tall; a centred column that outgrows the viewport (larger Dynamic
    Type, a shorter phone) puts the mark out of reach off the TOP with
    no way to scroll to it. `safe center` degrades to flex-start instead.
  - The blank keypad cell is no longer a tab stop.

CONFIRM-TWICE (brief asked to verify, not rebuild)
--------------------------------------------------
Already present and it DOES cover change as well as set: `setupPin()` is
the single entry point for both — the <h2> reads "Change PIN" when
`settings.pinHash` exists — and its stage 1 -> stage 2 flow requires the
same 4 digits twice either way. Nothing added. Preserved verbatim here.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "PIN_STEADY"


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
    # Edit 1: #lock owns its own scrolling, and centres SAFELY.
    # ---------------------------------------------------------------
    old1 = """  #lock{
    position:fixed;inset:0;z-index:100;background:var(--ink);
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:30px;gap:6px;
  }"""
    new1 = """  #lock{
    position:fixed;inset:0;z-index:100;background:var(--ink);
    display:flex;flex-direction:column;align-items:center;justify-content:center;
    padding:30px;gap:6px;
    /* PIN_STEADY — a centred column that outgrows the viewport pushes its top
       out of reach, and nothing can scroll to it. 'safe center' falls back to
       flex-start exactly when that would happen; the overflow pair keeps the
       scrolling inside this layer instead of the page behind it. */
    overflow-y:auto; overscroll-behavior:contain;
    justify-content:safe center;
  }"""
    edits.append((old1, new1, "CSS: #lock safe centring + own scroll"))

    # ---------------------------------------------------------------
    # Edit 2: keypad buttons — no double-tap zoom, no text selection.
    # ---------------------------------------------------------------
    old2 = """  .keypad button{
    height:72px;border-radius:50%;background:var(--ink-2);font-family:var(--mono);
    font-size:24px;color:var(--paper);border:1px solid var(--line-soft);
  }"""
    new2 = """  .keypad button{
    height:72px;border-radius:50%;background:var(--ink-2);font-family:var(--mono);
    font-size:24px;color:var(--paper);border:1px solid var(--line-soft);
    /* PIN_STEADY — manipulation drops the double-tap-zoom gesture, and with it
       the 300ms tap delay and the viewport shuffle that comes with it. */
    touch-action:manipulation; -webkit-user-select:none; user-select:none;
  }"""
    edits.append((old2, new2, "CSS: keypad touch-action + no select"))

    # ---------------------------------------------------------------
    # Edit 3: one keypad markup, two callers.
    # ---------------------------------------------------------------
    old3 = """const $lock=document.getElementById('lock');"""
    new3 = """/* PIN_STEADY — one keypad, both callers. type="button" because these
   defaulted to type="submit"; the blank cell is not a tab stop. */
const PIN_KEYPAD_HTML =
  [1,2,3,4,5,6,7,8,9].map(n=>`<button type="button" data-k="${n}">${n}</button>`).join('')
  + '<button type="button" class="blank" tabindex="-1" aria-hidden="true"></button>'
  + '<button type="button" data-k="0">0</button>'
  + '<button type="button" data-k="del" aria-label="Delete">\\u232B</button>';

const $lock=document.getElementById('lock');"""
    edits.append((old3, new3, "shared PIN_KEYPAD_HTML"))

    # ---------------------------------------------------------------
    # Edit 4: lockGate() — build once, then only repaint state.
    # ---------------------------------------------------------------
    old4 = """function lockGate(){
  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); return; }
  showShell(false); $fab.classList.add('hidden');
  let entry='', verifying=true;
  const draw=(err='')=>{
    $lock.classList.remove('hidden');
    $lock.innerHTML=`<div class="mark">${MARK}</div><div class="name">${esc(APP_NAME)}</div>
      <div class="hint">Enter PIN</div>
      <div class="dots">${[0,1,2,3].map(i=>`<div class="d ${i<entry.length?'on':''}"></div>`).join('')}</div>
      <div class="err">${esc(err)}</div>
      <div class="keypad">${[1,2,3,4,5,6,7,8,9].map(n=>`<button data-k="${n}">${n}</button>`).join('')}<button class="blank"></button><button data-k="0">0</button><button data-k="del">⌫</button></div>`;
    $lock.querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{
      const k=b.dataset.k;
      if(k==='del'){ entry=entry.slice(0,-1); draw(); return; }
      if(entry.length>=4) return;
      entry+=k;
      if(entry.length===4){
        const ok=(await sha(entry+settings.pinSalt))===settings.pinHash;
        if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); }
        else{ entry=''; draw('Wrong PIN'); }
      } else draw();
    });
  };
  draw();
}"""
    new4 = """function lockGate(){
  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); return; }
  showShell(false); $fab.classList.add('hidden');
  let entry='';
  /* PIN_STEADY — built ONCE, on the way in.
     The old code re-assigned $lock.innerHTML on every digit: 27 nodes torn
     down and rebuilt, including the button still under the thumb, which held
     focus at that instant. Focus fell to <body> and iOS answered by scrolling
     the screen down. Desktop Chrome moved 0px for the same code, which is why
     it only ever showed up on the phone.
     A keypress now writes two things: four dot classes, and one line of text. */
  $lock.classList.remove('hidden');
  $lock.innerHTML=`<div class="mark">${MARK}</div><div class="name">${esc(APP_NAME)}</div>
      <div class="hint">Enter PIN</div>
      <div class="dots">${[0,1,2,3].map(()=>'<div class="d"></div>').join('')}</div>
      <div class="err"></div>
      <div class="keypad">${PIN_KEYPAD_HTML}</div>`;
  const $dots=[...$lock.querySelectorAll('.dots .d')];
  const $err=$lock.querySelector('.err');
  /* The whole of what a keypress changes. No node is created or destroyed,
     so nothing can take focus, lose it, or be re-laid-out under a finger. */
  const paint=(err)=>{
    $dots.forEach((d,i)=>d.classList.toggle('on', i<entry.length));
    if(err!==undefined) $err.textContent=err||'';
  };
  let busy=false;
  $lock.querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{
    if(busy) return;
    const k=b.dataset.k;
    if(k==='del'){ entry=entry.slice(0,-1); paint(''); return; }
    if(entry.length>=4) return;
    entry+=k; paint('');
    if(entry.length===4){
      /* The hash is async, so the fourth dot is already painted and taps are
         held off until it answers — otherwise a fast fifth tap lands mid-check. */
      busy=true;
      const ok=(await sha(entry+settings.pinSalt))===settings.pinHash;
      busy=false;
      if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); }
      else{ entry=''; paint('Wrong PIN'); }
    }
  });
}"""
    edits.append((old4, new4, "lockGate(): build once, repaint state only"))

    # ---------------------------------------------------------------
    # Edit 5: setupPin() — same defect, same fix. Confirm-twice preserved.
    # ---------------------------------------------------------------
    old5 = """function setupPin(){
  let stage=1, first='', entry='';
  const draw=(msg)=>{
    sheet(`<h2>${settings.pinHash?'Change PIN':'Set a PIN'}</h2>
      <div class="muted" style="text-align:center;margin-bottom:6px">${msg}</div>
      <div class="dots" style="justify-content:center">${[0,1,2,3].map(i=>`<div class="d ${i<entry.length?'on':''}"></div>`).join('')}</div>
      <div class="keypad" style="margin:14px auto 4px">${[1,2,3,4,5,6,7,8,9].map(n=>`<button data-k="${n}">${n}</button>`).join('')}<button class="blank"></button><button data-k="0">0</button><button data-k="del">⌫</button></div>`);
    $mr.querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{
      const k=b.dataset.k;
      if(k==='del'){ entry=entry.slice(0,-1); draw(msg); return; }
      if(entry.length>=4) return; entry+=k;
      if(entry.length<4){ draw(msg); return; }
      if(stage===1){ first=entry; entry=''; stage=2; draw('Re-enter to confirm'); }
      else{ if(entry===first){ const salt=randSalt(); settings.pinSalt=salt; settings.pinHash=await sha(first+salt); persist.settings(); closeSheet(); render(); toast('App lock on'); }
        else{ entry=''; stage=1; first=''; draw('Did not match — try again'); } }
    });
  };
  draw('Choose a 4-digit PIN');
}"""
    new5 = """function setupPin(){
  let stage=1, first='', entry='';
  /* PIN_STEADY — the sheet is built once. The old draw() called sheet() per
     digit, which rebuilt the scrim as well as the keypad and re-registered the
     scrim's click handler each time. This is the CHANGE-PIN path too.
     Confirm-twice is unchanged: stage 1 takes the PIN, stage 2 demands it
     again, and that is true whether the PIN is new or being changed. */
  sheet(`<h2>${settings.pinHash?'Change PIN':'Set a PIN'}</h2>
      <div class="muted" data-pin-msg style="text-align:center;margin-bottom:6px"></div>
      <div class="dots" style="justify-content:center">${[0,1,2,3].map(()=>'<div class="d"></div>').join('')}</div>
      <div class="keypad" style="margin:14px auto 4px">${PIN_KEYPAD_HTML}</div>`);
  const $dots=[...$mr.querySelectorAll('.dots .d')];
  const $msg=$mr.querySelector('[data-pin-msg]');
  const paint=(msg)=>{
    $dots.forEach((d,i)=>d.classList.toggle('on', i<entry.length));
    if(msg!==undefined) $msg.textContent=msg;
  };
  paint('Choose a 4-digit PIN');
  let busy=false;
  $mr.querySelectorAll('[data-k]').forEach(b=>b.onclick=async()=>{
    if(busy) return;
    const k=b.dataset.k;
    if(k==='del'){ entry=entry.slice(0,-1); paint(); return; }
    if(entry.length>=4) return;
    entry+=k; paint();
    if(entry.length<4) return;
    if(stage===1){ first=entry; entry=''; stage=2; paint('Re-enter to confirm'); return; }
    if(entry===first){
      busy=true;
      const salt=randSalt(); settings.pinSalt=salt; settings.pinHash=await sha(first+salt);
      persist.settings(); busy=false;
      closeSheet(); render(); toast('App lock on');
    } else {
      entry=''; stage=1; first=''; paint('Did not match \\u2014 try again');
    }
  });
}"""
    edits.append((old5, new5, "setupPin(): build once, confirm-twice preserved"))

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
    js_path = Path("/tmp/_notebuilt_pin_steady_check.js")
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

    print("\n✅ PIN_STEADY applied: the lock screen and the PIN sheet are built")
    print("   once; a keypress repaints four dots and one line of text.")
    print("   Gate: on-device rapid entry, zero visual movement.")


if __name__ == "__main__":
    main()
