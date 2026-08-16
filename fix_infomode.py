#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — beginner mode: (i) markers that explain the app, and the switch
that turns them off.
Run from the same folder as index.html:
    python3 fix_infomode.py

EGS-STANDARDS §2 row 14 (`EGS-STD:infomode`) was the last unbuilt row on this
app. It was not absent so much as half-seeded: HELP_COPY already existed, four
entries deep, planted by the PIN-recovery, photo-send, themes and unlock ships
against the day info mode was built. Its own comment said so — "planted now so
info mode inherits it". This is that day, so the object moves up into the
infomode block where the rest of the copy now lives, rather than staying in the
recovery-code section it was parked in.

What lands:

  * `notebuilt.beginner` — per device, absent means ON, so a fresh install and
    every phone that already had Notebuilt both open in beginner mode. Its own
    key, NOT settings: like the theme it describes the phone, not the data, and
    it has no business travelling inside a backup to a different person's
    tablet. Written only by a tap; startup only ever reads it.
  * `.help-i` markers, drawn unconditionally by every screen, hidden in expert
    mode by ONE stylesheet rule. No render function knows which mode it is in.
  * Zero reflow between modes, enforced by only ever using hosts that have
    slack: the flex gap inside a .sec-head, a short fixed <h1>, or an
    absolutely-positioned corner in a sheet. See the CSS comment.
  * Sixteen HELP_COPY entries covering every major surface, in Edwin's words.
  * `EGS-STD:support`, which §7 has recorded as owed since 2026-08-16 — the app
    charges AND draws a Support page, so the marker's SKIP was silence on a row
    it actually implements. One comment; this is the next touch, so it lands.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import shutil
import sys
import time
from pathlib import Path

# The shared checker. One source of truth — if it cannot be imported, that is
# a hard stop, not a reason to continue without a syntax check.
sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
try:
    from fixscript_check import check_html
except ImportError as e:
    print(f"❌ cannot import platform/fixscript_check.py ({e}) — refusing to edit unverified.")
    sys.exit(1)

TARGET = Path("index.html")
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# 1. CSS — the marker, and the one rule that hides every one of them.
# ---------------------------------------------------------------------------
CSS_OLD = """  .sec-head .count{font-family:var(--mono);font-size:11px;color:var(--paper-faint)}
"""

CSS_NEW = """  .sec-head .count{font-family:var(--mono);font-size:11px;color:var(--paper-faint)}

  /* ---- Info markers ----
     EGS-STD:infomode — §2 row 14 lives here, on the block it describes.

     ONE RULE switches every marker off: the [data-guide="off"] line at the
     bottom of this block. No screen, no render function and no handler ever
     asks which mode the app is in — they all draw the marker and the
     stylesheet decides whether it is seen. That is deliberate. The moment a
     render function starts branching on the mode, expert becomes a second
     layout to test rather than the same layout with something hidden, and
     the two drift the first time one of them is edited alone.

     ZERO REFLOW BETWEEN MODES is the other half, and it is why there are
     exactly three hosts and no others:

       * inside a .sec-head, straight after .label — .rule is flex:1 and
         swallows the marker's width, so the label does not move and neither
         does the count or button on the right. 15px is under the 11px
         label's own 15.95px line box, so the row does not grow either.
       * inline at the end of a SHORT, FIXED topbar <h1> — "To Do",
         "Projects", "Notes", "Calculator". 15px sits inside a 25px serif
         line box without raising it, and none of those four can wrap.
       * .help-corner, absolute in a sheet's top-right — out of flow
         entirely, so a sheet title of any length is untouched by it.

     A variable-length title never gets an inline marker. It could wrap in
     beginner and not in expert, and a line that appears and disappears is
     precisely the reflow this rule exists to forbid.

     Colours are roles, not picks. The border is --line-strong because here
     the outline IS the control — the same reason the empty to-do punch and
     the unfilled PIN dot use it, and it is the token measured to clear 3:1
     on every ground. The glyph is --paper-dim, the secondary text role,
     measured past 4.5:1 in both themes. audit_contrast.py reads both out of
     this file, so neither can drift quietly. */
  .help-i{
    flex:none;align-self:center;position:relative;
    width:15px;height:15px;padding:0;border-radius:50%;
    border:1px solid var(--line-strong);background:none;
    color:var(--paper-dim);font-family:var(--serif);
    font-size:10px;font-style:italic;line-height:1;
    display:inline-flex;align-items:center;justify-content:center;
    vertical-align:-2px;
  }
  .help-i:active{border-color:var(--brass);color:var(--brass)}
  /* A 46px-ish tap target bought without one pixel of layout: an invisible
     pad overflowing the 15px dot. Biased right, into the .sec-head rule,
     which is inert — reaching further left would start stealing taps from
     labels that are themselves buttons (Site Notes is one). */
  .help-i::after{content:'';position:absolute;top:-11px;bottom:-11px;left:-6px;right:-14px}
  .sec-head .help-i{margin-left:-2px}
  .sheet{position:relative}
  .help-corner{position:absolute;top:9px;right:12px;z-index:1}
  /* Symmetric and short, because .sheet is overflow:auto — a pad reaching
     past the padding box on the right would invent a horizontal scrollbar. */
  .help-corner::after{left:-11px;right:-11px}
  /* THE ONE RULE. Expert mode is this line and nothing else. */
  :root[data-guide="off"] .help-i{display:none}
"""

