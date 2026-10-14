// test_houses_schema.mjs — real-browser gate for th_nb_houses_schema.
// Headless Google Chrome over raw CDP (Node's built-in WebSocket), no deps.
// Usage: node test_houses_schema.mjs <dir containing the NEW index.html> [old git ref, default 723a578]
//
// Serves three builds side by side on ONE origin, so they share localStorage
// exactly as an installed phone would across an update:
//   /index.html   the build under test
//   /old.html     the live build, read out of git (723a578 = 146341f stamp = notebuilt.ca)
//   /mutant.html  the build under test with the ungated category fill-in put back —
//                 the gate must catch it, or it is not a gate.
// 127.0.0.1 EVERYWHERE, never "localhost" — the Aug 13 trap.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = process.argv[2];
const OLD_REF = process.argv[3] || '723a578';
const REPO = dirname(fileURLToPath(import.meta.url));
const HOST = '127.0.0.1', HTTP = 8766, DBG = 9334;
const ORIGIN = `http://${HOST}:${HTTP}`;
const NEW = `${ORIGIN}/index.html`, OLD = `${ORIGIN}/old.html`, MUT = `${ORIGIN}/mutant.html`;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0; const failures = [];
function ok(cond, name, detail) {
  if (cond) { pass++; console.log('  PASS', name); }
  else { fail++; failures.push(name); console.log('  FAIL', name, detail !== undefined ? '→ ' + JSON.stringify(detail) : ''); }
}

// ---------- the three builds ----------
const serveDir = mkdtempSync(join(tmpdir(), 'nb-hschema-srv-'));
const newHtml = readFileSync(join(SRC, 'index.html'), 'utf8');
const oldHtml = execFileSync('git', ['-C', REPO, 'show', `${OLD_REF}:index.html`], { encoding: 'utf8', maxBuffer: 64 << 20 });
const LOAD_LINE = 'let housesFromFuture = nbHousesUp();';
if (!newHtml.includes(LOAD_LINE)) { console.error('ABORT: build under test has no per-record houses schema'); process.exit(2); }
if (oldHtml.includes('NB_HOUSES_SCHEMA')) { console.error(`ABORT: ${OLD_REF} is not a pre-change build`); process.exit(2); }
const oldStamp = (oldHtml.match(/EGS_VERSION = '([^']*)'/) || [])[1];
writeFileSync(join(serveDir, 'index.html'), newHtml);
writeFileSync(join(serveDir, 'old.html'), oldHtml);
writeFileSync(join(serveDir, 'mutant.html'),
  newHtml.replace(LOAD_LINE, "houses.forEach(h=>{ if(!h.category) h.category='construction'; });\n" + LOAD_LINE));
console.log(`old build: ${OLD_REF} (${oldStamp})`);

