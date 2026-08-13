#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — an unreadable settings file must never become a deleted one
Run from the same folder as index.html:
    python3 fix_settings_never_self_destruct.py

INCIDENT #2, REPRODUCED
-----------------------
Symptom: unlock recorded and verified in-session, gone after restart, on a
grandfathered install.

The reported prime suspect — the grandfather stamp assigning over
`settings.unlock` — is NOT it, and was ruled out by experiment, not by
reading: a 25-project grandfathered-and-unlocked fixture survives repeated
restarts with the activation intact. `unlockPriorProjects()` only ever
touches `settings.priorProjects`, by property assignment, and returns
early when the stamp already exists.

The real chain, reproduced in a browser:

  1. `notebuilt.settings` is unparseable for one launch (a partial write, an
     eviction — this device already showed storage pressure in incident #1)
  2. `load()` catches the parse error and SILENTLY returns defaults
  3. `settings.priorProjects` is therefore undefined, so the startup call
     to `unlockPriorProjects()` fires for the first time in months
  4. it stamps and calls `persist.settings()` — writing the stripped
     defaults straight over the only good copy
  5. the durability guard mirrors that same write into `settings_bak`,
     so the backup copy is destroyed by the identical stroke

Result: a transient read failure is converted into permanent deletion,
within milliseconds of launch, with no message.

BIGGER THAN THE UNLOCK
----------------------
`settings` also holds `vault` (the salt and verifier for protected
projects), `pinHash`, and `recovery`. The same path destroys all of them.
Losing the vault block makes every protected project permanently
unreadable — there is no other copy and nothing derived from the
passphrase is stored anywhere. That is the reason this fix is not scoped
to the unlock.

This is a regression from the unlock feature: before it, nothing persisted
settings at startup, so an unreadable blob stayed unreadable instead of
being overwritten.

THE FIX — three layers
----------------------
1. **Nothing writes settings at startup.** The startup stamp call is
   removed. `unlockPriorProjects()` already stamps lazily the first time
   the pitch needs it, which is a user-initiated moment, and `importData`
   already stamps a restored file. The trigger is gone.

2. **"Absent" and "unreadable" stop being the same thing.**
   `loadSettings()` treats a missing key as a fresh install (defaults, safe
   to write) and an unparseable one as an emergency: it first tries
   `settings_bak`, which the durability guard has been maintaining all
   along and which — with layer 1 in place — is no longer clobbered before
   it can be read. Most real occurrences now self-heal silently and
   completely. Only if BOTH copies are unreadable does it fall back to
   defaults, and then it latches `settingsUnreadable` and refuses every
   settings write, so the damaged original is preserved for recovery
   rather than overwritten. The person is told, because their vault and
   their PIN are in that file.

3. **A write that forgot a field must not delete it.** `saveSettings()`
   carries forward `unlock` and `vault` when the outgoing object omits
   them entirely and storage has them. An explicit `null` still turns
   either off, so "turn the vault off" and "restore a backup with no
   vault" both keep working — only omission is treated as an accident.
   A purchase and a vault key are not things any incidental write gets to
   remove.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    # 1 — tell "absent" apart from "unreadable"
    old_load = """let settings = load(K.settings,{ pinHash:null, pinSalt:null });"""
    new_load = """/* settings carries the vault salt and verifier, the PIN, the recovery
   credential and the unlock — the four things in this app that cannot be
   reconstructed from anything else. So an unreadable settings blob must
   never be quietly swapped for defaults: the next write would put those
   defaults over the only copy, which is precisely how a bad launch turns
   into permanent deletion. Missing is a fresh install. Unparseable is an
   emergency, and the two are not the same. */
let settingsUnreadable=false;
function loadSettings(){
  let raw=null;
  try{ raw=localStorage.getItem(K.settings); }catch(e){}
  if(raw==null||raw==='') return { pinHash:null, pinSalt:null };   /* fresh install */
  try{ return JSON.parse(raw); }catch(e){}
  /* The durability guard has been mirroring every good write into a twin.
     Nothing writes settings at startup any more, so that twin is still the
     last good copy at this point rather than a casualty of this launch. */
  try{
    const bak=localStorage.getItem(K.settings+'_bak');
    if(bak){ const v=JSON.parse(bak); console.warn('Notebuilt: settings recovered from the backup copy'); return v; }
  }catch(e){}
  /* Both copies unreadable. Keep what is on disk exactly as it is — it is
     the only remaining evidence — and refuse to write over it. */
  settingsUnreadable=true;
  return { pinHash:null, pinSalt:null };
}
let settings = loadSettings();"""
    edits.append((old_load, new_load, "loadSettings(): absent vs unreadable"))

    # 2 — a write that omits a field must not delete it
    old_persist = """const persist = { houses:()=>save(K.houses,houses), tasks:()=>save(K.tasks,tasks),
                  notes:()=>save(K.notes,notes), settings:()=>save(K.settings,settings),
                  categories:()=>save(K.categories,categories) };"""
    new_persist = """/* Omission is not deletion. `unlock` is a purchase and `vault` is the only
   way back into protected projects; neither may be dropped by a write that
   simply did not know about it. An explicit null still switches either off,
   so turning the vault off and restoring a vault-less backup both behave as
   before — only a field that is absent entirely gets carried forward. */
function saveSettings(){
  if(settingsUnreadable) return;          /* never overwrite the damaged original */
  let prev=null;
  try{ prev=JSON.parse(localStorage.getItem(K.settings)||'null'); }catch(e){}
  if(prev){
    if(settings.unlock===undefined && prev.unlock && prev.unlock.activationId) settings.unlock=prev.unlock;
    if(settings.vault===undefined  && prev.vault)  settings.vault =prev.vault;
  }
  save(K.settings,settings);
}
const persist = { houses:()=>save(K.houses,houses), tasks:()=>save(K.tasks,tasks),
                  notes:()=>save(K.notes,notes), settings:saveSettings,
                  categories:()=>save(K.categories,categories) };"""
    edits.append((old_persist, new_persist, "saveSettings(): omission is not deletion"))

    # 3 — nothing writes settings at startup any more
    old_stamp = """/* Recorded on the first run of the capped build, before anything can ask. */
unlockPriorProjects();"""
    new_stamp = """/* Deliberately NOT called at startup. It writes, and a write at startup is
   what turned an unreadable settings blob into a deleted one: the fallback
   defaults have no priorProjects, so this fired on the first bad launch and
   persisted them over the real record. It stamps lazily instead — from the
   pitch, which is user-initiated, and from importData for a restored file.
   Nothing about the app's startup may write settings. */"""
    edits.append((old_stamp, new_stamp, "remove the startup settings write"))

    # 4 — say it, because their vault and PIN are in that file
    old_boot = """/* Write it, then read it straight back."""
    new_boot = """/* Both copies of settings were unreadable. The app is running on defaults
   and refusing to save any of them, so nothing is being made worse — but
   the vault, the PIN and the unlock are all in that file, and staying quiet
   about it is how someone discovers it months later. */
if(settingsUnreadable){
  setTimeout(()=>{ try{
    alert('Notebuilt could not read your saved settings.\\n\\n'
      +'Your projects, notes and photos are safe and untouched. What is affected is your app lock, your vault passphrase record and your unlock.\\n\\n'
      +'Nothing has been overwritten — the file is being left exactly as it is. Restore your most recent backup to put it right.');
  }catch(e){} }, 1500);
}

/* Write it, then read it straight back."""
    edits.append((old_boot, new_boot, "tell the user when settings are unreadable"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    if working.count("fetch(") != 1:
        fail("fetch( count changed — expected exactly 1.")
    # Nothing may persist settings at module level (startup) any more.
    body = working[working.find("let settings = loadSettings();"):working.find("const uid =")]
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("unlockPriorProjects()") or s.startswith("persist.settings()") or s.startswith("saveSettings()"):
            fail(f"a settings write survives at startup: {s!r}")
    if "settings:saveSettings," not in working:
        fail("persist.settings is not routed through the guarded save.")
    if "if(settingsUnreadable) return;" not in working:
        fail("the damaged-original write block is missing.")
    if "load(K.settings," in working:
        fail("the old silent-fallback settings load survived.")
    if "API_BASE: 'https://api.polar.sh'" not in working:
        fail("API_BASE is not production.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: no settings write remains at startup")
    print("✅ guard: persist.settings routed through the guarded save")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_settings_guard_check.js")
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

    print("\n✅ an unreadable settings file is now recovered or preserved — never overwritten.")


if __name__ == "__main__":
    main()