# ---------------------------------------------------------------------------
# 2. JS — the mode, the marker helpers, the layered help sheet, and the copy.
# ---------------------------------------------------------------------------
JS_OLD = """/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */
let _db=null;
"""

JS_NEW = r"""/* ============================================================
   EGS-STD:infomode — beginner ⇄ expert, and the (i) markers
   ============================================================
   The stylesheet does the hiding (search .help-i for why). This half is the
   preference, the markers, the sheet they open, and the copy itself.

   Its own key, not settings, for the same reason the theme has one: this
   describes the PHONE, not the data. A backup restored onto a mate's tablet
   should not decide whether he gets the explanations. Absent means ON, which
   is what makes "existing installs default to beginner too" free — there is
   nothing to migrate, because there was never anything written.

   Startup reads and never writes. nbGuideApply() sets a DOM attribute, which
   is not storage; the only writers are nbGuideSet and the notice's dismiss,
   and a tap is the only way to either. */
const NB_GUIDE_KEY='notebuilt.beginner';
const NB_GUIDE_NOTICE_KEY='notebuilt.guideNoticeSeen';
function nbGuideOn(){
  try{ return localStorage.getItem(NB_GUIDE_KEY)!=='off'; }catch(e){ return true; }
}
function nbGuideApply(){
  document.documentElement.setAttribute('data-guide', nbGuideOn()?'on':'off');
}
function nbGuideSet(on){
  try{ localStorage.setItem(NB_GUIDE_KEY, on?'on':'off'); }catch(e){}
  nbGuideNoticeDismiss(true);      /* they found the switch; stop pointing at it */
  nbGuideApply();
}
nbGuideApply();

/* One line, once, for the phones that already had Notebuilt before markers
   existed. A fresh install never sees it — beginner mode IS the fresh
   install, and being told about a change you did not experience is noise.
   In flow, inside the page, so it can never stack with the install banner or
   the backup nudge, which are both fixed to the bottom of the screen. */
function nbGuideNoticeDue(){
  if(!nbGuideOn()) return false;
  try{
    if(localStorage.getItem(NB_GUIDE_NOTICE_KEY)) return false;
    if(localStorage.getItem(NB_GUIDE_KEY)) return false;   /* already chose, once */
  }catch(e){ return false; }
  return !!(houses.length||notes.length||tasks.length);     /* an existing install */
}
function nbGuideNoticeHtml(){
  if(!nbGuideNoticeDue()) return '';
  return '<div class="wrap"><div class="card row" style="margin:12px 0 0;align-items:flex-start">'
    +'<div class="grow muted" style="font-size:13px;line-height:1.55">New here: the small '
    +'<b style="color:var(--paper)">i</b> marks explain what each part of the app does. '
    +'Turn them off any time — Settings, under Guide.</div>'
    +'<button class="icon-btn" data-guide-notice-x aria-label="Got it" style="width:36px;height:36px;flex:none">'+I.x+'</button>'
    +'</div></div>';
}
function nbGuideNoticeDismiss(silent){
  try{ localStorage.setItem(NB_GUIDE_NOTICE_KEY,'1'); }catch(e){}
  if(!silent) render();
}

/* The marker. Two shapes, one behaviour — nbHelpMark goes in flow where the
   host has slack, nbHelpCorner is pinned in a sheet's corner where it does
   not. Both carry the key and nothing else; the copy is looked up at tap. */
function nbHelpMark(key){
  return '<button type="button" class="help-i" data-help="'+esc(key)+'" aria-label="What is this?">i</button>';
}
function nbHelpCorner(key){
  return '<button type="button" class="help-i help-corner" data-help="'+esc(key)+'" aria-label="What is this?">i</button>';
}
/* Called with $app from bind(), and with $mr from sheet(). Nowhere else has
   markers, and nothing else needs to know they exist. */
function nbHelpBind(root){
  if(!root) return;
  root.querySelectorAll('.help-i[data-help]').forEach(b=>b.onclick=ev=>{
    /* Half these markers sit on hosts that are themselves buttons — the Site
       Notes heading, a settings row that navigates. The marker wins its own
       tap and the host never sees it. */
    ev.preventDefault(); ev.stopPropagation();
    nbHelpSheet(b.dataset.help);
  });
}
/* Layered, not swapped. $mr holds exactly one sheet, so drawing help through
   sheet() would destroy the sheet the marker was tapped in — you would ask
   what Share does and lose the share screen answering it. This appends its
   own scrim above whatever is there and removes only its own node. */
function nbHelpSheet(key){
  const copy=HELP_COPY[key]; if(!copy) return;
  const el=document.createElement('div');
  el.className='scrim help-scrim';
  el.style.zIndex='81';                    /* one above .scrim, under the lock */
  el.innerHTML='<div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>'
    +'<h2>'+esc(HELP_TITLE[key]||'About this')+'</h2>'
    +'<div class="muted" style="font-size:13.5px;line-height:1.62">'
    +esc(copy).replace(/\n\n/g,'<br><br>')+'</div>'
    +'<button class="btn block" data-help-close style="margin-top:16px">Got it</button></div>';
  document.body.appendChild(el);
  const close=()=>{ if(el.parentNode) el.parentNode.removeChild(el); };
  el.addEventListener('click',ev=>{ if(ev.target===el) close(); });
  el.querySelector('[data-help-close]').onclick=close;
}

/* ---------- the copy ----------
   Moved here from the recovery-code section, where the first four entries
   were parked with a note saying they were "planted now so info mode
   inherits it". This is the inheritance.

   Two of them are read by things that are not markers and must keep their
   shape: 'pin-recovery' is quoted inside maybeOfferRecoveryCode(), where a
   longer entry would run into the sentence that follows it, and
   'photo-send' is the long version of the two lines the send sheet already
   shows. Both are reached by a marker as well.

   Plain paragraphs, split on a blank line. No markup: nbHelpSheet escapes
   every entry before it draws it, so a stray < in a future edit cannot turn
   into a tag. */
const HELP_TITLE={
  'guide':'Beginner mode',
  'todos':'To Do',
  'projects':'Projects',
  'categories':'Categories',
  'photos':'Photos',
  'photo-send':'Sending a photo out',
  'notes':'Notes',
  'calc':'Calculator',
  'applock':'App lock',
  'pin-recovery':'If you forget your PIN',
  'vault':'Protected projects',
  'backup':'Backup, export and restore',
  'import-project':'Import a shared project',
  'share':'Share a project',
  'theme':'Theme',
  'unlock':'Free, and unlocking'
};
const HELP_COPY={
  'guide':'Beginner mode puts a small circled i beside the parts of the app worth a sentence of explanation. Tap one and it tells you what that thing does, in plain words, including what it will not do.\n\nExpert hides every one of them. Nothing else changes, no feature goes away, and you can switch back in here whenever you like.\n\nThis setting stays on this phone. It is not in your backup, so the tablet on the bench and the phone in the truck can each be set to suit whoever picks it up.',

  'todos':'Everything you need to get done, in one list, whether it belongs to a project or not. Tap the punch on the left to move an item along: To do, then Doing, then Done. Tap the words to edit it, change its status, or move it to a project.\n\nDone items stay on the list until you tap Clear done, so at the end of the day you can see what you got through.\n\nTo-dos inside a protected project do not show up here. They stay inside that project, behind its passphrase.',

  'projects':'A project is a job — a house, a shop, a unit, or anything else you want photos, notes, specs and to-dos kept together for. Tap + to start one. Everything you put in it lives on this phone.\n\nThe chips along the top filter by category. The button in the corner changes the order they are listed in.\n\nNotebuilt is free for '+UNLOCK.FREE_PROJECTS+' projects with every feature switched on. Unlocking takes the limit off. Projects you have already made are yours to keep either way — nothing here ever locks or hides work you have already done.',

  'categories':'Categories are labels for sorting your projects — Construction, Personal, or anything you make up. Tap a chip along the top of Projects to show only that kind.\n\nIn here you can rename one, change its emoji, move it up or down the list, or remove it.\n\nDeleting a category never deletes a project. Projects that were in it simply show as Uncategorized until you give them a new one.',

  'photos':'Camera takes the picture inside Notebuilt. Library brings in one already on the phone. Tap a photo to open it, where you can rotate it, draw on it, make it the project’s cover, send it out, or delete it.\n\nPhotos taken here do not appear in your camera roll or your phone’s gallery, and that is on purpose. Job photos stay out of the family pictures, and out of whatever cloud backup the gallery is signed in to. They live in Notebuilt’s own storage on this device, and they come back with your backup file.\n\nIf you want one out of the app, open it and use Share or Save to device.\n\nCapture size, under Photos in Settings, trades picture quality against how much room the photos take up. You can push a single shot to Max from the viewfinder without changing the setting.',

  'photo-send':'Share hands the image straight to another app on this phone — your workforce app, a message, email. Save to device puts a copy in your Downloads folder, which is not the same place as your camera roll; your gallery may not show it. Only the picture is sent: no project name, no address, nothing about where it was taken. From a protected project, both of these take the photo out of the vault as an ordinary unprotected image, and whatever receives it keeps it — which is why it asks first, and why it needs the vault open to do it at all.',

  'notes':'Notes are for anything that is not a to-do — measurements, a supplier’s number, what the customer said on Tuesday. A note can belong to a project or stand on its own.\n\nMark one Important and it stays pinned to the top of the list.\n\nNotes save themselves as you type, and again when you back out of one, so there is no Save button to forget.\n\nNotes inside a protected project only appear inside that project.',

  'calc':'Five calculators sharing one set of measurement boxes.\n\nAdd / Subtract works a tape measure — two measurements, plus or minus. Multiply / Divide takes one measurement and a plain number. Board Feet is thickness × width × length ÷ 144. Area is width × length. Square-up gives the diagonal a square layout should measure corner to corner — the 3-4-5 check.\n\nEach mode keeps its own operator and its own numbers, and Clear empties only the mode you are looking at.\n\nSwitch ft/in and metric whenever you like. What you typed converts; it does not get thrown away. Nothing here is saved into a project — it is a scratch pad.',

  'applock':'A PIN on the front door. Turn it on and Notebuilt asks for four digits before it opens, which keeps a workmate, a kid, or whoever picks the phone up out of your projects.\n\nBe clear about what it is not. The PIN does not encrypt anything. Someone who knows their way around a phone could still reach the files underneath it. If you need the contents themselves unreadable, that is what a protected project and its vault passphrase are for.\n\nIf you forget the PIN there are two ways back in: your vault passphrase, if you set one up, or a one-time recovery code you wrote down beforehand. Only a scrambled version of that code is kept on the phone, so nobody can read it back off the device — us included.\n\nWith neither of those, there is no way in. That is the honest answer, not a policy.',

  'pin-recovery':'Your PIN keeps casual hands out of the app. It does not encrypt anything — the vault passphrase does.',

  'vault':'A protected project is encrypted on this phone with a passphrase only you know. Its notes, to-dos, specs and photos are unreadable until you unlock it — not by someone holding your phone, not by Notebuilt, not by us. Turn it on from a project’s Edit screen.\n\nThe passphrase is not your PIN, and it is not stored anywhere. There is no reset, no email link, no back door. Lose it and that project is gone for good. That is what real encryption costs, and we would rather say it plainly than sell you something softer.\n\nWhile it is unlocked the project behaves like any other. It locks itself again after fifteen minutes of nothing happening, when you tap Lock now, or when you close the app.\n\nA protected project never shows its contents in the cross-project lists, and it cannot be shared.',

  'backup':'Export writes everything — projects, photos, notes, to-dos — into one file and hands it to your phone. It lands in Downloads with today’s date in the name. That file is yours. There is no copy on our side, because there is no our side.\n\nPut it somewhere that will survive the phone: another device, a cloud drive, a memory stick. A backup that only exists on the phone you are protecting is not a backup.\n\nRestore reads a file back and replaces everything currently in the app. Use it on a new phone or after a reinstall, not on top of work you still want.\n\nAnything from a protected project stays encrypted inside the file. That is what makes the file safe to store anywhere, and it is why those projects come back locked, needing the same passphrase they were made with. Nothing in the file can stand in for it.\n\nNotebuilt reminds you when it has been three weeks since your last backup, and at most once a week after that. Dismiss it and it goes quiet.',

  'import-project':'If another Notebuilt user sends you a project file, this brings it in as a brand-new project of your own. It never overwrites or touches anything already in the app.\n\nWhatever they chose to leave out — the address, the photos — is simply not in the file, so it will not appear.\n\nFor your own backup use Restore instead. Restore replaces everything; this only adds.',

  'share':'This builds a file another Notebuilt user can import. You choose what travels: the project name and its specs always go, and the address, site notes, photos and to-dos only if you tick them. Photos make the file large, so leave them off unless they are the point of sending it.\n\nOnce you hand it to your phone’s share sheet it is out of Notebuilt’s hands. We are not in the middle of that transfer, and it cannot be taken back.\n\nProtected projects cannot be shared at all. There is no version of that which is safe.\n\nSharing the app itself is a different thing, from the icon on the To Do screen — that sends a link and nothing else.',

  'theme':'Day is for bright cabs and outdoors, where a dark screen turns into a mirror. Night is the notebook you know. Auto follows whatever your phone is set to, and changes with it. This one is kept per device, not in your backup — the phone in the truck and the tablet on the bench can each be set to suit where they are used.',

  'unlock':'Notebuilt is free for '+UNLOCK.FREE_PROJECTS+' projects with every single feature switched on — photos, the vault, backups, the calculator, all of it. Unlocking takes the limit off how many projects you keep. It is '+UNLOCK.PRICE+', once. No subscription, no account, no trial that runs out.\n\nProjects you already made never lock. Reaching the limit stops you starting another one; it never touches the ones you have.\n\nEntering your key sends it to Polar, who handle the payment, a single time, to register it. After that Notebuilt never contacts anything again — the unlock is not re-checked at launch, or ever. The key is stored in your settings, so your backup carries it to your next phone.\n\nWhy it is not in an app store: a store takes a cut of every sale, charges a yearly fee to be listed, and decides what the app may do and when an update is allowed out. Notebuilt is a web app you add to your home screen instead. It costs nothing to keep it there, a fix reaches you the day it is written, and nobody stands between you and it. The trade is honest — there is no store listing to look us up in, so the code is readable and the privacy page tells you exactly what the app does.\n\nAnd because the check runs on your own phone, in code you can read, it is honesty-based. We know that. Paying is a choice to keep this being built, not a lock we have you behind.'
};

/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */
let _db=null;
"""

