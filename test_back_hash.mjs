// test_back_hash.mjs — real-browser gate for NB_BACK_HASH (th_nb_back_hash).
// Headless Google Chrome over raw CDP (Node's built-in WebSocket), no deps.
// Usage: node test_back_hash.mjs <dir containing index.html>
//
// 127.0.0.1 EVERYWHERE, never "localhost": python's http.server binds IPv4 only
// and Chrome resolves localhost to ::1 first — the Aug 13 trap.
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const DIR = process.argv[2];
const HOST = '127.0.0.1', HTTP = 8765, DBG = 9333;
const BASE = `http://${HOST}:${HTTP}/index.html`;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));

let pass = 0, fail = 0; const failures = [];
function ok(cond, name, detail) {
  if (cond) { pass++; console.log('  PASS', name); }
  else { fail++; failures.push(name); console.log('  FAIL', name, detail !== undefined ? '→ ' + JSON.stringify(detail) : ''); }
}

// ---------- processes ----------
// Refuse to attach to a leftover Chrome: it would carry another run's profile (a PIN, a vault).
try { await fetch(`http://${HOST}:${DBG}/json/version`); console.error(`ABORT: something already listens on ${HOST}:${DBG} — kill the stale Chrome first.`); process.exit(2); } catch (e) {}
const server = spawn('python3', ['-m', 'http.server', String(HTTP), '--bind', HOST, '--directory', DIR], { stdio: 'ignore' });
const profile = mkdtempSync(join(tmpdir(), 'nb-back-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--remote-debugging-address=${HOST}`,
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check',
  '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', 'about:blank'], { stdio: 'ignore' });
function cleanup() { try { chrome.kill(); } catch (e) {} try { server.kill(); } catch (e) {} try { rmSync(profile, { recursive: true, force: true }); } catch (e) {} }
process.on('exit', cleanup);

let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) {
  try { wsUrl = (await (await fetch(`http://${HOST}:${DBG}/json/version`)).json()).webSocketDebuggerUrl; } catch (e) { await sleep(100); }
}
for (let i = 0; i < 50; i++) { try { await fetch(BASE); break; } catch (e) { await sleep(100); } }

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

// Installed before the app's own script on every document.
const PRELUDE = `
window.__xss=0; window.__bad=[]; window.__lockPaint=0; window.__pops=0;
addEventListener('popstate',()=>{ window.__pops++; });
new MutationObserver(ms=>{
  const app=document.getElementById('app'), lock=document.getElementById('lock');
  for(const m of ms){
    for(const n of m.addedNodes){
      if(n.nodeType===1 && /PWN/.test(n.outerHTML)) __bad.push(n.outerHTML.slice(0,120));
      if(app && lock && !lock.classList.contains('hidden') && (m.target===app || app.contains(m.target))) window.__lockPaint++;
    }
  }
}).observe(document,{childList:true,subtree:true});`;

