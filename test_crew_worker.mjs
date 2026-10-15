// test_crew_worker.mjs — real-browser gate for the crew worker side (th_nbp_stage4, spec §8/§9).
// Headless Google Chrome over raw CDP (Node's built-in WebSocket), no deps.
// Usage: node test_crew_worker.mjs <dir containing the NEW index.html> [old git ref, default HEAD]
//
// One origin, so every page shares storage the way one phone does:
//   /index.html    the build under test (the worker's Notebuilt)
//   /boss.html     the BOSS: the real platform component, nothing else. It builds
//                  Pro's stored list, cuts each worker's slice and splits it into
//                  links exactly as Pro does (sliceFor → split), and merges the
//                  reports back with mergeReport, as Pro's board will.
//   /old.html      the build before crew tasks, from git
//   /m-*.html      mutants — each must be caught, or the check is not a gate.
// 127.0.0.1 EVERYWHERE, never "localhost" — the Aug 13 trap.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = process.argv[2];
const OLD_REF = process.argv[3] || 'HEAD';
const REPO = dirname(fileURLToPath(import.meta.url));
const CANON = join(REPO, '..', '..', 'platform', 'crew_task.js');
const HOST = '127.0.0.1', HTTP = 8767, DBG = 9335;
const ORIGIN = `http://${HOST}:${HTTP}`;
const APP = `${ORIGIN}/index.html`, BOSS = `${ORIGIN}/boss.html`, OLD = `${ORIGIN}/old.html`;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0; const failures = [];
function ok(cond, name, detail) {
  if (cond) { pass++; console.log('  PASS', name); }
  else { fail++; failures.push(name); console.log('  FAIL', name, detail !== undefined ? '→ ' + JSON.stringify(detail).slice(0, 400) : ''); }
}

// ---------- the builds ----------
const serveDir = mkdtempSync(join(tmpdir(), 'nb-crew-srv-'));
const html = readFileSync(join(SRC, 'index.html'), 'utf8');
const oldHtml = execFileSync('git', ['-C', REPO, 'show', `${OLD_REF}:index.html`], { encoding: 'utf8', maxBuffer: 64 << 20 });
if (!html.includes("const CREW_DB='notebuilt-crew'")) { console.error('ABORT: build under test has no crew worker side'); process.exit(2); }
if (oldHtml.includes('EGS-SHARED:crew-task')) { console.error(`ABORT: ${OLD_REF} already has crew tasks`); process.exit(2); }
writeFileSync(join(serveDir, 'index.html'), html);
writeFileSync(join(serveDir, 'old.html'), oldHtml);
writeFileSync(join(serveDir, 'crew_task.js'), readFileSync(CANON, 'utf8'));
writeFileSync(join(serveDir, 'boss.html'), '<!doctype html><meta charset="utf-8"><title>boss</title><script src="crew_task.js"></script><script>window.navState=()=>1</script>');
const mutate = (name, from, to) => {
  if (!html.includes(from)) { console.error(`ABORT: mutant ${name} anchor missing`); process.exit(2); }
  writeFileSync(join(serveDir, `m-${name}.html`), html.replace(from, to));
};
// Not a "skip the strip" mutant: the router's own replaceState at boot strips any
// hash it does not know, so the payload leaves history twice over. What CAN go
// wrong is a capture that misses the hash — the list would be silently lost.
mutate('nocapture', "  if(typeof h!=='string' || h.indexOf('#crew=')!==0) return;", "  return;");
mutate('nopin', "window.addEventListener('hashchange',", "setTimeout(()=>crewOnShell(),300);\nwindow.addEventListener('hashchange',");
mutate('nojudge', 'const cj=crewJudgeAll(d.crew);', 'const cj={ok:true, recs:d.crew};');

