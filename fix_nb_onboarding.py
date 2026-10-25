#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — the walkthrough (th_nb_onboarding): a first-run tour that uses a
real sample job, a getting-started checklist, "what's new" pointers after an
update, and New project on the To Do landing.

Run from the same folder as index.html:
    python3 fix_nb_onboarding.py

PORTED FROM THE BUNDLE. The notebuilt-onboarding bundle shipped this change
as fix_onboarding.py, which wrote its backup, its exactly-once anchor count
and its syntax check out inline instead of importing platform/fixscript.py.
egs-deploy.sh --full (0792933) blocks any fix_*.py without the template's
import, and the rule (CLAUDE.md, Tier 2) is that every edit to a live app's
file starts as a copy of platform/fix-script-template.py. So this script is
that copy: the bundle's 25 edits and every word of their content carried
over verbatim (HOST_CSS, HOST_JS, HELP_START, BIND_JS, PRIVACY_LINE,
edits_for), every one of its guards kept, and the backup, the anchor count
and the syntax check taken from fixscript. Proven before it touched the real
file: run on scratch copies of 69c049f beside the bundle's own script, both
produced the same index.html, byte for byte (509,818 bytes, sha256 02b00f6a…).
fix_onboarding.py itself never entered this folder.

Needs, beside it:
  * ../../platform/guided_tour.js — the shared engine (EGSTour). It is filed
    in egs-platform FIRST (fb861b4), then pasted here BYTE-IDENTICAL between
    its marker lines, read at run time and never retyped, so the copy cannot
    drift on the way in. Same rule as crew_task.js.
  * sample/nb-sample-1.jpg … nb-sample-4.jpg — the sample job's photos.
    Checked against the SHA-256 sums below before anything is written.

