#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EGS service worker — fix the Illegal invocation that broke 2026.08.12-1407
Run from the Notebuilt repo:
    python3 fix_sw_illegal_invocation.py

ROOT CAUSE (reproduced in a real browser, 2026-08-13)
-----------------------------------------------------
raceTimeout() defaulted its timers like this:

    var T = timers || { set:setTimeout, clear:clearTimeout };
    ...
    var id = T.set(function(){ ... }, ms);

`T.set(fn, ms)` invokes setTimeout with `this === T` instead of the global.
Web IDL requires the correct receiver, so Chrome throws:

    TypeError: Illegal invocation

and because the call sits inside a `new Promise(function(resolve){...})`
executor, that throw becomes a REJECTION rather than a synchronous error.
`e.respondWith(<rejected promise>)` fails the request. Every navigation,
on a perfectly healthy network. That is ERR_FAILED.

Proof, on the true matched 1407 pair served locally:

    server log:  GET /index.html?repro=1 -> 200      (bytes delivered)
    browser:     chrome-error://chromewebdata/       (worker killed it)

WHY 30 NODE ASSERTIONS MISSED IT
--------------------------------
Node's setTimeout is a plain function and does not care about `this`.
The receiver rule is a Web IDL rule that exists only in browsers. No
amount of node coverage could have caught this — which is the actual
lesson of the incident, not "write more tests."

Two things change so it cannot recur:

1. The default timers are now plain wrappers, so the inner call is an
   ordinary global invocation with the correct receiver.

2. test_sw_logic.js gains a Web-IDL RECEIVER SIMULATION: it replaces
   global.setTimeout with one that throws "Illegal invocation" unless the
   receiver is the global, exactly as a browser does. That makes the bug
   reproducible in node. Verified to FAIL against the broken line and
   PASS against the fix.

A browser gate is still required before shipping — this only makes node
capable of catching THIS class, not of replacing the browser.

WHAT THIS TOUCHES
-----------------
Only sw_logic.js. The call site in service-worker.js was always correct.
Notebuilt currently carries the dc4ea1d ROLLBACK (no deadline at all), so
its two files are restored from da8ebb6 and then the fix is applied, with
a guard that the result is byte-identical to the skeleton.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

APP = Path(".")
PLATFORM = Path("/Volumes/AI Storage/EGS/platform")
MARKER = "SW_TIMER_RECEIVER"
STAMP = int(time.time())

OLD_T = """    var T = timers || { set:setTimeout, clear:clearTimeout };"""

NEW_T = """    /* SW_TIMER_RECEIVER — these MUST be wrappers, not bare references.
       `{set:setTimeout}` then `T.set(fn,ms)` calls setTimeout with `this === T`
       instead of the global, and Web IDL answers that with
       "TypeError: Illegal invocation". Inside this Promise executor that throw
       becomes a REJECTION, respondWith() gets a rejected promise, and every
       navigation dies with ERR_FAILED on a perfectly healthy network — which is
       exactly what 2026.08.12-1407 did to Notebuilt on device.
       Node's setTimeout ignores `this`, so no node test could ever have caught
       it; the receiver rule only exists in browsers. */
    var T = timers || { set:function(fn,ms){ return setTimeout(fn,ms); },
                        clear:function(id){ return clearTimeout(id); } };"""

TEST_OLD = """  // 5. the constant is a sane deadline, not a placeholder
  ok("NET_TIMEOUT_MS in the 3-4s band", L.NET_TIMEOUT_MS>=3000 && L.NET_TIMEOUT_MS<=4000, L.NET_TIMEOUT_MS);"""

TEST_NEW = """  // 5. the constant is a sane deadline, not a placeholder
  ok("NET_TIMEOUT_MS in the 3-4s band", L.NET_TIMEOUT_MS>=3000 && L.NET_TIMEOUT_MS<=4000, L.NET_TIMEOUT_MS);

  // 6. SW_TIMER_RECEIVER — the regression that shipped and broke the flagship.
  // Browsers enforce a Web IDL receiver on setTimeout; node does not, so this
  // simulates it. `{set:setTimeout}` + `T.set(...)` calls with `this === T` and
  // a real browser answers "Illegal invocation" — inside a Promise executor
  // that is a rejection, respondWith() gets it, and the navigation dies.
  // Without this shim node cannot see the bug at all.
  const realSetTimeout = global.setTimeout;
  global.setTimeout = function(fn, ms){
    if (this !== global && this !== undefined && this !== globalThis) {
      throw new TypeError("Illegal invocation");
    }
    return realSetTimeout(fn, ms);
  };
  let receiverOk = false, receiverErr = null;
  try {
    receiverOk = (await L.raceTimeout(Promise.resolve("NET"), 3500, () => "CACHE")) === "NET";
  } catch (e) { receiverErr = e.name + ": " + e.message; }
  let hangOk = false;
  try {
    hangOk = (await L.raceTimeout(new Promise(function(){}), 20, () => "CACHE")) === "CACHE";
  } catch (e) { receiverErr = receiverErr || (e.name + ": " + e.message); }
  global.setTimeout = realSetTimeout;
  ok("default timers survive a Web IDL receiver check (fast path)", receiverOk, receiverErr);
  ok("default timers survive a Web IDL receiver check (deadline path)", hangOk, receiverErr);"""