async function openPage(url) {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const p = { targetId, sessionId, dialogs: [], dialogAccept: true };
  p.send = (m, pa) => send(m, pa, sessionId);
  const h = m => {
    if (m.sessionId !== sessionId) return;
    if (m.method === 'Page.javascriptDialogOpening') { p.dialogs.push(m.params.message); p.send('Page.handleJavaScriptDialog', { accept: p.dialogAccept }); }
  };
  handlers.add(h); p.detach = () => handlers.delete(h);
  await p.send('Page.enable'); await p.send('Runtime.enable');
  await p.send('Page.addScriptToEvaluateOnNewDocument', { source: PRELUDE });
  p.ev = async expr => {
    const r = await p.send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
    return r.result.value;
  };
  await p.send('Page.navigate', { url });
  await waitReady(p);
  return p;
}
async function waitReady(p) {
  for (let i = 0; i < 100; i++) {
    try { if (await p.ev(`document.readyState==='complete' && typeof navState==='function'`)) { await sleep(150); return; } } catch (e) {}
    await sleep(100);
  }
  throw new Error('page never became ready');
}
async function closePage(p) { p.detach(); await send('Target.closeTarget', { targetId: p.targetId }); await sleep(200); }
// Wait until our own traversal queue is empty.
async function settle(p, extra = 120) {
  await sleep(80);
  for (let i = 0; i < 60; i++) { let r; try { r = await p.ev(`typeof _navExpect==='undefined' || (_navExpect===0 && _navQ.length===0)`); } catch (e) { r = true; } if (r) break; await sleep(50); }
  await sleep(extra);
}
// The phone's back: a browser-initiated history traversal, not page JS.
async function systemBack(p) {
  const h = await p.send('Page.getNavigationHistory');
  if (h.currentIndex === 0) return false;
  await p.send('Page.navigateToHistoryEntry', { entryId: h.entries[h.currentIndex - 1].id });
  await sleep(150);
  // An entry pushed by an earlier document (before a reload) is a cross-document load, not a popstate.
  const now = await p.send('Page.getNavigationHistory');
  if (now.entries[now.currentIndex].url.startsWith(`http://${HOST}`)) await waitReady(p);
  await settle(p); return true;
}
async function arrowBack(p) { await p.ev(`document.querySelector('#app [data-back]').click()`); await settle(p); }
const where = p => p.ev(`({v:view.name,p:view.param,s:history.state,hash:location.hash,app:history.length})`);
const at = async (p, name, param = null) => { const w = await where(p); return w.v === name && w.p === param; };
// History state must describe what is on screen.
const consistent = p => p.ev(`(()=>{const s=history.state; if(!s||!s.nb) return 'no nb state';
  const C=navOpenChain(); if(s.g) return C.length?'guard with overlays':'ok';
  if(s.v!==view.name||s.p!==view.param) return 'v/p mismatch '+s.v+'/'+s.p+' vs '+view.name+'/'+view.param;
  if(s.d-_navBase!==C.length) return 'depth '+(s.d-_navBase)+' vs overlays '+C.join(',');
  if(C.length && s.o!==C[C.length-1]) return 'top overlay '+s.o+' vs '+C[C.length-1];
  return 'ok'; })()`);
async function appEntries(p) { const h = await p.send('Page.getNavigationHistory'); return h.entries.slice(0, h.currentIndex + 1).filter(e => e.url.startsWith(`http://${HOST}`)).length; }

const PASS = 'correct horse battery';

// ======================================================================
console.log('\n[setup] seed data');
let p = await openPage(BASE);
await p.ev(`(async()=>{
  const t=Date.now();
  const mk=(id,name)=>({id,name,category:'construction',address:'1 Test St',status:'active',jobType:'',specs:[],photos:[],cover:null,notes:'',createdAt:t,updatedAt:t});
  houses.length=0; houses.push(mk('hA','Alpha'), mk('hB','Bravo'));
  houses[0].notes='alpha site notes'; houses[1].notes='BRAVOSITESECRET';
  notes.length=0;
  notes.push({id:'nA',title:'Alpha note',body:'in alpha',houseId:'hA',important:false,createdAt:t,updatedAt:t});
  notes.push({id:'nL',title:'Loose note',body:'loose body',houseId:null,important:false,createdAt:t,updatedAt:t});
  notes.push({id:'nB',title:'BRAVONOTETITLE',body:'BRAVONOTEBODY',houseId:'hB',important:false,createdAt:t,updatedAt:t});
  const c=document.createElement('canvas'); c.width=c.height=64; const x=c.getContext('2d'); x.fillStyle='#c33'; x.fillRect(0,0,64,64);
  const blob=await new Promise(r=>c.toBlob(r,'image/jpeg'));
  await photoPutFor('hA',{id:'pA',blob,houseId:'hA',createdAt:t}); houses[0].photos.push('pA'); houses[0].cover='pA';
  settings.camIntroSeen=true;
  persist.houses(); persist.notes(); persist.settings(); localStorage.removeItem('notebuilt.lastView');
})()`);
await closePage(p);

// ======================================================================
console.log('\n[1] cold boot: guard + tab');
p = await openPage(BASE);
let w = await where(p);
ok(w.v === 'todo' && w.s.d === 1 && w.hash === '#/todo', 'bare launch lands on To Do at d1', w);
ok(await appEntries(p) === 2, 'stack is [guard, todo]', await appEntries(p));

