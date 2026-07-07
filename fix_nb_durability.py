#!/usr/bin/env python3
"""
Notebuilt: data durability guard.
Protects your job notes/specs/tasks from the disappearing-data problem:
  - Requests PERSISTENT storage so the browser won't evict app data.
  - Keeps a last-known-good backup (_bak) of every key on each save.
  - SELF-HEALS: if a key is missing/blank but its backup is good, restores it
    before the app loads.
  - Refuses EMPTY overwrites of real data during the startup window (stops the
    "load fails -> save empty over everything" wipe).
Keys protected: pl.houses, pl.tasks, pl.notes, pl.settings.
(Photos are in IndexedDB and are safer; persistent storage protects them too.)

Run from the Notebuilt repo folder:  python3 fix_nb_durability.py
Targets index.html. Backs up first; aborts if the anchor doesn't match.
"""
import sys, shutil, time

PATH = sys.argv[1] if len(sys.argv) > 1 else 'index.html'

OLD = "const K = { houses:'pl.houses', tasks:'pl.tasks', notes:'pl.notes', settings:'pl.settings' };"

NEW = '''/* EGS durability guard: persist + backup + self-heal + empty-overwrite protection */
(function(){
  const CRIT = ['pl.houses','pl.tasks','pl.notes','pl.settings'];
  const boot = Date.now();
  let _set, _get;
  try { _set = localStorage.setItem.bind(localStorage); _get = localStorage.getItem.bind(localStorage); } catch(e){ return; }
  const blank = v => v==null || v==='' || v==='[]' || v==='{}' || v==='null' || v==='undefined';
  /* self-heal before the app loads its data */
  try { for (const k of CRIT){ const cur=_get(k), bak=_get(k+'_bak'); if (blank(cur) && !blank(bak)) _set(k, bak); } } catch(e){}
  /* guarded saves */
  try {
    localStorage.setItem = function(key, val){
      try {
        if (CRIT.includes(key)){
          const existing = _get(key);
          if (blank(val) && !blank(existing) && (Date.now()-boot) < 8000){
            console.warn('Durability: blocked empty overwrite of '+key+' at startup');
            return;
          }
          if (!blank(val)) { try { _set(key+'_bak', val); } catch(e){} }
        }
      } catch(e){}
      return _set(key, val);
    };
  } catch(e){}
  /* ask the browser not to evict our data (covers IndexedDB photos too) */
  try {
    if (navigator.storage && navigator.storage.persist){
      navigator.storage.persisted().then(p => { if(!p) navigator.storage.persist(); }).catch(()=>{});
    }
  } catch(e){}
})();
const K = { houses:'pl.houses', tasks:'pl.tasks', notes:'pl.notes', settings:'pl.settings' };'''

with open(PATH, 'r', encoding='utf-8') as f:
    html = f.read()

if 'EGS durability guard' in html:
    print("ABORT — durability guard already applied.")
    sys.exit(1)
c = html.count(OLD)
if c != 1:
    print("ABORT — anchor found %d times (expected 1). No changes made." % c)
    print("Re-upload your current Notebuilt index.html and I'll rebuild.")
    sys.exit(1)

bak = PATH + '.bak.' + time.strftime('%Y%m%d-%H%M%S')
shutil.copy2(PATH, bak)
html = html.replace(OLD, NEW, 1)
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print("OK — Notebuilt durability guard added (persist + backup + self-heal + overwrite guard).")
print("Backup saved to:", bak)
