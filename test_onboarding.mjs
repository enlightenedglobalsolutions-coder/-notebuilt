// test_onboarding.mjs — real-browser gate for th_nb_onboarding (the walkthrough,
// the checklist, the sample job, "what's new", New project on To Do).
// Headless Chrome over raw CDP (Node's built-in WebSocket), no deps — the same
// harness as test_houses_schema.mjs.
// Usage: node test_onboarding.mjs <dir with the NEW index.html + sample/> [old git ref, default 69c049f]
//   CHROME=/path/to/chrome overrides the Mac default.
//
// Serves, on ONE origin so they share storage the way an installed phone does
// across an update:
//   /index.html      the build under test, with sample/ beside it
//   /old.html        the live build, read out of git — the downgrade check
//   /m-<name>.html   mutants: each puts one guarded mistake back. The gate must
//                    catch every one, or it is not a gate.
// A second origin serves the same build with NO sample/ folder: the photos
// unreachable case. Taps are real input events at the element's centre, so a
// dimmed area that should block a tap is actually tested, not assumed.
// 127.0.0.1 EVERYWHERE, never "localhost" — the Aug 13 trap.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, writeFileSync, mkdirSync, cpSync, existsSync, readdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = process.argv[2];
const OLD_REF = process.argv[3] || '69c049f';
const REPO = dirname(fileURLToPath(import.meta.url));
const CANON = join(REPO, '..', '..', 'platform', 'guided_tour.js');
const HOST = '127.0.0.1', HTTP = 8768, HTTP2 = 8769, DBG = 9336;
const ORIGIN = `http://${HOST}:${HTTP}`, ORIGIN2 = `http://${HOST}:${HTTP2}`;
const NEW = `${ORIGIN}/index.html`, OLD = `${ORIGIN}/old.html`;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0; const failures = [];
function ok(cond, name, detail) {
  if (cond) { pass++; console.log('  PASS', name); }
  else { fail++; failures.push(name); console.log('  FAIL', name, detail !== undefined ? '→ ' + JSON.stringify(detail) : ''); }
}

// ---------- the builds ----------
if (!SRC || !existsSync(join(SRC, 'index.html'))) { console.error('ABORT: give the folder holding the new index.html'); process.exit(2); }
const html = readFileSync(join(SRC, 'index.html'), 'utf8');
if (!html.includes("const NB_TOUR_KEY='notebuilt.tour';")) { console.error('ABORT: the build under test has no walkthrough'); process.exit(2); }
const SAMPLES = readdirSync(join(SRC, 'sample')).filter(f => /^nb-sample-\d\.jpg$/.test(f)).sort();
if (SAMPLES.length !== 4) { console.error('ABORT: expected sample/nb-sample-1..4.jpg beside index.html'); process.exit(2); }
const oldHtml = execFileSync('git', ['-C', REPO, 'show', `${OLD_REF}:index.html`], { encoding: 'utf8', maxBuffer: 64 << 20 });
if (oldHtml.includes('NB_TOUR_KEY')) { console.error(`ABORT: ${OLD_REF} already has the walkthrough`); process.exit(2); }
const serveDir = mkdtempSync(join(tmpdir(), 'nb-tour-srv-'));
const bareDir = mkdtempSync(join(tmpdir(), 'nb-tour-bare-'));
writeFileSync(join(serveDir, 'index.html'), html);
writeFileSync(join(serveDir, 'old.html'), oldHtml);
cpSync(join(SRC, 'sample'), join(serveDir, 'sample'), { recursive: true });
writeFileSync(join(bareDir, 'index.html'), html);
const mutate = (name, from, to) => {
  if (html.split(from).length !== 2) { console.error(`ABORT: mutant ${name} anchor is not unique`); process.exit(2); }
  writeFileSync(join(serveDir, `m-${name}.html`), html.replace(from, to));
};
mutate('cap', 'nbCountedProjects() < UNLOCK.FREE_PROJECTS', 'houses.length < UNLOCK.FREE_PROJECTS');
mutate('remove', 'tasks=tasks.filter(t=>!(t.houseId===h.id && nbIsSample(t)));', 'tasks=tasks.filter(t=>!(t.houseId===h.id));');
mutate('bootwrite', "async function nbTourOnShell(){\n  if(view.name!=='todo') return;", "async function nbTourOnShell(){\n  nbTourWrite({boot:1});\n  if(view.name!=='todo') return;");
mutate('twice', "  if(have) return Promise.resolve({house:have, photos:(have.photos||[]).length, existed:true});\n  if(_nbSampleLoading && houseById(_nbSampleLoadingId)) return _nbSampleLoading;\n", '');
mutate('protectremove', '  if(h.protected){ vaultDeleteLocked(h.id); return; }\n  if(!confirm(NB_TOUR_COPY.settings.removeAsk)) return;', '  if(!confirm(NB_TOUR_COPY.settings.removeAsk)) return;');
mutate('checkcss', '  // At load, not on first use: a checklist card drawn on a later launch, with\n  // no walkthrough or pointer run first, still needs its stylesheet.\n  css();\n', '');
mutate('fresh', 'if(!s && nbFreshPhone()){ nbTourRun(true); return; }', 'if(!s && !houses.length && !tasks.length && !notes.length && !crewRecs.length){ nbTourRun(true); return; }');
mutate('until', '    until:()=>!(view.name===at.name && view.param===at.param) });', '  });');
const sha = b => createHash('sha256').update(b).digest('hex');
const FILE = Object.fromEntries(SAMPLES.map(f => { const b = readFileSync(join(SRC, 'sample', f)); return [f, { size: b.length, sha: sha(b) }]; }));