// ======================================================================
console.log('\n[2] back from every project sub-screen returns to the project');
await p.ev(`document.querySelector('#nav [data-nav="houses"]').click()`); await settle(p);
await p.ev(`document.querySelector('#app [data-house="hA"]').click()`); await settle(p);
ok(await at(p, 'house', 'hA'), 'opened project Alpha');
await p.ev(`document.querySelector('#app [data-open-house-notes="hA"]').click()`); await settle(p);
ok(await at(p, 'housenotes', 'hA'), 'opened site notes');
await arrowBack(p);
ok(await at(p, 'house', 'hA'), 'ARROW back from site notes → project (not the tab)', await where(p));
await p.ev(`document.querySelector('#app [data-open-house-notes="hA"]').click()`); await settle(p);
await systemBack(p);
ok(await at(p, 'house', 'hA'), 'SYSTEM back from site notes → project', await where(p));
await p.ev(`document.querySelector('#app [data-note="nA"]').click()`); await settle(p);
ok(await at(p, 'note', 'nA'), 'opened project note');
await systemBack(p);
ok(await at(p, 'house', 'hA'), 'SYSTEM back from project note → project, not Notes', await where(p));
await p.ev(`document.querySelector('#app [data-note="nA"]').click()`); await settle(p);
await arrowBack(p);
ok(await at(p, 'house', 'hA'), 'ARROW back from project note → project', await where(p));
// Save from a project note
const nBefore = await p.ev(`notes.length`);
await p.ev(`document.querySelector('#app [data-note="nA"]').click()`); await settle(p);
await p.ev(`document.querySelector('#note-title').value='Alpha note edited'`);
await p.ev(`document.querySelector('[data-save-note]').click()`); await settle(p, 300);
ok(await at(p, 'house', 'hA'), 'SAVE on project note → project', await where(p));
ok(await p.ev(`notes.find(n=>n.id==='nA').title`) === 'Alpha note edited' && await p.ev(`notes.length`) === nBefore, 'save persisted, no duplicate', await p.ev(`notes.map(n=>n.title)`));
// New note from inside the project
await p.ev(`document.querySelector('[data-add-note-house="hA"]').click()`); await settle(p);
ok(await at(p, 'note', 'new'), 'new project note editor');
await p.ev(`document.querySelector('#note-title').value='Fresh in Alpha'; document.querySelector('#note-body').value='fresh body'`);
await p.ev(`document.querySelector('[data-save-note]').click()`); await settle(p, 300);
ok(await at(p, 'house', 'hA'), 'SAVE on new project note → project', await where(p));
ok(await p.ev(`notes.filter(n=>n.title==='Fresh in Alpha').length`) === 1, 'new note saved exactly once', await p.ev(`notes.filter(n=>n.title==='Fresh in Alpha').length`));
// Delete from inside the project (confirm accepted)
const freshId = await p.ev(`notes.find(n=>n.title==='Fresh in Alpha').id`);
await p.ev(`document.querySelector('#app [data-note="${freshId}"]').click()`); await settle(p);
p.dialogs.length = 0;
await p.ev(`document.querySelector('[data-del-note]').click()`); await settle(p, 300);
ok(p.dialogs.length === 1 && /Delete this note/.test(p.dialogs[0]), 'delete asked for confirmation', p.dialogs);
ok(await at(p, 'house', 'hA') && !(await p.ev(`notes.some(n=>n.id==='${freshId}')`)), 'DELETE on project note → project, note gone', await where(p));
// Loose note opened from the Notes tab still returns to Notes.
await p.ev(`document.querySelector('#nav [data-nav="notes"]').click()`); await settle(p);
await p.ev(`document.querySelector('#app [data-note="nL"]').click()`); await settle(p);
await p.ev(`document.querySelector('[data-save-note]').click()`); await settle(p, 300);
ok(await at(p, 'notes'), 'SAVE on a loose note → Notes tab', await where(p));
ok(await consistent(p) === 'ok', 'history consistent after section 2', await consistent(p));

