#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — crew tasks, worker side, chunk 4 of 5: Send report
(th_nbp_stage4, spec §8 Screens, §5, §6 rule 12)
Run from the same folder as index.html, after chunks 1-3:
    python3 fix_crew4_report.py

1. A report is a full snapshot of this worker's live tasks, every time
   (EGSCrew.buildReport), measured and split BEFORE any share sheet opens
   (EGSCrew.split). What cannot fit a link is refused here, on the sending
   phone, naming its cause — a note too long is named and one tap opens it
   (rule 12). Nothing is ever found to be too long on arrival.
2. One part: the share sheet, with a one-line summary and the link —
   "Joe · Oak St reno · Mon: 7 done, 2 waiting, 1 open". No share sheet:
   the clipboard. No clipboard: the text on screen with a Copy button.
3. Several parts: one button per part, "Send report, part 1 of 2", each
   ticked as it goes. The report counts as sent only when every part is.
4. What the list screen then says: when the last report went out, how many
   changes have not been sent, and a half-sent report as half-sent.

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
MARKER = "async function crewSendReport("


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


REPORT = r"""
/* ---------- CREW — send report (spec §8, rule 12) ---------- */
function crewWeekday(day){
  const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(day||''); if(!m) return day||'';
  return new Date(+m[1],+m[2]-1,+m[3]).toLocaleDateString(undefined,{weekday:'short'});
}
/* Share, then clipboard, then the text on screen — there is always a way to
   get it out. Resolves true once it has left (shared or copied), false if the
   person backed out. `onManual` is called when they confirm a hand copy. */
async function crewShareText(text){
  if(navigator.share){
    try{ await navigator.share({ text }); return true; }
    catch(err){ if(err && err.name==='AbortError') return false; }
  }
  try{ await navigator.clipboard.writeText(text); toast('Copied — paste it into a text to your boss'); return true; }
  catch(e){}
  return await new Promise(resolve=>{
    sheet('<h2>Send this to your boss</h2>'
      +'<div class="muted" style="font-size:13px;margin-bottom:10px">Copy it and paste it into a text:</div>'
      +'<div class="card mono" style="font-size:12.5px;word-break:break-all;line-height:1.6;white-space:pre-wrap">'+esc(text)+'</div>'
      +'<button class="btn primary block" data-copy="'+esc(text)+'" style="margin-top:10px">Copy</button>'
      +'<button class="btn block" data-crew-sent-manual style="margin-top:8px">I’ve sent it</button>'
      +'<button class="btn block" data-crew-sent-cancel style="margin-top:8px">Not now</button>','crewreport');
    bindCopyButtons($mr);
    $mr.querySelector('[data-crew-sent-manual]').onclick=()=>{ closeSheet(); resolve(true); };
    $mr.querySelector('[data-crew-sent-cancel]').onclick=()=>{ closeSheet(); resolve(false); };
  });
}
async function crewMarkReport(key, report){
  const rec=crewByKey(key); if(!rec) return;
  try{ await crewSave(Object.assign({}, rec, {report})); }
  catch(e){ toast('Sent, but this phone couldn’t note that it was'); }
}
function crewReportRefused(key, r){
  const canEdit = r.code==='task_too_long' && r.taskId;
  sheet(`<h2>This report can’t go out yet</h2>
    <div class="muted" style="font-size:14px;line-height:1.6;margin-bottom:14px">${esc(r.reason||'This report is too big to send as a link.')}</div>
    ${canEdit?'<button class="btn primary block" data-crew-fix>Edit that note</button>':''}
    <button class="btn block" data-crew-ok style="margin-top:8px">OK</button>`,'crewreport');
  $mr.querySelector('[data-crew-ok]').onclick=closeSheet;
  if(canEdit) $mr.querySelector('[data-crew-fix]').onclick=()=>{ closeSheet(); crewStatusSheet(key, r.taskId); };
}
async function crewSendReport(key){
  const rec=crewByKey(key); if(!rec) return;
  const whole=EGSCrew.buildReport(rec.list, rec.workerId, rec.state, Date.now()/1000);
  _crewBuiltAt[key]=whole.sentAt;
  const sp=await EGSCrew.split(whole);
  if(!sp.ok){ crewReportRefused(key, sp); return; }
  const c=crewCounts(rec), L=rec.list;
  const line=L.workers[0].name+' · '+L.job.name+' · '+crewWeekday(L.day)+': '
    +c.done+' done, '+c.waiting+' waiting, '+c.open+' open';
  const N=sp.parts.length;
  if(N===1){
    if(await crewShareText(line+'\n'+sp.parts[0].link)){
      await crewMarkReport(key, {lastSentAt:whole.sentAt, send:{id:sp.sendId, parts:1, ticked:[1]}});
      toast('Report sent');
    }
    render(); return;
  }
  /* Several links. Each is its own share; each gets its own tick. */
  const ticked=[];
  const draw=()=>{
    sheet(`<h2>Send report</h2>
      <div class="muted" style="font-size:13.5px;line-height:1.55;margin-bottom:12px">This report is too long for one text, so it goes in ${N} parts. Send each one to ${esc(L.boss.name)}.</div>
      ${sp.parts.map(p=>`<button class="btn block${ticked.includes(p.part)?'':' primary'}" data-crew-part="${p.part}" style="margin-bottom:8px;justify-content:space-between">Send report, part ${p.part} of ${N}${ticked.includes(p.part)?' '+I.check:''}</button>`).join('')}
      <div class="muted" style="font-size:12.5px;margin-top:6px" data-crew-ticks>${ticked.length} of ${N} sent</div>`,'crewreport');
    $mr.querySelectorAll('[data-crew-part]').forEach(b=>b.onclick=async()=>{
      const n=+b.dataset.crewPart, p=sp.parts.find(x=>x.part===n);
      if(!(await crewShareText(line+' (part '+n+' of '+N+')\n'+p.link))){ draw(); return; }
      if(!ticked.includes(n)) ticked.push(n);
      ticked.sort((a,b)=>a-b);
      const all=ticked.length===N;
      const cur=crewByKey(key);
      await crewMarkReport(key, {lastSentAt: all?whole.sentAt:(cur?cur.report.lastSentAt:0), send:{id:sp.sendId, parts:N, ticked:ticked.slice()}});
      if(all){ closeSheet(); render(); toast('Report sent — all '+N+' parts'); }
      else draw();
    });
  };
  draw();
}
"""


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ already applied — nothing to do.")
        return
    if "function renderCrewList(" not in text:
        fail("chunk 3 (fix_crew3_screens.py) has not been applied.")

    edits = []
    old_at = "/* Crew lists land a moment after boot (IndexedDB)."
    edits.append((old_at, REPORT.lstrip("\n") + "\n" + old_at, "report code before crewAfterLoad"))

    old_sent = "  const sent=rec.report.lastSentAt?'Last report sent '+crewWhen(rec.report.lastSentAt):'No report sent yet';"
    new_sent = """  const rs=rec.report.send, half=rs && rs.ticked.length<rs.parts;
  const sent=(half?'Report part'+(rs.ticked.length===1?' ':'s ')+rs.ticked.join(', ')+' of '+rs.parts+' sent, not finished · ':'')
    +(rec.report.lastSentAt?'Last full report sent '+crewWhen(rec.report.lastSentAt):'No report sent yet');"""
    edits.append((old_sent, new_sent, "list screen says a half-sent report is half-sent"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1. Nothing written.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    fn = working[working.find("async function crewSendReport("):working.find("/* Crew lists land a moment after boot")]
    if fn.find("EGSCrew.split(") < 0 or fn.find("EGSCrew.split(") > fn.find("crewShareText("):
        fail("the report is not split (and refused) before anything is shared.")
    if "if(!sp.ok){ crewReportRefused(" not in fn:
        fail("a refused split does not stop the send.")

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
