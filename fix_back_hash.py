#!/usr/bin/env python3
"""fix_back_hash.py — th_nb_back_hash: one back resolver, hash-carried view state.

Back used to be a hardcoded map in goBack(), so leaving a project note landed on
the Notes tab, and nothing ever touched history, so Android's system back closed
the app. This replaces both with one resolver:

  * every navigation writes a history entry; popstate is the ONLY back path, and
    the header arrow is history.back(), so the arrow and the system button run
    the same code;
  * every overlay (viewer, annotate, sheet, vault ceremony, camera) owns an entry
    while it is open, so back closes it as a natural pop — nothing is re-pushed
    in the gap, so a fast double back cannot land a level deep;
  * every history mutation goes through one queue that waits out in-flight
    history.go() traversals, so two quick tab taps cannot interleave;
  * the stack is [guard, tab, ...]. Back onto the guard shows "press back again
    to exit" and waits there 2s; a second press is a native exit in the
    installed app (a browser tab instead leaves to whatever preceded it — a
    known difference, not a bug);
  * the hash and the notebuilt.lastView device key are untrusted: view names
    come from a constant Set, ids must match a stored record, and anything else
    lands on To Do. Nothing parsed reaches a sink — renderers interpolate ids
    from stored records;
  * cold launch restores the view, but the chain above the guard is seeded only
    at the first render after the PIN gate, so back at #lock is a one-entry
    native exit and nothing ever renders behind it.

Backup first, exact anchors (each must match exactly once), atomic abort,
already-applied guard, node --check on every inline script.
"""
import re, shutil, subprocess, sys, tempfile, time, os

PATH = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
MARK = 'NB_BACK_HASH'