// ======================================================================
console.log('\n[3] two-press exit + toast window');
await p.ev(`document.querySelector('#nav [data-nav="todo"]').click()`); await settle(p);
w = await where(p);
ok(w.v === 'todo' && w.s.d === 1, 'tab switch collapsed the stack to d1', w.s);
ok(await appEntries(p) === 2, 'collapsed stack is [guard, todo]', await appEntries(p));
await systemBack(p);
w = await where(p);
ok(w.s.g === 1 && w.v === 'todo', 'first back lands on the guard, view unchanged', w);
ok(await p.ev(`document.getElementById('toast').classList.contains('show') && /back again to exit/.test(document.getElementById('toast').textContent)`), 'toast: press back again to exit');
await sleep(2300);
w = await where(p);
ok(!w.s.g && w.s.d === 1 && w.v === 'todo', 'window expired → tab entry re-pushed', w.s);
await systemBack(p);
ok((await where(p)).s.g === 1, 'after reset, back re-arms the toast');
await p.ev(`document.querySelector('#nav [data-nav="houses"]').click()`); await settle(p);
w = await where(p);
ok(w.v === 'houses' && w.s.d === 1 && !w.s.g, 'nav tap inside the window disarms and leaves the guard', w.s);
await sleep(2300);
ok((await appEntries(p)) === 2 && (await where(p)).s.d === 1, 'no stray push after a disarmed window', await appEntries(p));
// Second press inside the window leaves the app (browser-tab semantics: to about:blank).
await p.ev(`document.querySelector('#nav [data-nav="todo"]').click()`); await settle(p);
await systemBack(p);
await systemBack(p);
const hist = await p.send('Page.getNavigationHistory');
ok(!hist.entries[hist.currentIndex].url.startsWith(`http://${HOST}`), 'second press inside the window leaves the app', hist.entries[hist.currentIndex].url);
await closePage(p);

// ======================================================================
console.log('\n[4] rapid double-back and double tab tap');
p = await openPage(BASE);
await p.ev(`go('houses'); go('house','hA')`); await settle(p);
await p.ev(`openTaskSheet('hA')`); await settle(p);
ok(await consistent(p) === 'ok' && (await where(p)).s.o === 'sheet', 'sheet owns an entry', await where(p));
await p.ev(`history.back(); history.back();`); await settle(p, 300);
w = await where(p);
ok(w.v === 'houses' && !(await p.ev(`!!$mr.innerHTML`)), 'double back = sheet closed + one level up, not two', w);
ok(await consistent(p) === 'ok', 'history consistent after double back', await consistent(p));
await p.ev(`go('house','hA'); go('housenotes','hA')`); await settle(p);
await p.ev(`go('notes'); go('calc');`); await settle(p, 300);
w = await where(p);
ok(w.v === 'calc' && w.s.v === 'calc' && w.s.d === 1 && !w.s.g, 'two quick tab taps from depth 3 → calc at d1', w.s);
ok(await appEntries(p) === 2, 'stack is [guard, calc]', await appEntries(p));
await systemBack(p);
ok((await where(p)).s.g === 1, 'back from calc → exit toast');
await closePage(p);

// ======================================================================
console.log('\n[5] overlays: sheet keeps focused node, viewer, annotate cancel+discard, camera');
p = await openPage(BASE);
await p.ev(`go('notes'); go('note','nL')`); await settle(p);
await p.ev(`(()=>{ const b=document.querySelector('#note-body'); b.focus(); b.value='typed but unsaved'; window.__node=b; })()`);
await p.ev(`openTaskSheet()`); await settle(p);
await systemBack(p);
ok(!(await p.ev(`!!$mr.innerHTML`)), 'back closed the sheet');
ok(await at(p, 'note', 'nL'), 'back with a sheet did not navigate', await where(p));
ok(await p.ev(`document.querySelector('#note-body')===window.__node && window.__node.isConnected && window.__node.value==='typed but unsaved'`), 'focused editor node identity survives (=== same node, value intact)');
ok(await consistent(p) === 'ok', 'consistent after sheet back', await consistent(p));
// scrim close consumes the entry (UI close, not back)
await p.ev(`openTaskSheet()`); await settle(p);
await p.ev(`document.querySelector('[data-scrim]').click()`); await settle(p);
ok(await consistent(p) === 'ok' && !(await where(p)).s.o, 'scrim close consumed the sheet entry', await where(p));
// viewer
await p.ev(`go('houses'); go('house','hA')`); await settle(p);
await p.ev(`openViewer('hA','pA')`); await settle(p);
ok((await where(p)).s.o === 'viewer', 'viewer owns an entry');
await systemBack(p);
ok(await p.ev(`$viewer.classList.contains('hidden')`) && await at(p, 'house', 'hA'), 'back closes the viewer, stays on project', await where(p));
// annotate: keep-editing branch, then discard branch
await p.ev(`openViewer('hA','pA')`); await settle(p);
await p.ev(`openAnnotate()`); await settle(p, 300);
await p.ev(`anUndo.push({fake:1})`);
p.dialogAccept = false; p.dialogs.length = 0;
await systemBack(p); await settle(p, 200);
ok(p.dialogs.length === 1, 'back on dirty annotate asks before discarding', p.dialogs);
ok(!(await p.ev(`$annotate.classList.contains('hidden')`)), 'keep-editing: annotate still open');
ok(await consistent(p) === 'ok' && (await where(p)).s.o === 'annotate', 'keep-editing: history state consistent (annotate entry restored)', [await consistent(p), await where(p)]);
p.dialogAccept = true;
await systemBack(p); await settle(p, 200);
ok(await p.ev(`$annotate.classList.contains('hidden') && !$viewer.classList.contains('hidden')`), 'discard: annotate closed, viewer still open');
ok(await consistent(p) === 'ok' && (await where(p)).s.o === 'viewer', 'discard: consistent, top is viewer', await where(p));
await systemBack(p);
ok(await p.ev(`$viewer.classList.contains('hidden')`) && await at(p, 'house', 'hA') && await consistent(p) === 'ok', 'then back closes the viewer');
// camera
await p.ev(`openCamera('hA')`);
for (let i = 0; i < 40 && !(await p.ev(`!!(cam.stream)`)); i++) await sleep(100);
ok(await p.ev(`!!cam.stream && cam.stream.getTracks().filter(t=>t.readyState==='live').length>=1`), 'viewfinder live (fake device)');
await p.ev(`window.__tracks=cam.stream.getTracks()`);
ok((await where(p)).s.o === 'camera', 'camera owns an entry');
await systemBack(p);
ok(await p.ev(`window.__tracks.every(t=>t.readyState==='ended') && cam.stream===null && !cam.open && cam.torchOn!==true`), 'back tears the stream down: live tracks 1→0, torch off', await p.ev(`window.__tracks.map(t=>t.readyState)`));
ok(await p.ev(`$camera.classList.contains('hidden')`) && await at(p, 'house', 'hA') && await consistent(p) === 'ok', 'camera closed, stayed on project, consistent');

