#!/usr/bin/env python3
"""
Notebuilt — Chunk 18: Add to Home Screen prompt
Run this from the same folder as your index.html:
    python3 fix_chunk18_install_prompt.py

Adds a quiet, dismissible "Add to Home Screen" banner — shown once, only
after the app is actually unlocked (not layered on the PIN screen), never
shown again once dismissed or installed. On Android/Chrome it uses the
real browser install prompt (beforeinstallprompt); on iOS, which doesn't
support that API, it shows simple manual instructions instead.

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
MARKER = "CHUNK18_INSTALL_PROMPT"  # already-applied guard

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

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: CSS — install banner styles
    # ---------------------------------------------------------------
    old1 = """  #lock .err{color:var(--danger);font-size:13px;min-height:18px;margin-top:6px}"""
    new1 = """  #lock .err{color:var(--danger);font-size:13px;min-height:18px;margin-top:6px}

  /* CHUNK18_INSTALL_PROMPT */
  #install-banner{
    position:fixed;left:12px;right:12px;bottom:calc(var(--safe-b) + 14px);z-index:40;
    background:var(--ink-3);border:1px solid var(--line);border-radius:var(--radius);
    padding:12px 10px 12px 16px;display:flex;align-items:center;gap:10px;
    box-shadow:0 8px 24px rgba(0,0,0,.4);
  }
  #install-banner .txt{flex:1;font-size:13px;line-height:1.4;color:var(--paper-dim)}
  #install-banner .txt b{color:var(--paper);display:block;font-family:var(--serif);font-size:15px;margin-bottom:2px}"""
    edits.append((old1, new1, "CSS: #install-banner styles"))

    # ---------------------------------------------------------------
    # Edit 2: no-PIN unlock path — hook the install prompt check
    # ---------------------------------------------------------------
    old2 = """  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); return; }"""
    new2 = """  if(!settings.pinHash){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); return; }"""
    edits.append((old2, new2, "lockGate(): hook install prompt on no-PIN unlock"))

    # ---------------------------------------------------------------
    # Edit 3: correct-PIN unlock path — hook the install prompt check
    # ---------------------------------------------------------------
    old3 = """        if(ok){ $lock.classList.add('hidden'); showShell(true); render(); }"""
    new3 = """        if(ok){ $lock.classList.add('hidden'); showShell(true); render(); maybeShowInstallPrompt(); }"""
    edits.append((old3, new3, "lockGate(): hook install prompt on correct-PIN unlock"))

    # ---------------------------------------------------------------
    # Edit 4: add the install-prompt JS module right after lockGate()
    # ---------------------------------------------------------------
    old4 = "lockGate();"
    new4 = """/* CHUNK18_INSTALL_PROMPT */
let deferredInstallPrompt=null;
let installPromptShown=false;
function isStandaloneApp(){ return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone===true; }
function isIOSDevice(){ return /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream; }
function appUnlocked(){ return $lock.classList.contains('hidden'); }

window.addEventListener('beforeinstallprompt', e=>{
  e.preventDefault();
  deferredInstallPrompt=e;
  maybeShowInstallPrompt();
});
if(isIOSDevice()) setTimeout(maybeShowInstallPrompt,1200);

function maybeShowInstallPrompt(){
  if(installPromptShown||isStandaloneApp()||localStorage.getItem('installPromptDismissed')||!appUnlocked()) return;
  if(deferredInstallPrompt) showInstallBanner('android');
  else if(isIOSDevice()) showInstallBanner('ios');
}
function showInstallBanner(mode){
  if(installPromptShown) return;
  installPromptShown=true;
  const el=document.createElement('div');
  el.id='install-banner';
  el.innerHTML = mode==='android'
    ? `<div class="txt"><b>Add ${esc(APP_NAME)} to your home screen</b>Quick, quiet access \\u2014 no app store needed.</div>
       <button class="btn primary sm" id="install-go">Add</button>
       <button class="icon-btn" id="install-x" aria-label="Dismiss" style="width:36px;height:36px;flex:none">${I.x}</button>`
    : `<div class="txt"><b>Add ${esc(APP_NAME)} to your home screen</b>Tap Share, then "Add to Home Screen."</div>
       <button class="icon-btn" id="install-x" aria-label="Dismiss" style="width:36px;height:36px;flex:none">${I.x}</button>`;
  document.body.appendChild(el);
  if(mode==='android'){
    document.getElementById('install-go').onclick=async()=>{
      if(!deferredInstallPrompt) return;
      deferredInstallPrompt.prompt();
      await deferredInstallPrompt.userChoice;
      deferredInstallPrompt=null;
      dismissInstallBanner();
    };
  }
  document.getElementById('install-x').onclick=dismissInstallBanner;
}
function dismissInstallBanner(){
  const el=document.getElementById('install-banner'); if(el) el.remove();
  localStorage.setItem('installPromptDismissed','1');
}

lockGate();"""
    edits.append((old4, new4, "add install-prompt module after lockGate()"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk18_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check. Review the diff manually.")
        result = None

    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 18 applied successfully: Add to Home Screen prompt.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