# ---------------------------------------------------------------------------
# 3. The old HELP_COPY definition comes out — it lives above now.
# ---------------------------------------------------------------------------
OLDCOPY_OLD = """/* PIN_RECOVERY — info-mode copy, planted now so info mode inherits it. */
const HELP_COPY={
  'theme':'Day is for bright cabs and outdoors, where a dark screen turns into a mirror. Night is the notebook you know. Auto follows whatever your phone is set to, and changes with it. This one is kept per device, not in your backup \\u2014 the phone in the truck and the tablet on the bench can each be set to suit where they are used.',
  'pin-recovery':'Your PIN keeps casual hands out of the app. It does not encrypt anything \\u2014 the vault passphrase does.',
  'photo-send':'Share hands the image straight to another app on this phone \\u2014 your workforce app, a message, email. Save to device puts a copy in your Downloads folder, which is not the same place as your camera roll; your gallery may not show it. Only the picture is sent: no project name, no address, nothing about where it was taken. From a protected project, both of these take the photo out of the vault as an ordinary unprotected image, and whatever receives it keeps it \\u2014 which is why it asks first, and why it needs the vault open to do it at all.',
  'unlock':'Free covers three projects, with every feature switched on \\u2014 photos, the vault, backups, the calculator. Unlocking lifts the limit on how many projects you keep, once, for one payment. Entering your key sends it to our payment provider a single time to activate it; after that Notebuilt never contacts anything again, and the unlock is never re-checked. The key is stored in your settings, so your backup carries it to your next phone.'
};
"""