ROUTER = r'''/* NB_BACK_HASH — one back resolver, hash-carried view state.
   history.state = {nb:1, v:view, p:param, d:depth, b:depth of the view entry,
   g:guard?, o:overlay kind?, f:[view,param] it was opened from, y:scroll}.
   The stack is [guard d0, tab d1, deeper views, overlays of the top view].
   popstate is the ONLY back path — the header arrow is history.back() — so
   there is no per-screen back logic anywhere. */
const NAV_VIEWS=new Set(['todo','houses','calc','notes','settings','house','housenotes','note','search','privacy','support']);
const NAV_TABS=new Set(['todo','houses','calc','notes','settings']);
const NAV_ID=/^[A-Za-z0-9_-]{1,80}$/;
const NAV_KEY='notebuilt.lastView';   /* describes this phone, never the data — not in settings, not in a backup */
const NAV_EXIT_MS=2000;
let _navBase=0, _navExpect=0, _navExpectT=null, _navQ=[], _navQuiet=false, _navExitT=null;

/* The hash and the device key are untrusted input. A view name must be one of
   the constant set; an id must match a stored record. Anything else is To Do. */
function navParse(name,param){
  const fall={name:'todo',param:null};
  if(typeof name!=='string' || !NAV_VIEWS.has(name)) return fall;
  if(name==='house'||name==='housenotes')
    return (typeof param==='string' && NAV_ID.test(param) && houseById(param)) ? {name,param} : fall;
  if(name==='note'){
    if(param==='new') return {name,param};
    return (typeof param==='string' && NAV_ID.test(param) && notes.some(n=>n.id===param)) ? {name,param} : fall;
  }
  return param==null ? {name,param:null} : fall;
}
function navParseHash(h){
  if(typeof h!=='string' || h.length>120) return null;
  const m=/^#\/([a-z]{1,12})(?:\/([A-Za-z0-9_-]{1,80}))?$/.exec(h);
  return m ? navParse(m[1], m[2]===undefined?null:m[2]) : null;
}
function navHash(t){ return '#/'+t.name+(t.param!=null?'/'+encodeURIComponent(t.param):''); }
function navEntry(t,d){ return {nb:1, v:t.name, p:t.param!=null?t.param:null, d, b:d}; }
function navTabOf(name){ return NAV_TABS.has(name)?name:(({house:'houses',housenotes:'houses',note:'notes'})[name]||(name==='privacy'||name==='support'?'settings':'todo')); }

/* A cold stack after process death: the one static parent table, used ONLY to
   seed. Back never consults it. */
function navSeedChain(t){
  if(NAV_TABS.has(t.name)) return [t];
  if(t.name==='house') return [{name:'houses',param:null},t];
  if(t.name==='housenotes') return [{name:'houses',param:null},{name:'house',param:t.param},t];
  if(t.name==='note'){
    const n=notes.find(x=>x.id===t.param);
    if(n && n.houseId && houseById(n.houseId)) return [{name:'houses',param:null},{name:'house',param:n.houseId},t];
    return [{name:'notes',param:null},t];
  }
  return [{name:navTabOf(t.name),param:null},t];
}

/* The queue. history.go() is async; anything that would touch history while a
   traversal we started is in flight waits for its popstate. */
function navOp(fn){ if(_navExpect) _navQ.push(fn); else fn(); }
function navFlush(){ while(_navQ.length && !_navExpect) _navQ.shift()(); }
function navTraverse(n){
  if(!n) return;
  _navExpect++;
  clearTimeout(_navExpectT);
  /* history.go() past either end fires no popstate — never wait forever. */
  _navExpectT=setTimeout(()=>{ _navExpect=0; navFlush(); },1500);
  history.go(n);
}
function navState(){ const s=history.state; return (s && s.nb) ? s : null; }

/* Leave the guard: put the tab entry back above it. */
function navUnguard(){
  if(_navExitT){ clearTimeout(_navExitT); _navExitT=null; }
  const s=navState(); if(!s || !s.g) return;
  const t={name:s.v,param:null};
  history.pushState(navEntry(t,1),'',navHash(t)); _navBase=1;
}
function navPush(t,o){
  navUnguard();
  const s=navState(); const d=(s?s.d:0)+1;
  if(o){ history.pushState(Object.assign(navEntry(t,d),{b:_navBase,o}),'',navHash(t)); return; }
  const e=navEntry(t,d); if(s) e.f=[s.v,s.p];
  history.pushState(e,'',navHash(t)); _navBase=d;
}

/* Open overlays, bottom to top in z-order: viewer 60, annotate 70, sheet 80,
   vault 110, camera 115. */
function navOpenChain(){
  const c=[];
  if(!$viewer.classList.contains('hidden')) c.push('viewer');
  if(!$annotate.classList.contains('hidden')) c.push('annotate');
  if($mr.innerHTML) c.push('sheet');
  if(!$vault.classList.contains('hidden')) c.push('vault');
  if(cam.open) c.push('camera');
  return c;
}
/* Make the entries above the view entry match the overlays on screen: one per
   overlay. Called by every overlay open and close, so a UI close (an X, a
   scrim tap, a save) consumes its entry and a back is always a natural pop. */
function navReconcile(){
  if(_navQuiet) return;
  navOp(()=>{
    const s0=navState(); if(!s0 || s0.unseeded) return;
    const C=navOpenChain();
    if(s0.g && !C.length) return;
    if(!s0.g && s0.d<_navBase){ navPush({name:view.name,param:view.param}); }
    for(let guard=0; guard<8; guard++){
      const s=navState(); const lvl=s.g?-1:s.d-_navBase;
      if(lvl>C.length){ navTraverse(C.length-lvl); return; }
      if(lvl===C.length) return;
      navPush({name:view.name,param:view.param}, C[Math.max(lvl,0)]);
    }
  });
}
/* Close overlays from the top until n remain. A blocker keeps its screen and
   returns false: the vault ceremony is never navigated out from under, and
   annotate asks before discarding. */
function navCloseTo(n){
  const C=navOpenChain();
  while(C.length>n){
    const k=C.pop();
    if(k==='vault') return false;
    if(k==='annotate'){ cancelAnnotate(); if(!$annotate.classList.contains('hidden')) return false; }
    else if(k==='camera') camClose();
    else if(k==='viewer') closeViewer();
    else if(k==='sheet') closeSheet();
  }
  return true;
}

function navArmExit(){
  toast('Press back again to exit');
  clearTimeout(_navExitT);
  _navExitT=setTimeout(()=>{ _navExitT=null; navOp(navUnguard); },NAV_EXIT_MS);
}

function navShow(name,param,y){
  /* Any navigation drops a pending unlock return. The privacy link re-arms it
     immediately after its own go(), so only a DELIBERATE departure — a nav
     tap, a project opened — loses it. */
  _unlockReturn=null;
  view={name,param}; render(); window.scrollTo(0,y||0);
}

function go(name,param=null){
  const t={name,param}, y=window.scrollY;
  const stampY=!_navExpect;
  navOp(()=>{
    const s=navState();
    if(!s || s.unseeded){ return; }
    if(NAV_TABS.has(name)){
      navUnguard();
      const s1=navState();
      if(s1.d<=1){ history.replaceState(navEntry(t,1),'',navHash(t)); _navBase=1; }
      else { navTraverse(1-s1.d); navOp(()=>{ history.replaceState(navEntry(t,1),'',navHash(t)); _navBase=1; }); }
    } else {
      if(stampY && !s.o && !s.g) history.replaceState(Object.assign({},s,{y}),'');
      navPush(t);
    }
  });
  navShow(name,param);
}
/* Leave this screen for a sibling: same depth, so back still returns to
   wherever this screen was opened from. */
function navReplace(name,param){
  const t={name,param};
  navOp(()=>{ const s=navState(); if(s && !s.g && !s.unseeded){ const e=navEntry(t,s.d); if(s.f) e.f=s.f; history.replaceState(e,'',navHash(t)); _navBase=s.d; } });
  navShow(name,param);
}
function navFromIs(name,param){ const s=navState(); return !!(s && s.f && s.f[0]===name && s.f[1]===param); }
/* The header arrow. The same path as the phone's back button. */
function navBack(){
  navOp(()=>{
    const s=navState();
    if(s && !s.g && !s.unseeded && s.d>1) history.back();
    else go(navTabOf(view.name));
  });
}

/* Called at the end of every render(): keeps the hash honest (a new note
   becomes its real id the moment it is autosaved) and records the device key. */
function navSync(){
  /* Snapshot NOW. Queued behind a traversal, a later navigation may have
     changed view by the time this runs; stamping that onto the entry below
     would mislabel it. Only the latest sync applies — it always runs last. */
  const at=view;
  navOp(()=>{
    if(at!==view) return;
    const s=navState(); if(!s) return;
    if(s.unseeded){ if($lock.classList.contains('hidden')) navSeed(); return; }
    if(!s.o && !s.g && (s.v!==view.name || s.p!==view.param)){
      const e=Object.assign({},s,{v:view.name,p:view.param}); history.replaceState(e,'',navHash(view));
    }
    try{ localStorage.setItem(NAV_KEY, navHash(view)); }catch(e){}
  });
}
function navSeed(){
  const chain=navSeedChain({name:view.name,param:view.param});
  history.replaceState({nb:1,g:1,d:0,b:0,v:chain[0].name,p:null},'',navHash(chain[0]));
  chain.forEach((t,i)=>{ const e=navEntry(t,i+1); if(i) e.f=[chain[i-1].name,chain[i-1].param]; history.pushState(e,'',navHash(t)); });
  _navBase=chain.length;
  try{ localStorage.setItem(NAV_KEY, navHash(view)); }catch(e){}
}

/* THE back resolver. */
function navOnPop(e){
  if(_navExpect){ _navExpect--; if(!_navExpect){ clearTimeout(_navExpectT); navFlush(); } return; }
  const s=e.state; if(!(s && s.nb)) return;
  /* The PIN gate owns the screen. History there is one entry, so this is only
     reachable after a reload — and nothing may render behind the keypad. */
  if(!$lock.classList.contains('hidden')) return;
  const lvl=s.g?-1:s.d-_navBase;
  let held;
  _navQuiet=true;
  try{ held=!navCloseTo(Math.max(lvl,0)); }finally{ _navQuiet=false; }
  if(held || lvl>=0){ navReconcile(); return; }
  if(s.g){
    /* Onto the guard: stay, say so, and let a second press leave. */
    history.replaceState(Object.assign({},s,{v:navTabOf(view.name),p:null}),'',navHash({name:navTabOf(view.name),param:null}));
    _navBase=0;
    navArmExit();
    return;
  }
  _navBase=s.b!=null?s.b:s.d;
  if(view.name==='privacy' && _unlockReturn){ unlockReturnFromPrivacy(); }
  else { const t=navParse(s.v,s.p); navShow(t.name,t.param,s.y); }
  if(s.o) navReconcile();
}

function navBoot(){
  window.addEventListener('popstate',navOnPop);
  const s=navState();
  if(s && !s.unseeded){
    /* A reload in the same session (the update banner's Refresh): the stack
       below is still ours. Re-validate — the project may be gone. */
    const t=navParse(s.v,s.p);
    if(t.name===s.v && t.param===s.p){
      view=t; _navBase=s.b!=null?s.b:s.d;
      if(s.g) navUnguard(); else if(s.o) navReconcile();
      return;
    }
  }
  let t;
  const h=location.hash;
  if(h && h!=='#') t=navParseHash(h)||{name:'todo',param:null};
  else { let k=null; try{ k=localStorage.getItem(NAV_KEY); }catch(e){} t=(k && navParseHash(k))||{name:'todo',param:null}; }
  view=t; _navBase=0;
  /* One entry until the first render past the PIN gate seeds the rest. */
  history.replaceState({nb:1,g:1,d:0,b:0,v:t.name,p:t.param,unseeded:1},'',navHash(t));
}
'''