// ---------- processes ----------
try { await fetch(`http://${HOST}:${DBG}/json/version`); console.error(`ABORT: something already listens on ${HOST}:${DBG}`); process.exit(2); } catch (e) {}
const server = spawn('python3', ['-m', 'http.server', String(HTTP), '--bind', HOST, '--directory', serveDir], { stdio: 'ignore' });
const profile = mkdtempSync(join(tmpdir(), 'nb-crew-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--remote-debugging-address=${HOST}`,
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
function cleanup() {
  try { chrome.kill(); } catch (e) {} try { server.kill(); } catch (e) {}
  try { rmSync(profile, { recursive: true, force: true }); } catch (e) {} try { rmSync(serveDir, { recursive: true, force: true }); } catch (e) {}
}
process.on('exit', cleanup);
let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) { try { wsUrl = (await (await fetch(`http://${HOST}:${DBG}/json/version`)).json()).webSocketDebuggerUrl; } catch (e) { await sleep(100); } }
for (let i = 0; i < 50; i++) { try { await fetch(APP); break; } catch (e) { await sleep(100); } }

// ---------- CDP ----------
const ws = new WebSocket(wsUrl);
await new Promise(r => ws.addEventListener('open', r));
let mid = 0; const pend = new Map(); const handlers = new Set();
ws.addEventListener('message', e => {
  const m = JSON.parse(e.data);
  if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  else handlers.forEach(h => h(m));
});
const send = (method, params = {}, sessionId) => { const id = ++mid; ws.send(JSON.stringify({ id, method, params, sessionId })); return new Promise((res, rej) => pend.set(id, { res, rej })); };
async function openPage(url, { wait = true } = {}) {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const p = { targetId, sessionId, dialogs: [], errors: [] };
  p.send = (m, pa) => send(m, pa, sessionId);
  const h = m => {
    if (m.sessionId !== sessionId) return;
    if (m.method === 'Page.javascriptDialogOpening') { p.dialogs.push(m.params.message); p.send('Page.handleJavaScriptDialog', { accept: true }); }
    if (m.method === 'Runtime.exceptionThrown') p.errors.push((m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split('\n')[0]);
  };
  handlers.add(h); p.detach = () => handlers.delete(h);
  await p.send('Page.enable'); await p.send('Runtime.enable');
  p.ev = async expr => {
    const r = await p.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  await p.send('Page.navigate', { url });
  if (wait) await ready(p);
  return p;
}
async function ready(p) {
  for (let i = 0; i < 100; i++) { try { if (await p.ev(`document.readyState==='complete' && typeof navState==='function'`)) break; } catch (e) {} await sleep(100); }
  await sleep(200);
}
async function closePage(p) { p.detach(); await send('Target.closeTarget', { targetId: p.targetId }); await sleep(150); }
const until = async (p, expr, ms = 4000) => { for (let i = 0; i < ms / 50; i++) { try { if (await p.ev(expr)) return true; } catch (e) {} await sleep(50); } return false; };
const crewDump = p => p.ev(`crewAll().then(a=>JSON.stringify(a.sort((x,y)=>x.key<y.key?-1:1)))`);
const sheetText = p => p.ev(`document.getElementById('modal-root').innerText`);
const appText = p => p.ev(`document.getElementById('app').innerText`);
const historyHasCrew = async p => (await p.send('Page.getNavigationHistory')).entries.some(e => e.url.includes('#crew='));
const local = link => link.replace('https://notebuilt.ca/', `${ORIGIN}/index.html`);

// ---------- the boss ----------
const boss = await openPage(BOSS);
await boss.ev(`(()=>{
  window.T0=Math.floor(Date.now()/1000)-3600;
  const d=new Date(); window.TODAY=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
  window.JOE=EGSCrew.newId(); window.MARIA=EGSCrew.newId();
  window.mkList=(n,textOf)=>({ f:'egs-crew', v:EGSCrew.VERSION, k:'list', listId:EGSCrew.newId(), issuedAt:T0,
    boss:{id:EGSCrew.newId(),name:'Mike'}, job:{id:EGSCrew.newId(),name:'Oak St reno'}, day:TODAY, mode:'private',
    workers:[{id:JOE,name:'Joe'},{id:MARIA,name:'Maria'}],
    tasks:Array.from({length:n},(_,i)=>({id:(i+1).toString(36), worker:JOE, text:textOf?textOf(i):'Task '+(i+1)+': hang door, unit 20'+i, order:i+1, editedAt:T0, gone:null})) });
  window.sendTo=async(list,sent,wid,now)=>{ const s=EGSCrew.sliceFor(list,wid,sent,now); const sp=await EGSCrew.split(s);
    if(!sp.ok) return {err:sp}; return {links:sp.parts.map(p=>p.link), sent:EGSCrew.recordSend(sent,list,[wid],now)}; };
  window.raw=async wire=>'1'+EGSCrew._wire.b64e(await EGSCrew._wire.deflate(new TextEncoder().encode(JSON.stringify(wire))));
  return true; })()`);
const B = expr => boss.ev(expr);

// Open a list link on the worker phone, as a fresh load. Returns the page once the
// preview (or a refusal) is up.
async function arrive(link, url = null) {
  const p = await openPage(url || local(link));
  await until(p, `!!document.querySelector('#modal-root [data-crew-add],#modal-root [data-crew-ok]')`);
  return p;
}

// ======================================================================
console.log('\n[1] cold arrival, no PIN — preview, Add, the link leaves history');
await B(`(async()=>{ window.L1=mkList(10); const r=await sendTo(L1,{},JOE,T0+60); window.S1=r.sent; window.links1=r.links; return true; })()`);
let links = await B(`links1`);
ok(links.length === 1 && links[0].length <= 700, 'a 10-task private slice is one link under SAFE_LINK_CHARS', links.map(l => l.length));
let p = await arrive(links[0]);
ok(p.errors.length === 0, 'boots without an uncaught error', p.errors);
let st = await sheetText(p);
ok(/Tasks from Mike · Oak St reno · .+ · 10 for you/.test(st), 'preview names boss, job, day and the count', st);
ok(!/waiting on part/.test(st), 'a whole list shows no parts line');
ok(/Chrome/.test(st), 'preview carries the open-in-Chrome line');
ok(await p.ev(`location.hash`) === '#/crew' && !(await historyHasCrew(p)), 'the payload is gone from the address and from history before Add');
ok(await crewDump(p) === '[]', 'nothing is stored before Add');
await p.ev(`document.querySelector('[data-crew-add]').click()`); await until(p, `view.name==='crewlist'`);
let recs = JSON.parse(await crewDump(p));
ok(recs.length === 1 && recs[0].schemaVersion === 1 && recs[0].workerId === await B('JOE'), 'Add stores one record, with its own schemaVersion', recs.map(r => r.key));
ok(!(await historyHasCrew(p)), 'still no #crew= anywhere in history after Add');
await p.ev(`go('todo')`); await sleep(300);
let txt = await appText(p);
ok(/From Mike · Oak St reno/.test(txt) && /0 of 10 done/.test(txt), 'To Do carries the Crew tasks card with progress', txt.slice(0, 300));
ok(await p.ev(`houses.length`) === 0, 'crew lists never become projects (the cap stays out of it)');
const KEY = recs[0].key;
await closePage(p);

console.log('\n[2] PIN set — nothing behind the keypad, preview after unlock');
p = await openPage(APP);
await p.ev(`(async()=>{ settings.pinSalt=randSalt(); settings.pinHash=await sha('1234'+settings.pinSalt); persist.settings(); return true; })()`);
await closePage(p);
await B(`(async()=>{ window.L2=mkList(3); window.links2=(await sendTo(L2,{},JOE,T0+60)).links; return true; })()`);
p = await openPage(local((await B('links2'))[0]));
await sleep(1200);
ok(await p.ev(`!$lock.classList.contains('hidden')`), 'the PIN gate is up');
ok(await p.ev(`document.getElementById('modal-root').innerHTML===''`), 'no preview is drawn behind the keypad');
ok(await p.ev(`location.hash`) === '#/crew' && !(await historyHasCrew(p)), 'the payload left the address before the PIN, too');
for (const d of '1234') { await p.ev(`document.querySelector('#lock [data-k="${d}"]').click()`); await sleep(60); }
ok(await until(p, `!!document.querySelector('#modal-root [data-crew-add]')`), 'after unlock the preview appears');
await p.ev(`document.querySelector('[data-crew-add]').click()`); await until(p, `view.name==='crewlist'`);
ok(JSON.parse(await crewDump(p)).length === 2, 'and Add stores it');
await p.ev(`(async()=>{ settings.pinHash=null; settings.pinSalt=null; persist.settings(); return true; })()`);
await closePage(p);

console.log('\n[2b] mutant: decode before the PIN — must be caught');
p = await openPage(APP);
await p.ev(`(async()=>{ settings.pinSalt=randSalt(); settings.pinHash=await sha('1234'+settings.pinSalt); persist.settings(); return true; })()`);
await closePage(p);
await B(`(async()=>{ window.L2b=mkList(2); window.links2b=(await sendTo(L2b,{},JOE,T0+60)).links; return true; })()`);
p = await openPage(`${ORIGIN}/m-nopin.html` + local((await B('links2b'))[0]).slice(APP.length));
await sleep(1500);
ok(await p.ev(`!$lock.classList.contains('hidden') && document.getElementById('modal-root').innerHTML!==''`), 'mutant draws the preview behind the lock (so [2] would catch it)');
await p.ev(`(async()=>{ settings.pinHash=null; settings.pinSalt=null; persist.settings(); return true; })()`);
await closePage(p);

console.log('\n[3] same-document arrival (link opened in a tab that has the app)');
await B(`(async()=>{ window.L3=mkList(2); window.links3=(await sendTo(L3,{},JOE,T0+60)).links; return true; })()`);
p = await openPage(APP);
await p.ev(`location.hash=${JSON.stringify((await B('links3'))[0].slice('https://notebuilt.ca/'.length))}; true`);
await sleep(300); await ready(p);
ok(await until(p, `!!document.querySelector('#modal-root [data-crew-add]')`), 'hashchange reloads into the preview');
ok(!(await historyHasCrew(p)) || (await p.ev(`location.hash`)) === '#/crew', 'the payload is out of the current entry');
await p.ev(`document.querySelector('[data-crew-cancel]').click()`); await sleep(200);
ok(JSON.parse(await crewDump(p)).length === 2, 'Cancel stores nothing');
await closePage(p);

console.log('\n[4] parts — out of order, twice, then complete (rule 11)');
await B(`(async()=>{ const W='stud joist header sill plate rafter truss shim lintel soffit fascia drywall batten flashing'.split(' ');
  const pad=i=>{ let s=''; while(s.length<150) s+=W[(s.length*7+i*13)%W.length]+(Math.random()*1e6|0)+' '; return ' — '+s.slice(0,150); };
  window.L4=mkList(8,i=>'Unit '+(200+i)+pad(i)); const r=await sendTo(L4,{},JOE,T0+60); window.links4=r.links; return r.links.length; })()`);
links = await B('links4');
ok(links.length >= 2, `a long slice splits into ${links.length} parts`);
p = await arrive(links[1]);
st = await sheetText(p);
ok(/part 2 of \d+, waiting on part/.test(st), 'part 2 first: the preview says which parts are missing', st);
await p.ev(`document.querySelector('[data-crew-add]').click()`); await until(p, `view.name==='crewlist'`);
ok(/isn’t all here yet/.test(await appText(p)), 'the list itself says it is incomplete');
const key4 = await p.ev(`view.param`), before4 = await crewDump(p);
await closePage(p);
p = await arrive(links[1]);
ok(await until(p, `view.name==='crewlist'`) && await crewDump(p) === before4, 'the same part again changes nothing');
await closePage(p);
for (let i = 0; i < links.length; i++) {
  if (i === 1) continue;
  p = await arrive(links[i]);
  await p.ev(`document.querySelector('[data-crew-add]')&&document.querySelector('[data-crew-add]').click()`); await until(p, `view.name==='crewlist'`);
  await closePage(p);
}
p = await openPage(APP); await p.ev(`go('crewlist',${JSON.stringify(key4)})`); await sleep(400);
txt = await appText(p);
ok(!/isn’t all here yet/.test(txt) && (txt.match(/Unit 20\d/g) || []).length === 8, 'every part in: complete, all 8 tasks, no banner', txt.slice(0, 200));
await closePage(p);

console.log('\n[5] the worker checks off; the boss edits and resends; nothing of the worker\'s is lost');
p = await openPage(APP); await p.ev(`go('crewlist',${JSON.stringify(KEY)})`); await sleep(400);
await p.ev(`document.querySelector('[data-crew-punch="1"]').click()`); await sleep(300);
ok(JSON.parse(await crewDump(p)).find(r => r.key === KEY).state['1'].status === 'done', 'one tap marks Done');
await p.ev(`document.querySelector('[data-crew-task="2"]').click()`); await sleep(250);
await p.ev(`document.querySelector('[data-crew-q="Electrician"]').click()`);
ok(await p.ev(`document.querySelector('#crew-note').value`) === 'Waiting on electrician' && await p.ev(`document.querySelector('[data-crew-st="waiting"]').classList.contains('primary')`), 'a quick pick sets Waiting on and fills the note');
await p.ev(`window.__ta=document.querySelector('#crew-note'); __ta.focus(); __ta.setSelectionRange(__ta.value.length,__ta.value.length); true`);
let steady = true;
for (const ch of ' after 2pm') {
  await p.send('Input.insertText', { text: ch }); await sleep(25);
  if (!(await p.ev(`document.activeElement===window.__ta && __ta.isConnected && document.querySelector('#crew-note')===__ta`))) steady = false;
}
ok(steady, 'typing the note keeps the same node and focus on every keystroke (keyboard stays up)');
await p.ev(`document.querySelector('[data-crew-save]').click()`); await sleep(300);
let s2 = JSON.parse(await crewDump(p)).find(r => r.key === KEY).state['2'];
ok(s2.status === 'waiting' && s2.note === 'Waiting on electrician after 2pm', 'Save stores status and note', s2);
await closePage(p);
await B(`(async()=>{ const L=L1; const t=n=>L.tasks.find(x=>x.id===n);
  t('1').text='Hang 6 doors, unit 204 (prehung)'; t('1').editedAt=T0+600;
  t('3').gone='cancelled'; t('3').editedAt=T0+600;
  t('4').worker=MARIA; t('4').editedAt=T0+600;
  L.tasks.push({id:'b', worker:JOE, text:'Sweep out unit 204', order:11, editedAt:T0+600, gone:null});
  const r=await sendTo(L,S1,JOE,T0+700); window.S1=r.sent; window.links5=r.links; return true; })()`);
p = await arrive((await B('links5'))[0]);
st = await sheetText(p);
ok(/Update to your crew list/.test(st) && /stay as they are/.test(st), 'a resend previews as an update that keeps your check-offs');
await p.ev(`document.querySelector('[data-crew-add]').click()`); await until(p, `view.name==='crewlist'`);
let r5 = JSON.parse(await crewDump(p)).find(r => r.key === KEY);
ok(r5.state['1'].status === 'done' && r5.state['2'].note === 'Waiting on electrician after 2pm', 'statuses and notes survive the resend', r5.state);
txt = await appText(p);
ok(/prehung/.test(txt) && /Sweep out unit 204/.test(txt), 'the boss\'s edit and new task arrive');
ok(/Cancelled/.test(txt) && /Moved to someone else/.test(txt), 'cancelled and reassigned tasks show as such');
await closePage(p);

console.log('\n[6] refusals — each one whole, nothing stored');
const reasons = JSON.parse(await B(`JSON.stringify(EGSCrew.REASONS)`));
const hostile = JSON.parse(await B(`(async()=>{
  const base=EGSCrew.sliceFor(L1,JOE,S1,T0+800), w=()=>EGSCrew._wire.toWire(JSON.parse(JSON.stringify(base)));
  const out={};
  { const a=w(); a[9][0][2]='<img src=x onerror=alert(1)>'; out.markup=await raw(a); }
  { const a=w(); a[0]=2; out.older=await raw(a); }
  { const a=w(); a[8][0][0]='tooLongId123'; out.badid=await raw(a); }
  { const a=w(); a[9][0][2]='x'.repeat(300000); out.bomb=await raw(a); }
  { const a=w(); a[7]=1; out.crewmode=await raw(a); }
  { const m=JSON.parse(JSON.stringify(L1)); m.job.id=EGSCrew.newId(); out.mismatch=(await sendTo(m,{},JOE,T0+900)).links[0].split('#crew=')[1]; }
  out.report=(await EGSCrew.encode(EGSCrew.buildReport(L1,JOE,{},T0+900))).value;
  out.newer='2'+(await raw(w())).slice(1);
  out.damaged='1AAAAAAA';
  return JSON.stringify(out); })()`));
const expect = { markup: reasons.invalid, older: reasons.older, badid: reasons.invalid, bomb: reasons.too_big, crewmode: 'whole-crew list',
  mismatch: reasons.list_mismatch, report: reasons.wrong_kind, newer: reasons.newer, damaged: reasons.damaged };
p = await openPage(APP); const store6 = await crewDump(p); await closePage(p);
for (const [k, payload] of Object.entries(hostile)) {
  p = await arrive(null, `${APP}#crew=${payload}`);
  st = await sheetText(p);
  ok(st.includes(expect[k]) && st.includes('Nothing on this phone was changed') && await crewDump(p) === store6 && !(await historyHasCrew(p)),
     `${k}: refused with its sentence, store byte-identical`, st.slice(0, 160));
  await closePage(p);
}

console.log('\n[7] report — what the boss receives');
p = await openPage(APP);
await p.ev(`window.__shared=[]; navigator.share=async d=>{ __shared.push(d.text); }; go('crewlist',${JSON.stringify(KEY)}); true`); await sleep(400);
await p.ev(`document.querySelector('[data-crew-report]').click()`); await until(p, `__shared.length===1`);
let shared = await p.ev(`__shared[0]`);
const [line, link] = shared.split('\n');
ok(/^Joe · Oak St reno · \w+: 1 done, 1 waiting, 7 open$/.test(line), 'one-line summary', line);
ok(link.startsWith('https://pro.notebuilt.ca/#report=') && link.length <= 700, 'the link goes to Pro and fits a text', link.length);
const merged = JSON.parse(await B(`(async()=>{ const d=await EGSCrew.decode(EGSCrew.fromHash(${JSON.stringify('#' + link.split('#')[1])},'report'),'report');
  if(!d.ok) return JSON.stringify(d); const m=EGSCrew.mergeReport(L1,S1,{},d.value); return JSON.stringify(m); })()`));
ok(merged.ok && merged.received[await B('JOE')].tasks['1'].status === 'done' && merged.received[await B('JOE')].tasks['2'].note === 'Waiting on electrician after 2pm',
   'the boss side decodes it and mergeReport applies done + waiting with the note', merged);
txt = await appText(p);
ok(/Last full report sent/.test(txt) && !/not sent/.test(txt), 'the list says when the report went out, nothing unsent');
await p.ev(`document.querySelector('[data-crew-punch="5"]').click()`); await sleep(300);
ok(/1 change not sent/.test(await appText(p)), 'a change after the report counts as not sent');
// no share sheet → clipboard
await p.ev(`window.__clip=null; delete navigator.share; navigator.share=undefined; navigator.clipboard.writeText=async t=>{ __clip=t; }; true`);
await p.ev(`document.querySelector('[data-crew-report]').click()`); await until(p, `__clip!==null`);
ok((await p.ev(`__clip`)).includes('#report='), 'with no share sheet the report goes to the clipboard');
await closePage(p);

console.log('\n[8] a long report splits; a note that cannot fit is refused by name (rule 12)');
p = await openPage(APP);
await p.ev(`(async()=>{ const rec=crewByKey(${JSON.stringify(KEY)}); let st=rec.state;
  const W='framing crew east wall electrician inspector plumber lumber drop delivery permit'.split(' ');
  const note=i=>{ let s='Waiting on '; while(s.length<280) s+=W[(s.length*5+i.charCodeAt(0))%W.length]+(Math.random()*1e6|0)+' '; return s.slice(0,280); };
  for(const t of EGSCrew.liveTasksFor(rec.list,rec.workerId)) st=EGSCrew.setStatus(st,t.id,'waiting',note(t.id),Date.now()/1000);
  await crewSave(Object.assign({},rec,{state:st})); window.__shared=[]; navigator.share=async d=>{ __shared.push(d.text); };
  go('crewlist',${JSON.stringify(KEY)}); return true; })()`); await sleep(400);
await p.ev(`document.querySelector('[data-crew-report]').click()`); await until(p, `!!document.querySelector('[data-crew-part]')`);
const nParts = await p.ev(`document.querySelectorAll('[data-crew-part]').length`);
ok(nParts >= 2, `ten 280-character notes go out as ${nParts} parts`);
await p.ev(`document.querySelector('[data-crew-part="1"]').click()`); await until(p, `__shared.length===1`); await sleep(200);
let rep = JSON.parse(await crewDump(p)).find(r => r.key === KEY).report;
ok(rep.send.ticked.join() === '1' && /1 of \d+ sent/.test(await sheetText(p)), 'part 1 ticked, the report not yet counted as sent', rep);
for (let i = 2; i <= nParts; i++) { await p.ev(`document.querySelector('[data-crew-part="${i}"]').click()`); await until(p, `__shared.length===${i}`); await sleep(200); }
rep = JSON.parse(await crewDump(p)).find(r => r.key === KEY).report;
ok(rep.send.ticked.length === nParts && rep.lastSentAt > 0, 'every part ticked: the report counts as sent');
const partsOk = JSON.parse(await B(`(async()=>{ let rec={}; for(const t of ${JSON.stringify(await p.ev('__shared'))}){ const l=t.split('\\n')[1];
  const d=await EGSCrew.decode(EGSCrew.fromHash('#'+l.split('#')[1],'report'),'report'); if(!d.ok) return JSON.stringify(d);
  const m=EGSCrew.mergeReport(L1,S1,rec,d.value); if(!m.ok) return JSON.stringify(m); rec=m.received; }
  const r=rec[JOE]; return JSON.stringify({complete:EGSCrew.partsStatus(r.send).complete, n:Object.keys(r.tasks).length}); })()`));
ok(partsOk.complete === true && partsOk.n === JSON.parse(await crewDump(p)).find(r => r.key === KEY).list.tasks.filter(t => !t.gone && t.worker === r5.workerId).length, 'the boss merges every part into a complete report, every live task in it', partsOk);
await p.ev(`(async()=>{ const rec=crewByKey(${JSON.stringify(KEY)}); const rare=String.fromCodePoint(...Array.from({length:280},(_,i)=>0x20000+i*37));
  await crewSave(Object.assign({},rec,{state:EGSCrew.setStatus(rec.state,'2','waiting',rare,Date.now()/1000)})); closeSheet(); render(); return true; })()`);
await p.ev(`document.querySelector('[data-crew-report]').click()`); await until(p, `!!document.querySelector('[data-crew-ok]')`);
st = await sheetText(p);
ok(/note on one task is too long/.test(st) && await p.ev(`!!document.querySelector('[data-crew-fix]')`), 'refused before any share sheet, naming the note, with a way to fix it', st.slice(0, 160));
await p.ev(`document.querySelector('[data-crew-fix]').click()`); await sleep(250);
ok(await p.ev(`!!document.querySelector('#crew-note')`), '"Edit that note" opens that task');
await p.ev(`(async()=>{ const rec=crewByKey(${JSON.stringify(KEY)}); await crewSave(Object.assign({},rec,{state:EGSCrew.setStatus(rec.state,'2','waiting','Waiting on electrician',Date.now()/1000)})); closeSheet(); return true; })()`);
await closePage(p);

console.log('\n[9] backup — crew lists ride along; restore is whole or nothing');
p = await openPage(APP);
await p.ev(`(async()=>{ const c=document.createElement('canvas'); c.width=c.height=16; c.getContext('2d').fillRect(0,0,9,9);
  const b=await new Promise(r=>c.toBlob(r,'image/jpeg')); await photoPut({id:'ph1',blob:b,houseId:'h',createdAt:1});
  window.__phBytes=Array.from(new Uint8Array(await b.arrayBuffer())).join(); return true; })()`);
const phBytes = await p.ev(`__phBytes`);
const crewBefore = await crewDump(p);
await p.ev(`(()=>{ const o=URL.createObjectURL; URL.createObjectURL=b=>{ window.__blob=b; return o.call(URL,b); }; return true; })()`);
await p.ev(`exportData().then(()=>true)`); await sleep(500);
const dump = JSON.parse(await p.ev(`__blob.text()`));
ok(Array.isArray(dump.crew) && dump.crew.length === JSON.parse(crewBefore).length && dump.contents.crewLists === dump.crew.length, 'the backup carries every crew list and counts them');
const feed = (pg, obj) => pg.ev(`(async()=>{ const f=new File([${JSON.stringify(JSON.stringify(obj))}],'b.json',{type:'application/json'}); await importData({target:{files:[f],value:''}}); return true; })()`);
await feed(p, dump); await sleep(700);
ok(await crewDump(p) === crewBefore, 'restore round-trip: the crew store is byte-identical');
ok(p.dialogs.some(d => /\d+ crew lists?/.test(d)), 'the restore confirm lists the crew lists');
const noCrew = JSON.parse(JSON.stringify(dump)); delete noCrew.crew; delete noCrew.contents.crewLists;
p.dialogs.length = 0;
await feed(p, noCrew); await sleep(700);
ok(await crewDump(p) === crewBefore && p.dialogs.some(d => /no crew lists, so the crew lists on this phone stay/.test(d)), 'a backup without crew lists leaves them as they are, and says so');
const evil = JSON.parse(JSON.stringify(dump)); evil.crew[0].list.tasks[0].text = '<script>alert(1)</script>'; evil.houses = [{ id: 'zz', name: 'SHOULD-NOT-LAND', status: 'active', specs: [], photos: [] }];
p.dialogs.length = 0;
const housesBefore = await p.ev(`JSON.stringify(houses)`);
await feed(p, evil); await sleep(500);
ok(p.dialogs.some(d => /crew lists in this file don.t check out/.test(d)) && await crewDump(p) === crewBefore && await p.ev(`JSON.stringify(houses)`) === housesBefore,
   'one hostile crew record refuses the whole restore — nothing touched', p.dialogs);
ok(await p.ev(`new Promise(r=>{ const q=indexedDB.open('notebuilt'); q.onsuccess=()=>{ const v=q.result.version; q.result.close(); r(v); }; })`) === 1, 'the photos database is still version 1');
ok(await p.ev(`photoGet('ph1').then(async x=>Array.from(new Uint8Array(await x.blob.arrayBuffer())).join())`) === phBytes, 'photo bytes identical after all of it');
await closePage(p);
p = await openPage(`${ORIGIN}/m-nojudge.html`);
await feed(p, evil); await sleep(700);
ok(/SHOULD-NOT-LAND/.test(await p.ev(`JSON.stringify(houses)`)), 'mutant without the crew judge lets the hostile file land (so [9] would catch it)');
await feed(p, dump); await sleep(700);
await closePage(p);

console.log('\n[10] the cap, the older build, cold restore, 320px');
p = await openPage(APP);
await p.ev(`(()=>{ for(let i=0;i<3;i++) houses.push({id:'cap'+i,name:'Cap '+i,category:'construction',status:'active',specs:[],photos:[],cover:null,notes:'',createdAt:1,updatedAt:1}); persist.houses(); return true; })()`);
ok(await p.ev(`!unlockCanCreateProject()`), 'three projects: the free cap is reached');
const housesAtCap = await p.ev(`JSON.stringify(houses)`);
await closePage(p);
await B(`(async()=>{ window.L10=mkList(2); window.links10=(await sendTo(L10,{},JOE,T0+60)).links; return true; })()`);
p = await arrive((await B('links10'))[0]);
await p.ev(`document.querySelector('[data-crew-add]').click()`);
ok(await until(p, `view.name==='crewlist'`) && await p.ev(`JSON.stringify(houses)`) === housesAtCap, 'a crew list still imports at the cap, and the projects do not move');
const key10 = await p.ev(`view.param`);
await closePage(p);
p = await openPage(OLD);
ok(p.errors.length === 0 && await p.ev(`photoGet('ph1').then(x=>!!x)`), 'the build before crew tasks boots on this data and its photos still open');
await closePage(p);
p = await openPage(`${ORIGIN}/old.html#crew=${hostile.damaged}`);
ok(p.errors.length === 0 && await p.ev(`view.name`) === 'todo', 'the older build sends a crew link to To Do without breaking');
await closePage(p);
p = await openPage(APP); await p.ev(`go('crewlist',${JSON.stringify(key10)})`); await sleep(400); await closePage(p);
p = await openPage(APP); await sleep(400);
ok(await p.ev(`view.name`) === 'crewlist' && await p.ev(`view.param`) === key10 && /Your tasks/i.test(await appText(p)), 'cold open after process death returns to the crew list',
   { v: await p.ev(`view.name`), prm: await p.ev(`view.param`), key10, last: await p.ev(`localStorage.getItem('notebuilt.lastView')`), hash: await p.ev(`location.hash`) });
await p.ev(`document.querySelector('#app [data-back]').click()`); await sleep(500);
ok(await p.ev(`view.name`) === 'todo', 'back from it lands on To Do');
await p.send('Emulation.setDeviceMetricsOverride', { width: 320, height: 640, deviceScaleFactor: 2, mobile: true });
for (const [v, prm] of [['todo', null], ['crew', null], ['crewlist', KEY]]) {
  await p.ev(`go(${JSON.stringify(v)},${JSON.stringify(prm)})`); await sleep(350);
  ok(await p.ev(`document.documentElement.scrollWidth<=320`), `no sideways scroll at 320px: ${v}`, await p.ev(`document.documentElement.scrollWidth`));
}
await p.ev(`document.querySelector('[data-crew-task="2"]').click()`); await sleep(250);
ok(await p.ev(`document.documentElement.scrollWidth<=320 && document.querySelector('.sheet').scrollWidth<=document.querySelector('.sheet').clientWidth`), 'the status sheet fits at 320px');
await p.ev(`closeSheet(); true`); await sleep(150);
for (const mode of ['install', 'backup']) {
  await p.ev(mode === 'install' ? `installPromptShown=false; showInstallBanner('android'); true` : `showDataSafetyBanner(true,true); true`); await sleep(200);
  const geo = await p.ev(`(()=>{ const b=document.getElementById(${JSON.stringify(mode + '-banner')}).getBoundingClientRect(), s=document.querySelector('.crew-send').getBoundingClientRect();
    return {sendBottom:s.bottom, bannerTop:b.top}; })()`);
  ok(geo.sendBottom <= geo.bannerTop, `Send report sits above the ${mode} banner, never under it`, geo);
  await p.ev(`window.scrollTo(0, document.documentElement.scrollHeight); true`); await sleep(150);
  const last = await p.ev(`(()=>{ const c=[...document.querySelectorAll('#app .card.task')].pop().getBoundingClientRect(), s=document.querySelector('.crew-send').getBoundingClientRect(); return {cardBottom:c.bottom, sendTop:s.top}; })()`);
  ok(last.cardBottom <= last.sendTop, `with the ${mode} banner up, the last task still scrolls clear of the button`, last);
  await p.ev(`document.getElementById(${JSON.stringify(mode + '-banner')}).remove(); true`); await sleep(150);
}
ok(await p.ev(`document.querySelector('.crew-send').style.bottom==='' && document.getElementById('app').style.paddingBottom===''`), 'with the banner gone, Send report and the page go back to their places');
await closePage(p);

console.log('\n[11] mutant: a capture that misses the hash — must be caught');
await B(`(async()=>{ window.L11=mkList(1); window.links11=(await sendTo(L11,{},JOE,T0+60)).links; return true; })()`);
p = await arrive(null, `${ORIGIN}/m-nocapture.html#crew=` + (await B('links11'))[0].split('#crew=')[1]);
ok(await p.ev(`!document.querySelector('#modal-root [data-crew-add]')`) && !(await historyHasCrew(p)), 'mutant silently drops the list (so [1] would catch it)');
await closePage(p);

ws.close();
console.log(`\n${pass} passed, ${fail} failed`);
if (fail) console.log('FAILED:\n  ' + failures.join('\n  '));
cleanup(); process.exit(fail ? 1 : 0);