// ---------- processes ----------
try { await fetch(`http://${HOST}:${DBG}/json/version`); console.error(`ABORT: something already listens on ${HOST}:${DBG}`); process.exit(2); } catch (e) {}
const server = spawn('python3', ['-m', 'http.server', String(HTTP), '--bind', HOST, '--directory', serveDir], { stdio: 'ignore' });
const server2 = spawn('python3', ['-m', 'http.server', String(HTTP2), '--bind', HOST, '--directory', bareDir], { stdio: 'ignore' });
const profile = mkdtempSync(join(tmpdir(), 'nb-tour-'));
const root = typeof process.getuid === 'function' && process.getuid() === 0;
const chrome = spawn(CHROME, ['--headless=new', ...(root ? ['--no-sandbox'] : []), `--remote-debugging-port=${DBG}`, `--remote-debugging-address=${HOST}`,
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-background-networking', 'about:blank'], { stdio: 'ignore' });
function cleanup() {
  try { chrome.kill(); } catch (e) {} try { server.kill(); } catch (e) {} try { server2.kill(); } catch (e) {}
  for (const d of [profile, serveDir, bareDir]) { try { rmSync(d, { recursive: true, force: true }); } catch (e) {} }
}
process.on('exit', cleanup);
let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) {
  try { wsUrl = (await (await fetch(`http://${HOST}:${DBG}/json/version`)).json()).webSocketDebuggerUrl; } catch (e) { await sleep(100); }
}
for (const o of [NEW, `${ORIGIN2}/index.html`]) for (let i = 0; i < 50; i++) { try { await fetch(o); break; } catch (e) { await sleep(100); } }

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

async function openPage(url, { w = 390, h = 844, theme = 'dark', ready = 'typeof navState==="function"' } = {}) {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const p = { targetId, sessionId, dialogs: [], errors: [], answer: true };
  p.send = (m, pa) => send(m, pa, sessionId);
  const hd = m => {
    if (m.sessionId !== sessionId) return;
    if (m.method === 'Page.javascriptDialogOpening') { p.dialogs.push(m.params.message); p.send('Page.handleJavaScriptDialog', { accept: p.answer }); }
    if (m.method === 'Runtime.exceptionThrown') p.errors.push((m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split('\n')[0]);
  };
  handlers.add(hd); p.detach = () => handlers.delete(hd);
  await p.send('Page.enable'); await p.send('Runtime.enable');
  await p.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 2, mobile: true });
  await p.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: theme }] });
  p.ev = async expr => {
    const r = await p.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  await p.send('Page.navigate', { url });
  for (let i = 0; i < 100; i++) { try { if (await p.ev(`document.readyState==='complete' && ${ready}`)) break; } catch (e) {} await sleep(100); }
  await sleep(150);
  p.tap = async (x, y) => { for (const type of ['mousePressed', 'mouseReleased']) await p.send('Input.dispatchMouseEvent', { type, x, y, button: 'left', clickCount: 1 }); await sleep(60); };
  p.center = sel => p.ev(`(()=>{const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return null; const b=e.getBoundingClientRect(); return {x:b.left+b.width/2, y:b.top+Math.min(b.height/2,20), w:b.width, h:b.height};})()`);
  // A person scrolls a button into view before tapping it; so does this.
  p.tapSel = async sel => {
    const moved = await p.ev(`(()=>{ const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return false; const b=e.getBoundingClientRect();
      if(b.top>=0 && b.bottom<=innerHeight) return false; e.scrollIntoView({block:'center'}); return true; })()`);
    if (moved) await sleep(150);
    const c = await p.center(sel); if (!c) throw new Error('nothing to tap at ' + sel); await p.tap(c.x, c.y); return c; };
  p.type = async text => { for (const ch of text) { await p.send('Input.insertText', { text: ch }); await sleep(20); } };
  return p;
}
async function closePage(p) { p.detach(); await send('Target.closeTarget', { targetId: p.targetId }); await sleep(150); }

// ---------- helpers ----------
const wipe = p => p.ev(`(async()=>{ localStorage.clear();
  for (const n of ['notebuilt','notebuilt-crew']) await new Promise(r=>{ const q=indexedDB.deleteDatabase(n); q.onsuccess=q.onerror=q.onblocked=()=>r(); });
  return true; })()`);
async function boot(url, seed = {}, opts = {}) {
  let p = await openPage(NEW, { ready: 'true' });
  await wipe(p);
  await p.ev(`(()=>{ const s=${JSON.stringify(seed)}; for(const [k,v] of Object.entries(s)) if(v!==null) localStorage.setItem(k, typeof v==='string'?v:JSON.stringify(v)); return true; })()`);
  await closePage(p);
  p = await openPage(url, opts);
  return p;
}
const waitFor = async (p, expr, ms = 6000) => { for (let i = 0; i < ms / 100; i++) { try { if (await p.ev(expr)) return true; } catch (e) {} await sleep(100); } return false; };
const cardTitle = p => p.ev(`(document.querySelector('.egs-tour .egs-tour-title')||{}).textContent||null`);
const atStep = (p, t, ms = 6000) => waitFor(p, `(document.querySelector('.egs-tour .egs-tour-title')||{}).textContent===${JSON.stringify(t)}`, ms);
const pointerTitle = p => p.ev(`(()=>{ const r=document.querySelector('.egs-point'); if(!r||r.style.display==='none') return null; return r.querySelector('.egs-tour-title').textContent; })()`);
const store = p => p.ev(`JSON.stringify(Object.fromEntries(Object.keys(localStorage).filter(k=>k.indexOf('notebuilt.')===0 && k!=='notebuilt.lastView').sort().map(k=>[k,localStorage.getItem(k)])))`);
const tourState = async p => JSON.parse(await p.ev(`localStorage.getItem('notebuilt.tour')||'null'`));
const appText = p => p.ev(`document.getElementById('app').innerText`);
// What a person can actually tap at an element's centre: the topmost element there.
const hitIs = (p, sel) => p.ev(`(()=>{ const t=document.querySelector(${JSON.stringify(sel)}); if(!t) return false; const b=t.getBoundingClientRect();
  const e=document.elementFromPoint(b.left+b.width/2, b.top+Math.min(b.height/2,20)); return !!e && (e===t || t.contains(e)); })()`);
const HIDDEN = `(()=>{ const r=document.querySelector('.egs-tour'); return !r || getComputedStyle(r).display==='none'; })()`;
const EXISTING = {
  'notebuilt.houses': [
    { id: 'hA', name: 'Alder Job', category: 'construction', address: '', status: 'active', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: 1790000000000, updatedAt: 1790000000000, schemaVersion: 2 },
    { id: 'hB', name: 'Birch Job', category: 'construction', address: '', status: 'done', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: 1790000000000, updatedAt: 1790000000001, schemaVersion: 2 }],
  'notebuilt.tasks': [{ id: 'tA', text: 'Hang doors', status: 'todo', houseId: 'hA', createdAt: 1790000000000, updatedAt: 1790000000000, doneAt: null, dueDate: null }],
  'notebuilt.notes': [],
  'notebuilt.settings': { pinHash: null, pinSalt: null, sortHouses: 'updated', units: 'imperial', schemaVersion: 2 },
  'notebuilt.guideNoticeSeen': '1'
};
// A real walk through the tour up to the end, with real taps and real typing.
async function walk(p, name, todo) {
  await p.tapSel('.egs-tour .primary');
  if (!(await atStep(p, 'This is a sample job', 9000))) return 'no open-sample step';
  await p.tapSel('#app [data-tour="sample"]');
  if (!(await atStep(p, 'Everything for the job, in the job'))) return 'no inside step';
  await p.tapSel('.egs-tour .primary');
  if (!(await atStep(p, 'Now start your own'))) return 'no new-project step';
  await sleep(400);
  await p.tapSel('#app [data-new-project]');
  if (!(await waitFor(p, `!!document.getElementById('h-name')`))) return 'no project sheet';
  await p.ev(`(()=>{ const i=document.getElementById('h-name'); i.focus(); window.__n=i; window.__lost=0; return true; })()`);
  for (const ch of name) { await p.send('Input.insertText', { text: ch }); await sleep(25);
    if (!(await p.ev(`document.activeElement===window.__n && document.getElementById('h-name')===window.__n`))) await p.ev(`window.__lost++`); }
  p.nameLost = await p.ev(`window.__lost`);
  await p.tapSel('#h-save');
  if (!(await atStep(p, 'Add one thing that needs doing'))) return 'no add-todo step';
  await sleep(500);
  p.addReach = await hitIs(p, '#app [data-add-house-task]');
  await p.tapSel('#app [data-add-house-task]');
  if (!(await waitFor(p, `!!document.getElementById('t-text')`))) return 'no to-do sheet';
  await p.ev(`document.getElementById('t-text').focus(); true`);
  await p.type(todo);
  await p.tapSel('#t-save');
  if (!(await atStep(p, 'Now check To Do'))) return 'no go-todo step';
  await sleep(400);
  await p.tapSel('#nav [data-nav="todo"]');
  if (!(await atStep(p, 'Every job, one list'))) return 'no one-list step';
  await sleep(300);
  await p.tapSel('.egs-tour .primary');
  if (!(await atStep(p, 'Keep the private stuff private'))) return 'no vault step';
  await p.tapSel('.egs-tour .primary');
  if (!(await atStep(p, 'You’re set'))) return 'no done step';
  await p.tapSel('.egs-tour .primary');
  if (!(await waitFor(p, `!EGSTour.active()`))) return 'tour did not end';
  return 'ok';
}

