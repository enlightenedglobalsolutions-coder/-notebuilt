#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — two themes: a daylight trade palette beside the night one.
Run from the same folder as index.html:
    python3 fix_themes_day_and_night.py

EGS-STANDARDS §2 row 13. Notebuilt shipped dark-only: one :root block, no
prefers-color-scheme, no data-theme, ~96 references to --ink/--paper.

Three things land here.

1. THE MECHANISM. A script in <head> reads notebuilt.theme and stamps
   data-theme on <html> BEFORE the stylesheet is parsed, so the first paint
   is already the right theme. Applying a theme from the app's own boot code
   paints the wrong colours first and corrects them a frame later — that
   flash is the whole reason the read has to happen up there.

   The mode is stored in its own one-word key, NOT in settings: the <head>
   script has to read it before any app code exists, and settings can be an
   unreadable blob — a state this app already handles and draws a card for.
   A bare string survives that. It is written on a tap and never at startup,
   so the Aug-13 law ("nothing about the app's startup may write settings")
   is untouched — this key is not settings, and nothing writes it on load.

   'system' is stamped as itself rather than resolved to light/dark, so the
   CSS media query does the following. That means a live OS switch is
   tracked by the stylesheet with no JavaScript in the path at all.

2. THE ROLE SPLIT — the trap this row exists to name. --ink and --paper
   EXCHANGE ROLES between themes: --ink is the ground and --paper is the
   text in both, but the values swap ends of the scale. Every rule that used
   them as roles keeps working untouched. Every rule that used them as
   VALUES breaks, and those are the edits below:

     .unit-toggle button.on{background:var(--brass);color:var(--ink)}

   reads "dark text on gold" today and would become light-on-gold in
   daylight. So the accent splits in two, and they always travel together:

     --brass       accent that must be READ against the ground   (deepens in
                   daylight to #855E11, or it fails on paper)
     --brass-fill  accent as a metal PLATE                       (stays gold)
     --on-brass    the only thing written on that plate          (stays dark)

3. THE MEASURED PALETTE. Contrast was computed, not eyeballed, for every
   text-on-ground pairing in BOTH themes. That measurement found the shipped
   dark theme already failing: --paper-faint at 2.70:1 on a card (it draws
   the version stamp, task meta and completed to-dos), --danger at 3.72:1,
   --doing at 4.44:1. The gate for this work says both themes pass, so the
   dark values are lifted by the smallest hue-preserving step that clears
   4.5:1 — #6E6B61 -> #949186, #C8654B -> #D07A64, #6E92B8 -> #7194B9.
   Notebuilt looks like itself; the faint text is now actually readable.

   Daylight is a design, not an inversion: warm drafting paper, graphite
   rules, the same brass. Not a photo-negative of the night theme.

Surfaces that are dark BY NATURE — the photo viewer, the annotate stage, the
camera viewfinder, the vault progress veil — re-declare the role tokens to
their night values in a scoped block. A photograph and a live lens are
content, judged against a dark ground in any theme, the way every photo app
does it. Without that block the daylight theme paints dark text onto
near-black: #viewer .v-count is var(--paper-dim), and it would vanish.

Backs up first, exact-match anchors asserted ==1, EVERY inline script block
syntax-checked, atomic.
"""
import re
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


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the app's repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # ------------------------------------------------------------------
    # 1. The <head> boot script — before the stylesheet, deliberately.
    # ------------------------------------------------------------------
    # Anchored on <title>, not on the EGS_VERSION line: that line's value
    # changes every deploy, and an anchor that rots on the next ship is an
    # anchor that will abort a rerun for no reason.
    old = """<title>Notebuilt</title>
<style>"""
    new = """<title>Notebuilt</title>
<!-- EGS-STD:themes — §2 row 13. This script runs BEFORE the stylesheet on
     purpose: it stamps the chosen mode on <html> so the very first paint is
     already the right theme. Read only — it never writes, so the "nothing at
     startup writes preferences" law holds. 'system' is stamped as itself and
     left for the CSS media query to follow, which is why a live OS switch
     needs no JavaScript. The status-bar colours live here, in one place, so
     the toggle later cannot drift from what the first frame used. -->
<script>window.NB_THEME_BAR={dark:'#15181D',light:'#E9E4D7'};
(function(){var m='system';
  try{var s=localStorage.getItem('notebuilt.theme');if(s==='light'||s==='dark')m=s;}catch(e){}
  document.documentElement.setAttribute('data-theme',m);
  var dark=(m==='dark')||(m==='system'&&!(window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches));
  var t=document.querySelector('meta[name="theme-color"]');
  if(t)t.setAttribute('content',dark?window.NB_THEME_BAR.dark:window.NB_THEME_BAR.light);})();</script>
<style>"""
    edits.append((old, new, "head theme boot script"))

    # ------------------------------------------------------------------
    # 2. The token block: night base, daylight override, dark-by-nature scope.
    # ------------------------------------------------------------------
    old = """  /* ---- Design tokens: a leather field-notebook holding spec-stamp pages ---- */
  :root{
    --ink:#15181D;        /* notebook cover / app shell */
    --ink-2:#1C2027;      /* raised surface */
    --ink-3:#252A33;      /* card */
    --line:#333A45;       /* hairline rule (blueprint) */
    --line-soft:#2A2F39;
    --paper:#ECE6D8;      /* light text on dark */
    --paper-dim:#A7A294;  /* secondary text */
    --paper-faint:#6E6B61;/* tertiary */
    --brass:#D7A94B;      /* hardware accent */
    --brass-deep:#9A6E27;
    --doing:#6E92B8;      /* slate blue */
    --done:#7E9D63;       /* sage */
    --danger:#C8654B;
    --radius:14px;"""
    new = """  /* ---- Design tokens: a leather field-notebook holding spec-stamp pages ----
     EGS-STD:themes — §2 row 13 lives here, on the block it describes.

     THE ROLE RULE, because this is the one that bites: --ink is always the
     GROUND and --paper is always the TEXT ON IT. The names describe roles,
     not brightnesses, and the values swap ends of the scale between themes.
     Read every rule below as a role and it stays correct in both. Read one
     as a colour — "--paper is the light one" — and it inverts in daylight.

     The accent is split for the same reason, and the two halves always
     appear together: --brass is the accent you READ (it deepens on paper or
     it fails contrast), --brass-fill is the gold PLATE, and --on-brass is
     the only thing ever written on that plate. Never put --paper or --ink on
     a brass fill; --on-brass is what that is for.

     Every text-on-ground pairing here was measured, not eyeballed, and
     clears 4.5:1 in BOTH themes. --paper-faint, --doing and --danger were
     lifted from their launch values, which did not: --paper-faint sat at
     2.70:1 on a card while drawing the version stamp, to-do meta lines and
     completed to-dos. The lift is the smallest hue-preserving step that
     clears the bar, so the night theme still looks like itself. */
  :root{
    /* Night — the shipped identity, and the base every theme falls back to. */
    --ink:#15181D;        /* GROUND: notebook cover / app shell */
    --ink-2:#1C2027;      /* raised surface */
    --ink-3:#252A33;      /* card */
    --line:#333A45;       /* hairline rule (blueprint) */
    --line-soft:#2A2F39;
    --paper:#ECE6D8;      /* TEXT on the ground */
    --paper-dim:#A7A294;  /* secondary text */
    --paper-faint:#949186;/* tertiary — was #6E6B61, 2.70:1 on a card */
    --brass:#D7A94B;      /* accent you READ */
    --brass-fill:#D7A94B; /* accent as a PLATE */
    --on-brass:#231A07;   /* the only ink that goes on that plate */
    --brass-deep:#9A6E27;
    --doing:#7194B9;      /* slate blue — was #6E92B8, 4.44:1 on a card */
    --done:#7E9D63;       /* sage */
    --danger:#D07A64;     /* was #C8654B, 3.72:1 on a card */
    --done-wash:rgba(126,157,99,.14);
    --nav-bg:rgba(20,24,29,.92);
    --scrim:rgba(0,0,0,.55);
    --shadow-pop:0 8px 22px rgba(0,0,0,.45);
    --shadow-card:0 8px 24px rgba(0,0,0,.4);
    --radius:14px;"""
    edits.append((old, new, "night token block"))

    # The daylight block + the dark-by-nature scope go after the :root close.
    old = """    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}"""
    new = """    --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  }

  /* ---- Daylight: a spec sheet on a job-site table ----
     Not an inversion of the night theme. Warm drafting paper, graphite
     rules, the same brass — Notebuilt in a bright cab or out on a deck,
     where a dark screen is a mirror. Elevation still runs the same
     direction as at night (raised = further from the ground colour), so
     every existing rule reads correctly without being rewritten.

     ORDER MATTERS BELOW. The media block is guarded so an explicit choice
     of night wins over a daylight phone, and the [data-theme="light"] block
     is written AFTER it because the two have identical specificity — source
     order is the only thing separating them. Moving either one breaks a
     mode without breaking anything a quick look would catch. */
  @media (prefers-color-scheme: light){
    :root:not([data-theme="dark"]){
      --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
      --line:#998F78; --line-soft:#C9C0AC;
      --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C;
      --brass:#855E11; --brass-fill:#D7A94B; --on-brass:#231A07;
      --brass-deep:#6B4A0C;
      --doing:#35608A; --done:#4A6B33; --danger:#A83E27;
      --done-wash:rgba(74,107,51,.13);
      --nav-bg:rgba(243,239,229,.92);
      --scrim:rgba(38,32,20,.44);
      --shadow-pop:0 8px 22px rgba(58,48,30,.20);
      --shadow-card:0 8px 24px rgba(58,48,30,.15);
    }
  }
  :root[data-theme="light"]{
    --ink:#E9E4D7; --ink-2:#F2EEE3; --ink-3:#FAF7EF;
    --line:#998F78; --line-soft:#C9C0AC;
    --paper:#1E222A; --paper-dim:#55595F; --paper-faint:#68655C;
    --brass:#855E11; --brass-fill:#D7A94B; --on-brass:#231A07;
    --brass-deep:#6B4A0C;
    --doing:#35608A; --done:#4A6B33; --danger:#A83E27;
    --done-wash:rgba(74,107,51,.13);
    --nav-bg:rgba(243,239,229,.92);
    --scrim:rgba(38,32,20,.44);
    --shadow-pop:0 8px 22px rgba(58,48,30,.20);
    --shadow-card:0 8px 24px rgba(58,48,30,.15);
  }

  /* ---- Surfaces that are dark BY NATURE, in either theme ----
     A photograph and a live lens are content, not chrome. They are judged
     against a dark ground in daylight exactly as at night, the way every
     photo app on the phone does it — so these four layers re-declare the
     role tokens to their night values instead of inheriting the page's.

     This is a scope, not a list of overrides, and that is the point: every
     rule inside these layers already speaks in roles, so pinning the roles
     once fixes all of them at a stroke. Without it, daylight paints dark
     text onto near-black — #viewer .v-count is var(--paper-dim), and it
     would simply disappear.

     #vault is NOT here: the ceremony screen is chrome, and follows. Only
     #vault-busy, the veil drawn over it while keys derive, is pinned. */
  #viewer,#annotate,#camera,#vault-busy{
    --ink:#15181D; --ink-2:#1C2027; --ink-3:#252A33;
    --line:#333A45; --line-soft:#2A2F39;
    --paper:#ECE6D8; --paper-dim:#A7A294; --paper-faint:#949186;
    --brass:#D7A94B; --brass-fill:#D7A94B; --on-brass:#231A07;
    --doing:#7194B9; --done:#7E9D63; --danger:#D07A64;
    color:var(--paper);
  }

  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}"""
    edits.append((old, new, "daylight block + dark-by-nature scope"))

    # ------------------------------------------------------------------
    # 3. Every gold PLATE moves to --brass-fill/--on-brass, together.
    # ------------------------------------------------------------------
    plates = [
        ("""  .chip-filter.active{background:var(--brass);color:#231a07;border-color:var(--brass)}""",
         """  .chip-filter.active{background:var(--brass-fill);color:var(--on-brass);border-color:var(--brass-fill)}""",
         "category chip, selected"),
        ("""  .btn.primary{background:var(--brass);color:#231a07;border-color:var(--brass)}""",
         """  .btn.primary{background:var(--brass-fill);color:var(--on-brass);border-color:var(--brass-fill)}""",
         "primary button"),
        ("""    width:58px;height:58px;border-radius:18px;background:var(--brass);color:#231a07;
    display:grid;place-items:center;box-shadow:0 8px 22px rgba(0,0,0,.45);""",
         """    width:58px;height:58px;border-radius:18px;background:var(--brass-fill);color:var(--on-brass);
    display:grid;place-items:center;box-shadow:var(--shadow-pop);""",
         "FAB"),
        ("""    background:var(--brass);color:#231a07;font-weight:600;font-size:14px;
    padding:11px 18px;border-radius:12px;box-shadow:0 8px 22px rgba(0,0,0,.4);""",
         """    background:var(--brass-fill);color:var(--on-brass);font-weight:600;font-size:14px;
    padding:11px 18px;border-radius:12px;box-shadow:var(--shadow-card);""",
         "toast"),
        ("""  .a-tool.active{background:var(--brass);color:#231a07}""",
         """  .a-tool.active{background:var(--brass-fill);color:var(--on-brass)}""",
         "annotate tool, active"),
        ("""  .cam-chip.on{background:var(--brass);border-color:var(--brass);color:#231a07}""",
         """  .cam-chip.on{background:var(--brass-fill);border-color:var(--brass-fill);color:var(--on-brass)}""",
         "camera chip, on"),
        ("""  .cam-flash.on{background:var(--brass);border-color:var(--brass);color:#231a07}""",
         """  .cam-flash.on{background:var(--brass-fill);border-color:var(--brass-fill);color:var(--on-brass)}""",
         "camera flash, on"),
        # The trap, caught in the wild. --ink meant "the dark one" here.
        ("""  .unit-toggle button.on{background:var(--brass);color:var(--ink)}""",
         """  /* --on-brass, NOT --ink: --ink is the GROUND role, and in daylight the
     ground is the pale one — this read as dark-on-gold only because night
     was the only theme. This single line is the whole role-token lesson. */
  .unit-toggle button.on{background:var(--brass-fill);color:var(--on-brass)}""",
         "unit toggle, selected"),
        # Continuous light: white plate, dark glyph. Inside the pinned scope,
        # so var(--ink) resolves to the same #15181D it always was.
        ("""  .cam-flash.torch{background:var(--paper);border-color:var(--paper);color:#15181D}""",
         """  .cam-flash.torch{background:var(--paper);border-color:var(--paper);color:var(--ink)}""",
         "camera torch plate"),
    ]
    edits.extend(plates)

    # ------------------------------------------------------------------
    # 4. The remaining raw colours that are chrome, not content.
    # ------------------------------------------------------------------
    edits.append((
        """  .punch.done{border-color:var(--done);color:var(--done);background:rgba(126,157,99,.14)}""",
        """  .punch.done{border-color:var(--done);color:var(--done);background:var(--done-wash)}""",
        "done punch wash"))
    edits.append((
        """    background:rgba(20,24,29,.92);backdrop-filter:blur(12px);""",
        """    background:var(--nav-bg);backdrop-filter:blur(12px);""",
        "bottom nav"))
    edits.append((
        """  .scrim{position:fixed;inset:0;z-index:80;background:rgba(0,0,0,.55);display:flex;align-items:flex-end}""",
        """  .scrim{position:fixed;inset:0;z-index:80;background:var(--scrim);display:flex;align-items:flex-end}""",
        "sheet scrim"))
    edits.append((
        """  #install-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
  }""",
        """  #install-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:var(--shadow-card);
  }""",
        "install banner shadow"))
    edits.append((
        """  #backup-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
  }""",
        """  #backup-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:var(--shadow-card);
  }""",
        "backup banner shadow"))

    # Two plates that sit on PHOTOGRAPHS. They stay raw and dark in both
    # themes for the same reason #viewer does, and the comment is the edit —
    # so the session-2 sweep does not "finish the job" by tokenising them.
    edits.append((
        """  .sorted-star{
    position:absolute;top:5px;right:5px;display:grid;place-items:center;
    width:26px;height:26px;border-radius:50%;
    background:rgba(21,24,29,.72);color:var(--brass);
  }""",
        """  /* Raw and dark on purpose, in both themes: this plate sits on a photo
     thumbnail, and a photo is not chrome. Tokenising it would make the
     badge pale-on-photo in daylight and lose the star. */
  .sorted-star{
    position:absolute;top:5px;right:5px;display:grid;place-items:center;
    width:26px;height:26px;border-radius:50%;
    background:rgba(21,24,29,.72);color:#D7A94B;
  }""",
        "sorted star plate"))
    edits.append((
        """  .photo-grid .ph .x{
    position:absolute;top:3px;right:3px;width:24px;height:24px;border-radius:50%;
    background:rgba(0,0,0,.55);display:grid;place-items:center;color:#fff;
  }""",
        """  /* Also on a photo, also raw in both themes — see .sorted-star. */
  .photo-grid .ph .x{
    position:absolute;top:3px;right:3px;width:24px;height:24px;border-radius:50%;
    background:rgba(0,0,0,.55);display:grid;place-items:center;color:#fff;
  }""",
        "photo remove button"))

    # ------------------------------------------------------------------
    # 5. --gold never existed. The fallback was doing all the work.
    # ------------------------------------------------------------------
    edits.append((
        """    ${schemaFromFuture?`<div class="card" style="border:1px solid var(--gold,#C89F47);margin-bottom:14px">""",
        """    ${schemaFromFuture?`<div class="card" style="border:1px solid var(--brass);margin-bottom:14px">""",
        "schema-from-future card border"))
    edits.append((
        """    ${settingsUnreadable?`<div class="card" style="border:1px solid var(--danger,#b5453b);margin-bottom:14px">""",
        """    ${settingsUnreadable?`<div class="card" style="border:1px solid var(--danger);margin-bottom:14px">""",
        "unreadable-settings card border"))

    # ------------------------------------------------------------------
    # 6. The toggle's other half, in the app block.
    # ------------------------------------------------------------------
    old = """/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */"""
    new = """/* ============================================================
   EGS-STD:themes — day, night, and follow-the-phone
   ============================================================
   The <head> script did the part that matters for the first frame. Nothing
   in this block runs early enough to prevent a flash of the wrong theme;
   this half is the toggle, and keeping the status bar in step.

   nbThemeMode() is a pure read and is safe to call at any time. The only
   writer is nbSetTheme below, and only a tap reaches it — startup never
   does. A fix-script guard pins that: the name may appear exactly twice in
   the file, its definition and its one call site. */
const NB_THEME_KEY='notebuilt.theme';
function nbThemeMode(){
  try{ const m=localStorage.getItem(NB_THEME_KEY); return (m==='light'||m==='dark')?m:'system'; }
  catch(e){ return 'system'; }
}
const NB_THEME_LABEL={light:'Day',dark:'Night',system:'Auto'};
/* What the phone would show right now, which is only the same as the mode
   when the mode is not 'system'. Absent matchMedia, night — the identity. */
function nbThemeIsDark(){
  const m=nbThemeMode();
  if(m!=='system') return m==='dark';
  return !(window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
}
/* Colours come from the CSS; the status bar is the one thing that cannot,
   so it is set here from the same NB_THEME_BAR the first frame used. */
function nbApplyTheme(){
  document.documentElement.setAttribute('data-theme',nbThemeMode());
  const bar=window.NB_THEME_BAR||{dark:'#15181D',light:'#E9E4D7'};
  const meta=document.querySelector('meta[name="theme-color"]');
  if(meta) meta.setAttribute('content', nbThemeIsDark()?bar.dark:bar.light);
}
function nbSetTheme(mode){
  if(mode!=='light'&&mode!=='dark') mode='system';
  try{ localStorage.setItem(NB_THEME_KEY,mode); }catch(e){}
  nbApplyTheme();
}
/* Following a live OS switch is the stylesheet's job — data-theme stays
   'system' and the media query re-evaluates on its own. This listener is
   here only for the status bar, which no media query can reach. */
if(window.matchMedia){
  const nbMQ=window.matchMedia('(prefers-color-scheme: light)');
  const nbOnSystemChange=()=>{ if(nbThemeMode()==='system') nbApplyTheme(); };
  if(nbMQ.addEventListener) nbMQ.addEventListener('change',nbOnSystemChange);
  else if(nbMQ.addListener) nbMQ.addListener(nbOnSystemChange);
}

/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */"""
    edits.append((old, new, "theme helpers"))

    # ------------------------------------------------------------------
    # 7. Settings: the three-way toggle, in the app's own segmented idiom.
    # ------------------------------------------------------------------
    old = """    <div class="sec-head"><span class="label">Units</span><span class="rule"></span></div>"""
    new = """    <div class="sec-head"><span class="label">Appearance</span><span class="rule"></span></div>
    <div class="card row" data-help="theme"><div class="grow"><div>Theme</div><div class="muted" style="font-size:13px">${
      nbThemeMode()==='system'
        ? 'Following your phone \\u2014 '+(nbThemeIsDark()?'night':'day')+' right now.'
        : (nbThemeMode()==='light' ? 'Daylight, whatever your phone is set to.'
                                   : 'Night, whatever your phone is set to.')}</div></div>
      <div class="unit-toggle">${['light','dark','system'].map(m=>
        `<button class="${nbThemeMode()===m?'on':''}" data-theme-set="${m}">${NB_THEME_LABEL[m]}</button>`).join('')}</div></div>

    <div class="sec-head"><span class="label">Units</span><span class="rule"></span></div>"""
    edits.append((old, new, "settings appearance section"))

    old = """  $app.querySelectorAll('[data-units-set]').forEach(b=>b.onclick=()=>{ settings.units=b.dataset.unitsSet; persist.settings(); render(); });"""
    new = """  /* Its own key, not settings — so this deliberately does NOT go through
     persist.settings(). See the EGS-STD:themes block for why. */
  $app.querySelectorAll('[data-theme-set]').forEach(b=>b.onclick=()=>{ nbSetTheme(b.dataset.themeSet); render(); toast('Theme: '+NB_THEME_LABEL[nbThemeMode()]); });
  $app.querySelectorAll('[data-units-set]').forEach(b=>b.onclick=()=>{ settings.units=b.dataset.unitsSet; persist.settings(); render(); });"""
    edits.append((old, new, "settings theme handler"))

    old = """const HELP_COPY={
  'pin-recovery':"""
    new = """const HELP_COPY={
  'theme':'Day is for bright cabs and outdoors, where a dark screen turns into a mirror. Night is the notebook you know. Auto follows whatever your phone is set to, and changes with it. This one is kept per device, not in your backup \\u2014 the phone in the truck and the tablet on the bench can each be set to suit where they are used.',
  'pin-recovery':"""
    edits.append((old, new, "theme help copy"))

    # ------------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    # Each of these was mutation-tested: broken on purpose, confirmed to abort.

    # The mechanism landed, and landed BEFORE the stylesheet.
    if "EGS-STD:themes" not in working:
        fail("the row-13 marker did not land — egs-deploy.sh --full could not assert it.")
    head_script = working.find("localStorage.getItem('notebuilt.theme')")
    style_open = working.find("<style>")
    if head_script < 0 or head_script > style_open:
        fail("the theme read is not ahead of the stylesheet — that is the flash this fix exists to prevent.")

    # All three modes are reachable in CSS, and daylight is written after the
    # guarded media block. Equal specificity means source order is the only
    # thing that makes an explicit Day choice win, so it is asserted.
    media_light = working.find('@media (prefers-color-scheme: light)')
    explicit_light = working.find(':root[data-theme="light"]{')
    if media_light < 0 or explicit_light < 0:
        fail("a theme block is missing — light would not render.")
    if explicit_light < media_light:
        fail("[data-theme=\"light\"] precedes the media block; equal specificity means Day would lose to a night phone.")
    if ':root:not([data-theme="dark"])' not in working:
        fail("the media block is unguarded — an explicit Night would be overridden by a daylight phone.")

    # The role split, stated as an invariant: a gold plate and its ink always
    # travel together. If a future edit puts --brass-fill somewhere without
    # --on-brass, that is text of unknown colour on gold, and this catches it.
    # Structural, not a magic number: walk every declaration block in the
    # stylesheet and require that any rule painting a gold plate also names
    # the ink that goes on it. A future edit that adds a plate and forgets
    # --on-brass is exactly the mistake .unit-toggle made, and this catches
    # it by shape rather than by a count that has to be maintained.
    style_txt = working[working.find("<style>"):working.find("</style>")]
    plates_seen = 0
    for m in re.finditer(r"\{([^{}]*)\}", style_txt):
        body = m.group(1)
        if "var(--brass-fill)" in body:
            plates_seen += 1
            if "var(--on-brass)" not in body:
                fail(f"a gold plate carries no --on-brass ink: {body.strip()[:70]}")
    if plates_seen != 8:
        fail(f"{plates_seen} gold plates found, expected 8 — a plate was added or lost.")
    if working.count("--brass-fill:") != 4:
        fail("--brass-fill is not defined in all four token scopes.")
    if "#231a07" in working:
        fail("a raw on-brass hex survived — it should all be --on-brass now.")
    if "var(--brass);color:var(--ink)" in working:
        fail("the unit toggle still puts the GROUND role on a gold plate.")

    # The startup-write law. nbSetTheme is defined once and called once, from
    # the tap handler — nothing else, and nothing on the boot path.
    if working.count("nbSetTheme(") != 2:
        fail("nbSetTheme is reached from somewhere new — startup must never write the theme.")
    if working.count("localStorage.setItem(NB_THEME_KEY") != 1:
        fail("more than one writer for the theme key.")

    # The dark-by-nature scope, and the token architecture it depends on.
    if "#viewer,#annotate,#camera,#vault-busy{" not in working:
        fail("the dark-by-nature scope is gone — daylight would paint dark text onto the photo viewer.")
    if "var(--gold," in working:
        fail("--gold is still referenced, and it is not a token that exists.")

    # What must NOT have moved: the version stamp, the schema block and the
    # gate are all in this file and none of them are this fix's business.
    for marker, n in (("EGS-STD:coldopen-version", 3), ("EGS-STD:schema", 1),
                      ("EGS-STD:gate", 1)):
        if working.count(marker) != n:
            fail(f"{marker} count changed ({working.count(marker)}, expected {n}) — this fix touched something it should not have.")
    if working.count("window.EGS_VERSION") != 3:
        fail("the version stamp moved.")

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

    print("\n✅ Notebuilt has a daylight theme and a night one, the mode is stamped "
          "before the first paint, and every text pairing in both clears 4.5:1.")


if __name__ == "__main__":
    main()
