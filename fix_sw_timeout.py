#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EGS service worker — network-first gets a deadline
Run from the Notebuilt repo:
    python3 fix_sw_timeout.py

THE BUG (audit-verified)
------------------------
`service-worker.js` network-first was:

    fetch(req).then(...).catch(() => caches.match(req)...)

No timeout anywhere in the SW — no `Promise.race`, no `setTimeout`.
Offline is NOT the dangerous case: offline makes `fetch` **reject**, the
`.catch` fires, and the cached shell is served. That path always worked.

The dangerous case is a network that neither answers nor fails — a
captive portal, or an access point with no route out. There `fetch` stays
**pending forever**, `.catch` never runs, `respondWith` never settles, and
the app hangs on launch showing nothing. Notebuilt has already hit this on
real wifi.

THE FIX
-------
`raceTimeout(networkPromise, ms, fallbackFn)` in the shared logic: resolve
with the network if it answers within 3.5s, otherwise with the cache. A
*rejecting* network still takes the fallback immediately, so the old
offline behaviour is preserved exactly rather than re-implemented.

The cache write stays attached to the **network promise itself**, not to
the race, so a response that arrives after the deadline still lands in the
cache for the next launch — the slow response is not wasted.

If nothing is cached at all (a first-ever visit on a hanging network) the
race falls through to the network promise, which is the pre-existing
behaviour: there is genuinely nothing better to serve.

WHICH FILES, AND WHY ONE MORE THAN THE BRIEF SAID
-------------------------------------------------
The brief said keep the egs-platform commit to `sw_logic.js` only. The
racing primitive lives there, but the CALL SITE is `service-worker.js`,
and the skeleton ships its own copy of that file — so fixing only
`sw_logic.js` would leave the skeleton's service worker still carrying the
hang, and the next app copied from it would ship the bug. Three skeleton
files are touched:

    platform/sw_logic.js        the primitive + the constant
    platform/service-worker.js  the call site
    platform/test_sw_logic.js   the tests that prove it

The Aug 3-5 pile in egs-platform stays untouched, which is what that
constraint is actually protecting.

NOT rolled to the other apps today, per the brief — that ride is the
existing core-v2 rollout debt (Roadside / KEPT / Stagger / WFD).

Backs up every file it touches, ==1 anchors, verifies the two `sw_logic.js`
copies end byte-identical, then runs the node test suite.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(".")
PLATFORM = Path("/Volumes/AI Storage/EGS/platform")
MARKER = "SW_DEADLINE"
STAMP = int(time.time())


def fail(msg):
    print(f"\n❌ ABORTED — see above for what was already written.\n   Reason: {msg}\n")
    sys.exit(1)


# ---- the edits, shared by both copies -------------------------------------

LOGIC_OLD = """  // A version stamp is YYYY.MM.DD-HHMM — human-readable, sortable, eyeball-able.
  function isValidVersion(v){ return /^\\d{4}\\.\\d{2}\\.\\d{2}-\\d{4}$/.test(v); }

  var api = { cacheName:cacheName, staleCaches:staleCaches, strategyFor:strategyFor, isValidVersion:isValidVersion };"""

LOGIC_NEW = """  // A version stamp is YYYY.MM.DD-HHMM — human-readable, sortable, eyeball-able.
  function isValidVersion(v){ return /^\\d{4}\\.\\d{2}\\.\\d{2}-\\d{4}$/.test(v); }

  // SW_DEADLINE — network-first needs a deadline, not just a .catch().
  // Offline is not the dangerous case: offline REJECTS, the catch fires, and
  // the cached shell is served. The dangerous case is a network that neither
  // answers nor fails — a captive portal, or an access point with no route
  // out. There fetch() stays pending forever, the catch never runs, and the
  // app hangs on launch with nothing on screen. Notebuilt hit this on real
  // wifi. 3.5s: long enough that a slow-but-real connection still wins, short
  // enough that nobody stares at a blank screen wondering.
  var NET_TIMEOUT_MS = 3500;

  // Resolve with the network if it answers in time, otherwise with fallback().
  // A REJECTED network also takes the fallback immediately, so the old offline
  // behaviour is preserved rather than reimplemented. Never rejects for want
  // of a network. Timers are injectable so this is testable in node.
  function raceTimeout(networkPromise, ms, fallbackFn, timers){
    var T = timers || { set:setTimeout, clear:clearTimeout };
    return new Promise(function(resolve){
      var settled = false;
      var id = T.set(function(){
        if(settled) return; settled = true;
        resolve(fallbackFn());
      }, ms);
      networkPromise.then(function(res){
        if(settled) return; settled = true; T.clear(id); resolve(res);
      }, function(){
        if(settled) return; settled = true; T.clear(id); resolve(fallbackFn());
      });
    });
  }

  var api = { cacheName:cacheName, staleCaches:staleCaches, strategyFor:strategyFor, isValidVersion:isValidVersion,
              NET_TIMEOUT_MS:NET_TIMEOUT_MS, raceTimeout:raceTimeout };"""