// ======================================================================
console.log('\n[0] the engine is the platform copy, byte for byte');
const B = '/* EGS-SHARED:guided-tour BEGIN */', E = '/* EGS-SHARED:guided-tour END */';
const lines = html.split('\n');
ok(lines.filter(l => l === B).length === 1 && lines.filter(l => l === E).length === 1, 'marker lines present once each, flush-left');
const block = lines.slice(lines.indexOf(B), lines.indexOf(E) + 1).join('\n') + '\n';
if (existsSync(CANON)) ok(block === readFileSync(CANON, 'utf8'), 'block === platform/guided_tour.js');
else console.log('  SKIP no platform/guided_tour.js at ' + CANON);
ok(!/innerHTML/.test(block), 'the engine builds its layers without innerHTML');

console.log('\n[1] a fresh phone: the welcome card, and nothing written');
let p = await boot(OLD);
await sleep(900);
const oldKeys = await p.ev(`Object.keys(localStorage).filter(k=>k.indexOf('notebuilt.')===0).sort().join()`);
await closePage(p);
p = await boot(NEW);
ok(await atStep(p, 'Welcome to Notebuilt', 4000), 'the welcome card is up');
ok(p.errors.length === 0, 'boots without an uncaught error', p.errors);
const newKeys = await p.ev(`Object.keys(localStorage).filter(k=>k.indexOf('notebuilt.')===0).sort().join()`);
ok(newKeys === oldKeys, `boot writes no key the live build does not (${newKeys})`, { old: oldKeys, new: newKeys });
ok(await p.ev(`photoAll().then(a=>a.length)`) === 0, 'no photos stored before anyone taps');
ok(!(await p.ev(`!!document.querySelector('.nb-hero')`)), 'the landing card stands down behind the walkthrough');
const fab = await p.center('#fab');
await p.tap(fab.x, fab.y); await sleep(300);
ok(await p.ev(`!document.getElementById('modal-root').innerHTML`), 'a tap on the dimmed page does nothing (the + under it stays shut)');

console.log('\n[2] Show me around: the whole walk, real taps, real typing');
await p.ev(`showInstallBanner('android'); true`); await sleep(200);
ok(await p.ev(`getComputedStyle(document.getElementById('install-banner')).display==='none'`), 'an install banner stands aside while the walkthrough runs');
const res = await walk(p, 'Maple St reno', 'Pick up casing');
ok(await p.ev(`getComputedStyle(document.getElementById('install-banner')).display!=='none'`), 'and comes back when it ends');
await p.ev(`dismissInstallBanner(); localStorage.removeItem('notebuilt.installPromptDismissed'); true`);
ok(res === 'ok', 'walked every step to the end', res);
ok(p.nameLost === 0, 'typing in New project: the field kept focus and node identity on every key', p.nameLost);
ok(p.addReach === true, 'Add to-do was scrolled clear of the bottom bar before it was pointed at');
const s1 = await tourState(p);
ok(s1 && s1.firstRun === true && s1.done === true && Array.isArray(s1.seen) && s1.seen.length === 2, 'state: firstRun, done, every what\'s-new marked seen', s1);
const sample = await p.ev(`(async()=>{ const h=nbSampleProject(); if(!h) return null; const recs=await photoAll(); const mine=recs.filter(r=>r.houseId===h.id);
  const out=[]; for(const r of mine){ const b=new Uint8Array(await r.blob.arrayBuffer()); const d=await crypto.subtle.digest('SHA-256', b);
    out.push({id:r.id, size:b.length, sha:[...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,'0')).join('')}); }
  return { h:{ photos:h.photos, cover:h.cover, name:h.name, sample:h.sample, notes:h.notes },
           tasks:tasks.filter(t=>t.houseId===h.id&&t.sample==='nb-sample-1').length, notes:notes.filter(n=>n.houseId===h.id&&n.sample==='nb-sample-1').length, recs:out }; })()`);
ok(sample && sample.h.photos.length === 4 && sample.recs.length === 4, 'sample job: one project, four photos stored', sample && sample.h);
const want = SAMPLES.map(f => FILE[f].sha).sort().join(), got = (sample?.recs || []).map(r => r.sha).sort().join();
ok(want === got, 'the stored photos are the reviewed files, byte for byte');
ok(sample && sample.h.cover === sample.h.photos[3], 'cover is the kitchen (the fourth photo)');
ok(sample && sample.tasks === 5 && sample.notes === 1, 'five to-dos and one note, each marked sample', sample && { t: sample.tasks, n: sample.notes });
ok(await p.ev(`houses.filter(h=>h.sample).length`) === 1, 'exactly one sample');
ok(/Pick up casing/.test(await appText(p)) && /Fireplace surround/.test(await appText(p)), 'To Do lists their to-do and the sample\'s together');
ok(await p.ev(`!!document.querySelector('[data-egs-check-card]')`), 'the checklist is on To Do after the walkthrough');
ok(await p.ev(`document.querySelector('.egs-check-count').textContent`) === '2 of 5', 'checklist: project and to-do ticked by what is in the app', await p.ev(`document.querySelector('.egs-check-count').textContent`));
ok(await p.ev(`nbGuideNoticeDue()`) === false, 'the old i-marks notice does not show on a walkthrough phone');
await p.ev(`maybeShowDataSafetyNudge(); true`); await sleep(300);
ok(await p.ev(`!!document.getElementById('backup-banner')`), 'with a project of their own, the backup nudge does show');
ok(p.errors.length === 0, 'no uncaught error anywhere in the walk', p.errors);

