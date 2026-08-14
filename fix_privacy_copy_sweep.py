#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — privacy/copy sweep: three items, one deploy
Run from the same folder as index.html:
    python3 fix_privacy_copy_sweep.py

Copy and markup only. No logic change to activation, no new request, no
service-worker change. The one piece of behaviour added is a return path,
which exists so that reading the privacy page cannot cost someone the pitch
they were standing in.

1. PRIVACY PAGE — NAME THE SECOND CALL
   Shipped 1757 made the flow "one call, or two if the first is refused"
   (activate, then validate). The page still described one. The brief's
   sentence is inserted verbatim, directly after the existing activation
   sentence.

2. UNLOCK PITCH — A QUIET LINK TO THAT PAGE
   One tertiary text link below the activation paragraph and above the
   buttons, in both variants — which is one edit, because the two variants
   differ only in their opening `lead` and share everything below it.

   Rendered as a <button> styled as a link rather than an <a href>: an
   anchor here would either need a real href or a "#" that pushes a history
   entry the app does not own. It reads as a link and behaves as one.

   THE RETURN PATH is the part with teeth. Leaving the pitch to read the
   privacy page must not discard where you were:

     * `_unlockReturn` records the view underneath, the resume-to-New-project
       intent, and any typed key.
     * `go()` clears it on entry, so tapping the nav bar — a deliberate
       departure — drops the pending return instead of ambushing the person
       with a sheet on some unrelated screen. The link sets it AFTER its own
       go('privacy') for exactly that reason.
     * `goBack()` from the privacy page restores the underlying view and
       reopens the sheet.
     * A recorded key reopens the KEY sheet with the text still in it;
       otherwise the pitch reopens. The link only exists on the pitch today,
       so the key branch is dormant — but "key field contents if any" is in
       the brief, and the mechanism costs nothing to get right now.

3. "NO EMAIL ADDRESS NEEDED" — MAKE IT TRUE
   Checkout does ask for an email; it is how Polar delivers the key. The
   sentence is replaced with the brief's wording. One anchor covers both
   variants, again because the sentence lives in the shared block.

4. HELP_COPY['photo-send'] — DELIBERATELY UNTOUCHED
   Held for Edwin's wording, which has not arrived in this session. A guard
   below asserts the current text is still byte-identical, so this sweep
   cannot quietly rewrite it.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")