OLDCOPY_NEW = """/* PIN_RECOVERY — the copy that stood here has moved into the
   EGS-STD:infomode block, with the rest of it. Info mode inherited it,
   which is what the note here always said would happen. maybeOfferRecoveryCode()
   below still reads HELP_COPY['pin-recovery']; nothing about that changed. */
"""

# ---------------------------------------------------------------------------
# 4. bind() — one line for the markers, two for the toggle and the notice.
# ---------------------------------------------------------------------------
BIND_OLD = """  $app.querySelectorAll('[data-theme-set]').forEach(b=>b.onclick=()=>{ nbSetTheme(b.dataset.themeSet); render(); toast('Theme: '+NB_THEME_LABEL[nbThemeMode()]); });
"""

BIND_NEW = """  $app.querySelectorAll('[data-theme-set]').forEach(b=>b.onclick=()=>{ nbSetTheme(b.dataset.themeSet); render(); toast('Theme: '+NB_THEME_LABEL[nbThemeMode()]); });
  /* EGS-STD:infomode — its own key too, and for the same reason as the theme
     above: it describes this phone, not the data, so persist.settings() is
     deliberately not involved. */
  $app.querySelectorAll('[data-guide-set]').forEach(b=>b.onclick=()=>{ nbGuideSet(b.dataset.guideSet==='on'); render(); toast(nbGuideOn()?'Beginner mode on':'Expert mode on'); });
  const gnX=$app.querySelector('[data-guide-notice-x]'); if(gnX) gnX.onclick=()=>nbGuideNoticeDismiss(false);
  nbHelpBind($app);
"""