console.log('\n[2b] a later launch: the checklist is still a styled card');
const styled = q => q.ev(`(()=>{ const c=document.querySelector('[data-egs-check-card]'); if(!c) return null;
  const l=document.querySelector('.egs-check-list'), cs=getComputedStyle(c);
  return { css:!!document.getElementById('egs-tour-css'), radius:cs.borderTopLeftRadius, list:getComputedStyle(l).listStyleType, tour:EGSTour.active(), pointing:EGSTour.pointing() }; })()`);
let p2 = await openPage(NEW); await sleep(1200);
const st = await styled(p2);
ok(st && st.css && st.radius !== '0px' && st.list === 'none' && !st.tour && !st.pointing, 'with no walkthrough or pointer run first, the card has its stylesheet', st);
await closePage(p2);
p2 = await openPage(`${ORIGIN}/m-checkcss.html`); await sleep(1200);
const stm = await styled(p2);
ok(stm && !stm.css && stm.list !== 'none', 'mutant: no stylesheet at load leaves it a bare list (so [2b] would catch it)', stm);
await closePage(p2);

console.log('\n[3] the cap: the sample is not one of the free three');
ok(await p.ev(`nbCountedProjects()`) === 1 && await p.ev(`houses.length`) === 2, 'counted 1 of 2 projects');
for (const n of ['Second job', 'Third job']) {
  if (n === 'Third job') ok(await p.ev(`unlockCanCreateProject()`) === true, 'with the sample and two of their own, a third can still be made');
  await p.ev(`go('todo'); true`); await sleep(250);
  await p.ev(`document.querySelector('#app [data-new-project]').click(); true`); await sleep(250);
  await p.ev(`document.getElementById('h-name').value=${JSON.stringify(n)}; document.getElementById('h-save').click(); true`); await sleep(350);
}
ok(await p.ev(`houses.length`) === 4 && await p.ev(`nbCountedProjects()`) === 3, 'with the sample there, three projects of their own were made');
await p.ev(`go('settings'); true`); await sleep(300);
ok(/3 of 3 used/.test(await appText(p)), 'Settings says 3 of 3 used');
await p.ev(`go('todo'); true`); await sleep(250);
await p.ev(`document.querySelector('#app [data-new-project]').click(); true`); await sleep(300);
const pitch = await p.ev(`document.getElementById('modal-root').innerText`);
ok(/Unlock unlimited projects/.test(pitch) && /using all 3/.test(pitch), 'the fourth asks to unlock, and counts three', pitch.slice(0, 120));
await p.ev(`closeSheet(); true`);
const keep = { store: await store(p) };
await closePage(p);

console.log('\n[3m] mutant: the cap counting the sample — must be caught');
p = await openPage(`${ORIGIN}/m-cap.html`);
await p.ev(`(()=>{ const x=houses.find(h=>h.name==='Third job'); houses=houses.filter(h=>h!==x); return true; })()`);   // in memory only: sample + two of their own
ok(await p.ev(`houses.length`) === 3 && !(await p.ev(`unlockCanCreateProject()`)), 'mutant refuses the third of their own (so [3] would catch it)');
await closePage(p);

console.log('\n[4] Settings: remove the sample, load it back, never two');
p = await openPage(NEW);
const mineTask = await p.ev(`(()=>{ const h=nbSampleProject(); const t={id:'tMine',text:'My own note on the sample',status:'todo',houseId:h.id,createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null}; tasks.push(t); persist.tasks(); return h.id; })()`);
await p.ev(`go('settings'); true`); await sleep(300);
ok(/Sample job/.test(await appText(p)) && await p.ev(`!!document.querySelector('[data-sample-remove]')`), 'Getting started shows the sample as loaded, with Remove');
p.answer = false;
await p.tapSel('[data-sample-remove]'); await sleep(300);
ok(p.dialogs.length === 1 && /Remove the sample job/.test(p.dialogs[0]) && await p.ev(`!!nbSampleProject()`), 'Remove asks first, and No keeps everything');
p.answer = true;
await p.tapSel('[data-sample-remove]'); await sleep(900);
ok(!(await p.ev(`!!nbSampleProject()`)), 'Yes removes the project');
ok(await p.ev(`tasks.filter(t=>t.sample).length + notes.filter(n=>n.sample).length`) === 0, 'its own to-dos and note went with it');
ok(await p.ev(`(tasks.find(t=>t.id==='tMine')||{}).houseId`) === null, 'the to-do they added to it stays, unfiled');
ok(await p.ev(`photoAll().then(a=>a.filter(r=>r.houseId===${JSON.stringify(mineTask)}).length)`) === 0, 'its photos are gone from storage');
ok(await p.ev(`houses.length`) === 3 && /Maple St reno/.test(await p.ev(`houses.map(h=>h.name).join()`)), 'their own projects are untouched');
await p.ev(`go('settings'); true`); await sleep(300);
await p.tapSel('[data-sample-load]');
ok(await waitFor(p, `(nbSampleProject()||{photos:[]}).photos.length===4`, 8000), 'Load brings it back, all four photos');
ok(await p.ev(`view.name==='house' && view.param===nbSampleProject().id`), 'and opens it');
await p.ev(`go('settings'); true`); await sleep(300);
await p.ev(`Promise.all([nbSampleLoad(), nbSampleLoad(), nbSampleLoadTap()]).then(()=>true)`); await sleep(500);
ok(await p.ev(`houses.filter(h=>h.sample).length`) === 1, 'three loads at once still make exactly one sample');
ok(p.errors.length === 0, 'no uncaught error', p.errors);
await closePage(p);

console.log('\n[4m] mutants: Remove that takes their to-do, and a second sample — must be caught');
p = await openPage(`${ORIGIN}/m-remove.html`);
await p.ev(`(()=>{ const h=nbSampleProject(); tasks.push({id:'tMine2',text:'x',status:'todo',houseId:h.id,createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null}); persist.tasks(); return true; })()`);
await p.ev(`nbSampleRemove(nbSampleProject().id).then(()=>true)`); await sleep(300);
ok(!(await p.ev(`tasks.some(t=>t.id==='tMine2')`)), 'mutant deletes the to-do they added (so [4] would catch it)');
await closePage(p);
p = await openPage(`${ORIGIN}/m-twice.html`);
await p.ev(`Promise.all([nbSampleLoad(), nbSampleLoad()]).then(()=>true)`); await sleep(400);
ok(await p.ev(`houses.filter(h=>h.sample).length`) > 1, 'mutant makes a second sample (so [4] would catch it)');
await closePage(p);

