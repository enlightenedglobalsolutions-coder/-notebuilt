#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notebuilt — Backup v3b: say why a re-seal failed in words

Round-trip testing of fix_backup_v3.py turned up one rough edge. When a
protected record in a backup will not open, WebCrypto throws an error
whose entire message is "OperationError", and that word was going
straight into the alert:

    Re-seal failed, so nothing was restored and this device is
    untouched:

    OperationError

The outcome sentence is right and the abort is correct — the device is
genuinely untouched — but "OperationError" tells the person holding the
phone nothing they can act on. This replaces it with a sentence.

Backs up first, exact-match anchor asserted to match once, node --check
before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "BACKUP_V3_RESEAL_COPY"


def fail(msg):
    print(f"\n❌ ABORTED — no changes were made.\n   Reason: {msg}\n")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found in this folder.")
    text = TARGET.read_text(encoding="utf-8")
    if MARKER in text:
        print("✅ Already applied — nothing to do.")
        return
    if "BACKUP_V3" not in text:
        fail("fix_backup_v3.py has not been applied yet — run that first.")

    old = """        }catch(err){
          vaultBusyDone(); reset();
          alert('Re-seal failed, so nothing was restored and this device is untouched:\\n\\n'
                +(err.message||err));
          return;
        }"""
    new = """        }catch(err){
          vaultBusyDone(); reset();
          /* BACKUP_V3_RESEAL_COPY — WebCrypto's whole message for a record that
             will not open is "OperationError", which is no use to anyone
             standing there holding the phone. */
          const why = (err && err.name==='OperationError')
            ? 'a protected record in the backup would not open \\u2014 the file may be damaged'
            : (err.message||err);
          alert('Re-seal failed, so nothing was restored and this device is untouched:\\n\\n'+why);
          return;
        }"""

    count = text.count(old)
    if count != 1:
        fail(f"anchor matched {count} time(s), expected exactly 1.")
    working = text.replace(old, new, 1)

    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"\U0001f5c4  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 1 edit to {TARGET}")

    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        shutil.copy2(backup_path, TARGET)
        fail("no <script> block found after edit — restored from backup.")
    js_path = Path("/tmp/_notebuilt_backup_v3b_check.js")
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

    print("\n✅ Backup v3b applied: the re-seal abort explains itself.")


if __name__ == "__main__":
    main()