// ======================================================================
console.log('\n[6] auto-save on back');
await p.ev(`go('notes'); go('note','new')`); await settle(p);
await p.ev(`document.querySelector('#note-title').value='Autosaved by back'; document.querySelector('#note-body').value='body text'`);
await systemBack(p); await settle(p, 300);
ok(await p.ev(`JSON.parse(localStorage.getItem('notebuilt.notes')).filter(n=>n.title==='Autosaved by back').length`) === 1, 'system back from a new note persists it exactly once');
await p.ev(`go('houses'); go('house','hA'); go('housenotes','hA')`); await settle(p);
await p.ev(`(()=>{ const t=document.querySelector('[data-house-notes-full]'); t.value='site notes via back'; t.dispatchEvent(new Event('input')); })()`);
await systemBack(p); await sleep(700);
ok(await p.ev(`JSON.parse(localStorage.getItem('notebuilt.houses')).find(h=>h.id==='hA').notes`) === 'site notes via back', 'site notes typed then back → saved');
await closePage(p);

// ======================================================================
console.log('\n[7] vault regression + ceremony absorbs back');
p = await openPage(BASE);
await p.ev(`go('houses'); go('house','hB')`); await settle(p);
await p.ev(`void vaultProtectOn('hB')`); await settle(p);
ok(!(await p.ev(`$vault.classList.contains('hidden')`)) && (await where(p)).s.o === 'vault', 'ceremony open and owns an entry');
await systemBack(p);
ok(!(await p.ev(`$vault.classList.contains('hidden')`)) && await consistent(p) === 'ok', 'back during the ceremony is absorbed, state consistent', await consistent(p));
await p.ev(`$vault.querySelector('[data-v-next]').click()`); await sleep(100);
await p.ev(`$vault.querySelector('#v-p1').value=${JSON.stringify(PASS)}; $vault.querySelector('#v-p2').value=${JSON.stringify(PASS)}; $vault.querySelector('[data-v-next]').click()`); await sleep(100);
await p.ev(`const a=$vault.querySelector('#v-ack'); a.checked=true; a.onchange(); $vault.querySelector('[data-v-next]').click()`);
for (let i = 0; i < 100 && !(await p.ev(`!!$vault.querySelector('#v-vp')`)); i++) await sleep(100);
await p.ev(`$vault.querySelector('#v-vp').value=${JSON.stringify(PASS)}; $vault.querySelector('[data-v-go]').click()`);
for (let i = 0; i < 100 && !(await p.ev(`$vault.classList.contains('hidden')`)); i++) await sleep(100);
await settle(p, 400);
ok(await at(p, 'house', 'hB') && await consistent(p) === 'ok', 'ceremony done → on Bravo, consistent', [await where(p), await consistent(p)]);
const disk = await p.ev(`localStorage.getItem('notebuilt.houses')+localStorage.getItem('notebuilt.notes')`);
ok(!/BRAVOSITESECRET|BRAVONOTEBODY|BRAVONOTETITLE/.test(disk), 'sealed: no Bravo plaintext on disk');
ok(await p.ev(`isEnc(houses.find(h=>h.id==='hB').notes) && isEnc(notes.find(n=>n.id==='nB').body)`), 'sealed fields are ciphertext records');
ok(/BRAVOSITESECRET/.test(await p.ev(`document.getElementById('app').innerText`)), 'unlocked: plaintext on screen');
await p.ev(`vaultRelock()`); await settle(p);
ok(await p.ev(`!!document.querySelector('#app [data-vault-open]')`) && !/BRAVOSITESECRET/.test(await p.ev(`document.getElementById('app').innerText`)), 'relocked: locked gate, no plaintext');
await p.ev(`go('notes')`); await settle(p);
ok(!/BRAVONOTETITLE/.test(await p.ev(`document.getElementById('app').innerText`)), 'hidden from cross-project Notes list');
ok(await p.ev(`vaultUnlock('wrong passphrase here')`) === false, 'wrong passphrase rejected');
ok(await p.ev(`vaultUnlock(${JSON.stringify(PASS)})`) === true, 'right passphrase opens');
await p.ev(`go('houses'); go('house','hB')`); await settle(p, 400);
ok(/BRAVOSITESECRET/.test(await p.ev(`document.getElementById('app').innerText`)), 'plaintext intact after unlock');
await p.ev(`go('note','nB')`); await settle(p, 300);
ok(await at(p, 'note', 'nB'), 'on the protected note (unlocked)');
await closePage(p);   // process death