console.log('\n[5] Skip: no sample, and the landing card carries on');
p = await boot(NEW);
ok(await atStep(p, 'Welcome to Notebuilt', 4000), 'welcome card');
await p.tapSel('.egs-tour .egs-tour-link');
ok(await waitFor(p, `!EGSTour.active()`), 'Skip ends it');
const s5 = await tourState(p);
ok(s5 && s5.firstRun === true && s5.skipped === true && s5.seen.length === 2, 'state: firstRun, skipped, what\'s new seen', s5);
ok(await p.ev(`houses.length+tasks.length+notes.length`) === 0 && await p.ev(`photoAll().then(a=>a.length)`) === 0, 'Skip loads nothing');
ok(await p.ev(`!!document.querySelector('.nb-hero [data-new-project]')`), 'the landing shows Create your first project');
await closePage(p);
p = await openPage(NEW); await sleep(1300);
ok(!(await p.ev(`EGSTour.active()`)) && !(await pointerTitle(p)), 'next open: no welcome, no pointers');
await p.tapSel('.nb-hero [data-tour-start]');
ok(await atStep(p, 'Welcome to Notebuilt', 3000), 'Show me around first starts it again');
await p.tapSel('.egs-tour .egs-tour-x');
ok(await waitFor(p, `!EGSTour.active()`), 'the X ends it');
await p.tapSel('.nb-hero [data-new-project]'); await sleep(300);
ok(await p.ev(`!!document.getElementById('h-name')`), 'Create your first project opens New project');
await closePage(p);

console.log('\n[5m] mutant: writing at boot — must be caught');
p = await boot(`${ORIGIN}/m-bootwrite.html`); await sleep(1200);
ok((await p.ev(`Object.keys(localStorage).filter(k=>k.indexOf('notebuilt.')===0).sort().join()`)) !== oldKeys, 'mutant writes at boot (so [1] would catch it)');
await closePage(p);

console.log('\n[6] a phone that already had Notebuilt: what\'s new, never the welcome');
p = await boot(NEW, EXISTING);
const before = await store(p);
ok(await waitFor(p, `(()=>{ const r=document.querySelector('.egs-point'); return !!r && r.style.display!=='none'; })()`, 4000), 'a pointer shows');
ok(!(await p.ev(`EGSTour.active()`)), 'no welcome card');
ok(await pointerTitle(p) === 'Projects are on To Do now', 'first: Projects are on To Do now');
ok(await p.ev(`(()=>{ const r=document.querySelector('.egs-point .egs-tour-ring').getBoundingClientRect(), t=document.querySelector('#app [data-new-project]').getBoundingClientRect();
  return r.left<=t.left && r.right>=t.right && r.top<=t.top && r.bottom>=t.bottom; })()`), 'its ring is round New project');
ok(await store(p) === before, 'boot wrote nothing to their data');
ok(/Alder Job/.test(await appText(p)) && !/Birch Job/.test(await p.ev(`document.querySelector('.nb-jobs').innerText`)), 'Projects row: active jobs only (Birch is done)');
await p.tapSel('#app [data-go="search"]'); await sleep(300);
ok(await p.ev(`view.name`) === 'search', 'the page under a pointer still works (a real tap opened Search)');
ok(!(await pointerTitle(p)), 'off To Do, the pointer waits out of sight');
await p.ev(`go('todo'); true`);
ok(await waitFor(p, `(()=>{ const r=document.querySelector('.egs-point'); return !!r && r.style.display!=='none'; })()`), 'back on To Do, it is there again');
ok(await store(p) === before, 'still nothing written to their data');
await p.tapSel('.egs-point .primary');
ok(await waitFor(p, `(document.querySelector('.egs-point .egs-tour-title')||{}).textContent==='New in Settings: Getting started'`), 'second: Getting started in Settings');
await sleep(500);
ok(await p.ev(`!!document.getElementById('backup-banner')`) && !(await pointerTitle(p)), 'while the backup banner covers Settings, the pointer waits out of sight');
await p.tapSel('#backup-x');
ok(await waitFor(p, `(()=>{ const r=document.querySelector('.egs-point'); return !!r && r.style.display!=='none'; })()`), 'banner dismissed: the pointer shows');
ok(await hitIs(p, '#nav [data-nav="settings"]'), 'and what it points at can be tapped');
await p.tapSel('.egs-point .primary'); await sleep(300);
ok(!(await p.ev(`!!document.querySelector('.egs-point')`)), 'Got it clears it');
const s6 = await tourState(p);
ok(s6 && !s6.firstRun && s6.seen.length === 2, 'state: not a first run, both seen', s6);
ok(!(await p.ev(`!!document.querySelector('[data-egs-check-card]')`)), 'no checklist for a phone that already had Notebuilt');
await closePage(p);
p = await openPage(NEW); await sleep(1400);
ok(!(await pointerTitle(p)) && !(await p.ev(`EGSTour.active()`)), 'next open: nothing pointed at');
await p.ev(`go('settings'); true`); await sleep(300);
await p.tapSel('[data-tour-start]');
ok(await atStep(p, 'Welcome to Notebuilt', 3000), 'Settings → Replay starts the walkthrough');
await p.tapSel('.egs-tour .egs-tour-x'); await sleep(300);
await closePage(p);
p = await boot(NEW, Object.assign({}, EXISTING, { 'notebuilt.guideNoticeSeen': null }));
await sleep(900);
ok(await p.ev(`nbGuideNoticeDue()`) === true, 'an existing phone that never saw the i-marks notice still gets it');
await closePage(p);

console.log('\n[7] behind the PIN: nothing until it is entered');
const salt = 'a1b2c3d4';
const pinSet = Object.assign({}, EXISTING, { 'notebuilt.settings': Object.assign({}, EXISTING['notebuilt.settings'], { pinSalt: salt, pinHash: sha('1234' + salt) }) });
p = await boot(NEW, pinSet); await sleep(1500);
ok(await p.ev(`!$lock.classList.contains('hidden')`), 'the PIN gate is up');
ok(await p.ev(`!document.querySelector('.egs-point,.egs-tour')`), 'no pointer or walkthrough behind the keypad');
for (const k of '1234') { await p.ev(`document.querySelector('#lock [data-k="${k}"]').click(); true`); await sleep(80); }
await sleep(1500);
ok(/A way back into the app/.test(await p.ev(`document.getElementById('modal-root').innerText`)), 'past the PIN: the one-time recovery-code offer has the screen');
ok(!(await pointerTitle(p)) && !(await p.ev(`EGSTour.active()`)), 'and what\'s new waits rather than stacking on it');
await closePage(p);
const pinOffered = JSON.parse(JSON.stringify(pinSet)); pinOffered['notebuilt.settings'].recoveryOfferedAt = 1790000000000;
p = await boot(NEW, pinOffered); await sleep(1200);
ok(await p.ev(`!document.querySelector('.egs-point,.egs-tour')`), 'offer already made: still nothing behind the keypad');
for (const k of '1234') { await p.ev(`document.querySelector('#lock [data-k="${k}"]').click(); true`); await sleep(80); }
ok(await waitFor(p, `!!document.querySelector('.egs-point') && document.querySelector('.egs-point').style.display!=='none'`, 4000), 'past the PIN, with nothing else on screen, what\'s new appears');
await closePage(p);

