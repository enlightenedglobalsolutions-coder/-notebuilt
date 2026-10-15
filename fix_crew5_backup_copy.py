#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 5 of 5: backup, help, privacy
(th_nbp_stage4, spec §8 Privacy and help, §6 rules 1, 8, 10)
Run from the same folder as index.html, after chunks 1-4:
    python3 fix_crew5_backup_copy.py

1. BACKUP (rule 8). Every crew list rides in the export as `crew`, each
   record judged on the way out exactly as it is on the way in. If the crew
   lists cannot be read, the file carries no crew section at all — never an
   empty one, which a restore would read as "there are none".
2. RESTORE. A crew section is judged WHOLE by crewJudgeAll() before the
   manifest is even shown: one bad record refuses the entire restore and
   this device is untouched (rule 1, no partial imports). With a section,
   the crew store is replaced in one transaction; without one, the crew
   lists on this phone stay exactly as they are, and the confirm says so.
3. HELP — three first-person (i) entries: crew, crewstatus, crewreport.
   crew says plainly that whoever holds a link can open it as you (rule 10).
4. PRIVACY — crew lists: what the # does, that they stay on this phone and
   in backups, and that the vault does not cover them in this version.
5. The newer-data card in Settings counts crew lists from a newer build.

Backs up first, anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "crewLists:crewDump?crewDump.length:null"


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def line_with(src, start):
    hits=[l for l in src.split("\n") if l.startswith(start)]
    if len(hits)!=1:
        fail(f"expected one line starting {start!r}, found {len(hits)}")
    return hits[0]


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "async function crewSendReport(" not in text:
        fail("chunk 4 (fix_crew4_report.py) has not been applied.")

    edits = []

    # 1 — export ------------------------------------------------------------
    old_dump = "  const dump={ app:'notebuilt', version:3, exportedAt:now(), houses, tasks, notes, photos:photoData,\n"
    new_dump = """  /* CREW — every crew list rides in the backup (spec §6 rule 8), judged on
     the way out as it is on the way in. One from a newer build travels as
     it sits. If they cannot be read, the file carries NO crew section —
     never an empty one, which a restore would take for "there are none". */
  let crewDump=null;
  try{
    const out=[];
    for(const r of await crewAll()){ const j=crewJudge(r); if(j.ok) out.push(j.rec); }
    crewDump=out;
  }catch(e){ console.warn('Notebuilt: crew lists could not be read for the backup',e); }
""" + old_dump
    edits.append((old_dump, new_dump, "gather crew lists for the export"))

    old_set = "               settings: settings,\n"
    new_set = "               settings: settings,\n               crew: crewDump,\n"
    edits.append((old_set, new_set, "crew section in the file"))

    old_cont = "                          settings:true, vault:!!settings.vault } };"
    new_cont = "                          settings:true, vault:!!settings.vault, crewLists:crewDump?crewDump.length:null } };"
    edits.append((old_cont, new_cont, "crew count in the contents block"))

    # 2 — manifest + restore -------------------------------------------------
    old_man = "    hasVault:      !!(d.vault && d.vault.salt && d.vault.verifier)\n  };"
    new_man = "    hasVault:      !!(d.vault && d.vault.salt && d.vault.verifier),\n    crewLists:     Array.isArray(d.crew) ? d.crew.length : null   /* null: no crew section */\n  };"
    edits.append((old_man, new_man, "manifest knows the crew section"))

    old_mt = line_with(text, "    + (m.hasVault      ? ")
    new_mt = old_mt + "\n    + (m.crewLists!=null ? n(m.crewLists,'crew list') : '')"
    edits.append((old_mt, new_mt, "manifest text lists crew lists"))

    old_conf = r"""      +'\nRestore REPLACES everything currently in the app with what is listed above.\n'"""
    new_conf = old_conf + r"""
      +(m.crewLists==null ? 'This backup has no crew lists, so the crew lists on this phone stay as they are.\n' : '')"""
    edits.append((old_conf, new_conf, "confirm says what happens to crew lists"))

    old_pre = "  const m=backupManifest(d);\n  if(!confirm(backupManifestText(m)"
    new_pre = """  /* CREW — the crew section is judged whole before anything is shown. One
     record that does not check out refuses the entire restore: nothing on
     this device is touched (spec §6 rule 1, no partial imports). */
  let crewIn=null;
  if(d.crew!=null){
    const cj=crewJudgeAll(d.crew);
    if(!cj.ok){
      reset();
      alert('Could not restore: the crew lists in this file don\\u2019t check out ('+cj.why+').\\n\\n'
           +'Nothing on this device was touched.');
      return;
    }
    crewIn=cj.recs;
  }
""" + old_pre
    edits.append((old_pre, new_pre, "judge the crew section before the confirm"))

    old_commit = "      await photoPut(rec);\n    }\n    reset();\n    go('houses');"
    new_commit = """      await photoPut(rec);
    }
    /* CREW — replaced only when the file carries crew lists, in one
       transaction; otherwise the ones on this phone stay (rule 8). */
    if(crewIn){ await crewReplaceAll(crewIn); await crewLoad(); }
    reset();
    go('houses');"""
    edits.append((old_commit, new_commit, "restore replaces the crew store"))

    # 3 — help copy -----------------------------------------------------------
    old_help = "  'share':'This builds a file another Notebuilt user can import."
    new_help = """  'crew':'Crew lists come from a boss who uses Notebuilt Pro. They text you a link; tap it, open it in Chrome, and your tasks for the day land here, at the top of To Do. Nothing counts toward the free project limit.\\n\\nI keep them on this phone only. No account, no server: the list is packed into the link itself, in the part after the #, and browsers never send that part anywhere. So a list is exactly as private as the text that carried it.\\n\\nOne honest catch in this first version: whoever has your link can open it as you. There are no sign-ins yet, so it runs on trust. Keep your links to yourself.',

  'crewstatus':'Tap the round mark to mark a task done, and again to undo it. Tap the task itself to say you are waiting on something. The quick picks fill in a note you can change or add to.\\n\\nIf your boss changes the list and sends it again, everything you have checked off and every note you wrote stays as it is. A task that was cancelled or moved to someone else stays on your screen, struck through, so you can see what changed.',

  'crewreport':'Send report puts every task on this list (done, waiting and open, with your notes) into one link and opens your phone\\u2019s share sheet, so you can text it to your boss. Send it as often as you like: each report covers every task, so a later one just brings your boss up to date.\\n\\nIf it is too long for one text, it goes in parts. Send every part. "Changes not sent" counts what you have changed since your last full report.',

""" + old_help
    edits.append((old_help, new_help, "help copy for the crew screens"))

    # 4 — privacy ---------------------------------------------------------------
    old_priv = """    <div class="sec-head"><span class="label">Your data, your control</span><span class="rule"></span></div>"""
    new_priv = """    <div class="sec-head"><span class="label">Crew lists</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">If a boss sends you a crew list from Notebuilt Pro, it comes as a link in a text message. The list is packed into the part of the link after the <b style="color:var(--paper)">#</b>, and browsers never send that part to any server. GitHub Pages, which serves this app, never sees it, and neither do I. A crew list is exactly as private as the text that carried it.<br><br>It's stored on this phone, in its own storage, and it goes into your backups. In this version the vault doesn't cover crew lists. When you send a report, it goes back the same way: a link, handed to your phone's share sheet. Notebuilt doesn't send anything by itself.</div>

""" + old_priv
    edits.append((old_priv, new_priv, "privacy page: crew lists"))

    # 5 — newer-data card ----------------------------------------------------
    old_card = "${(schemaFromFuture||housesFromFuture)?`<div class=\"card\" style=\"border:1px solid var(--brass);margin-bottom:14px\">"
    new_card = "${(schemaFromFuture||housesFromFuture||crewFromFuture)?`<div class=\"card\" style=\"border:1px solid var(--brass);margin-bottom:14px\">"
    edits.append((old_card, new_card, "newer-data card counts crew lists"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    imp = working[working.find("async function importData("):working.find("APP LOCK (PIN, hashed")]
    j, c = imp.find("crewJudgeAll(d.crew)"), imp.find("if(!confirm(backupManifestText(m)")
    if j < 0 or c < 0 or j > c:
        fail("the crew section is not judged before the restore confirm.")
    if imp.find("crewReplaceAll(crewIn)") < imp.find("if(!confirm(backupManifestText(m)"):
        fail("the crew store is replaced before the person confirmed.")
    if "crew: crewDump," not in working:
        fail("the crew section is missing from the export.")

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