// ======================================================================
console.log('\n[8] process death: resume, protected resumes locked');
p = await openPage(BASE);
w = await where(p);
ok(w.v === 'note' && w.p === 'nB', 'bare relaunch resumes the last view from the device key', w);
ok(await p.ev(`!!document.querySelector('#app [data-vault-open]') && !!document.querySelector('#app .lock-hero')`), 'protected note resumes on the LOCKED gate');
const txt = await p.ev(`document.getElementById('app').innerText + document.getElementById('app').innerHTML`);
ok(!/BRAVONOTEBODY|BRAVOSITESECRET/.test(txt), 'zero decrypted content in $app');
ok(await appEntries(p) === 4, 'seeded stack [guard, houses, house/hB, note/nB]', await appEntries(p));
await systemBack(p);
ok(await at(p, 'house', 'hB'), 'back from the resumed note → its project (seeded parent)', await where(p));
await systemBack(p);
ok(await at(p, 'houses'), 'back again → Projects', await where(p));
await closePage(p);
// hash URL restore
p = await openPage(BASE + '#/housenotes/hA');
ok(await at(p, 'housenotes', 'hA'), 'hash URL restores site notes');
await systemBack(p);
ok(await at(p, 'house', 'hA'), 'back → seeded project', await where(p));
await closePage(p);
// reload keeps the stack (the update banner's Refresh)
p = await openPage(BASE);
await p.ev(`go('houses'); go('house','hA'); go('housenotes','hA')`); await settle(p);
await p.send('Page.reload'); await waitReady(p); await settle(p);
ok(await at(p, 'housenotes', 'hA') && await appEntries(p) === 4, 'reload keeps view and stack', [await where(p), await appEntries(p)]);
await systemBack(p);
ok(await at(p, 'house', 'hA'), 'back after reload → project', [await where(p), await p.ev('window.__pops'), (await p.send('Page.getNavigationHistory')).currentIndex]);
await systemBack(p);
ok(await at(p, 'houses') && await consistent(p) === 'ok', 'and again → Projects: rapid-nav entries were not mislabeled', await where(p));
await closePage(p);