console.log('\n[8] the sample photos cannot be reached');
p = await openPage(`${ORIGIN2}/index.html`, { ready: 'true' }); await wipe(p); await closePage(p);
p = await openPage(`${ORIGIN2}/index.html`);
ok(await atStep(p, 'Welcome to Notebuilt', 4000), 'welcome card');
await p.tapSel('.egs-tour .primary');
ok(await atStep(p, 'This is a sample job', 9000), 'the walkthrough carries on');
ok(await p.ev(`nbSampleProject() && nbSampleProject().photos.length===0 && tasks.filter(t=>t.sample).length===5`), 'the job is there, with no photos');
ok(p.errors.length === 0, 'no uncaught error', p.errors);
await closePage(p);

console.log('\n[9] a crew link on a fresh phone: the list, not the walkthrough');
p = await boot(`${NEW}#crew=1AAAA`); await sleep(1600);
ok(!(await p.ev(`!!document.querySelector('.egs-tour')`)), 'no welcome card over a crew link');
ok(/Couldn.t open this list|Crew list/.test(await p.ev(`document.getElementById('modal-root').innerText`)), 'the crew sheet is what shows');
ok(await tourState(p) === null, 'nothing written');
await closePage(p);

console.log('\n[10] 320px wide, both themes');
for (const theme of ['dark', 'light']) {
  p = await boot(NEW, {}, { w: 320, h: 640, theme });
  ok(await atStep(p, 'Welcome to Notebuilt', 4000), `${theme}: welcome card`);
  const fit = await p.ev(`(()=>{ const c=document.querySelector('.egs-tour .egs-tour-card').getBoundingClientRect();
    return { l:c.left, r:c.right, t:c.top, b:c.bottom, sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth }; })()`);
  ok(fit.l >= 0 && fit.r <= 320 && fit.t >= 0 && fit.b <= 640 && fit.sw <= fit.cw, `${theme}: the card fits, no sideways scroll`, fit);
  const cr = await p.ev(`(()=>{ const L=c=>{ const m=c.match(/[\\d.]+/g).map(Number); const f=v=>{ v/=255; return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4); }; return .2126*f(m[0])+.7152*f(m[1])+.0722*f(m[2]); };
    const R=(a,b)=>{ const x=L(a), y=L(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); };
    const card=document.querySelector('.egs-tour .egs-tour-card'), bg=getComputedStyle(card).backgroundColor;
    const pr=document.querySelector('.egs-tour .primary'), pcs=getComputedStyle(pr);
    return { title:R(getComputedStyle(card.querySelector('.egs-tour-title')).color,bg), body:R(getComputedStyle(card.querySelector('.egs-tour-body')).color,bg),
             lead:R(getComputedStyle(card.querySelector('.egs-tour-lead')).color,bg), button:R(pcs.color,pcs.backgroundColor) }; })()`);
  ok(Object.values(cr).every(v => v >= 4.5), `${theme}: every text on the card clears 4.5:1`, cr);
  await p.tapSel('.egs-tour .primary');
  ok(await atStep(p, 'This is a sample job', 9000), `${theme}: on to the sample`);
  const row = await p.ev(`(()=>{ const r=document.querySelector('.nb-jobs'); return { sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth, rowRight:r.getBoundingClientRect().right }; })()`);
  ok(row.sw <= row.cw && row.rowRight <= 320, `${theme}: the Projects row scrolls inside itself, the page does not`, row);
  await closePage(p);
}

console.log('\n[11] backup and restore carry the sample; the walkthrough state stays on the phone');
p = await boot(NEW); await atStep(p, 'Welcome to Notebuilt', 4000);
await p.tapSel('.egs-tour .primary'); await atStep(p, 'This is a sample job', 9000);
await p.ev(`EGSTour.stop(); true`);
await p.ev(`maybeShowDataSafetyNudge(); true`); await sleep(300);
ok(!(await p.ev(`!!document.getElementById('backup-banner')`)), 'a phone holding only the sample is not nudged to back up');
const dump = await p.ev(`(async()=>{ let got=null; const o=URL.createObjectURL; URL.createObjectURL=function(b){ if(b&&b.type==='application/json') got=b; return o.call(URL,b); };
  try{ await exportData(); } finally { URL.createObjectURL=o; } return got ? await got.text() : null; })()`);
