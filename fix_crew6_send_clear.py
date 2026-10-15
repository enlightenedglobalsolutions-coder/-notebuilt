#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 6: Send report is never covered
(th_nbp_stage4, spec §8 "a sticky bottom button, clear of the gesture bar")
Run from the same folder as index.html, after chunks 1-5:
    python3 fix_crew6_send_clear.py

FOUND BY LOOKING, not by the assertions: a phone-width screenshot of the
crew list in a browser tab showed the "Add Notebuilt to your home screen"
banner sitting fixed over the bottom of the screen, and the sticky Send
report button completely underneath it. A worker opening their first crew
link in Chrome would see no way to report until they dismissed a banner
they had no reason to touch. The backup nudge banner sits in the same place.

The banners are built and removed on the fly and wrap to different heights,
so a fixed offset cannot know where they end. crewLiftSend() measures: when
a banner is on screen the button sits 10px above its top edge; when there
is none it goes back to its place above the nav. The page's bottom
padding grows by the same amount, so the last task can still be scrolled
clear of the lifted button, and every other screen gets it back. It runs after every render
of a crew list, whenever something is added to or removed from <body> (both
banners live there), and on resize.

Backs up first, anchors asserted ==1, node --check, atomic, never
overwrites an earlier backup.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "function crewLiftSend("


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


LIFT = r"""/* The install and backup banners are fixed over the bottom of the screen,
   and wrap to different heights. Send report must never be under one: when a
   banner is showing, the button sits just above its top edge. */
function crewLiftSend(){
  const app=document.getElementById('app'); if(!app) return;
  const btn=app.querySelector('.crew-send');
  const ban=['install-banner','backup-banner'].map(id=>document.getElementById(id)).find(Boolean);
  /* The page grows by as much as the button rose, so the last task can
     still be scrolled clear of it. Any other screen gets its padding back. */
  if(!btn || !ban){ if(btn) btn.style.bottom=''; app.style.paddingBottom=''; return; }
  const lift=Math.round(innerHeight - ban.getBoundingClientRect().top + 10);
  btn.style.bottom=lift+'px';
  app.style.paddingBottom=(lift+btn.offsetHeight+16)+'px';
}
new MutationObserver(crewLiftSend).observe(document.body,{childList:true});
window.addEventListener('resize',crewLiftSend);
"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "crewLists:crewDump?crewDump.length:null" not in text:
        fail("chunk 5 (fix_crew5_backup_copy.py) has not been applied.")

    edits = []
    old_at = "/* Crew lists land a moment after boot (IndexedDB)."
    edits.append((old_at, LIFT + old_at, "crewLiftSend before crewAfterLoad"))

    old_bind = "  $app.querySelectorAll('[data-crew-report]').forEach(b=>b.onclick=()=>crewSendReport(b.dataset.crewReport));\n"
    edits.append((old_bind, old_bind + "  crewLiftSend();\n", "lift after every render"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # the observer needs <body> to exist: the app script sits at the end of it
    if working.find("new MutationObserver(crewLiftSend)") < working.find("<body"):
        fail("the observer would run before <body> exists.")

    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", working, flags=re.S)
    with tempfile.TemporaryDirectory() as td:
        for i, s in enumerate(scripts):
            p = Path(td) / f"s{i}.js"
            p.write_text(s, encoding="utf-8")
            r = subprocess.run(["node", "--check", str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                fail(f"script block {i} fails node --check:\n{r.stderr}")

    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_name(f"{TARGET.name}.bak.{stamp}")
    n = 1
    while bak.exists():          # never overwrite an earlier backup (same-second runs)
        n += 1
        bak = TARGET.with_name(f"{TARGET.name}.bak.{stamp}-{n}")
    shutil.copy2(TARGET, bak)
    TARGET.write_text(working, encoding="utf-8")
    print(f"✅ applied {len(edits)} edits. Backup: {bak}")


if __name__ == "__main__":
    main()