What changes, all in index.html:
  1. ENGINE — the shared block, in its own <script>, straight after the
     crew-task block and ahead of the app's script.
  2. NB_TOUR — the walkthrough script (NB_TOUR_COPY, every word a person
     reads, in one place, first person), the sample job, the checklist,
     what's new, and the Settings rows. ONE new device key, notebuilt.tour,
     written only by a tap. Not in settings, not in the backup — it
     describes the phone, like the theme and beginner keys.
  3. LANDING — To Do gets a Projects row (New project, then the active jobs)
     under the notices. With nothing in the app at all, a welcome card with
     Create your first project takes the empty list's place.
  4. THE CAP — the free-project count skips the sample job (one, at most):
     creating, the pitch, the Settings row, and both priorProjects stamps.
  5. HOUSEKEEPING — the backup nudge and the old "i marks" notice ignore a
     phone whose only data is the sample; Delete on the sample's Edit screen
     goes through the same asked-first remove as Settings (a PROTECTED sample
     goes through the vault's own delete, first, like any protected project);
     the privacy page names the one new download (the sample's four photos,
     from the app's own site, only when asked for); and the ordinary Delete
     prompt stops saying photos stay — the line after it deletes them.
  6. BOOT — nbTourOnShell() beside crewOnShell() on both shell paths, past
     the PIN. It reads; it never writes.

Nothing about photos, the vault, backups or storage shapes changes. The
sample's records are ordinary records plus one field, `sample`, which older
builds carry through untouched (test_onboarding.mjs proves it on 69c049f).

Backs up first, exact-match anchors asserted ==1, post-conditions asserted,
EVERY inline script block syntax-checked before anything is written, written
atomically.
"""
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

# The shared guards. One source of truth — if they cannot be imported, that is
# a hard stop, not a reason to continue without a backup or a syntax check.
sys.path.insert(0, "/Volumes/AI Storage/EGS/platform")
try:
    from fixscript import backup, apply_edits, EditError, check_html, check_file
except ImportError as e:
    print(f"❌ cannot import platform/fixscript.py ({e}) — refusing to edit unguarded.")
    sys.exit(1)

TARGET = Path("index.html")
HERE = Path(__file__).resolve().parent
CANON = HERE.parent.parent / "platform" / "guided_tour.js"
BEGIN = "/* EGS-SHARED:guided-tour BEGIN */"
END = "/* EGS-SHARED:guided-tour END */"
MARKER = "const NB_TOUR_KEY='notebuilt.tour';"

SAMPLE = {
    "nb-sample-1.jpg": "9cdd197d9fee878084c5688d0ba2220a8d5dfef2197cb5dd1f3a6eab9a707984",
    "nb-sample-2.jpg": "533640b43e6a0fb406d72a5d09dbd14180c1955bd3015a292ad9861e3653730f",
    "nb-sample-3.jpg": "acf93398294b6033442c6bdfe1401f8dcb370a9bd010a36c880372cc43ffb6e9",
    "nb-sample-4.jpg": "4f1597c1354b9ab08c72dab1756a6a2e551505cab945aed3ffa93e637f97e0e2",
}


HOST_CSS = r"""  /* ---- NB_TOUR — the landing's projects row, the welcome card, and the
     shared walkthrough engine's colours ----
     The engine (EGSTour) carries its own stylesheet and asks only for its
     colours. Each is mapped here to a ROLE token, never a hex, so both
     themes are right by construction and audit_contrast.py's matrix already
     covers every pairing: --paper and --paper-dim on --ink-3 for the card,
     --brass for accent text, --on-brass on --brass-fill for the button, and
     --line-strong for the empty checkbox, an outline that IS the control. */
  :root{
    --egs-tour-card:var(--ink-3); --egs-tour-text:var(--paper); --egs-tour-muted:var(--paper-dim);
    --egs-tour-accent:var(--brass-fill); --egs-tour-accent-text:var(--brass); --egs-tour-on-accent:var(--on-brass);
    --egs-tour-scrim:var(--scrim); --egs-tour-line:var(--line-soft); --egs-tour-strong:var(--line-strong);
    --egs-tour-ring:var(--brass-fill); --egs-tour-shadow:var(--shadow-pop); --egs-tour-radius:var(--radius);
    --egs-tour-font:var(--sans); --egs-tour-title-font:var(--serif); --egs-tour-mono:var(--mono);
  }
  /* One row that scrolls sideways inside itself, edge to edge of the screen;
     the page never scrolls sideways (the 320px rule). */
  .nb-jobs{display:flex;gap:8px;overflow-x:auto;margin:0 -16px 4px;padding:0 16px 6px;
    scrollbar-width:none;-webkit-overflow-scrolling:touch}
  .nb-jobs::-webkit-scrollbar{display:none}
  .nb-job{flex:none;display:inline-flex;align-items:center;gap:8px;max-width:230px;min-height:44px;
    padding:0 14px;border-radius:999px;background:var(--ink-3);border:1px solid var(--line-soft);
    color:var(--paper);font-size:14.5px}
  .nb-job:active{border-color:var(--brass)}
  .nb-job svg{width:15px;height:15px;flex:none;color:var(--brass)}
  .nb-job-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .nb-job-n{flex:none;font-family:var(--mono);font-size:11px;line-height:1.35;padding:1px 7px;border-radius:999px;
    background:var(--brass-fill);color:var(--on-brass)}
  .sec-head .nb-new{padding:2px 12px;gap:6px}
  .sec-head .nb-new svg{width:15px;height:15px}
  /* The install and backup banners sit over the bottom nav, which is exactly
     where two walkthrough steps point. They stand aside while one runs and
     come straight back after (egs-tour-on is the engine's flag on <html>). */
  .egs-tour-on #install-banner,.egs-tour-on #backup-banner{display:none}
  .nb-hero{text-align:center;padding:22px 18px 18px;margin-top:12px}
  .nb-hero-mark{display:grid;place-items:center;margin-bottom:10px}
  .nb-hero-mark svg{width:58px;height:58px}
  .nb-hero-title{font-family:var(--serif);font-size:23px;font-weight:600;line-height:1.25}
  .nb-hero-lead{font-family:var(--serif);font-style:italic;font-size:16px;color:var(--brass);margin-top:3px}
  .nb-hero-body{color:var(--paper-dim);font-size:14px;line-height:1.6;margin:12px 0 16px}
"""

HOST_JS = r"""/* ============================================================
   NB_TOUR — the first-run walkthrough, the getting-started checklist,
   the sample job, and "what's new" pointers.

   The engine is EGSTour, the shared block above this script; it draws and
   it waits, and it stores nothing. Everything Notebuilt-specific is here,
   and every word a person reads is in NB_TOUR_COPY — the walkthrough
   script, in one place, in first person.

   STORAGE — one key of its own, notebuilt.tour, for the same reason the
   theme and beginner mode have theirs: it describes this PHONE, not the
   data. Whether the person holding it has seen the walkthrough is not a
   thing a backup restored onto a mate's tablet should decide, so it is not
   in settings and not in the export.
     { v:1, firstRun, startedAt, done, skipped, endedAt, seen:[ids], check }
   firstRun — this phone began with the welcome card (a new user): the
   checklist shows by default, and the old "New here: the i marks" notice
   does not, because the walkthrough already said it.

   STARTUP NEVER WRITES IT. nbTourOnShell() only reads. The key is written
   by a tap — Show me around, Skip, the X, Got it, Hide, Replay — and by
   nothing else. A welcome card left untouched writes nothing at all, and
   simply comes back next time.

   THE SAMPLE JOB is ordinary data — a real project, real to-dos, a real
   note, four real photos — so every screen shows it exactly as it would
   show the person's own. Each record carries sample:NB_SAMPLE_ID, which is
   how it is found again (one copy, at most), removed as a set, and kept out
   of the free-project count. Only ONE sample is ever exempt from the cap,
   so a file edited to mark every project a sample buys one, not unlimited.
   ============================================================ */
const NB_TOUR_KEY='notebuilt.tour';
const NB_SAMPLE_ID='nb-sample-1';

/* THE SCRIPT. Every string the walkthrough, the checklist, "what's new",
   the landing card and the Settings rows show. Plain text only — the
   engine writes it with textContent, and the landing and Settings run it
   through esc(), so a stray < can never become a tag. */
const NB_TOUR_COPY={
  next:'Next', skipStep:'Skip this step', showMe:'Show me', close:'End the walkthrough',
  stepOf:'Step {n} of {m}', gotIt:'Got it',
  steps:{
    welcome:{ title:'Welcome to Notebuilt', lead:'The notebook app for real tradespeople.',
      body:'Run three or four jobs at once and keep every one of them straight — its own photos, notes and to-dos, all in one place.\n\nI’ve set up a sample job so you can see how it works. It takes about a minute.',
      go:'Show me around', skip:'Skip — I’ll look around myself',
      loading:'Setting up the sample job…',
      noPhotos:'The sample photos didn’t load — the rest of the job is there',
      failed:'The sample job couldn’t be set up just now',
      unreadable:'Your saved projects couldn’t be read, so I didn’t add the sample. Restore your latest backup first.' },
    openSample:{ title:'This is a sample job',
      body:'It’s one of my own jobs, filled in the way a real one would be. Tap it to look inside.' },
    inside:{ title:'Everything for the job, in the job',
      body:'Photos you take inside a project are saved right here, not mixed into your camera roll. Its notes and to-dos live in here too, and nothing spills over into your other jobs.' },
    newProject:{ title:'Now start your own',
      body:'Tap New project and give it a name. The job you’re on right now is perfect.' },
    addTodo:{ title:'Add one thing that needs doing',
      body:'Tap Add to-do and write something for this job — a part to pick up, a callback, a cut to make.' },
    goTodo:{ title:'Now check To Do', body:'Tap To Do at the bottom of the screen.' },
    oneList:{ title:'Every job, one list',
      body:'Your to-do and the sample job’s, side by side, each one tagged with its job. Everything that needs doing on every site, without opening a single project.' },
    vault:{ title:'Keep the private stuff private',
      body:'Door codes, client details, photos nobody else should see? Open a project, tap Edit, and turn on Protect this project. Its notes, to-dos and photos are encrypted behind a passphrase only you know — not even I can open them.' },
    done:{ title:'You’re set',
      body:'The checklist on To Do walks you through the rest, and the little i marks explain any part of the app.\n\nThe sample job doesn’t count toward your '+UNLOCK.FREE_PROJECTS+' free projects. Delete it whenever you like — Settings brings it back.',
      go:'Done' }
  },
  hero:{ title:'Welcome to Notebuilt', lead:'The notebook app for real tradespeople.',
    body:'Start with a project — a house, a unit, a job site. Its photos, notes and to-dos stay together, and every to-do also lands on this list.',
    create:'Create your first project', tour:'Show me around first' },
  jobs:{ label:'Projects', create:'New project' },
  checklist:{ title:'Getting started', count:'{d} of {n}', hide:'Hide', optional:'optional',
    doneTitle:'You’re all set', doneBody:'That’s everything that makes Notebuilt worth having. Hide this whenever you like.',
    hidden:'Checklist hidden — Settings brings it back',
    items:[
      { id:'project', label:'Start your first project' },
      { id:'todo',    label:'Add a to-do to it' },
      { id:'photo',   label:'Take a photo on the job' },
      { id:'note',    label:'Write a note' },
      { id:'backup',  label:'Back up to a file' },
      { id:'vault',   label:'Protect a private project', optional:true }
    ],
    points:{
      photo:{ title:'Take it from here', body:'Camera takes the picture inside Notebuilt, and it stays in this project.' },
      note:{ title:'Add a note here', body:'Measurements, a supplier’s number, what the customer said on Tuesday.' },
      backup:{ title:'Tap Export', body:'One file with everything in it. Keep it somewhere other than this phone.' }
    } },
  whatsNew:{ counter:'{n} of {m}', eyebrow:'New', next:'Next', done:'Got it' },
  settings:{ label:'Getting started',
    tour:'Walkthrough', tourSub:'A one-minute tour, using the sample job.', replay:'Replay',
    sample:'Sample job', sampleSub:'A filled-in job to look around in, or to show someone. It doesn’t count toward your free projects.',
    sampleHere:'Loaded. It doesn’t count toward your free projects.', load:'Load', remove:'Remove',
    check:'Checklist', checkSub:'Five first steps, shown on To Do until they’re done.', show:'Show', hide:'Hide',
    removeAsk:'Remove the sample job and everything in it?\n\nTo-dos and notes you added to it yourself stay, unfiled. Its photos go with it.',
    removed:'Sample job removed', loading:'Loading the sample job…', loaded:'Sample job loaded',
    already:'The sample job is already here' },
  /* One of Edwin's own jobs. The photos are files in sample/, fetched from
     the app's own site only when someone asks for the sample; 0-based
     `cover` is the kitchen. To-dos are listed top to bottom as To Do shows
     them within each status, newest first. */
  sample:{ name:'Sample · Great Room & Kitchen', jobType:'trim',
    siteNotes:'Scaffold casters stay on pads — new floor.',
    photos:['sample/nb-sample-1.jpg','sample/nb-sample-2.jpg','sample/nb-sample-3.jpg','sample/nb-sample-4.jpg'],
    cover:3,
    todos:[
      { text:'Tall wall: book drywall (insulation and poly done)', status:'todo' },
      { text:'Set the jamb in the second opening', status:'todo' },
      { text:'Case all door openings', status:'todo' },
      { text:'Fireplace surround: confirm finish with client', status:'doing' },
      { text:'Flooring install', status:'done' }
    ],
    note:{ title:'Fireplace surround', body:'Client still choosing tile or stone.' } }
};

/* "What's new" — pointed at once, after an update, on phones that already
   had Notebuilt. A fresh phone marks every entry seen when it starts the
   walkthrough, so a new user is never told about a change they did not
   live through. New entries go at the END, with an id never used before.
   `when` says whether an entry's target can exist on this phone right now;
   one that cannot is left unseen for a later open, and never holds up the
   rest (the Projects row is not drawn while the empty-app card is). */
const NB_WHATS_NEW=[
  { id:'2026-10-projects-on-todo', target:'#app [data-tour="projects"]', when:()=>!nbHeroShown(),
    title:'Projects are on To Do now',
    body:'Your active jobs sit at the top of the list. Tap one to jump in, or tap New project to start one from right here.' },
  { id:'2026-10-getting-started', target:'#nav [data-nav="settings"]',
    title:'New in Settings: Getting started',
    body:'Replay the walkthrough, or load a sample job — handy for showing someone what Notebuilt does.' }
];

/* ---------- state: read anywhere, written only by a tap ---------- */
/* EGS-STD:schema, on this key too: v is the shape of the record. One above
   NB_TOUR_V came from a newer Notebuilt — never written over, and while it
   is there this build points at nothing and starts nothing on its own. */
const NB_TOUR_V=1;
function nbTourFromFuture(){ const s=nbTourState(); return !!(s && typeof s.v==='number' && s.v>NB_TOUR_V); }
function nbTourState(){
  try{ const v=JSON.parse(localStorage.getItem(NB_TOUR_KEY)||'null'); return (v && typeof v==='object' && !Array.isArray(v)) ? v : null; }
  catch(e){ return null; }
}
function nbTourWrite(patch){
  const cur=nbTourState();
  if(cur && typeof cur.v==='number' && cur.v>NB_TOUR_V) return cur;
  const next=Object.assign({}, cur||{}, patch, {v:NB_TOUR_V});
  try{ localStorage.setItem(NB_TOUR_KEY, JSON.stringify(next)); }catch(e){}
  return next;
}
function nbTourFirstRunHere(){ const s=nbTourState(); return !!(s && s.firstRun); }
function nbWhatsNewIds(){ return NB_WHATS_NEW.map(x=>x.id); }
/* The first tap of a walkthrough. `auto` is true only for the welcome card a
   fresh phone opened on — that is what makes this phone a new user's. */
function nbTourBegin(auto){
  const s=nbTourState();
  const seen=Array.from(new Set([].concat((s&&Array.isArray(s.seen))?s.seen:[], nbWhatsNewIds())));
  nbTourWrite({ firstRun: s ? !!s.firstRun : !!auto, seen, startedAt:(s&&s.startedAt)||now() });
}

/* ---------- what is on disk ----------
   "Nothing here yet" is decided by the raw values, not by what parsed. load()
   answers [] for a value it cannot read, and a phone whose projects cannot be
   read is the opposite of new: the welcome card's first tap writes, and a
   write over an unreadable key — and over its _bak twin, which the
   durability guard keeps in step — is how unreadable turns into deleted. */
const NB_TOUR_STORES=['notebuilt.houses','notebuilt.tasks','notebuilt.notes'];
function nbRawBlank(k){
  let v=null; try{ v=localStorage.getItem(k); }catch(e){ return false; }
  return v==null || v==='' || v==='[]';
}
function nbStoresUnreadable(){
  return NB_TOUR_STORES.some(k=>{
    let v=null; try{ v=localStorage.getItem(k); }catch(e){ return true; }
    if(v==null || v==='') return false;
    try{ return !Array.isArray(JSON.parse(v)); }catch(e){ return true; }
  });
}
function nbFreshPhone(){
  return !houses.length && !tasks.length && !notes.length && !crewRecs.length
    && NB_TOUR_STORES.every(k=>nbRawBlank(k) && nbRawBlank(k+'_bak'));
}
/* Redrawing under someone is only safe on a list, with nothing open and
   nothing being typed into (EGS-DECISIONS 2026-08-12, node identity). */
function nbSafeToRedraw(){
  const a=document.activeElement;
  return ['todo','houses','settings'].indexOf(view.name)>=0 && !$mr.firstChild
    && !(a && $app.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
}

/* ---------- the sample job ---------- */
function nbIsSample(r){ return !!(r && r.sample===NB_SAMPLE_ID); }
function nbSampleProject(){ return houses.find(nbIsSample)||null; }
/* The free cap counts real projects. One sample, at most, is not one. */
function nbCountedProjects(){ return houses.length - (houses.some(nbIsSample)?1:0); }
function nbOwnProjects(){ return houses.filter(h=>!nbIsSample(h)); }

/* Loads it once. A second call while the first is running gets the same
   promise, and a call when it is already here gets that one — there is
   never a second copy. Order is the durability order handlePhoto() uses:
   records first, then each photo persisted the moment it lands, so a death
   part-way strands at most one photo and recoverOrphanPhotos() re-attaches
   even that. The photos come from this app's own site (sample/), the same
   place index.html comes from, and only now — nothing is sent, nothing of
   the person's goes anywhere, and the privacy page says so. */
let _nbSampleLoading=null, _nbSampleLoadingId=null;
function nbSampleLoad(){
  const have=nbSampleProject();
  if(have) return Promise.resolve({house:have, photos:(have.photos||[]).length, existed:true});
  if(_nbSampleLoading && houseById(_nbSampleLoadingId)) return _nbSampleLoading;
  /* Never write a sample over projects that could not be read. */
  if(nbStoresUnreadable()) return Promise.reject(new Error('unreadable'));
  const S=NB_TOUR_COPY.sample, base=now()-60*60*1000;
  const h={ id:uid(), name:S.name, category:'construction', address:'', status:'active', jobType:S.jobType,
            specs:[], photos:[], cover:null, notes:S.siteNotes, createdAt:base, updatedAt:base, sample:NB_SAMPLE_ID };
  _nbSampleLoadingId=h.id;
  _nbSampleLoading=(async()=>{
    houses.push(h); persist.houses();
    S.todos.forEach((t,k)=>{
      const at=base-k*60000;
      tasks.push({ id:uid(), text:t.text, status:t.status, houseId:h.id, createdAt:at, updatedAt:at,
                   doneAt:t.status==='done'?at:null, dueDate:null, sample:NB_SAMPLE_ID });
    });
    persist.tasks();
    notes.push({ id:uid(), title:S.note.title, body:S.note.body, houseId:h.id, important:false,
                 createdAt:base, updatedAt:base, sample:NB_SAMPLE_ID });
    persist.notes();
    let got=0;
    for(let k=0;k<S.photos.length;k++){
      try{
        const res=await fetch(S.photos[k]);
        if(!res.ok) throw new Error('HTTP '+res.status);
        const blob=await res.blob();
        if(!/^image\//.test(blob.type||'')) throw new Error('not an image');
        const pid=uid();
        await photoPutFor(h.id,{ id:pid, blob, houseId:h.id, createdAt:base+k });
        if(!houseById(h.id)){                       /* removed while it was loading: take this one back too */
          try{ await photoDel(pid); }catch(e){}
          break;
        }
        h.photos.push(pid);
        if(!h.cover || k===S.cover) h.cover=pid;
        persist.houses();
        got++;
      }catch(e){ console.warn('Notebuilt: a sample photo did not load', e); }
    }
    return {house:h, photos:got, existed:false};
  })();
  const p=_nbSampleLoading;
  p.then(()=>{ if(_nbSampleLoading===p) _nbSampleLoading=null; }, ()=>{ if(_nbSampleLoading===p) _nbSampleLoading=null; });
  return p;
}

/* It opens the sample when it lands — but only if the person is still where
   they tapped Load, with nothing open. Anywhere else, a toast says it is
   there and the screen they are on is left alone. */
async function nbSampleLoadTap(){
  const C=NB_TOUR_COPY.settings, W=NB_TOUR_COPY.steps.welcome;
  const have=nbSampleProject();
  if(have){ toast(C.already); go('house',have.id); return; }
  const from={ name:view.name, param:view.param };
  toast(C.loading);
  let r=null, why=null;
  try{ r=await nbSampleLoad(); }catch(e){ why=e; }
  if(!r){ toast(why && why.message==='unreadable' ? W.unreadable : W.failed); if(nbSafeToRedraw()) render(); return; }
  toast(r.photos ? C.loaded : W.noPhotos);
  if(view.name===from.name && view.param===from.param && !$mr.firstChild) go('house', r.house.id);
  else if(nbSafeToRedraw()) render();
}

/* Every delete asks first (EGS standard). The sample's own to-dos and note go
   with it; anything the person added to it is unfiled, the way deleting any
   project leaves its to-dos behind. Records first, photos after: a death in
   between can only leave unreferenced bytes, never a project pointing at
   photos that are gone. */
async function nbSampleRemove(id){
  const h=houseById(id); if(!h || !nbIsSample(h)) return;
  /* Protected, its notes and to-dos are ciphertext under the vault key, and
     unfiling them would strand them where nothing can open them again. So it
     goes the way every protected project goes: the vault's own delete, which
     asks twice and takes everything in it. */
  if(h.protected){ vaultDeleteLocked(h.id); return; }
  if(!confirm(NB_TOUR_COPY.settings.removeAsk)) return;
  const pids=(h.photos||[]).slice();
  tasks=tasks.filter(t=>!(t.houseId===h.id && nbIsSample(t)));
  notes=notes.filter(n=>!(n.houseId===h.id && nbIsSample(n)));
  tasks.forEach(t=>{ if(t.houseId===h.id) t.houseId=null; });
  notes.forEach(n=>{ if(n.houseId===h.id) n.houseId=null; });
  houses=houses.filter(x=>x.id!==h.id);
  if(settings.vault && settings.vault.migration && settings.vault.migration.houseId===h.id){
    settings.vault.migration=null; persist.settings();
  }
  persist.houses(); persist.tasks(); persist.notes();
  if((view.name==='house'||view.name==='housenotes') && view.param===h.id) go('todo'); else render();
  toast(NB_TOUR_COPY.settings.removed);
  for(const pid of pids){ try{ await photoDel(pid); }catch(e){} }
  /* A photo that landed in storage before its id reached the list. */
  try{ for(const rec of await photoAll()){ if(rec.houseId===h.id) await photoDel(rec.id); } }catch(e){}
}

/* ---------- the landing: checklist, then projects (or the welcome card) ---------- */
/* Not while the walkthrough is up: its own welcome card says the same thing. */
function nbHeroShown(){ return !houses.length && !tasks.length && !EGSTour.active(); }
function nbStartHtml(){
  if(nbHeroShown()) return nbHeroHtml();
  return (nbChecklistShown() ? '<div class="wrap">'+EGSTour.checklistHtml(nbChecklistModel(), esc)+'</div>' : '')+nbJobsHtml();
}
function nbHeroHtml(){
  const C=NB_TOUR_COPY.hero;
  return `<div class="wrap"><div class="card nb-hero">
    <div class="nb-hero-mark">${MARK}</div>
    <div class="nb-hero-title">${esc(C.title)}</div>
    <div class="nb-hero-lead">${esc(C.lead)}</div>
    <div class="nb-hero-body">${esc(C.body)}</div>
    <button type="button" class="btn primary block" data-new-project>${I.plus} ${esc(C.create)}</button>
    <button type="button" class="btn block" data-tour-start="landing" style="margin-top:10px">${esc(C.tour)}</button>
  </div></div>`;
}
/* Active jobs, most recently touched first, as one row that scrolls sideways
   inside itself — the page never does. A protected project shows its name
   and a lock and nothing else, exactly as the Projects list does: how much is
   in there is itself information. */
function nbJobsHtml(){
  const C=NB_TOUR_COPY.jobs;
  const live=houses.filter(h=>h.status!=='done').sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));
  const chip=h=>{
    if(h.protected) return `<button type="button" class="nb-job" data-house="${esc(h.id)}">${I.lock}<span class="nb-job-name">${esc(h.name)}</span></button>`;
    const open=tasks.filter(t=>t.houseId===h.id && t.status!=='done').length;
    return `<button type="button" class="nb-job"${nbIsSample(h)?' data-tour="sample"':''} data-house="${esc(h.id)}"><span class="nb-job-name">${esc(h.name)}</span>${open?`<span class="nb-job-n">${open}</span>`:''}</button>`;
  };
  return `<div class="wrap" data-tour="projects"><div class="sec-head"><span class="label">${esc(C.label)}</span>${nbHelpMark('projects')}<span class="rule"></span><button type="button" class="btn sm nb-new" data-new-project>${I.plus} ${esc(C.create)}</button></div>
    ${live.length?`<div class="nb-jobs">${live.map(chip).join('')}</div>`:''}</div>`;
}

/* ---------- the checklist ---------- */
function nbChecklistShown(){
  if(EGSTour.active()) return false;
  const s=nbTourState(); if(!s) return false;
  if(s.check==='off') return false;
  if(s.check==='on') return true;
  return !!s.firstRun;
}
/* Ticked by what is actually in the app, never by a flag that could drift
   from it. The sample job counts for nothing here — it is not their work. */
function nbChecklistModel(){
  const C=NB_TOUR_COPY.checklist;
  const own=nbOwnProjects(), ownIds=new Set(own.map(h=>h.id));
  const done={
    project: own.length>0,
    todo:    tasks.some(t=>t.houseId && ownIds.has(t.houseId)),
    photo:   own.some(h=>(h.photos||[]).length>0),
    note:    notes.some(n=>!nbIsSample(n)) || own.some(h=>typeof h.notes==='string' ? h.notes.trim().length>0 : !!h.notes),
    backup:  !!settings.lastBackupAt,
    vault:   houses.some(h=>h.protected)
  };
  return { title:C.title, doneTitle:C.doneTitle, doneBody:C.doneBody, hideLabel:C.hide,
           countLabel:C.count, optionalLabel:C.optional,
           items:C.items.map(x=>({ id:x.id, label:x.label, optional:!!x.optional, done:!!done[x.id] })) };
}
/* Each item takes them to where it gets done. The pointers are the engine's
   non-modal kind: the page stays usable, and tapping the thing clears it. */
function nbPoint(sel, c){
  const at={ name:view.name, param:view.param };     /* go() has already moved view */
  EGSTour.point('#app '+sel, { title:c.title, body:c.body, button:NB_TOUR_COPY.gotIt,
    zIndex:54, isBusy:nbTourBusy, dismissOnTargetTap:true,
    until:()=>!(view.name===at.name && view.param===at.param) });   /* gone the moment they leave */
}
function nbChecklistGo(id){
  const P=NB_TOUR_COPY.checklist.points;
  const own=nbOwnProjects().sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0));
  const h=own.find(x=>!x.protected)||own[0]||null;
  if(id==='vault'){ nbHelpSheet('vault'); return; }
  if(id==='backup'){ go('support'); nbPoint('[data-export]', P.backup); return; }
  if(id==='project' || !h){ openHouseSheet(); return; }
  go('house', h.id);
  if(id==='todo'){ openTaskSheet(h.id); return; }
  if(id==='photo'){ nbPoint('[data-open-camera]', P.photo); return; }
  if(id==='note'){ nbPoint('[data-add-note-house]', P.note); return; }
}