# ---------------------------------------------------------------------------
# 5. sheet() — an optional corner marker, and binding what it drew.
# ---------------------------------------------------------------------------
SHEET_OLD = """function sheet(html){
  $mr.innerHTML=`<div class="scrim" data-scrim><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>${html}</div></div>`;
  $mr.querySelector('[data-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-scrim')) closeSheet(); });
}
"""

SHEET_NEW = """/* EGS-STD:infomode — the optional second argument is a HELP_COPY key, and
   the marker it draws is pinned to the sheet's corner rather than put in the
   title. Sheet titles carry project names, and a name long enough to wrap
   would wrap differently with a marker than without it. */
function sheet(html,helpKey){
  $mr.innerHTML=`<div class="scrim" data-scrim><div class="sheet" role="dialog" aria-modal="true"><div class="grab"></div>${helpKey?nbHelpCorner(helpKey):''}${html}</div></div>`;
  $mr.querySelector('[data-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-scrim')) closeSheet(); });
  nbHelpBind($mr);
}
"""

# ---------------------------------------------------------------------------
# 6..n  Marker placements. Each one is a host with slack — see the CSS note.
# ---------------------------------------------------------------------------
PLACEMENTS = [
    # --- To Do: title marker, plus the one-line notice in BOTH return paths.
    ("""<h1>To Do</h1>""",
     """<h1>To Do ${nbHelpMark('todos')}</h1>""",
     "To Do title marker"),

    ("""  if(!list.length) return head+`<div class="empty">${I.today}""",
     """  if(!list.length) return head+nbGuideNoticeHtml()+`<div class="empty">${I.today}""",
     "guide notice, empty To Do"),

    ("""  return head+`<div class="wrap">${sec('In progress',doing)}${sec('To do',todo)}${doneSec}</div>`;""",
     """  return head+nbGuideNoticeHtml()+`<div class="wrap">${sec('In progress',doing)}${sec('To do',todo)}${doneSec}</div>`;""",
     "guide notice, To Do list"),

    # --- Projects
    ("""<h1>Projects</h1>""",
     """<h1>Projects ${nbHelpMark('projects')}</h1>""",
     "Projects title marker"),

    # --- Notes (renderHouseNotes also draws <h1>Notes</h1>, hence the eyebrow)
    ("""<span class="eyebrow">Notebook</span><h1>Notes</h1>""",
     """<span class="eyebrow">Notebook</span><h1>Notes ${nbHelpMark('notes')}</h1>""",
     "Notes title marker"),

    # --- Calculator
    ("""'</span><h1>Calculator</h1></div>'+unitTog""",
     """'</span><h1>Calculator '+nbHelpMark('calc')+'</h1></div>'+unitTog""",
     "Calculator title marker"),

    # --- Project detail: photos
    ("""  const photoGrid=`<div class="sec-head"><span class="label">Photos</span><span class="rule"></span><span class="count">${photos.length}</span></div>""",
     """  const photoGrid=`<div class="sec-head"><span class="label">Photos</span>${nbHelpMark('photos')}<span class="rule"></span><span class="count">${photos.length}</span></div>""",
     "project photos marker"),

    # --- Project detail: notebook
    ("""  const notebookBlock=`<div class="sec-head"><span class="label">Notebook</span><span class="rule"></span><span class="count">${houseNotes.length}</span></div>""",
     """  const notebookBlock=`<div class="sec-head"><span class="label">Notebook</span>${nbHelpMark('notes')}<span class="rule"></span><span class="count">${houseNotes.length}</span></div>""",
     "project notebook marker"),

    # --- Settings sections
    ("""    <div class="sec-head"><span class="label">Security</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Security</span>${nbHelpMark('applock')}<span class="rule"></span></div>""",
     "settings security marker"),

    ("""    <div class="sec-head"><span class="label">Protected projects</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Protected projects</span>${nbHelpMark('vault')}<span class="rule"></span></div>""",
     "settings vault marker"),

    ("""    <div class="sec-head"><span class="label">Appearance</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Appearance</span>${nbHelpMark('theme')}<span class="rule"></span></div>""",
     "settings appearance marker"),

    ("""    <div class="sec-head"><span class="label">Photos</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Photos</span>${nbHelpMark('photos')}<span class="rule"></span></div>""",
     "settings photos marker"),

    ("""    <div class="sec-head"><span class="label">Unlock</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Unlock</span>${nbHelpMark('unlock')}<span class="rule"></span></div>""",
     "settings unlock marker"),

    # --- Support page
    ("""    <div class="sec-head"><span class="label">Back up your data</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Back up your data</span>${nbHelpMark('backup')}<span class="rule"></span></div>""",
     "support backup marker"),

    ("""    <div class="sec-head"><span class="label">Import a shared project</span><span class="rule"></span></div>""",
     """    <div class="sec-head"><span class="label">Import a shared project</span>${nbHelpMark('import-project')}<span class="rule"></span></div>""",
     "support import marker"),

]