EDITS = [
  # 1. go() becomes the router block.
  ('go', '''function go(name,param=null){
  /* Any navigation drops a pending unlock return. The privacy link re-arms it
     immediately after its own go(), so only a DELIBERATE departure — a nav
     tap, a project opened — loses it. */
  _unlockReturn=null;
  view={name,param}; render(); window.scrollTo(0,0);
}
''', ROUTER),
  # 2. every render keeps the hash honest.
  ('render-tail', '''  renderFab();
  hydratePhotos();
}
''', '''  renderFab();
  hydratePhotos();
  navSync();                                       /* NB_BACK_HASH */
}
'''),
  # 3. the arrow is history.back().
  ('bind-back', "  $app.querySelectorAll('[data-back]').forEach(b=>b.onclick=goBack);\n",
                "  $app.querySelectorAll('[data-back]').forEach(b=>b.onclick=navBack);   /* NB_BACK_HASH — same path as the phone's back */\n"),
  # 4. the hardcoded map goes.
  ('goBack', '''function goBack(){
  /* Came here from the unlock pitch: put it back, with what was in it. */
  if(view.name==='privacy' && unlockReturnFromPrivacy()) return;
  if(view.name==='housenotes'){ go('house', view.param); return; }
  const to = ({house:'houses', note:'notes', search:'todo', privacy:'settings', support:'settings'})[view.name] || 'todo';
  go(to);
}
''', ''),
  # 5. returning from privacy is a pop now: history is already there.
  ('unlock-return', '''  _unlockReturn=null;
  go(r.from.name, r.from.param);
''', '''  _unlockReturn=null;
  navShow(r.from.name, r.from.param);   /* NB_BACK_HASH — reached from a pop; history is already there */
'''),
  # 6. sheets own an entry.
  ('closeSheet', "function closeSheet(){ $mr.innerHTML=''; }\n",
                 "function closeSheet(){ $mr.innerHTML=''; navReconcile(); }\n"),
  ('sheet', '''  $mr.querySelector('[data-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-scrim')) closeSheet(); });
  nbHelpBind($mr);
}
''', '''  $mr.querySelector('[data-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-scrim')) closeSheet(); });
  nbHelpBind($mr);
  navReconcile();                                  /* NB_BACK_HASH */
}
'''),
  # 7. the crop sheet writes $mr itself; route its open and closes through the same hooks.
  ('crop-open', "  $mr.querySelector('[data-crop-cancel]').onclick=()=>{ $mr.innerHTML=''; };\n  $mr.querySelector('[data-crop-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-crop-scrim')) $mr.innerHTML=''; });\n",
                "  navReconcile();                                  /* NB_BACK_HASH */\n  $mr.querySelector('[data-crop-cancel]').onclick=()=>{ closeSheet(); };\n  $mr.querySelector('[data-crop-scrim]').addEventListener('click',e=>{ if(e.target.hasAttribute('data-crop-scrim')) closeSheet(); });\n"),
  ('crop-save', "      $mr.innerHTML=''; render(); toast('Cover cropped & set');\n",
                "      closeSheet(); render(); toast('Cover cropped & set');\n"),
  # 8. viewer, annotate, camera, vault ceremony.
  ('openViewer', '''  $viewer.classList.remove('hidden');
  renderViewerFrame();
}
function closeViewer(){
  $viewer.classList.add('hidden'); $viewer.innerHTML='';
  document.body.style.overflow='';
}
''', '''  $viewer.classList.remove('hidden');
  navReconcile();                                  /* NB_BACK_HASH */
  renderViewerFrame();
}
function closeViewer(){
  $viewer.classList.add('hidden'); $viewer.innerHTML='';
  document.body.style.overflow='';
  navReconcile();
}
'''),
  ('annotate', '''  $annotate.classList.remove('hidden');
  await renderAnnotateFrame();
}
function closeAnnotate(){
  $annotate.classList.add('hidden'); $annotate.innerHTML=''; anUndo=[]; anPending=null;
}
''', '''  $annotate.classList.remove('hidden');
  navReconcile();                                  /* NB_BACK_HASH */
  await renderAnnotateFrame();
}
function closeAnnotate(){
  $annotate.classList.add('hidden'); $annotate.innerHTML=''; anUndo=[]; anPending=null;
  navReconcile();
}
'''),
  ('openCamera', '''  $camera.classList.remove('hidden');
  if(!settings.camIntroSeen){ camDrawIntro(); return; }
''', '''  $camera.classList.remove('hidden');
  navReconcile();                                  /* NB_BACK_HASH */
  if(!settings.camIntroSeen){ camDrawIntro(); return; }
'''),
  ('camClose', '''  $camera.classList.add('hidden'); $camera.innerHTML='';
  document.body.style.overflow='';
  render();
}
''', '''  $camera.classList.add('hidden'); $camera.innerHTML='';
  document.body.style.overflow='';
  navReconcile();                                  /* NB_BACK_HASH */
  render();
}
'''),
  ('vaultOverlay', '''  $vault.innerHTML=html;
  document.body.style.overflow='hidden';
}
function vaultCloseOverlay(){
  $vault.classList.add('hidden'); $vault.innerHTML='';
  document.body.style.overflow='';
}
''', '''  $vault.innerHTML=html;
  document.body.style.overflow='hidden';
  navReconcile();                                  /* NB_BACK_HASH */
}
function vaultCloseOverlay(){
  $vault.classList.add('hidden'); $vault.innerHTML='';
  document.body.style.overflow='';
  navReconcile();
}
'''),
  # 9. a note's Save / Delete is an honest back: to wherever it was opened from.
  ('note-del', "persist.notes(); go('notes'); toast('Note deleted');\n",
               "persist.notes(); navBack(); toast('Note deleted');   /* NB_BACK_HASH */\n"),
  ('note-empty', "  if(!title && !body.trim()){ go('notes'); return; }\n",
                 "  if(!title && !body.trim()){ navBack(); return; }   /* NB_BACK_HASH */\n"),
  ('note-save', "  persist.notes(); go(houseId&&isProtected(houseId)?'house':'notes', houseId&&isProtected(houseId)?houseId:null); toast('Saved');\n",
                '''  persist.notes();
  /* AUTOSAVE_CLAIM — this Save IS the save. Claim its snapshot, or the
     render() that leaving triggers autosaves the still-painted 'new' editor
     and pushes a second copy (reproduced on v2026.08.30-1117: 2 copies). */
  _lastAutosavedSnapshot=id+'|'+title+'|'+body+'|'+houseId+'|'+important;
  /* NB_BACK_HASH — back to wherever the note was opened from. Moved into a
     protected project from somewhere else, it is shown where it now lives —
     in place of the note, so back from there still returns to its origin. */
  if(houseId && isProtected(houseId) && !navFromIs('house',houseId)) navReplace('house',houseId); else navBack();
  toast('Saved');
'''),
  # 10. restore before the first render.
  ('boot', "\nlockGate();\n/* VAULT_ENVELOPE — re-attach", "\nnavBoot();                                         /* NB_BACK_HASH — before the first render */\nlockGate();\n/* VAULT_ENVELOPE — re-attach"),
]