/* ---------- Settings: Getting started ---------- */
function nbStartSettingsHtml(){
  const C=NB_TOUR_COPY.settings, here=!!nbSampleProject(), on=nbChecklistShown();
  return `<div class="sec-head"><span class="label">${esc(C.label)}</span>${nbHelpMark('start')}<span class="rule"></span></div>
    <div class="card row"><div class="grow"><div>${esc(C.tour)}</div><div class="muted" style="font-size:13px">${esc(C.tourSub)}</div></div>
      <button class="btn sm" data-tour-start>${esc(C.replay)}</button></div>
    <div class="card row"><div class="grow"><div>${esc(C.sample)}</div><div class="muted" style="font-size:13px">${esc(here?C.sampleHere:C.sampleSub)}</div></div>
      ${here?`<button class="btn sm danger" data-sample-remove>${esc(C.remove)}</button>`:`<button class="btn sm" data-sample-load>${esc(C.load)}</button>`}</div>
    <div class="card row"><div class="grow"><div>${esc(C.check)}</div><div class="muted" style="font-size:13px">${esc(C.checkSub)}</div></div>
      <div class="unit-toggle"><button class="${on?'on':''}" data-check-set="on">${esc(C.show)}</button><button class="${on?'':'on'}" data-check-set="off">${esc(C.hide)}</button></div></div>`;
}