const d = JSON.parse(dump || '{}');
ok(d.houses?.filter(h => h.sample === 'nb-sample-1').length === 1 && d.tasks?.filter(t => t.sample).length === 5 && Object.keys(d.photos || {}).length === 4, 'the export holds the sample, flags and photos');
ok(!dump.includes('notebuilt.tour') && !JSON.stringify(d.settings || {}).includes('firstRun'), 'the export holds no walkthrough state');
await closePage(p);
p = await boot(NEW, { 'notebuilt.tour': { v: 1, firstRun: false, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'], skipped: true } });
await sleep(900);
p.answer = true;
await p.ev(`(async()=>{ const f=new File([${JSON.stringify(dump)}], 'b.json', {type:'application/json'}); await importData({target:{files:[f], value:''}}); return true; })()`);
await sleep(1500);
ok(await p.ev(`houses.filter(h=>h.sample==='nb-sample-1').length`) === 1 && await p.ev(`nbCountedProjects()`) === 0, 'restored: the sample is still a sample, and still not counted');
ok(await p.ev(`photoAll().then(a=>a.length)`) === 4, 'restored: its four photos');
await closePage(p);

console.log('\n[12] the live build on data this build wrote');
p = await openPage(OLD); await sleep(900);
ok(p.errors.length === 0, `old build (${OLD_REF}) boots without an uncaught error`, p.errors);
await p.ev(`go('houses'); true`); await sleep(300);
ok(/Sample · Great Room & Kitchen/.test(await appText(p)), 'old build lists the sample like any project');
const sid = await p.ev(`houses.find(h=>h.sample).id`);
await p.ev(`openCategoryPicker(${JSON.stringify(sid)}); true`); await sleep(200);
await p.ev(`[...document.querySelectorAll('[data-move-cat]')].find(b=>b.dataset.moveCat!=='construction').click(); true`); await sleep(300);
ok(await p.ev(`JSON.parse(localStorage.getItem('notebuilt.houses')).find(h=>h.id===${JSON.stringify(sid)}).sample`) === 'nb-sample-1', 'an edit on the old build carries the sample field through');
await closePage(p);

console.log('\n[13] projects that cannot be read are never treated as a new phone');
const BROKEN = '[{"id":"a1","name":"Al';
const GOOD = JSON.stringify([{ id: 'a1', name: 'Alder Job', category: 'construction', address: '', status: 'active', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: 1790000000000, updatedAt: 1790000000000, schemaVersion: 2 }]);
p = await boot(NEW, { 'notebuilt.houses': BROKEN, 'notebuilt.houses_bak': GOOD });
await sleep(1500);
ok(!(await p.ev(`EGSTour.active()`)), 'no welcome card over unreadable projects');
ok(await p.ev(`(async()=>{ try{ await nbSampleLoad(); return 'loaded'; }catch(e){ return e.message; } })()`) === 'unreadable', 'the sample refuses to load over them');
await p.ev(`go('settings'); true`); await sleep(300);
await p.tapSel('[data-sample-load]'); await sleep(800);
ok(await p.ev(`localStorage.getItem('notebuilt.houses')`) === BROKEN && await p.ev(`localStorage.getItem('notebuilt.houses_bak')`) === GOOD, 'the unreadable value and its good twin are both untouched');
ok(/couldn.t be read/.test(await p.ev(`document.getElementById('toast').textContent`)), 'and it says why');
await closePage(p);
p = await boot(`${ORIGIN}/m-fresh.html`, { 'notebuilt.houses': BROKEN, 'notebuilt.houses_bak': GOOD });
ok(await atStep(p, 'Welcome to Notebuilt', 4000), 'mutant: judging "fresh" by what parsed shows the welcome (so [13] would catch it)');
await closePage(p);

console.log('\n[14] a PROTECTED sample goes the vault’s way: nothing of theirs is stranded');
const vaultUp = q => q.ev(`(async()=>{ const salt=b64FromBytes(crypto.getRandomValues(new Uint8Array(16)));
  _vaultKey=await vaultDeriveKey('correct horse battery', salt); const verifier=await vaultSealText(VAULT_VERIFIER_TEXT);
  settings.vault={ salt, verifier, migration:null }; persist.settings(); await vaultEnsureEnvelopeKeys(); return true; })()`);
async function protectedSample(url) {
  const q = await boot(url); await atStep(q, 'Welcome to Notebuilt', 4000);
  await q.ev(`EGSTour.stop(); true`);
  await q.ev(`nbSampleLoad().then(()=>true)`);
  await waitFor(q, `(nbSampleProject()||{photos:[]}).photos.length===4`, 8000);
  await vaultUp(q);
  const sid = await q.ev(`nbSampleProject().id`);
  q.answer = true;
  await q.ev(`vaultProtectOn(${JSON.stringify(sid)}).then(()=>true)`);
  await waitFor(q, `nbSampleProject().protected===true && !document.getElementById('vault-busy')`, 15000);
  await q.ev(`(async()=>{ const t={id:'tGate',text:'Gate code 4417',status:'todo',houseId:${JSON.stringify(sid)},createdAt:now(),updatedAt:now(),doneAt:null,dueDate:null};
    tasks.push(t); await vaultAlignRecord(t,['text'],t.houseId); persist.tasks();
    const n={id:'nAlarm',title:'Alarm',body:'Disarm 9921',houseId:${JSON.stringify(sid)},important:false,createdAt:now(),updatedAt:now()};
    notes.push(n); await vaultAlignRecord(n,['title','body'],n.houseId); persist.notes(); return true; })()`);
  q.dialogs.length = 0;
  return { q, sid };
}
let ps = await protectedSample(NEW);
ok(await ps.q.ev(`isEnc(tasks.find(t=>t.id==='tGate').text)`), 'set up: a protected sample holding their own sealed to-do and note');
await ps.q.ev(`go('settings'); true`); await sleep(300);
await ps.q.tapSel('[data-sample-remove]'); await sleep(900);
ok(ps.q.dialogs.length === 2 && /Last check/.test(ps.q.dialogs[1]), 'Remove asks twice, the vault’s way', ps.q.dialogs);
ok(!(await ps.q.ev(`!!houseById(${JSON.stringify(ps.sid)})`)), 'the project is gone');
ok(await ps.q.ev(`tasks.concat(notes).filter(r=>!r.houseId && (isEnc(r.text)||isEnc(r.title)||isEnc(r.body))).length`) === 0, 'no sealed record is left unfiled where nothing can open it');
await closePage(ps.q);
ps = await protectedSample(NEW);
await ps.q.ev(`openHouseSheet(houseById(${JSON.stringify(ps.sid)})); true`); await sleep(300);
await ps.q.ev(`document.getElementById('h-del').click(); true`); await sleep(900);
ok(ps.q.dialogs.length === 2 && !(await ps.q.ev(`!!houseById(${JSON.stringify(ps.sid)})`)) && await ps.q.ev(`tasks.concat(notes).filter(r=>!r.houseId && (isEnc(r.text)||isEnc(r.title)||isEnc(r.body))).length`) === 0,
  'Edit → Delete on it does the same', ps.q.dialogs);
await closePage(ps.q);
ps = await protectedSample(`${ORIGIN}/m-protectremove.html`);
await ps.q.ev(`go('settings'); true`); await sleep(300);
await ps.q.tapSel('[data-sample-remove]'); await sleep(900);
ok(await ps.q.ev(`tasks.concat(notes).filter(r=>!r.houseId && (isEnc(r.text)||isEnc(r.title)||isEnc(r.body))).length`) > 0, 'mutant: unfiling a protected sample strands sealed records (so [14] would catch it)');
await closePage(ps.q);

console.log('\n[15] Delete removes the project it was asked about');
const flag = (id, name) => ({ id, name, category: 'construction', address: '', status: 'active', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: 1790000000000, updatedAt: 1790000000000, schemaVersion: 2, sample: 'nb-sample-1' });
p = await boot(NEW, { 'notebuilt.houses': [flag('s1', 'First flagged'), flag('s2', 'Second flagged')], 'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'] } });
await sleep(900);
await p.ev(`openHouseSheet(houseById('s2')); true`); await sleep(300);
await p.ev(`document.getElementById('h-del').click(); true`); await sleep(700);
ok(await p.ev(`houses.map(h=>h.id).join()`) === 's1', 'Delete on the second one removes the second one', await p.ev(`houses.map(h=>h.id).join()`));
await closePage(p);

console.log('\n[16] removed while it was still loading: no photo left behind, and a fresh load works');
p = await boot(NEW, { 'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'], skipped: true } });
await sleep(900);
await p.ev(`(()=>{ const f=window.fetch; window.fetch=(u,o)=>new Promise(r=>setTimeout(r,400)).then(()=>f(u,o)); return true; })()`);
await p.ev(`window.__ld=nbSampleLoad(); true`);
await waitFor(p, `!!nbSampleProject()`);
const sidL = await p.ev(`nbSampleProject().id`);
await p.ev(`nbSampleRemove(nbSampleProject().id).then(()=>true)`);
await p.ev(`window.__ld.then(()=>true,()=>true)`); await sleep(500);
ok(await p.ev(`photoAll().then(a=>a.filter(r=>r.houseId===${JSON.stringify(sidL)}).length)`) === 0, 'not one photo of the removed sample is left in storage');
await p.ev(`nbSampleLoad().then(r=>window.__r=r)`);
ok(await p.ev(`!!houseById(window.__r.house.id) && window.__r.house.id!==${JSON.stringify(sidL)}`), 'Load afterwards makes a new one, not the removed one');
await closePage(p);

