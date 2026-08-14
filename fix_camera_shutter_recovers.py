#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — a failed capture must not brick the shutter
Run from the same folder as index.html:
    python3 fix_camera_shutter_recovers.py

FOUND WHILE PROVING THE FLASH `finally`
----------------------------------------
`camShoot()` disables the shutter on entry and re-enables it on the
"could not capture that frame" path — but a capture that THROWS skips that
line entirely and the exception leaves the function. The shutter stays
disabled, the viewfinder stays live, and the camera looks frozen until it is
closed and reopened. On a jobsite that is a lost visit.

Proven in a browser with a throwing capture: the error propagates and the
button never comes back.

This is pre-existing — it predates the tri-state flash and was reachable
before it. It surfaces now because the flash work put a `finally` around the
capture for the lamp, and the shutter belongs in exactly the same place for
exactly the same reason: it is state that must be released whether or not the
capture worked.

THE FIX
-------
Re-enable the shutter in that same `finally`, and report the failure rather
than letting it vanish as an unhandled rejection. Idempotent on the success
path, where `camDrawReview()` replaces the whole control strip a moment
later, and harmless on the null-blob path, which already re-enables it.

The re-entry latch (`cam.saving || cam.shot`) is untouched, so re-enabling
the button cannot produce a second record for one frame.

Backs up first, exact-match anchors asserted ==1, node --check, atomic.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")


def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found. Run this from the notebuilt repo folder.")

    text = TARGET.read_text(encoding="utf-8")
    edits = []

    old_fin = """  } finally {
    /* The point of the wrapper: a capture that throws still puts the light
       out. A phone left burning is worse than a photo not taken. */
    if(litForShot) await camSetTorch(false);
  }"""
    new_fin = """  } catch(err){
    /* A capture that throws used to leave the function with the shutter still
       disabled, so the camera looked frozen until it was closed and reopened.
       Say what happened and let the person try again. */
    blob=null;
    toast('Could not capture that frame');
  } finally {
    /* The point of the wrapper: a capture that throws still puts the light
       out. A phone left burning is worse than a photo not taken. The shutter
       belongs here for the same reason — it is state that must be released
       whether or not the capture worked. */
    if(litForShot) await camSetTorch(false);
    if(btn) btn.removeAttribute('disabled');
  }"""
    edits.append((old_fin, new_fin, "camShoot(): release the shutter too"))

    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---- guards ---------------------------------------------------------
    shoot = working[working.find("async function camShoot(){"):working.find("function camRetake()")]
    fin = shoot[shoot.index("} finally {"):]
    if "camSetTorch(false)" not in fin:
        fail("the finally no longer extinguishes the shot-scoped light.")
    if "btn.removeAttribute('disabled')" not in fin:
        fail("the finally does not release the shutter.")
    if "litForShot" not in fin:
        fail("the finally no longer checks whether THIS shot struck the lamp.")
    # The re-entry latch must still be the thing preventing a double record.
    if "if(cam.saving || cam.shot) return;" not in shoot:
        fail("the one-shot-in-flight latch was disturbed.")
    # A thrown capture must not be mistaken for a good frame.
    if "blob=null;" not in shoot[shoot.index("} catch(err){"):shoot.index("} finally {")]:
        fail("a thrown capture could still be treated as a usable frame.")

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")
    print("✅ guard: lamp and shutter both released in the finally; latch untouched")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_shutter_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(["node", "--check", str(js_path)], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check.")
        result = None
    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ one bad frame no longer costs the camera session.")


if __name__ == "__main__":
    main()