/* ---------- the walkthrough ---------- */
/* Anything drawn over the page that the walkthrough must stand clear of. */
function nbTourBusy(){
  return !!($mr.firstChild || !$lock.classList.contains('hidden') || !$viewer.classList.contains('hidden')
    || !$annotate.classList.contains('hidden') || !$vault.classList.contains('hidden') || cam.open
    || document.querySelector('.help-scrim') || document.getElementById('vault-busy'));
}
function nbTourSteps(auto){
  const C=NB_TOUR_COPY, S=C.steps;
  /* mine — the project they make on the "start your own" step. tP and tT —
     when each action step first opened, so only something made AFTER the
     step was asked for counts as doing it. Set once each: Show me runs
     prepare() again, and must not move the line. */
  let mine=null, tP=0, tT=0;
  const sample=()=>nbSampleProject();
  const newestOwn=()=>nbOwnProjects().sort((a,b)=>(b.createdAt||0)-(a.createdAt||0))[0]||null;
  const onHouse=id=>view.name==='house' && view.param===id;
  return [
    { id:'welcome', uncounted:true, title:S.welcome.title, lead:S.welcome.lead, body:S.welcome.body,
      primary:S.welcome.go,
      onPrimary:ctl=>{
        nbTourBegin(auto);
        ctl.wait(S.welcome.loading);
        nbSampleLoad().then(r=>{
          if(!ctl.alive()){ if(nbSafeToRedraw()) render(); return; }   /* closed while it loaded */
          ctl.wait(null);
          if(!r.existed && !r.photos) toast(S.welcome.noPhotos);
          render(); ctl.next();
        }, e=>{
          if(!ctl.alive()) return;
          ctl.wait(null);
          toast(e && e.message==='unreadable' ? S.welcome.unreadable : S.welcome.failed);
          ctl.end('stopped');
        });
      },
      secondary:{ label:S.welcome.skip, onTap:ctl=>ctl.end('skipped') } },
    { id:'open-sample', title:S.openSample.title, body:S.openSample.body,
      target:'#app [data-tour="sample"]',
      prepare:()=>{ if(view.name!=='todo') go('todo'); },
      waitFor:()=>{ const sp=sample(); return !!(sp && onHouse(sp.id)); },
      skipIf:()=>!sample() },
    { id:'inside', title:S.inside.title, body:S.inside.body, primary:C.next,
      target:'#app .photo-grid', pad:8,
      prepare:()=>{ const sp=sample(); if(sp && !onHouse(sp.id)) go('house', sp.id); },
      skipIf:()=>!sample() },
    { id:'new-project', title:S.newProject.title, body:S.newProject.body,
      target:'#app [data-new-project]',
      skipIf:()=>!unlockCanCreateProject(),
      prepare:()=>{ if(!tP) tP=now(); if(view.name!=='todo') go('todo'); },
      waitFor:()=>{ const h=nbOwnProjects().find(x=>(x.createdAt||0)>=tP-1000); if(h){ mine=h.id; return true; } return false; } },
    { id:'add-todo', title:S.addTodo.title, body:S.addTodo.body,
      target:'#app [data-add-house-task]',
      prepare:()=>{ if(!tT) tT=now(); if(mine && !onHouse(mine)) go('house', mine); },
      waitFor:()=>tasks.some(t=>t.houseId===mine && (t.createdAt||0)>=tT-1000),
      skipIf:()=>{ if(!mine){ const h=newestOwn(); mine=h?h.id:null; } const h=mine&&houseById(mine); return !h || (h.protected && !vaultUnlocked()); } },
    { id:'go-todo', title:S.goTodo.title, body:S.goTodo.body,
      target:'#nav [data-nav="todo"]',
      waitFor:()=>view.name==='todo',
      skipIf:()=>view.name==='todo' },
    { id:'one-list', title:S.oneList.title, body:S.oneList.body, primary:C.next,
      target:'#app [data-tour="todo-list"]', maxHole:0.45,
      prepare:()=>{ if(view.name!=='todo') go('todo'); },
      skipIf:()=>!tasks.some(t=>!isProtected(t.houseId)) },
    { id:'vault', title:S.vault.title, body:S.vault.body, primary:C.next },
    { id:'done', title:S.done.title, body:S.done.body, primary:S.done.go }
  ];
}
/* auto: the welcome card a fresh phone opened on, before anyone tapped. */
function nbTourRun(auto){
  if(EGSTour.active()) return;
  const C=NB_TOUR_COPY;
  EGSTour.run(nbTourSteps(auto), {
    zIndex:55, isBusy:nbTourBusy,
    labels:{ next:C.next, skipStep:C.skipStep, showMe:C.showMe, close:C.close, stepOf:C.stepOf },
    onEnd:reason=>{
      /* Only a person ends a walkthrough as done or skipped, so these are
         taps too. 'replaced' and 'stopped' come from code and write nothing. */
      if(reason==='done'){ nbTourBegin(auto); nbTourWrite({ done:true, endedAt:now() }); }
      else if(reason==='skipped'){ nbTourBegin(auto); nbTourWrite({ skipped:true, endedAt:now() }); }
      try{ render(); }catch(e){}
    }
  });
  /* Redraw under it: the landing's welcome card stands down while the
     walkthrough's own says the same thing. */
  try{ render(); }catch(e){}
}
/* From a tap: the empty-app card's "Show me around first" (fromLanding), or
   Settings → Replay. The tap is the write. From the empty-app card on a phone
   with nothing in it, this IS a new user's first walkthrough — one who came in
   through a crew or deep link and so never saw the welcome card. */