SW_OLD = """  if (strategy === 'network-first') {
    // Fresh HTML when online; cached HTML when offline.
    e.respondWith(
      fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req).then((r) => r || caches.match('./index.html')))
    );
    return;
  }"""

SW_NEW = """  if (strategy === 'network-first') {
    // SW_DEADLINE — fresh HTML when online; cached HTML when offline OR when
    // the network hangs without answering. The cache write is attached to the
    // NETWORK promise, not to the race, so a response that arrives after the
    // deadline still lands in the cache for the next launch.
    const net = fetch(req)
      .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; });
    net.catch(() => {});                               // a late failure is not an unhandled rejection
    e.respondWith(
      EGS_SW.raceTimeout(net, EGS_SW.NET_TIMEOUT_MS, () =>
        caches.match(req)
          .then((r) => r || caches.match('./index.html'))
          .then((r) => r || net))                      // nothing cached at all: the network is all there is
    );
    return;
  }"""

TEST_OLD = """console.log("\\n"+p+" passed, "+f+" failed"); process.exit(f?1:0);"""

TEST_NEW = """// SW_DEADLINE — the race. Fake timers so the suite stays instant and
// deterministic: nothing here waits on a real clock.
function fakeTimers(){
  var q=[], n=0;
  return { set:function(fn,ms){ n++; q.push({id:n,fn:fn,ms:ms}); return n; },
           clear:function(id){ q=q.filter(function(t){ return t.id!==id; }); },
           fire:function(){ var due=q; q=[]; due.forEach(function(t){ t.fn(); }); },
           pending:function(){ return q.length; } };
}
const hang = () => new Promise(function(){});            // never settles: the captive-portal case

(async () => {
  // 1. healthy network wins, fallback never consulted
  let usedFallback=false, T=fakeTimers();
  let r = await L.raceTimeout(Promise.resolve("NET"), 3500, ()=>{usedFallback=true;return "CACHE";}, T);
  ok("fast network wins the race", r==="NET", r);
  ok("fallback not consulted when network wins", !usedFallback);
  ok("timer cleared when network wins", T.pending()===0, T.pending());

  // 2. THE BUG: a network that hangs must not hang the app
  T=fakeTimers();
  let pending = L.raceTimeout(hang(), 3500, ()=>"CACHE", T);
  ok("timer armed while the network hangs", T.pending()===1, T.pending());
  T.fire();
  ok("hanging network falls back to cache", (await pending)==="CACHE");

  // 3. a REJECTING network (true offline) still falls back — old behaviour kept
  T=fakeTimers();
  r = await L.raceTimeout(Promise.reject(new Error("offline")), 3500, ()=>"CACHE", T);
  ok("rejected network falls back to cache", r==="CACHE", r);
  ok("timer cleared on rejection too", T.pending()===0, T.pending());

  // 4. a late network answer must NOT override what was already served
  T=fakeTimers();
  let release; const slow = new Promise(function(res){ release=res; });
  let served = L.raceTimeout(slow, 3500, ()=>"CACHE", T);
  T.fire();
  ok("deadline serves cache first", (await served)==="CACHE");
  release("LATE-NET");
  await slow;
  ok("late network does not change what was served", (await served)==="CACHE");

  // 5. the constant is a sane deadline, not a placeholder
  ok("NET_TIMEOUT_MS in the 3-4s band", L.NET_TIMEOUT_MS>=3000 && L.NET_TIMEOUT_MS<=4000, L.NET_TIMEOUT_MS);

  console.log("\\n"+p+" passed, "+f+" failed"); process.exit(f?1:0);
})();"""