# The three sheet() calls that gain a help key. Each is edited at its closing
# argument so the anchor stays small and unmistakable.
SHEET_KEYS = [
    ("""    <button class="btn primary block" id="sh-go">${I.share} Share project</button>`);""",
     """    <button class="btn primary block" id="sh-go">${I.share} Share project</button>`,'share');""",
     "share sheet help key"),

    ("""      <button class="btn primary block sm" id="cat-new-save" style="margin-top:8px">${I.plus} Add category</button>
    </div>`);""",
     """      <button class="btn primary block sm" id="cat-new-save" style="margin-top:8px">${I.plus} Add category</button>
    </div>`,'categories');""",
     "manage categories help key"),

    ("""    +'<button class="btn block" style="margin-top:10px" data-ph-cancel>Cancel</button>');""",
     """    +'<button class="btn block" style="margin-top:10px" data-ph-cancel>Cancel</button>','photo-send');""",
     "photo send help key"),
]

# ---------------------------------------------------------------------------
# The Guide section in Settings, and the EGS-STD:support marker §7 has owed
# since 2026-08-16.
# ---------------------------------------------------------------------------
GUIDE_OLD = """    <div class="sec-head"><span class="label">Units</span><span class="rule"></span></div>
"""

GUIDE_NEW = """    <div class="sec-head"><span class="label">Guide</span>${nbHelpMark('guide')}<span class="rule"></span></div>
    <div class="card row"><div class="grow"><div>Beginner mode</div><div class="muted" style="font-size:13px">${nbGuideOn()
      ? 'Small i marks sit beside each part of the app. Tap one to read what it does.'
      : 'Expert \\u2014 the i marks are hidden. Nothing else changes.'}</div></div>
      <div class="unit-toggle"><button class="${nbGuideOn()?'on':''}" data-guide-set="on">Beginner</button><button class="${nbGuideOn()?'':'on'}" data-guide-set="off">Expert</button></div></div>

    <div class="sec-head"><span class="label">Units</span><span class="rule"></span></div>
"""