function nbTourStart(fromLanding){
  if(EGSTour.active()) return;
  nbTourBegin(!!fromLanding && !houses.length && !tasks.length && !notes.length);
  nbTourRun(false);
}
/* Called wherever the shell is revealed — past the PIN, if there is one.
   READS ONLY. A crew link, a deep link, or a sheet already up means this is
   not the moment; the next ordinary open is. */
async function nbTourOnShell(){
  if(view.name!=='todo') return;
  try{ if(crewReady) await crewReady; }catch(e){}
  await new Promise(r=>setTimeout(r,450));
  if(!appUnlocked() || view.name!=='todo' || EGSTour.active() || $mr.firstChild || nbTourFromFuture()) return;
  const s=nbTourState();
  if(!s && nbFreshPhone()){ nbTourRun(true); return; }
  const fresh=EGSTour.unseen(NB_WHATS_NEW, s && s.seen).filter(x=>!x.when || x.when());
  if(!fresh.length) return;
  const W=NB_TOUR_COPY.whatsNew;
  EGSTour.pointSeries(fresh, { zIndex:54, isBusy:nbTourBusy, eyebrow:W.eyebrow, counter:W.counter, next:W.next, done:W.done,
    onSeen:id=>{ const cur=nbTourState(); const seen=(cur && Array.isArray(cur.seen)) ? cur.seen.slice() : [];
                 if(seen.indexOf(id)<0) seen.push(id); nbTourWrite({ seen }); } });
}