console.log('\n[17] a checklist pointer belongs to its screen');
for (const [label, url, expectGone] of [['build', NEW, true], ['mutant (no until)', `${ORIGIN}/m-until.html`, false]]) {
  p = await boot(url, Object.assign({}, EXISTING, { 'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'], check: 'on' } }));
  await sleep(900);
  await p.ev(`nbChecklistGo('photo'); true`); await sleep(500);
  const on = await p.ev(`EGSTour.pointing()`);
  await p.ev(`go('todo'); true`); await sleep(900);
  const after = await p.ev(`EGSTour.pointing()`);
  if (expectGone) ok(on && !after, 'pointing at Camera, then gone the moment they leave the project', { on, after });
  else ok(on && after, 'mutant: without until it follows them (so [17] would catch it)', { on, after });
  await closePage(p);
}

console.log('\n[18] Load in Settings never moves someone who has moved on');
p = await boot(NEW, Object.assign({}, EXISTING, { 'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'] } }));
await sleep(900);
await p.ev(`(()=>{ const f=window.fetch; window.fetch=(u,o)=>new Promise(r=>setTimeout(r,500)).then(()=>f(u,o)); return true; })()`);
await p.ev(`go('settings'); true`); await sleep(300);
await p.ev(`document.querySelector('[data-sample-load]').click(); true`); await sleep(100);
await p.ev(`go('house','hA'); openTaskSheet('hA'); true`); await sleep(300);
await p.ev(`(()=>{ const i=document.getElementById('t-text'); i.focus(); window.__i=i; return true; })()`);
await p.type('Order hinges');
await waitFor(p, `(nbSampleProject()||{photos:[]}).photos.length===4`, 9000); await sleep(400);
ok(await p.ev(`view.name==='house' && view.param==='hA'`), 'still on the project they went to');
ok(await p.ev(`document.getElementById('t-text')===window.__i && window.__i.value==='Order hinges' && document.activeElement===window.__i`), 'the sheet, the field and what they typed are untouched');
await closePage(p);

console.log('\n[19] Show me around first, on a phone that never saw the welcome card');
p = await boot(`${NEW}#/calc`); await sleep(1300);
ok(!(await p.ev(`EGSTour.active()`)) && await tourState(p) === null, 'a deep link: no welcome, nothing written');
await p.ev(`go('todo'); true`); await sleep(300);
await p.tapSel('.nb-hero [data-tour-start]');
ok(await atStep(p, 'Welcome to Notebuilt', 3000), 'the empty-app card starts it');
ok((await tourState(p) || {}).firstRun === true, 'and the phone is recorded as a new user’s');
await closePage(p);

console.log('\n[20] Replay at the free cap passes over "start your own"');
const capped = Object.assign({}, EXISTING, {
  'notebuilt.houses': ['hA', 'hC', 'hD'].map((id, k) => ({ id, name: 'Job ' + id, category: 'construction', address: '', status: 'active', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: 1790000000000 + k, updatedAt: 1790000000000 + k, schemaVersion: 2 })),
  'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'] } });
p = await boot(NEW, capped); await sleep(900);
await p.ev(`go('settings'); true`); await sleep(300);
await p.tapSel('[data-tour-start]');
await atStep(p, 'Welcome to Notebuilt', 3000);
await p.tapSel('.egs-tour .primary');
await atStep(p, 'This is a sample job', 9000);
await p.tapSel('#app [data-tour="sample"]');
await atStep(p, 'Everything for the job, in the job');
await p.tapSel('.egs-tour .primary');
ok(await atStep(p, 'Add one thing that needs doing'), 'at the cap, the next step is the to-do in their newest project', await cardTitle(p));
ok(await p.ev(`view.name==='house' && view.param==='hD'`), 'and it took them to that project');
await p.ev(`EGSTour.stop(); true`);
await closePage(p);

console.log('\n[21] what’s new on a phone with notes but no projects');
p = await boot(NEW, { 'notebuilt.notes': [{ id: 'n1', title: 'Supplier', body: '555-0100', houseId: null, important: false, createdAt: 1790000000000, updatedAt: 1790000000000 }] });
ok(await waitFor(p, `(()=>{ const r=document.querySelector('.egs-point'); return !!r && r.style.display!=='none'; })()`, 4000), 'a pointer shows');
ok(await pointerTitle(p) === 'New in Settings: Getting started', 'the Projects-row pointer is held back (there is no row); Settings is shown');
await p.tapSel('.egs-point .primary'); await sleep(300);
ok(JSON.stringify((await tourState(p)).seen) === JSON.stringify(['2026-10-getting-started']), 'only what was shown is marked seen');
await closePage(p);

console.log('\n[22] a walkthrough record from a newer Notebuilt is left alone');
const FUTURE = JSON.stringify({ v: 2, seen: [], newerField: 'KEEP' });
p = await boot(NEW, Object.assign({}, EXISTING, { 'notebuilt.tour': FUTURE }));
await sleep(1500);
ok(!(await p.ev(`EGSTour.active() || EGSTour.pointing()`)), 'nothing started, nothing pointed at');
await p.ev(`nbTourWrite({ check:'off' }); true`);
ok(await p.ev(`localStorage.getItem('notebuilt.tour')`) === FUTURE, 'a write leaves it byte-identical');
await closePage(p);

console.log('\n[23] the ordinary Delete prompt says what it deletes');
p = await boot(NEW, Object.assign({}, EXISTING, { 'notebuilt.tour': { v: 1, seen: ['2026-10-projects-on-todo', '2026-10-getting-started'] } }));
await sleep(900);
p.answer = false;
await p.ev(`openHouseSheet(houseById('hA')); true`); await sleep(300);
await p.ev(`document.getElementById('h-del').click(); true`); await sleep(300);
ok(/with its specs and photos/.test(p.dialogs[0] || '') && /to-dos and notes stay/.test(p.dialogs[0] || '') && await p.ev(`!!houseById('hA')`), 'it names the photos, and No keeps the project', p.dialogs[0]);
await closePage(p);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { console.log('FAILED:\n  ' + failures.join('\n  ')); process.exit(1); }
process.exit(0);