SUPPORT_OLD = """function renderSupport(){
"""

SUPPORT_NEW = """/* EGS-STD:support — §2 row 7 lives here, on the view it describes. The row
   is conditional on an app charging or having a Support page; Notebuilt does
   both, so its SKIP at the deploy gate was silence on a row this app really
   implements, not a legitimate omission. §7 has recorded it as owed since
   2026-08-16. This is the next touch. */
function renderSupport(){
"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")

    edits = [
        (CSS_OLD, CSS_NEW, "info-marker CSS"),
        (JS_OLD, JS_NEW, "infomode JS block"),
        (OLDCOPY_OLD, OLDCOPY_NEW, "old HELP_COPY removal"),
        (BIND_OLD, BIND_NEW, "bind() wiring"),
        (SHEET_OLD, SHEET_NEW, "sheet() help key"),
        (GUIDE_OLD, GUIDE_NEW, "settings Guide section"),
        (SUPPORT_OLD, SUPPORT_NEW, "EGS-STD:support marker"),
    ]
    edits += [(o, n, l) for (o, n, l) in PLACEMENTS if o != n]
    edits += SHEET_KEYS

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # What this edit is FOR.
    if "EGS-STD:infomode" not in working:
        fail("the infomode marker did not land.")
    if working.count(':root[data-guide="off"] .help-i{display:none}') != 1:
        fail("expert mode must be exactly one stylesheet rule — found a different count.")
    if working.count("const HELP_COPY={") != 1:
        fail("HELP_COPY is not defined exactly once.")

    # Every marker key drawn must have copy behind it, and every entry of copy
    # must be reachable from something. A marker whose key is a typo renders
    # perfectly and does nothing when tapped, which is the failure this catches.
    import re as _re
    body = working.split("const HELP_COPY={", 1)[1].split("\n};", 1)[0]
    have = set(_re.findall(r"^  '([a-z-]+)':", body, _re.M))
    drawn = set(_re.findall(r"nbHelpMark\('([a-z-]+)'\)", working))
    keyed = {k for _, n, _ in SHEET_KEYS for k in _re.findall(r"'([a-z-]+)'\);$", n)}
    if len(keyed) != len(SHEET_KEYS):
        fail("a sheet help key could not be read back out of its own edit.")
    reached = drawn | keyed
    missing = reached - have
    if missing:
        fail(f"markers drawn with no copy behind them: {sorted(missing)}")
    orphan = have - reached
    # 'pin-recovery' is quoted directly by maybeOfferRecoveryCode(), not by a
    # marker, and is the one entry allowed to be unreachable from a tap.
    if orphan != {'pin-recovery'}:
        fail(f"copy nothing can reach: {sorted(orphan)}")
    titles = set(_re.findall(r"^  '([a-z-]+)':",
                 working.split("const HELP_TITLE={", 1)[1].split("\n};", 1)[0], _re.M))
    if titles != have:
        fail(f"HELP_TITLE and HELP_COPY disagree: {sorted(titles ^ have)}")
    print(f"   (i) markers: {len(drawn)} in flow + {len(keyed)} sheet corners · "
          f"{len(have)} HELP_COPY entries, all titled")

    # No marker may sit on a host without slack. Legal hosts are a .sec-head,
    # one of four short fixed <h1>s, or a sheet corner. A marker inside a
    # variable-length title is the reflow bug this whole design exists to
    # avoid, so pin the count of title markers at exactly those four.
    n_titles = (len(_re.findall(r"<h1>[^<]*\$\{nbHelpMark", working))
                + len(_re.findall(r"<h1>[^<]*'\+nbHelpMark", working)))
    if n_titles != 4:
        fail(f"{n_titles} title markers — a marker landed on a title that is not one of the four fixed ones.")

    # The startup-write law: one writer each, and only a tap reaches either.
    if working.count("localStorage.setItem(NB_GUIDE_KEY") != 1:
        fail("NB_GUIDE_KEY must have exactly one writer.")
    if working.count("localStorage.setItem(NB_GUIDE_NOTICE_KEY") != 1:
        fail("NB_GUIDE_NOTICE_KEY must have exactly one writer.")
    # Per-device means per-device: the guide block may not touch settings, or
    # the preference would ride a backup onto somebody else's phone.
    guide_block = working.split("EGS-STD:infomode — beginner", 1)[1] \
                         .split("/* ---------- IndexedDB", 1)[0]
    if "persist.settings" in guide_block or "saveSettings" in guide_block:
        fail("the guide preference reached into settings — it is per-device, like the theme.")

    # What must not change.
    if working.count("const NB_THEME_KEY='notebuilt.theme';") != 1:
        fail("the theme key moved.")
    if working.count("nbSetTheme") != 3:
        fail("nbSetTheme is no longer its comment, its definition and one call site.")
    if "EGS-STD:themes" not in working or "EGS-STD:schema" not in working \
       or "EGS-STD:gate" not in working or "EGS-STD:coldopen-version" not in working:
        fail("an existing standards marker was lost.")

    # ---- backup, then write --------------------------------------------
    stamp = int(time.time())
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}")
    n = 1
    while backup_path.exists():
        backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{stamp}-{n}")
        n += 1
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edit(s) to {TARGET}")

    # ---- syntax check: EVERY inline block, or restore -------------------
    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit stands WITHOUT a syntax check.")
        else:
            shutil.copy2(backup_path, TARGET)
            fail("restored from backup — nothing was changed.")

    print("\n✅ Notebuilt opens in beginner mode, every major surface carries an (i), "
          "and one stylesheet rule takes them all away.")


if __name__ == "__main__":
    main()