"""

HELP_START = r"""  'start':'The walkthrough is a one-minute tour of Notebuilt, using the sample job. Replay it from here any time.\n\nThe sample job is one of my own jobs, real photos and all, filled in the way I keep a job. It is there to look around in, or to show someone what the app does, and it does not count toward your free projects. Loading it downloads its four photos from the same website the app itself comes from; nothing of yours goes anywhere. Remove takes it away along with its photos, notes and to-dos. To-dos and notes you added to it yourself stay, unfiled. If you made it a protected project, it is deleted the way any protected project is: everything in it goes.\n\nThe checklist sits at the top of To Do until you have done the five things that make Notebuilt worth having. Hide it whenever you like, and bring it back from here.'"""

BIND_JS = r"""  /* NB_TOUR — New project on the landing, the walkthrough, the checklist and
     the Getting started rows. The taps on a screen that write notebuilt.tour
     are these; the walkthrough's own buttons are the rest. */
  $app.querySelectorAll('[data-new-project]').forEach(b=>b.onclick=()=>openHouseSheet());
  $app.querySelectorAll('[data-tour-start]').forEach(b=>b.onclick=()=>nbTourStart(b.dataset.tourStart==='landing'));
  $app.querySelectorAll('[data-egs-check]').forEach(b=>b.onclick=()=>nbChecklistGo(b.dataset.egsCheck));
  $app.querySelectorAll('[data-egs-check-hide]').forEach(b=>b.onclick=()=>{ nbTourWrite({check:'off'}); render(); toast(NB_TOUR_COPY.checklist.hidden); });
  $app.querySelectorAll('[data-check-set]').forEach(b=>b.onclick=()=>{ nbTourWrite({check:b.dataset.checkSet==='on'?'on':'off'}); render(); });
  const sLoad=$app.querySelector('[data-sample-load]'); if(sLoad) sLoad.onclick=()=>nbSampleLoadTap();
  const sDel=$app.querySelector('[data-sample-remove]'); if(sDel) sDel.onclick=()=>{ const sp=nbSampleProject(); if(sp) nbSampleRemove(sp.id); };