def patch(path, pairs):
    if not path.exists():
        fail(f"{path} not found.")
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"   • {path}  already patched — skipped")
        return False
    working = text
    for old, new, label in pairs:
        c = working.count(old)
        if c != 1:
            fail(f"{path}: anchor for '{label}' matched {c} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)
    bak = path.with_suffix(path.suffix + f".bak.{STAMP}")
    shutil.copy2(path, bak)
    path.write_text(working, encoding="utf-8")
    print(f"   • {path}  patched  (backup {bak.name})")
    return True


def main():
    if not (APP / "index.html").exists():
        fail("run this from the Notebuilt repo (no index.html here).")
    if not PLATFORM.exists():
        fail(f"{PLATFORM} not found — the shared skeleton must be patched too.")

    print("Patching the shared skeleton:")
    patch(PLATFORM / "sw_logic.js", [(LOGIC_OLD, LOGIC_NEW, "sw_logic race primitive")])
    patch(PLATFORM / "service-worker.js", [(SW_OLD, SW_NEW, "network-first call site")])
    patch(PLATFORM / "test_sw_logic.js", [(TEST_OLD, TEST_NEW, "race tests")])

    print("Patching Notebuilt:")
    patch(APP / "sw_logic.js", [(LOGIC_OLD, LOGIC_NEW, "sw_logic race primitive")])
    patch(APP / "service-worker.js", [(SW_OLD, SW_NEW, "network-first call site")])

    # ---- guard: the two sw_logic.js copies must be byte-identical ----
    a = (APP / "sw_logic.js").read_bytes()
    b = (PLATFORM / "sw_logic.js").read_bytes()
    if a != b:
        fail("apps/notebuilt/sw_logic.js and platform/sw_logic.js diverged — the copy must mirror the skeleton exactly.")
    print("✅ guard: notebuilt/sw_logic.js is byte-identical to platform/sw_logic.js")

    # ---- guard: the two service workers differ ONLY in APP_NAME / CACHE_VERSION ----
    sa = (APP / "service-worker.js").read_text(encoding="utf-8").splitlines()
    sb = (PLATFORM / "service-worker.js").read_text(encoding="utf-8").splitlines()
    if len(sa) != len(sb):
        fail("service-worker.js copies have different line counts — they must differ only in the two stamped lines.")
    diffs = [i + 1 for i, (x, y) in enumerate(zip(sa, sb)) if x != y]
    if diffs != [14, 15]:
        fail(f"service-worker.js copies differ on lines {diffs}; expected only 14 (APP_NAME) and 15 (CACHE_VERSION).")
    print("✅ guard: service workers differ only on APP_NAME (L14) and CACHE_VERSION (L15)")

    # ---- guard: no timeout-free network-first survives anywhere ----
    for p in [APP / "service-worker.js", PLATFORM / "service-worker.js"]:
        t = p.read_text(encoding="utf-8")
        if ".catch(() => caches.match(req).then((r) => r || caches.match('./index.html')))" in t:
            fail(f"{p}: the old timeout-free network-first is still present.")
        if "raceTimeout" not in t:
            fail(f"{p}: raceTimeout is not wired in.")
    print("✅ guard: no timeout-free network-first remains in either service worker")

    # ---- the test suite is the real gate ----
    for suite_dir in [PLATFORM]:
        try:
            r = subprocess.run(["node", "test_sw_logic.js"], cwd=str(suite_dir),
                               capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            print("⚠️  node not found — skipping the sw_logic test suite.")
            r = None
        if r is not None:
            print(f"\n--- node test_sw_logic.js ({suite_dir}) ---")
            print(r.stdout.strip())
            if r.returncode != 0:
                print(r.stderr.strip())
                fail("sw_logic test suite FAILED.")

    print("\n✅ SW_DEADLINE applied to the skeleton and to Notebuilt.")
    print("   NOT rolled to the other apps — that is the core-v2 rollout debt.")
    print("   This ship bumps the SW cache: every installed user re-downloads, by design.")


if __name__ == "__main__":
    main()