# The photo-send copy as it stands. Item 4 says leave it alone; this is how
# the script proves it did.
PHOTO_SEND_HELD = ("'photo-send':'Share hands the image straight to another app on this phone")


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # ---- 1. the second call, named -------------------------------------
    old_priv = """      If you unlock the app, tapping <b style="color:var(--paper)">Activate</b> sends your key once to Polar, who handle the payment, to register it. That single moment is the only time. Nothing of yours goes with it — no projects, no photos, no identifier for you — and once it succeeds the unlock is never re-checked, at launch or ever.<br><br>"""
    new_priv = """      If you unlock the app, tapping <b style="color:var(--paper)">Activate</b> sends your key once to Polar, who handle the payment, to register it. That single moment is the only time. Nothing of yours goes with it — no projects, no photos, no identifier for you — and once it succeeds the unlock is never re-checked, at launch or ever.<br><br>
      If that first request is refused, Notebuilt asks the server one follow-up question — is this key valid? — and nothing more. Still nothing before you enter a key, still nothing ever again after.<br><br>"""
    edits.append((old_priv, new_priv, "privacy: name the follow-up call"))

    # ---- 3. the email line ---------------------------------------------
    old_email = """      +'<b style="color:var(--paper)">'+esc(UNLOCK.PRICE)+', once.</b> No subscription, no account, no email address needed.<br><br>'"""
    new_email = """      +'<b style="color:var(--paper)">'+esc(UNLOCK.PRICE)+', once.</b> No subscription, no account \\u2014 just an email at checkout so your key can reach you.<br><br>'"""
    edits.append((old_email, new_email, "pitch: the email line, made true"))

    # ---- 2. the link, and the state it must not lose --------------------
    old_state = """/* resume=true means they were stopped mid-action at the cap, so finishing
   the unlock should hand back the thing they were trying to do. */"""
    new_state = """/* Where to come back to when the privacy page is closed: the view that was
   underneath, what the person was in the middle of, and anything they had
   already typed. Cleared by go(), so walking off via the nav bar drops it
   rather than reopening a sheet somewhere it does not belong. */
let _unlockReturn=null;
function unlockOpenPrivacy(resume){
  const key=(function(){ const el=$mr.querySelector('#u-key'); return el?el.value:''; })();
  const from={ name:view.name, param:view.param };
  closeSheet();
  go('privacy');
  _unlockReturn={ from, resume:!!resume, key:key||'' };   /* set AFTER go(), which clears it */
}
function unlockReturnFromPrivacy(){
  const r=_unlockReturn; if(!r) return false;
  _unlockReturn=null;
  go(r.from.name, r.from.param);
  /* Typed text outranks the pitch: if they had a key in hand, put them back
     in front of it. The link only exists on the pitch today, so this is
     dormant until it is not. */
  if(r.key) unlockKeySheet(r.key, r.resume); else unlockPitch(r.resume);
  return true;
}

/* resume=true means they were stopped mid-action at the cap, so finishing
   the unlock should hand back the thing they were trying to do. */"""
    edits.append((old_state, new_state, "unlock return state"))

    old_link = """    +'</div>'
    +(UNLOCK.EXTERNAL_PURCHASE
        ? '<a class="btn primary block" style="margin-top:14px;text-decoration:none" href="'+esc(UNLOCK.CHECKOUT_URL)+'" target="_blank" rel="noopener noreferrer">Unlock — '+esc(UNLOCK.PRICE)+'</a>'
        : '')"""
    new_link = """    +'</div>'
    /* Tertiary on purpose: body size, muted, and not a fourth button
       competing with the three real choices below it. */
    +'<button type="button" data-unlock-privacy style="display:block;margin:12px 0 0;padding:0;border:0;background:none;'
    +'font:inherit;font-size:13.5px;color:var(--paper-dim);text-decoration:underline;cursor:pointer">'
    +'Read the full privacy promise \\u2192</button>'
    +(UNLOCK.EXTERNAL_PURCHASE
        ? '<a class="btn primary block" style="margin-top:14px;text-decoration:none" href="'+esc(UNLOCK.CHECKOUT_URL)+'" target="_blank" rel="noopener noreferrer">Unlock — '+esc(UNLOCK.PRICE)+'</a>'
        : '')"""
    edits.append((old_link, new_link, "pitch: the privacy link"))

    old_bind = """  $mr.querySelector('[data-unlock-key]').onclick=()=>unlockKeySheet('',resume);
  $mr.querySelector('[data-unlock-later]').onclick=()=>closeSheet();"""
    new_bind = """  $mr.querySelector('[data-unlock-key]').onclick=()=>unlockKeySheet('',resume);
  $mr.querySelector('[data-unlock-later]').onclick=()=>closeSheet();
  $mr.querySelector('[data-unlock-privacy]').onclick=()=>unlockOpenPrivacy(resume);"""
    edits.append((old_bind, new_bind, "pitch: bind the link"))

    # go() forgets a pending return; goBack() honours one
    old_go = """function go(name,param=null){ view={name,param}; render(); window.scrollTo(0,0); }"""
    new_go = """function go(name,param=null){
  /* Any navigation drops a pending unlock return. The privacy link re-arms it
     immediately after its own go(), so only a DELIBERATE departure — a nav
     tap, a project opened — loses it. */
  _unlockReturn=null;
  view={name,param}; render(); window.scrollTo(0,0);
}"""
    edits.append((old_go, new_go, "go(): forget a stale return"))

    old_back = """function goBack(){
  if(view.name==='housenotes'){ go('house', view.param); return; }"""
    new_back = """function goBack(){
  /* Came here from the unlock pitch: put it back, with what was in it. */
  if(view.name==='privacy' && unlockReturnFromPrivacy()) return;
  if(view.name==='housenotes'){ go('house', view.param); return; }"""
    edits.append((old_back, new_back, "goBack(): honour the return"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # Copy only: the request surface must be untouched.
    if working.count("fetch(") != text.count("fetch("):
        fail("the number of fetch( calls changed — this sweep is copy only.")
    hosts = sorted(set(h for h in re.findall(r"https://[a-z0-9.-]+", working) if "polar" in h))
    if hosts != ["https://api.polar.sh", "https://buy.polar.sh"]:
        fail(f"the polar host set changed: {hosts}")
    # Item 3 must be gone from every variant.
    if "no email address needed" in working:
        fail("the old email claim survived.")
    if "just an email at checkout so your key can reach you" not in working:
        fail("the replacement email line did not land.")
    # Item 4: held, and proven held.
    if PHOTO_SEND_HELD not in working:
        fail("HELP_COPY['photo-send'] was modified — item 4 says hold it.")
    if working.count("'photo-send':") != text.count("'photo-send':"):
        fail("HELP_COPY['photo-send'] was duplicated or removed.")
    # The link is one control, on the shared block, so both variants get it.
    if working.count("data-unlock-privacy") != 2:      # markup + binding
        fail(f"expected the privacy link once in markup and once in binding, "
             f"found {working.count('data-unlock-privacy')} references.")
    pitch = working[working.find("function unlockPitch("):working.find("function unlockKeySheet(")]
    if pitch.count("data-unlock-privacy") != 2:
        fail("the privacy link is not inside unlockPitch.")
    if pitch.find("data-unlock-privacy") > pitch.find("UNLOCK.EXTERNAL_PURCHASE"):
        fail("the link must sit above the buttons.")
    # It must not be a fourth button.
    if 'class="btn' in pitch[pitch.find("data-unlock-privacy")-260:pitch.find("data-unlock-privacy")]:
        fail("the privacy link is styled as a button.")
    # The return must be cleared by navigation and honoured by back.
    if "_unlockReturn=null;" not in working[working.find("function go(name"):working.find("let _leavingView")]:
        fail("go() does not clear a pending return.")
    if "unlockReturnFromPrivacy()" not in working[working.find("function goBack()"):working.find("/* CHUNK14_PRIVACY_PAGE */")]:
        fail("goBack() does not honour the return.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: no change to fetch( count or the polar host set")
    print("✅ guard: old email claim gone; link is a text control above the buttons")
    print("✅ guard: HELP_COPY['photo-send'] untouched (item 4 held)")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_copysweep_check.js")
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

    print("\n✅ the page describes what the app does, and reading it costs you nothing.")


if __name__ == "__main__":
    main()
