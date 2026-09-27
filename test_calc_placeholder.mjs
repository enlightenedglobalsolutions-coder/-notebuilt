// test_calc_placeholder.mjs — real-browser gate for th_nb_calc_placeholder,
// plus the CALC_STEADY regression (the keyboard stays up while typing).
// Headless Google Chrome over raw CDP (Node's built-in WebSocket), no deps.
// Usage: node test_calc_placeholder.mjs <dir containing index.html> [shotDir]
//
// 127.0.0.1 everywhere, never "localhost" (python binds IPv4; Chrome tries ::1).
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const DIR = process.argv[2], SHOTS = process.argv[3];
const HOST = '127.0.0.1', HTTP = 8767, DBG = 9335;
const BASE = `http://${HOST}:${HTTP}/index.html`;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const sleep = ms => new Promise(r => setTimeout(r, ms));
let pass = 0, fail = 0; const failures = [];
function ok(c, name, detail) {
  if (c) { pass++; console.log('  PASS', name); }
  else { fail++; failures.push(name); console.log('  FAIL', name, detail !== undefined ? '→ ' + JSON.stringify(detail) : ''); }
}

try { await fetch(`http://${HOST}:${DBG}/json/version`); console.error(`ABORT: something already listens on ${HOST}:${DBG}`); process.exit(2); } catch (e) {}
const server = spawn('python3', ['-m', 'http.server', String(HTTP), '--bind', HOST, '--directory', DIR], { stdio: 'ignore' });
const profile = mkdtempSync(join(tmpdir(), 'nb-calc-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${DBG}`, `--remote-debugging-address=${HOST}`,
  `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--window-size=390,844', 'about:blank'], { stdio: 'ignore' });
const cleanup = () => { try { chrome.kill(); } catch (e) {} try { server.kill(); } catch (e) {} try { rmSync(profile, { recursive: true, force: true }); } catch (e) {} };
process.on('exit', cleanup);

let wsUrl;
for (let i = 0; i < 100 && !wsUrl; i++) { try { wsUrl = (await (await fetch(`http://${HOST}:${DBG}/json/version`)).json()).webSocketDebuggerUrl; } catch (e) { await sleep(100); } }
for (let i = 0; i < 50; i++) { try { await fetch(BASE); break; } catch (e) { await sleep(100); } }
const ws = new WebSocket(wsUrl); await new Promise(r => ws.addEventListener('open', r));
let mid = 0; const pend = new Map();
ws.addEventListener('message', e => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { const { res, rej } = pend.get(m.id); pend.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); } });
const send = (method, params = {}, sessionId) => { const id = ++mid; ws.send(JSON.stringify({ id, method, params, sessionId })); return new Promise((res, rej) => pend.set(id, { res, rej })); };

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const ps = (m, pa) => send(m, pa, sessionId);
await ps('Page.enable'); await ps('Runtime.enable');
await ps('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
const ev = async x => { const r = await ps('Runtime.evaluate', { expression: x, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text); return r.result.value; };
await ps('Page.navigate', { url: BASE });
for (let i = 0; i < 100; i++) { try { if (await ev(`document.readyState==='complete' && typeof renderCalc==='function'`)) break; } catch (e) {} await sleep(100); }
await sleep(300);
await ev(`go('calc')`); await sleep(200);

const MODES = ['tape', 'md', 'bf', 'area', 'sq'];
const setMode = async m => { await ev(`calcClear(); document.querySelector('[data-calc-mode="${m}"]').click()`); await sleep(120); };
const setUnits = async u => { await ev(`document.querySelector('[data-units-set="${u}"]').click()`); await sleep(120); };
const hex = h => { const n = parseInt(h.slice(1), 16); return `rgb(${n >> 16 & 255}, ${n >> 8 & 255}, ${n & 255})`; };

// ---------------------------------------------------------------- wording
console.log('\n[1] empty boxes draw no digit — every mode, both unit systems');
for (const units of ['imperial', 'metric']) {
  await setUnits(units);
  for (const m of MODES) {
    await setMode(m);
    const boxes = await ev(`[...document.querySelectorAll('#app .meas input')].map(i=>({k:[...i.attributes].map(a=>a.name).find(n=>n.startsWith('data-meas-')),v:i.value,ph:i.placeholder}))`);
    const bad = boxes.filter(b => b.v !== '' || (b.k === 'data-meas-frac' ? b.ph !== '3/8…' : b.ph !== ''));
    ok(boxes.length >= 2 && !bad.length, `${units} ${m}: ${boxes.length} boxes empty, ft/in/m/cm blank, frac "3/8…"`, bad);
  }
}
await setUnits('imperial');
for (const op of ['*', '/']) {
  await setMode('md'); await ev(`document.querySelector('[data-calc-op="${op}"]').click()`); await sleep(100);
  const r = await ev(`(()=>{const i=document.querySelector('#c-num');return {v:i.value,ph:i.placeholder,label:i.closest('.field').querySelector('label').textContent}})()`);
  ok(r.v === '' && r.ph === 'how many', `${r.label}: placeholder "how many", not a number`, r);
}

// ---------------------------------------------------------------- dimming
console.log('\n[2] placeholder colour is the dim token, not text colour — both themes');
for (const [theme, want] of [['dark', '#7C7A74'], ['light', '#87847C']]) {
  await ev(`nbSetTheme('${theme}'); render()`); await sleep(150);
  await setMode('md');
  const c = await ev(`(()=>{const i=document.querySelector('#app [data-meas-frac]');const p=getComputedStyle(i,'::placeholder');return {ph:p.color,op:p.opacity,text:getComputedStyle(i).color}})()`);
  ok(c.ph === hex(want) && c.op === '1', `${theme}: ::placeholder is ${want} at opacity 1`, c);
  ok(c.ph !== c.text, `${theme}: placeholder colour differs from typed-value colour`, c);
  if (SHOTS) {
    const { data } = await ps('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(SHOTS, `calc-${theme}-empty.png`), Buffer.from(data, 'base64'));
    await ev(`(()=>{const i=document.querySelector('#app [data-meas-ft]'); i.value='0'; i.dispatchEvent(new Event('input'));})()`); await sleep(100);
    const s2 = await ps('Page.captureScreenshot', { format: 'png' });
    writeFileSync(join(SHOTS, `calc-${theme}-typed-zero.png`), Buffer.from(s2.data, 'base64'));
  }
}
await ev(`nbSetTheme('system'); render()`); await sleep(150);

// ---------------------------------------------------------------- CALC_STEADY
console.log('\n[3] CALC_STEADY — the keyboard stays up: same node, focus kept, every keystroke');
async function typeInto(sel, text, label) {
  await ev(`(()=>{const i=document.querySelector(${JSON.stringify(sel)}); i.focus(); window.__n=i;})()`);
  let lost = null;
  for (const ch of text) {
    await ps('Input.insertText', { text: ch }); await sleep(40);
    const s = await ev(`({same:document.querySelector(${JSON.stringify(sel)})===window.__n, conn:window.__n.isConnected, focus:document.activeElement===window.__n, v:window.__n.value})`);
    if (!s.same || !s.conn || !s.focus) { lost = { ch, ...s }; break; }
  }
  const v = await ev(`window.__n.value`);
  ok(!lost && v === text, `${label}: "${text}" typed, node === and focused after every key`, lost || v);
}
for (const units of ['imperial', 'metric']) {
  await setUnits(units);
  for (const m of MODES) {
    await setMode(m);
    const sels = await ev(`[...document.querySelectorAll('#app .meas input')].map(i=>'#app [data-meas="'+i.closest('.meas').dataset.meas+'"] ['+[...i.attributes].map(a=>a.name).find(n=>n.startsWith('data-meas-'))+']')`);
    for (const sel of sels) await typeInto(sel, sel.includes('frac') ? '3/8' : '12', `${units} ${m} ${sel.split('[').pop().replace(']', '')}`);
  }
}
await setUnits('imperial');
for (const op of ['*', '/']) {
  await setMode('md');
  await typeInto('#app [data-meas-ft]', '10', `md${op} first measurement`);
  await ev(`document.querySelector('[data-calc-op="${op}"]').click()`); await sleep(100);
  await typeInto('#c-num', '3.5', op === '*' ? 'TIMES field' : 'DIVIDE BY field');
  const res = await ev(`document.querySelector('.cresult .cbig').textContent`);
  ok(res && !/—|^\s*$/.test(res), `result computed with the keyboard still up (${res.trim()})`, res);
}

console.log(`\n${pass} passed, ${fail} failed`);
if (fail) console.log('FAILED:\n  ' + failures.join('\n  '));
ws.close(); cleanup(); process.exit(fail ? 1 : 0);