// ---------- processes ----------
try { await fetch(`http://${HOST}:${DBG}/json/version`); console.error(`ABORT: something already listens on ${HOST}:${DBG}`); process.exit(2); } catch (e) {}
const server = spawn('python3', ['-m', 'http.server', String(HTTP), '--bind', HOST, '--directory', serveDir], { stdio: 'ignore' });
const profile = mkdtempSync(join(tmpdir(), 'nb-hschema-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--remote-debugging-address=${HOST}`,
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', 'about:blank'], { stdio: 'ignore' });
function cleanup() {
  try { chrome.kill(); } catch (e) {} try { server.kill(); } catch (e) {}
  try { rmSync(profile, { recursive: true, force: true }); } catch (e) {} try { rmSync(serveDir, { recursive: true, force: true }); } catch (e) {}
}
process.on('exit', cleanup);

let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) {
  try { wsUrl = (await (await fetch(`http://${HOST}:${DBG}/json/version`)).json()).webSocketDebuggerUrl; } catch (e) { await sleep(100); }
}
for (let i = 0; i < 50; i++) { try { await fetch(NEW); break; } catch (e) { await sleep(100); } }

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

async function openPage(url) {
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
  for (let i = 0; i < 100; i++) {
    try { if (await p.ev(`document.readyState==='complete' && typeof navState==='function'`)) break; } catch (e) {}
    await sleep(100);
  }
  await sleep(150);
  return p;
}
async function closePage(p) { p.detach(); await send('Target.closeTarget', { targetId: p.targetId }); await sleep(200); }

// ---------- fixtures ----------
const t = 1790000000000;
const rec = (id, name, extra = {}) => ({ id, name, category: 'construction', address: '1 Test St', status: 'active', jobType: '', specs: [], photos: [], cover: null, notes: '', createdAt: t, updatedAt: t, ...extra });
const without = (o, k) => { const c = { ...o }; delete c[k]; return c; };
// v1: no number, one with no category (pre-categories), one already categorised
const V1 = [without(rec('a1', 'Alder'), 'category'), rec('a2', 'Birch', { category: 'apps' })];
// v3 records from an invented newer build: extra fields, and `category` renamed
const F1 = rec('f1', 'Fir', { schemaVersion: 3, v3Field: 'FUTURE1', rooms: [{ id: 'r1', name: 'Kitchen' }] });
const F2 = without(rec('f2', 'Gum', { schemaVersion: 3, categoryRef: 'construction' }), 'category');
const MIXED = [F1, F2, without(rec('m3', 'Hazel'), 'category')];
const SET_V3 = { pinHash: null, pinSalt: null, sortHouses: 'updated', units: 'imperial', schemaVersion: 3, v3Pref: 'KEPT' };
const NEWER_NOTICE = 'This data is from a newer Notebuilt';
const NEWER_CARD = 'This data was saved by a newer Notebuilt';

// Boot `url` on storage seeded fresh with `seed` ({key: string|object|null}).
async function boot(url, seed) {
  let p = await openPage(NEW);
  await p.ev(`(()=>{ localStorage.clear(); const s=${JSON.stringify(seed)};
    for(const [k,v] of Object.entries(s)) if(v!==null) localStorage.setItem(k, typeof v==='string'?v:JSON.stringify(v)); return true; })()`);
  await closePage(p);
  p = await openPage(url);
  await sleep(2100); // past the 1800ms notice toast
  p.toasts = await p.ev(`[...document.querySelectorAll('.toast,#toast')].map(e=>e.innerText).filter(Boolean)`);
  return p;
}
const raw = (p, k) => p.ev(`localStorage.getItem(${JSON.stringify(k)})`);
const storedHouses = async p => JSON.parse(await raw(p, 'notebuilt.houses') || '[]');
const storedSettings = async p => { try { return JSON.parse(await raw(p, 'notebuilt.settings') || 'null'); } catch (e) { return 'UNPARSEABLE'; } };
const byId = (arr, id) => arr.find(h => h.id === id) || {};
// Real UI: the sort sheet (writes settings) and the category picker (writes houses).
async function uiSort(p) {
  await p.ev(`go('houses'); true`); await sleep(250);
  await p.ev(`document.querySelector('[data-sort-houses]').click(); true`); await sleep(200);
  await p.ev(`document.querySelector('[data-sort-opt="alpha"]').click(); true`); await sleep(250);
}
async function uiMove(p, id) {
  await p.ev(`openCategoryPicker(${JSON.stringify(id)}); true`); await sleep(200);
  const to = await p.ev(`(()=>{const b=[...document.querySelectorAll('[data-move-cat]')].find(b=>b.dataset.moveCat!=='construction'); if(!b) return null; b.click(); return b.dataset.moveCat;})()`);
  await sleep(250); return to;
}
const settingsCardShown = async p => { await p.ev(`go('settings'); true`); await sleep(300); return (await p.ev(`document.getElementById('app').innerText`)).includes(NEWER_CARD); };
const listed = async (p, names) => { await p.ev(`go('houses'); true`); await sleep(300); const txt = await p.ev(`document.getElementById('app').innerText`); return names.filter(n => !txt.includes(n)); };
// Feed a file to a real file-input handler.
const feed = (p, fn, obj, name) => p.ev(`(async()=>{ const f=new File([${JSON.stringify(JSON.stringify(obj))}], ${JSON.stringify(name)}, {type:'application/json'});
  await ${fn}({target:{files:[f], value:''}}); return true; })()`);

// ======================================================================
console.log('\n[1] v1 data (no numbers) on the new build');
let p = await boot(NEW, { 'notebuilt.houses': V1 });
ok(p.errors.length === 0, 'boots without an uncaught error', p.errors);
ok(await raw(p, 'notebuilt.houses') === JSON.stringify(V1), 'boot writes nothing to houses');
ok(await p.ev(`houses.every(h=>h.schemaVersion===2 && h.category)`), 'in memory every v1 record is brought to v2');
ok(await p.ev(`housesFromFuture`) === false && p.toasts.every(s => !s.includes(NEWER_NOTICE)), 'no newer-data notice for older data', p.toasts);
ok((await listed(p, ['Alder', 'Birch'])).length === 0, 'both projects listed');
await uiMove(p, 'a1');
let hs = await storedHouses(p);
ok(hs.every(h => h.schemaVersion === 2 && h.category), 'after a real edit every stored record carries category + schemaVersion:2', hs);
await closePage(p);

console.log('\n[1b] the live build on data the new build wrote');
p = await openPage(OLD);
ok(p.errors.length === 0, `old build (${oldStamp}) boots without an uncaught error`, p.errors);
ok((await listed(p, ['Alder', 'Birch'])).length === 0, 'old build lists every project');
ok(await p.ev(`schemaFromFuture`) === false, 'old build raises no false newer-data flag');
await uiMove(p, 'a2');
hs = await storedHouses(p);
ok(hs.every(h => h.schemaVersion === 2), 'old build\'s edits carry schemaVersion through', hs);
await closePage(p);

for (const [label, settingsSeed] of [['settings at v3', SET_V3], ['settings absent', null], ['settings unreadable', '{broken']]) {
  console.log(`\n[2] newer + v1 records mixed, ${label}`);
  p = await boot(NEW, { 'notebuilt.houses': MIXED, 'notebuilt.settings': settingsSeed });
  ok(p.errors.length === 0, 'boots without an uncaught error', p.errors);
  ok(await p.ev(`housesFromFuture`) === true, 'housesFromFuture is set');
  const mem = await p.ev(`houses.map(h=>({id:h.id,c:h.category,v:h.schemaVersion}))`);
  ok(byId(mem, 'f2').c === undefined && byId(mem, 'f2').v === 3, 'in memory the v3 record is not filled in or restamped', mem);
  ok(byId(mem, 'm3').c === 'construction' && byId(mem, 'm3').v === 2, 'in memory the v1 record beside it is brought up', mem);
  if (label === 'settings unreadable') ok(p.toasts.some(s => /could not be read/.test(s)), 'unreadable-settings toast shown (the more urgent one)', p.toasts);
  else ok(p.toasts.some(s => s.includes(NEWER_NOTICE)), 'newer-data toast shown', p.toasts);
  ok(await settingsCardShown(p), 'newer-data card shown in Settings');
  await uiSort(p);
  await uiMove(p, 'f1');
  await uiMove(p, 'm3');
  hs = await storedHouses(p);
  const f1 = byId(hs, 'f1'), f2 = byId(hs, 'f2'), m3 = byId(hs, 'm3');
  ok(!('category' in f2) && f2.categoryRef === 'construction' && f2.schemaVersion === 3, 'on disk the v3 record got no category and kept its number', f2);
  ok(f1.v3Field === 'FUTURE1' && f1.rooms?.length === 1 && f1.schemaVersion === 3, 'on disk the edited v3 record kept its unknown fields and number', f1);
  ok(m3.category && m3.schemaVersion === 2, 'on disk the v1 record is v2', m3);
  const s = await storedSettings(p);
  if (label === 'settings at v3') ok(s.schemaVersion === 3 && s.v3Pref === 'KEPT', 'settings number not lowered, unknown setting kept', s);
  if (label === 'settings unreadable') ok(s === 'UNPARSEABLE', 'damaged settings left exactly as they were');
  await closePage(p);
}

console.log('\n[3] mutation: the ungated fill-in put back must be caught');
p = await boot(MUT, { 'notebuilt.houses': MIXED, 'notebuilt.settings': SET_V3 });
await uiMove(p, 'f1');
ok('category' in byId(await storedHouses(p), 'f2'), 'mutant writes category into the v3 record (so [2] would catch it)');
await closePage(p);

console.log('\n[4] new project, shared import');
p = await boot(NEW, { 'notebuilt.houses': [rec('n0', 'Oak', { schemaVersion: 2 })] });
await p.ev(`openHouseSheet(); true`); await sleep(250);
await p.ev(`document.querySelector('#h-name').value='Pine'; document.querySelector('#h-save').click(); true`); await sleep(400);
await feed(p, 'importSharedProject', { app: 'notebuilt-project-share', project: { name: 'Shared Spruce', specs: [] } }, 'share.json'); await sleep(300);
hs = await storedHouses(p);
const pine = hs.find(h => h.name === 'Pine') || {}, spr = hs.find(h => h.name === 'Shared Spruce') || {};
ok(pine.schemaVersion === 2, 'new project stored with schemaVersion:2', pine);
ok(spr.schemaVersion === 2 && !!spr.category, 'shared import stored with schemaVersion:2 and a category', spr);
await closePage(p);

console.log('\n[5] restore');
p = await boot(NEW, { 'notebuilt.houses': [rec('x0', 'Willow', { schemaVersion: 2 })] });
await feed(p, 'importData', { app: 'notebuilt', version: 2, exportedAt: t, houses: V1, tasks: [], notes: [], photos: {} }, 'old-backup.json'); await sleep(800);
hs = await storedHouses(p);
ok(hs.length === 2 && hs.every(h => h.schemaVersion === 2 && h.category), 'old backup (no numbers, no settings) restores as v2 records', hs);
ok(await p.ev(`housesFromFuture`) === false, 'no newer-data flag after an old restore');
await feed(p, 'importData', { app: 'notebuilt', version: 3, exportedAt: t, houses: MIXED, tasks: [], notes: [], photos: {}, settings: { schemaVersion: 2 } }, 'v3-backup.json'); await sleep(800);
hs = await storedHouses(p);
ok(!('category' in byId(hs, 'f2')) && byId(hs, 'f2').schemaVersion === 3, 'a restored v3 record is left as it came', byId(hs, 'f2'));
ok(byId(hs, 'm3').schemaVersion === 2, 'its v1 neighbour is brought up');
ok(await p.ev(`housesFromFuture`) === true, 'restore of newer records sets the flag');
await closePage(p);

console.log('\n[6] export carries the numbers');
p = await boot(NEW, { 'notebuilt.houses': V1 });
await p.ev(`(()=>{ const o=URL.createObjectURL; URL.createObjectURL=b=>{ window.__blob=b; return o.call(URL,b); }; return true; })()`);
await p.ev(`exportData().then(()=>true)`); await sleep(400);
const dump = JSON.parse(await p.ev(`window.__blob.text()`));
ok(dump.houses.length === 2 && dump.houses.every(h => h.schemaVersion === 2), 'every exported record carries schemaVersion:2', dump.houses);
await closePage(p);

console.log('\n[7] vault protect-on keeps the number');
const PASS = 'correct horse battery';
p = await boot(NEW, { 'notebuilt.houses': [rec('v1', 'Yew', { notes: 'secret' })] });
await p.ev(`void vaultProtectOn('v1')`); await sleep(300);
await p.ev(`$vault.querySelector('[data-v-next]').click()`); await sleep(100);
await p.ev(`$vault.querySelector('#v-p1').value=${JSON.stringify(PASS)}; $vault.querySelector('#v-p2').value=${JSON.stringify(PASS)}; $vault.querySelector('[data-v-next]').click()`); await sleep(100);
await p.ev(`const a=$vault.querySelector('#v-ack'); a.checked=true; a.onchange(); $vault.querySelector('[data-v-next]').click()`);
for (let i = 0; i < 100 && !(await p.ev(`!!$vault.querySelector('#v-vp')`)); i++) await sleep(100);
await p.ev(`$vault.querySelector('#v-vp').value=${JSON.stringify(PASS)}; $vault.querySelector('[data-v-go]').click()`);
for (let i = 0; i < 100 && !(await p.ev(`$vault.classList.contains('hidden')`)); i++) await sleep(100);
const yew = byId(await storedHouses(p), 'v1');
ok(yew.protected === true && yew.schemaVersion === 2 && yew.notes !== 'secret', 'protected record is sealed and still carries schemaVersion:2', { protected: yew.protected, v: yew.schemaVersion });
await closePage(p);

ws.close();
console.log(`\n${pass} passed, ${fail} failed`);
if (fail) { console.log('FAILED:\n  ' + failures.join('\n  ')); }
cleanup(); process.exit(fail ? 1 : 0);