def fail(msg):
    print(f"\n❌ ABORTED.\n   Reason: {msg}\n")
    sys.exit(1)


def patch(path, pairs, allow_marker_skip=True):
    text = path.read_text(encoding="utf-8")
    if MARKER in text and allow_marker_skip:
        print(f"   • {path.name}  already patched — skipped")
        return
    working = text
    for old, new, label in pairs:
        c = working.count(old)
        if c != 1:
            fail(f"{path}: anchor for '{label}' matched {c} time(s), expected 1.")
        working = working.replace(old, new, 1)
    shutil.copy2(path, path.with_suffix(path.suffix + f".bak.{STAMP}"))
    path.write_text(working, encoding="utf-8")
    print(f"   • {path.name}  patched")


def main():
    if not (APP / "index.html").exists():
        fail("run this from the Notebuilt repo.")

    print("Restoring the deadline into Notebuilt from da8ebb6 (currently rolled back):")
    for name in ["service-worker.js", "sw_logic.js"]:
        cur = APP / name
        shutil.copy2(cur, cur.with_suffix(cur.suffix + f".bak.{STAMP}"))
        r = subprocess.run(["git", "show", f"da8ebb6:{name}"], capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"could not read da8ebb6:{name} — {r.stderr.strip()}")
        cur.write_text(r.stdout, encoding="utf-8")
        print(f"   • {name}  restored from da8ebb6")

    print("Applying the receiver fix:")
    patch(APP / "sw_logic.js", [(OLD_T, NEW_T, "timer receiver")])
    patch(PLATFORM / "sw_logic.js", [(OLD_T, NEW_T, "timer receiver")])
    print("Adding the node regression test:")
    patch(PLATFORM / "test_sw_logic.js", [(TEST_OLD, TEST_NEW, "receiver simulation")])

    # ---- guards ----
    a = (APP / "sw_logic.js").read_bytes()
    b = (PLATFORM / "sw_logic.js").read_bytes()
    if a != b:
        fail("notebuilt/sw_logic.js and platform/sw_logic.js diverged.")
    print("✅ guard: notebuilt/sw_logic.js is byte-identical to platform/sw_logic.js")

    for p in [APP / "sw_logic.js", PLATFORM / "sw_logic.js"]:
        t = p.read_text(encoding="utf-8")
        if "{ set:setTimeout, clear:clearTimeout }" in t:
            fail(f"{p}: the bare-reference timers are still present.")
    print("✅ guard: no bare setTimeout reference remains")

    for p in [APP / "service-worker.js", PLATFORM / "service-worker.js"]:
        if "raceTimeout" not in p.read_text(encoding="utf-8"):
            fail(f"{p}: the deadline call site is missing.")
    print("✅ guard: the deadline is wired in both service workers")

    for f_ in [APP / "sw_logic.js", APP / "service-worker.js",
               PLATFORM / "sw_logic.js", PLATFORM / "service-worker.js",
               PLATFORM / "test_sw_logic.js"]:
        r = subprocess.run(["node", "--check", str(f_)], capture_output=True, text=True)
        if r.returncode != 0:
            fail(f"syntax check failed for {f_}:\n{r.stderr}")
    print("✅ node --check passed on all five files")

    for suite in ["test_sw_logic.js", "test_sw_fetch.js"]:
        r = subprocess.run(["node", suite], cwd=str(PLATFORM), capture_output=True, text=True, timeout=90)
        print(f"\n--- node {suite} ---")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip())
            fail(f"{suite} FAILED.")

    print("\n✅ SW_TIMER_RECEIVER applied. NOW PROVE IT IN A REAL BROWSER before shipping.")


if __name__ == "__main__":
    main()
