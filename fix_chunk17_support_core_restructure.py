#!/usr/bin/env python3
"""
Notebuilt — Chunk 17: restructure Support & Backup page
Run this from the same folder as your index.html:
    python3 fix_chunk17_support_core_restructure.py

Splits renderSupport() into two clearly-marked pieces:
  - APP-SPECIFIC block (APP_BACKUP_DESC + APP_MONETIZATION) — the only
    part that should ever be edited per app
  - EGS CORE block (egsSupportCoreHtml()) — copy-paste verbatim into
    every future EGS app, never edit the copy inside it

Removes the Founding Member $21 tier and Founding Members' mailing list
entirely (unbacked promises: "never paywalled" when there's no paywall,
"a vote on what's built" with no actual mechanism, an open-ended "forever"
commitment). Replaces with an honest, generic mission statement plus a
per-app pricing/monetization slot.

Notebuilt's APP_MONETIZATION is set to model:'paid' with a placeholder
blurb — edit the price into that blurb once it's decided.

Backs up first, applies edits with exact-match anchors, aborts atomically
if anything doesn't match, and validates JS syntax before finishing.
"""
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

TARGET = Path("index.html")
MARKER = "CHUNK17_SUPPORT_CORE_RESTRUCTURE"  # already-applied guard
PREREQ_MARKER = "CHUNK16_SUPPORT_PAGE"

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

    if PREREQ_MARKER not in text:
        fail("Chunk 16 (Support & Backup page) doesn't look applied yet. Run fix_chunk16_support_page.py first.")

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: Privacy page's link row — drop the Founding Member mention
    # ---------------------------------------------------------------
    old1 = """    <div class="card row" data-go="support" style="cursor:pointer;margin-top:12px"><div class="grow"><div>Support EGS &amp; back up your data</div><div class="muted" style="font-size:13px">Founding Member perks, payment options, export/restore.</div></div><span class="chev">${I.chevronR}</span></div>"""
    new1 = """    <div class="card row" data-go="support" style="cursor:pointer;margin-top:12px"><div class="grow"><div>Support EGS &amp; back up your data</div><div class="muted" style="font-size:13px">Payment options, export/restore, and how EGS works.</div></div><span class="chev">${I.chevronR}</span></div>"""
    edits.append((old1, new1, "Privacy page: drop Founding Member mention"))

    # ---------------------------------------------------------------
    # Edit 2: restructure renderSupport() into APP-SPECIFIC + EGS CORE
    # ---------------------------------------------------------------
    old2 = """function renderSupport(){
  const tabs=PAYMENT_TABS.map(t=>`<button class="btn sm ${t.id===supportTab?'primary':''}" data-pay-tab="${t.id}">${t.label}</button>`).join('');
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Support &amp; Backup</h1></div>
  </div>
  <div class="wrap">
    <div class="sec-head"><span class="label">Back up your data</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Save your projects, photos, notes and to-dos to a file. Keep it safe \\u2014 you can restore it anytime, even on a new phone or after reinstalling.</div>
    <div class="row" style="gap:10px;margin:10px 0 22px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>

    <div class="sec-head"><span class="label">Support EGS</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Enlightened Global Solutions is on a mission to make the world better \\u2014 one job site, one app, one solution at a time. Your contribution lets us focus 100% on that mission.</div>
    <div class="row" data-go="privacy" style="cursor:pointer;margin:6px 0 18px"><span class="muted" style="font-size:13px">\\ud83d\\udd12 Our privacy promise & how we make money \\u2192</span></div>

    <div class="card" style="background:var(--ink-2)">
      <div style="font-weight:600;margin-bottom:6px">\\ud83d\\udce8 Founding Members' list</div>
      <div class="muted" style="font-size:13px;line-height:1.5">Become a Founding Member ($21) and I'll personally add you to the private list \\u2014 a short email only when there's real news: a new app, a real update. Nothing else.</div>
      <div class="muted" style="font-size:11.5px;line-height:1.5;margin-top:8px">You'll get a one-click confirm email (double opt-in). No public signup, no tracking, never sold, leave anytime.</div>
    </div>

    <div class="card" style="margin-top:12px">
      <div style="font-family:var(--serif);font-size:17px;margin-bottom:10px">\\u2605 Founding Member \\u2014 $21 once</div>
      <div class="muted" style="font-size:13.5px;line-height:1.8">
        \\u2713 This app, yours forever \\u2014 never paywalled, never sold, never your data<br>
        \\u2713 Free lifetime trials of every app we build next<br>
        \\u2713 A direct line to the builder<br>
        \\u2713 A vote on what gets built next<br>
        \\u2713 A seat at the table \\u2014 no shareholders, just the tradespeople who use it
      </div>
      <div class="muted" style="font-size:12px;margin-top:10px">Or give any amount below \\u2014 every bit keeps EGS independent.</div>
    </div>

    <div class="row" style="gap:8px;flex-wrap:wrap;margin:18px 0 12px">${tabs}</div>
    <div id="pay-detail">${paymentDetailHtml(supportTab)}</div>

    <div class="muted" style="font-size:12px;text-align:center;margin-top:22px;line-height:1.6">Contributions are voluntary and support EGS operations.<br>Every amount makes a difference. Thank you. \\ud83d\\ude4f</div>
  </div>`;
}"""
    new2 = """/* CHUNK17_SUPPORT_CORE_RESTRUCTURE
   ============================================================
   APP-SPECIFIC — edit only this block when reusing this page in
   a new app. Everything in egsSupportCoreHtml() below is meant
   to be copied verbatim, unedited, into every EGS app.
   ============================================================ */
const APP_BACKUP_DESC = "Save your projects, photos, notes and to-dos to a file. Keep it safe \\u2014 you can restore it anytime, even on a new phone or after reinstalling.";
const APP_MONETIZATION = {
  model: 'paid', // 'paid' or 'free' \\u2014 controls the section label below
  blurb: "Notebuilt is a one-time purchase \\u2014 no subscription, no trial that runs out, no features held hostage after 30 days. Pay once and it's yours, priced like a real tool because it's built to save you real time on the job. [Edit this line with your actual price once it's set.]"
};

function renderSupport(){
  const tabs=PAYMENT_TABS.map(t=>`<button class="btn sm ${t.id===supportTab?'primary':''}" data-pay-tab="${t.id}">${t.label}</button>`).join('');
  return `<div class="topbar">
    <button class="icon-btn" data-back aria-label="Back">${I.back}</button>
    <div class="grow"><span class="eyebrow">${esc(APP_NAME)}</span><h1>Support &amp; Backup</h1></div>
  </div>
  <div class="wrap">
    <div class="sec-head"><span class="label">Back up your data</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">${APP_BACKUP_DESC}</div>
    <div class="row" style="gap:10px;margin:10px 0 22px">
      <button class="btn primary" style="flex:1" data-export>${I.download} Export</button>
      <label class="btn" style="flex:1;text-align:center;display:flex;align-items:center;justify-content:center;gap:8px">${I.upload} Restore<input type="file" accept="application/json,.json" hidden data-import></label>
    </div>

    <div class="sec-head"><span class="label">${APP_MONETIZATION.model==='paid'?'Pricing':'Free, always'}</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">${APP_MONETIZATION.blurb}</div>

    ${egsSupportCoreHtml(tabs)}
  </div>`;
}

/* ============================================================
   EGS CORE \\u2014 SUPPORT SECTION
   Copy this function verbatim into every new EGS app. Do not
   edit the copy below \\u2014 only PAYMENT_CONFIG (near the top of
   the file) should ever change, and only to add real payment
   links.
   ============================================================ */
function egsSupportCoreHtml(tabs){
  return `<div class="sec-head"><span class="label">Support EGS</span><span class="rule"></span></div>
    <div class="card muted" style="font-size:13.5px;line-height:1.6">Enlightened Global Solutions is a one-person, Canadian shop building tools the way I'd want them built \\u2014 privacy-first, no subscriptions, no shortcuts. If this app has been useful to you, a contribution below helps keep it that way.</div>
    <div class="row" data-go="privacy" style="cursor:pointer;margin:6px 0 18px"><span class="muted" style="font-size:13px">\\ud83d\\udd12 Our privacy promise &amp; how we make money \\u2192</span></div>

    <div class="row" style="gap:8px;flex-wrap:wrap;margin:4px 0 12px">${tabs}</div>
    <div id="pay-detail">${paymentDetailHtml(supportTab)}</div>

    <div class="card" style="margin-top:18px;text-align:center;font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--paper-faint)">Built by one person in Canada \\u00b7 no shareholders, no ads, ever<br>Contributions are voluntary. Every bit helps keep EGS independent. Thank you.</div>`;
}"""
    edits.append((old2, new2, "restructure renderSupport() into APP-SPECIFIC + EGS CORE, remove Founding Member tier"))

    # ---------------------------------------------------------------
    # Apply all edits with strict match-count guarding
    # ---------------------------------------------------------------
    working = text
    for old, new, label in edits:
        count = working.count(old)
        if count != 1:
            fail(f"anchor for '{label}' matched {count} time(s), expected exactly 1.")
        working = working.replace(old, new, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied {len(edits)} edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk17_check.js")
    js_path.write_text(scripts[0], encoding="utf-8")
    try:
        result = subprocess.run(
            ["node", "--check", str(js_path)],
            capture_output=True, text=True, timeout=30
        )
    except FileNotFoundError:
        print("⚠️  node not found — skipping syntax check. Review the diff manually.")
        result = None

    if result is not None:
        if result.returncode != 0:
            shutil.copy2(backup_path, TARGET)
            fail(f"JS syntax check failed, restored from backup:\n{result.stderr}")
        print("✅ JS syntax check passed (node --check)")

    print("\n✅ Chunk 17 applied successfully: Support page restructured, Founding Member tier removed.")
    print("   ⚠️  Edit APP_MONETIZATION.blurb near the top of index.html once you've set a real price.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
