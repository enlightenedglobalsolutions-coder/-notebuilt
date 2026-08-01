#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — share: landing-header placement + promotion into the EGS core
Run this from the same folder as your index.html:
    python3 fix_share_core.py

Requires fix_share_app.py.

TWO ENTRY POINTS, ONE HANDLER
  * a share icon in the landing (To Do) header, left of the search icon
  * the button on the Support & Backup page
Both call doShareApp(). Both draw the glyph from one const. Nothing to drift.

PROMOTED INTO THE CORE
appShareUrl(), doShareApp(), the glyph and the Support-page block all move into
the EGS CORE section so every EGS app inherits them by copying the block
verbatim, as the banner instructs. Notebuilt's app-specific copy in
renderSupport() comes out in the same edit. The only thing left in app-specific
territory is SHARE_APP_LINE — the pitch — which is per-app by nature, exactly
like PAYMENT_CONFIG.

FINDINGS FROM READING WFD, WHICH THE BRIEF DID NOT ANTICIPATE
  1. There was no version marker on egsSupportCoreHtml anywhere — not in
     Notebuilt, Roadside, KEPT or Stagger. "Version-bumped" therefore means
     introducing versioning, not incrementing it. This marks the block v2 and
     records what v2 added. v1 is every existing unversioned copy.
  2. WFD has NO share block in its core — its share is a header-only ES5 IIFE.
     So there was no core implementation to unify with; this establishes the
     core one, with WFD's glyph and behaviour as the reference.
  3. WFD's glyph is Feather "share-2" (three nodes), NOT the box-with-up-arrow
     Notebuilt already uses for "Share project". Same path data as WFD is used
     here, but stroked currentColor rather than WFD's hardcoded #185FA5, so it
     inherits the host app's icon colour instead of importing WFD's palette.
  4. WFD hardcodes https://wfdegs.ca. Notebuilt computes the URL from location,
     which is kept: it is correct on any host and has no value to get stale.
  5. WFD's clipboard path is an else-if only, and it swallows a rejected
     navigator.share without falling back. Notebuilt's version distinguishes
     AbortError from a real failure and falls through. That behaviour is kept
     and is what goes into the core.

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
MARKER = "EGS_SHARE_GLYPH"
REQUIRES = ["SHARE_APP"]

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
            fail(f"{req} not found — run fix_share_app.py first.")

    edits = []

    # ---------------------------------------------------------------
    # Edit 1: app-specific keeps only the pitch line; mechanism moves to core
    # ---------------------------------------------------------------
    old = r"""/* The share line. One string, easy to veto or rewrite. */
const SHARE_APP_LINE = 'Notebuilt — the field notebook for construction crews. Private, offline, yours.';

function appShareUrl(){
  /* the app's own directory URL, never a deep link into any state */
  return location.origin + location.pathname.replace(/[^/]*$/, '');
}
async function doShareApp(){
  const url=appShareUrl();
  if(navigator.share){
    try{
      await navigator.share({ title:APP_NAME, text:SHARE_APP_LINE, url });
      return;                                     /* the OS sheet said its piece */
    }catch(err){
      if(err && err.name==='AbortError') return;  /* user backed out — say nothing */
      /* anything else: fall through to the clipboard */
    }
  }
  try{
    await navigator.clipboard.writeText(SHARE_APP_LINE+' '+url);
    toast('Link copied');
  }catch(e){
    /* clipboard refused (insecure context, permissions) — show it instead of
       swallowing it, so there is always a way to get the link out */
    sheet('<h2>Share '+esc(APP_NAME)+'</h2>'
      +'<div class="muted" style="font-size:13px;margin-bottom:10px">Copy this and send it on:</div>'
      +'<div class="card mono" style="font-size:12.5px;word-break:break-all;line-height:1.6">'
      +esc(SHARE_APP_LINE+' '+url)+'</div>'
      +'<button class="btn primary block" data-copy="'+esc(SHARE_APP_LINE+' '+url)+'" style="margin-top:10px">Copy</button>');
    bindCopyButtons($mr);
  }
}

function renderSupport(){"""

    new = r"""/* The share line — the pitch, per app, like PAYMENT_CONFIG. The mechanism that
   sends it lives in the EGS CORE block below. Easy to veto or rewrite. */
const SHARE_APP_LINE = 'Notebuilt — the field notebook for construction crews. Private, offline, yours.';

function renderSupport(){"""
    edits.append((old, new, "app-specific: keep the line, move the mechanism"))

    # ---------------------------------------------------------------
    # Edit 2: drop the app-specific Support-page block (moves into core)
    # ---------------------------------------------------------------
    old = r"""    <div class="sec-head"><span class="label">Share ${esc(APP_NAME)}</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Know a crew who'd use this? Passing it on is its own kind of support, and it costs nothing. This sends the app's public link and nothing else &mdash; none of your projects, photos or notes go with it.</div>
    <button class="btn block" data-share-app style="margin:10px 0 22px;display:flex;align-items:center;justify-content:center;gap:8px">${I.share} Share ${esc(APP_NAME)}</button>

    ${egsSupportCoreHtml(tabs)}"""
    new = r"""    ${egsSupportCoreHtml(tabs)}"""
    edits.append((old, new, "remove app-specific Support share block"))

    # ---------------------------------------------------------------
    # Edit 3: version the core banner and add the mechanism above it
    # ---------------------------------------------------------------
    # The core banner writes its dashes as backslash-u escapes, so the anchor is
    # built explicitly rather than typed.
    D = "\\u2014"
    old = ("/* ============================================================\n"
           "   EGS CORE " + D + " SUPPORT SECTION\n"
           "   Copy this function verbatim into every new EGS app. Do not\n"
           "   edit the copy below " + D + " only PAYMENT_CONFIG (near the top of\n"
           "   the file) should ever change, and only to add real payment\n"
           "   links.\n"
           "   ============================================================ */\n"
           "function egsSupportCoreHtml(tabs){")

    new = r"""/* ============================================================
   EGS CORE — SUPPORT SECTION · v2
   Copy this block verbatim into every new EGS app. Do not edit
   the copy below — only PAYMENT_CONFIG and SHARE_APP_LINE (both
   near the top of the file) should ever change, and only to
   carry that app's real payment links and its own pitch line.

   v2 — adds share-the-app: EGS_SHARE_GLYPH, appShareUrl(),
        doShareApp(), and the Share section inside
        egsSupportCoreHtml(). Hosts supply APP_NAME and
        SHARE_APP_LINE, and may place a second entry point (a
        header icon) that calls doShareApp() and draws
        EGS_SHARE_GLYPH — one handler, one glyph, no drift.
   v1 — every existing unversioned copy: support blurb, privacy
        row, payment tabs, footer. Roadside, KEPT, Stagger and
        WFD are all still v1 as of this edit.
   ============================================================ */

/* Feather "share-2", the glyph WFD uses — same path data, stroked
   currentColor so it takes the host app's icon colour. */
const EGS_SHARE_GLYPH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>';

function appShareUrl(){
  /* the app's own directory URL, never a deep link into any state */
  return location.origin + location.pathname.replace(/[^/]*$/, '');
}
/* The ONE share handler. Every entry point calls this. It can only ever send
   the public app link: no project, photo, note, setting or vault state is
   reachable from here, and keeping that true is the point. */
async function doShareApp(){
  const url=appShareUrl();
  if(navigator.share){
    try{
      await navigator.share({ title:APP_NAME, text:SHARE_APP_LINE, url });
      return;                                     /* the OS sheet said its piece */
    }catch(err){
      if(err && err.name==='AbortError') return;  /* user backed out — say nothing */
      /* anything else: fall through to the clipboard rather than swallow it */
    }
  }
  try{
    await navigator.clipboard.writeText(SHARE_APP_LINE+' '+url);
    toast('Link copied');
  }catch(e){
    /* clipboard refused (insecure context, permissions) — show it instead of
       swallowing it, so there is always a way to get the link out */
    sheet('<h2>Share '+esc(APP_NAME)+'</h2>'
      +'<div class="muted" style="font-size:13px;margin-bottom:10px">Copy this and send it on:</div>'
      +'<div class="card mono" style="font-size:12.5px;word-break:break-all;line-height:1.6">'
      +esc(SHARE_APP_LINE+' '+url)+'</div>'
      +'<button class="btn primary block" data-copy="'+esc(SHARE_APP_LINE+' '+url)+'" style="margin-top:10px">Copy</button>');
    bindCopyButtons($mr);
  }
}

function egsSupportCoreHtml(tabs){"""
    edits.append((old, new, "core: v2 banner + share mechanism"))

    # ---------------------------------------------------------------
    # Edit 4: the Share section inside the core block
    # ---------------------------------------------------------------
    LOCK, ARROW = "\\ud83d\\udd12", "\\u2192"
    PRIVACY_ROW = ('    <div class="row" data-go="privacy" style="cursor:pointer;margin:6px 0 18px">'
                   '<span class="muted" style="font-size:13px">' + LOCK
                   + ' Our privacy promise &amp; how we make money ' + ARROW + '</span></div>\n')
    old = PRIVACY_ROW
    new = PRIVACY_ROW + r"""

    <div class="sec-head"><span class="label">Share ${esc(APP_NAME)}</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Passing it on is its own kind of support, and it costs nothing. This sends the app's public link and nothing else &mdash; none of your own data goes with it.</div>
    <button class="btn block" data-share-app style="margin:10px 0 22px;display:flex;align-items:center;justify-content:center;gap:8px"><span style="display:inline-flex;width:18px;height:18px">${EGS_SHARE_GLYPH}</span> Share ${esc(APP_NAME)}</button>
"""
    edits.append((old, new, "core: Share section"))

    # ---------------------------------------------------------------
    # Edit 5: landing header entry point, left of search
    # ---------------------------------------------------------------
    old = r"""  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">${esc(d.toLocaleDateString(undefined,{weekday:'long'}))} · ${esc(d.toLocaleDateString(undefined,{month:'long',day:'numeric'}))}</span><h1>To Do</h1></div>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;"""
    new = r"""  /* Landing header: share, then search. Two icon buttons is the ceiling here —
     the eyebrow date is the widest thing in this bar at phone width. */
  const head=`<div class="topbar"><div class="grow"><span class="eyebrow">${esc(d.toLocaleDateString(undefined,{weekday:'long'}))} · ${esc(d.toLocaleDateString(undefined,{month:'long',day:'numeric'}))}</span><h1>To Do</h1></div>
    <button class="icon-btn" data-share-app aria-label="Share ${esc(APP_NAME)}" title="Share ${esc(APP_NAME)}">${EGS_SHARE_GLYPH}</button>
    <button class="icon-btn" data-go="search" aria-label="Search">${I.search}</button></div>`;"""
    edits.append((old, new, "landing header: share icon"))

    # ---------------------------------------------------------------
    # Edit 6: bind every entry point, not just the first
    # ---------------------------------------------------------------
    old = r"""  const shareAppBtn=$app.querySelector('[data-share-app]'); if(shareAppBtn) shareAppBtn.onclick=doShareApp;"""
    new = r"""  $app.querySelectorAll('[data-share-app]').forEach(b=>b.onclick=doShareApp);"""
    edits.append((old, new, "bind(): all share entry points"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # The glyph must be defined exactly once — the whole point of the const.
    if working.count("<circle cx=\"18\" cy=\"5\" r=\"3\"/>") != 1:
        fail("share glyph path data appears more than once — it must have a single definition.")
    print("✅ assertion: the share glyph is defined exactly once")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit; restored from backup.")
    js_path = Path("/tmp/_notebuilt_sharecore_check.js")
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

    print("\n✅ Share promoted to EGS CORE v2, with a landing-header entry point.")

if __name__ == "__main__":
    main()