def node_check(html):
  scripts = re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', html, re.S)
  for i, js in enumerate(scripts):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
      f.write(js); p = f.name
    r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
    os.unlink(p)
    if r.returncode:
      print(f'ABORT: script block {i} fails node --check:\n{r.stderr}'); return False
  return True

def main():
  src = open(PATH, encoding='utf-8').read()
  if MARK in src:
    print(f'{MARK} already applied — nothing to do.'); return 0
  out = src
  for name, old, new in EDITS:
    n = out.count(old)
    if n != 1:
      print(f'ABORT: anchor "{name}" matched {n} times (need exactly 1). Nothing written.'); return 1
    out = out.replace(old, new)
  for gone in ('goBack',):
    if re.search(r'\b%s\b' % gone, out):
      print(f'ABORT: "{gone}" still referenced after the edit. Nothing written.'); return 1
  if not node_check(out):
    print('Nothing written.'); return 1
  bak = f'{PATH}.bak.{time.strftime("%Y%m%d-%H%M%S")}'
  shutil.copy2(PATH, bak)
  open(PATH, 'w', encoding='utf-8').write(out)
  print(f'Backup: {bak}\nApplied {len(EDITS)} edits. {len(src)} -> {len(out)} bytes.')
  return 0

if __name__ == '__main__':
  sys.exit(main())