// ======================================================================
console.log('\n[9] PIN gate: back shows nothing, paints nothing');
p = await openPage(BASE);
await p.ev(`(async()=>{ settings.pinSalt=randSalt(); settings.pinHash=await sha('1357'+settings.pinSalt); persist.settings(); })()`);
await p.ev(`go('houses'); go('house','hA')`); await settle(p);
await closePage(p);
p = await openPage(BASE);
ok(await p.ev(`!$lock.classList.contains('hidden')`), 'PIN gate up on relaunch');
ok(await p.ev(`document.getElementById('app').childElementCount`) === 0, '$app has zero children behind the keypad');
ok(await appEntries(p) === 1, 'history at the PIN gate is ONE app entry — back can only exit', await appEntries(p));
ok(await p.ev(`history.state.unseeded===1`), 'chain not seeded while locked');
await sleep(600);
ok(await p.ev(`window.__lockPaint`) === 0 && await p.ev(`document.getElementById('app').childElementCount`) === 0, 'zero $app mutations while the lock is up (DOM, not visibility)', await p.ev(`window.__lockPaint`));
try { await p.ev(`history.back()`); } catch (e) {}   // navigates the target away mid-evaluate
await sleep(500);
const stillHere = (await p.send('Page.getNavigationHistory'));
// At the app's first entry: in a tab this goes to the prior page; in the installed PWA it is a native exit.
ok(!stillHere.entries[stillHere.currentIndex].url.startsWith(`http://${HOST}`), 'back at the PIN gate leaves the app — one press, no walk');
await p.send('Page.navigateToHistoryEntry', { entryId: stillHere.entries[stillHere.currentIndex + 1].id }); await sleep(300); await waitReady(p);
ok(await p.ev(`!$lock.classList.contains('hidden') && document.getElementById('app').childElementCount===0 && window.__lockPaint===0`), 're-entering: PIN gate again, $app still empty');
// unlock with the keypad
for (const d of '1357') await p.ev(`document.querySelector('#lock [data-k="${d}"]').click()`);
for (let i = 0; i < 40 && !(await p.ev(`$lock.classList.contains('hidden')`)); i++) await sleep(100);
await settle(p, 300);
ok(await at(p, 'house', 'hA') && await appEntries(p) === 3, 'after PIN: resumed project, stack seeded', [await where(p), await appEntries(p)]);
await systemBack(p);
ok(await at(p, 'houses'), 'back → Projects');
await p.ev(`(async()=>{ settings.pinHash=null; settings.pinSalt=null; persist.settings(); })()`);
await closePage(p);

// ======================================================================
console.log('\n[10] hostile hash / device key corpus');
const corpus = [
  `#/house/"><img src=x onerror="__xss=1" data-x=PWN>`,
  `#/house/hA"><img src=x onerror=__xss=1 PWN>`,
  `#/__proto__`, `#/constructor`, `#/toString`, `#/note/../hA`, `#/house/zzzz-unknown`,
  `#/house/` + 'a'.repeat(500), `#%2Fhouse%2FhA`, `#/HOUSE/hA`, `#/settings/extra`,
  `#/note/<script>__xss=1</script>PWN`, `#/house/hA/extra`, `#javascript:__xss=1//PWN`, `#/house/hA%22%3E%3Cimg%20src=x%20onerror=__xss=1%3EPWN`,
];
for (const h of corpus) {
  p = await openPage(BASE + h);
  await sleep(200);
  const r = await p.ev(`({v:view.name,p:view.param,hash:location.hash,xss:window.__xss,bad:window.__bad.length,html:/PWN/.test(document.getElementById('app').innerHTML+document.getElementById('modal-root').innerHTML)})`);
  ok(r.v === 'todo' && r.p === null && r.hash === '#/todo' && r.xss === 0 && r.bad === 0 && !r.html, 'hostile hash → To Do, no sink: ' + h.slice(0, 50), r);
  await closePage(p);
}
p = await openPage(BASE);
await p.ev(`localStorage.setItem('notebuilt.lastView', '#/house/"><img src=x onerror=__xss=1>PWN')`);
await closePage(p);
p = await openPage(BASE);
ok(await p.ev(`view.name==='todo' && window.__xss===0 && window.__bad.length===0`), 'hostile device key → To Do');
await closePage(p);

// ======================================================================
console.log(`\n${pass} passed, ${fail} failed`);
if (fail) console.log('FAILED:\n  ' + failures.join('\n  '));
ws.close(); cleanup();
process.exit(fail ? 1 : 0);