"""

PRIVACY_LINE = "      If you load the sample job, its four photos come down from the same place, the same way. They are part of the app, and nothing of yours goes up.<br><br>\n"


def edits_for(canon):
    E = []
    def add(old, new, label):
        E.append((old, new, label))

    # 1. engine + 2. host code + its stylesheet
    add('/* EGS-SHARED:crew-task END */\n</script>\n<script>\n"use strict";\n',
        '/* EGS-SHARED:crew-task END */\n</script>\n<script>\n' + canon + '</script>\n<script>\n"use strict";\n',
        "engine block after crew-task")
    add("/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */\n",
        HOST_JS + "/* ---------- IndexedDB for photos (blobs, never uploaded) ---------- */\n",
        "NB_TOUR section ahead of the photo database")
    add("  #crop-stage:active{cursor:grabbing}\n</style>\n",
        "  #crop-stage:active{cursor:grabbing}\n" + HOST_CSS + "</style>\n",
        "stylesheet: projects row, welcome card, engine colours")
    add("  'unlock':'Free, and unlocking'\n};\n",
        "  'unlock':'Free, and unlocking',\n  'start':'Getting started'\n};\n",
        "HELP_TITLE start")
    add("not a lock I have you behind.'\n};\n",
        "not a lock I have you behind.',\n\n" + HELP_START + "\n};\n",
        "HELP_COPY start")

    # 3. landing
    add("  if(!list.length) return head+nbGuideNoticeHtml()+crewCardHtml()+`<div class=\"empty\">${I.today}<div class=\"t\">Nothing on the list yet</div><div>Tap + to add what you're working on. Mark it Doing when you start, Done when it's finished.</div></div>`;\n",
        "  /* NB_TOUR — under the notices: the checklist and the Projects row, or, with\n"
        "     nothing in the app at all, the welcome card in place of the empty list. */\n"
        "  const start=nbStartHtml();\n"
        "  if(!list.length) return head+nbGuideNoticeHtml()+crewCardHtml()+start+(nbHeroShown()?'':`<div class=\"empty\">${I.today}<div class=\"t\">Nothing on the list yet</div><div>Tap + to add what you're working on. Mark it Doing when you start, Done when it's finished.</div></div>`);\n",
        "To Do empty state")
    add("  return head+nbGuideNoticeHtml()+crewCardHtml()+`<div class=\"wrap\">${sec('In progress',doing)}${sec('To do',todo)}${doneSec}</div>`;\n",
        "  return head+nbGuideNoticeHtml()+crewCardHtml()+start+`<div class=\"wrap\" data-tour=\"todo-list\">${sec('In progress',doing)}${sec('To do',todo)}${doneSec}</div>`;\n",
        "To Do list")
    add("data-guide-set=\"off\">Expert</button></div></div>\n\n    <div class=\"sec-head\"><span class=\"label\">Units</span>",
        "data-guide-set=\"off\">Expert</button></div></div>\n\n    ${nbStartSettingsHtml()}\n\n    <div class=\"sec-head\"><span class=\"label\">Units</span>",
        "Settings: Getting started")
    add("  const gnX=$app.querySelector('[data-guide-notice-x]'); if(gnX) gnX.onclick=()=>nbGuideNoticeDismiss(false);\n",
        "  const gnX=$app.querySelector('[data-guide-notice-x]'); if(gnX) gnX.onclick=()=>nbGuideNoticeDismiss(false);\n" + BIND_JS,
        "bind(): taps")

    # 4. the cap
    add("  settings.priorProjects=houses.length; persist.settings();\n",
        "  settings.priorProjects=nbCountedProjects(); persist.settings();   /* NB_TOUR — the sample is not one */\n",
        "priorProjects stamp (pitch)")
    add("function unlockCanCreateProject(){ return unlockIsOn() || houses.length < UNLOCK.FREE_PROJECTS; }\n",
        "/* NB_TOUR — the sample job is not one of the free three (one sample, at most). */\n"
        "function unlockCanCreateProject(){ return unlockIsOn() || nbCountedProjects() < UNLOCK.FREE_PROJECTS; }\n",
        "unlockCanCreateProject")
    add("    ? 'You have <b style=\"color:var(--paper)\">'+houses.length+' projects</b>, from before Notebuilt had a limit.",
        "    ? 'You have <b style=\"color:var(--paper)\">'+nbCountedProjects()+' projects</b>, from before Notebuilt had a limit.",
        "pitch: grandfathered count")
    add("    : 'Notebuilt is free for '+free+' projects'+(houses.length===free?', and you are using all '+free+'.':', and you have '+houses.length+'.')+'<br><br>'\n",
        "    : 'Notebuilt is free for '+free+' projects'+(nbCountedProjects()===free?', and you are using all '+free+'.':', and you have '+nbCountedProjects()+'.')+'<br><br>'\n",
        "pitch: free count")
    add("(houses.length>UNLOCK.FREE_PROJECTS?'Free':",
        "(nbCountedProjects()>UNLOCK.FREE_PROJECTS?'Free':",
        "Settings unlock row: title")
    add("        : houses.length>UNLOCK.FREE_PROJECTS\n",
        "        : nbCountedProjects()>UNLOCK.FREE_PROJECTS\n",
        "Settings unlock row: branch")
    add("          ? houses.length+' projects, all yours to keep. '",
        "          ? nbCountedProjects()+' projects, all yours to keep. '",
        "Settings unlock row: grandfathered")
    add("          : houses.length+' of '+UNLOCK.FREE_PROJECTS+' used. '",
        "          : nbCountedProjects()+' of '+UNLOCK.FREE_PROJECTS+' used. '",
        "Settings unlock row: used")
    add("    if(!(d.settings && typeof d.settings.priorProjects==='number')) settings.priorProjects=houses.length;\n",
        "    if(!(d.settings && typeof d.settings.priorProjects==='number')) settings.priorProjects=nbCountedProjects();\n",
        "priorProjects stamp (restore)")

    # 5. housekeeping
    add("  if(!houses.length) return;\n  const snoozeUntil=",
        "  if(!nbCountedProjects()) return;     /* NB_TOUR — the sample job alone is nothing to back up */\n  const snoozeUntil=",
        "backup nudge")
    add("  return !!(houses.length||notes.length||tasks.length);     /* an existing install */\n",
        "  /* NB_TOUR — a phone that began with the walkthrough is a fresh install,\n"
        "     whatever the sample job put in it, and the walkthrough's last card has\n"
        "     already told them about the i marks. */\n"
        "  if(nbTourFirstRunHere()) return false;\n"
        "  return !!(houses.length||notes.length||tasks.length);     /* an existing install */\n",
        "i-marks notice")
    add("    if(edit.protected){ closeSheet(); vaultDeleteLocked(edit.id); return; }\n",
        "    if(edit.protected){ closeSheet(); vaultDeleteLocked(edit.id); return; }\n"
        "    if(nbIsSample(edit)){ closeSheet(); nbSampleRemove(edit.id); return; }   /* NB_TOUR — this sample, as a set, asked first */\n",
        "Edit sheet: deleting the sample (protected still goes the vault's way first)")
    # The confirm on an ordinary project's Delete said its photos stay. The next
    # line deletes them. A delete prompt that misdescribes what it deletes is the
    # one kind that cannot be allowed to stand (found in review, pre-existing).
    add("    if(!confirm(`Delete \"${edit.name}\" and its specs? Photos and to-dos for it stay but unlink.`)) return;\n",
        "    if(!confirm(`Delete \"${edit.name}\" with its specs and photos?\\n\\nIts to-dos and notes stay, unfiled.`)) return;\n",
        "Edit sheet: the delete prompt says what it deletes")
    add("      Only to load the app itself from GitHub Pages — no data leaves your phone to do that.<br><br>\n",
        "      Only to load the app itself from GitHub Pages — no data leaves your phone to do that.<br><br>\n" + PRIVACY_LINE,
        "privacy page: the sample download")

    # 6. boot
    add("maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); crewOnShell(); return; }\n",
        "maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); crewOnShell(); nbTourOnShell(); return; }\n",
        "shell, no PIN")
    add("maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); maybeOfferRecoveryCode(); crewOnShell(); }\n",
        "maybeShowInstallPrompt(); maybeShowDataSafetyNudge(); maybeOfferRecoveryCode(); crewOnShell(); nbTourOnShell(); }\n",
        "shell, past the PIN")
    return E


# Refuse to write when the syntax check cannot actually run (no node).
# Mirrors egs-deploy.sh --allow-untracked: default is to refuse, and the
# override has to be typed on purpose.
ALLOW_UNVERIFIED = "--allow-unverified" in sys.argv


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "EGS-SHARED:guided-tour" in text:
        fail("index.html already mentions the guided-tour markers, but not this change's code — stop and look.")
    if not CANON.exists():
        fail(f"the shared engine is not at {CANON}. File it in egs-platform first "
             f"(Thread: EGS platform — guided tour component), then run this again.")
    canon = CANON.read_text(encoding="utf-8")
    if not (canon.startswith(BEGIN + "\n") and canon.endswith(END + "\n")):
        fail("platform/guided_tour.js does not start and end with its marker lines.")
    for name, want in SAMPLE.items():
        p = HERE / "sample" / name
        if not p.exists():
            fail(f"sample/{name} is missing. Copy the bundle's sample/ folder in beside this script.")
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            fail(f"sample/{name} is not the reviewed photo (sha256 {got[:12]}…, expected {want[:12]}…).")

    # ---- the edits ------------------------------------------------------
    # Exact strings, never regex, each anchor exactly once — apply_edits
    # raises before anything is written.
    edits = edits_for(canon)
    try:
        working = apply_edits(text, edits)
    except EditError as e:
        fail(f"{e} Nothing written.")

    # ---- guards ---------------------------------------------------------
    # The bundle's post-conditions, all kept.
    lines = working.split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        fail("the engine's marker lines are not each present exactly once, flush-left.")
    b, e = lines.index(BEGIN), lines.index(END)
    if "\n".join(lines[b:e + 1]) + "\n" != canon:
        fail("the pasted engine is not byte-identical to platform/guided_tour.js.")
    app_at = working.find('const APP_NAME = "Notebuilt";')
    if app_at < 0 or not (working.find(END) < app_at):
        fail("the engine must load before the app's own script.")
    if "houses.length < UNLOCK.FREE_PROJECTS" in working or "houses.length>UNLOCK.FREE_PROJECTS" in working:
        fail("a free-project count still includes the sample job.")
    del_at = working.find("if(edit.protected){ closeSheet(); vaultDeleteLocked(edit.id); return; }")
    if del_at < 0 or not (del_at < working.find("if(nbIsSample(edit)){ closeSheet(); nbSampleRemove(edit.id); return; }")):
        fail("a protected project must reach the vault's delete before the sample's.")
    if working.count("nbTourOnShell();") != 2:
        fail("nbTourOnShell() must be called on exactly the two shell paths.")
    a_at = working.find("async function nbTourOnShell(")
    z_at = working.find("/* ---------- IndexedDB for photos")
    if a_at < 0 or z_at < 0 or z_at < a_at or "EGSTour.pointSeries(" not in working[a_at:z_at]:
        fail("could not find nbTourOnShell to check it — stop and look.")
    body = working[a_at:z_at]
    if "nbTourWrite(" in body.split("EGSTour.pointSeries(")[0] or "localStorage.setItem" in body:
        fail("nbTourOnShell writes before anyone has tapped — startup must not write.")
    if working.count("localStorage.setItem(NB_TOUR_KEY") != 1:
        fail("notebuilt.tour must have exactly one writer, nbTourWrite().")
    if "indexedDB.open('notebuilt',1)" not in working or working.count("indexedDB.open(") != 2:
        fail("the databases changed — the photos database must stay exactly at version 1.")
    if "innerHTML" in working[working.find(BEGIN):working.find(END)]:
        fail("the engine must build its layers without innerHTML.")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", working, flags=re.S)
    if len(scripts) < 5:
        fail(f"expected at least 5 script blocks, found {len(scripts)}.")

    # ---- syntax check: EVERY inline block, before anything is written ----
    ok, report = check_html(working)
    print(report)
    if not ok:
        if "node not found" in report and ALLOW_UNVERIFIED:
            print("⚠️  --allow-unverified given — the edit goes ahead WITHOUT a syntax check.")
        else:
            fail("nothing written.")

    # ---- backup, then write atomically ----------------------------------
    # Tier 1: backup before any write. backup() never clobbers an earlier one.
    backup_path = backup(TARGET)
    print(f"\U0001f5c4  Backup saved to {backup_path}")
    tmp = TARGET.with_name(f".{TARGET.name}.fix-nb-onboarding.tmp")
    tmp.write_text(working, encoding="utf-8")
    os.replace(tmp, TARGET)

    # ---- what landed on disk, checked again, or restore -----------------
    ok, report = check_file(TARGET)
    if not ok and not ("node not found" in report and ALLOW_UNVERIFIED):
        print(report)
        shutil.copy2(backup_path, TARGET)
        fail("restored from backup — nothing was changed.")

    print(f"✅ applied {len(edits)} edits ({len(text):,} → {len(working):,} characters). Backup: {backup_path}")


if __name__ == "__main__":
    main()
