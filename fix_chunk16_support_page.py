#!/usr/bin/env python3
"""
Notebuilt — Chunk 16: Support & Backup page (matches WFD's pattern)
Run this from the same folder as your index.html:
    python3 fix_chunk16_support_page.py

Adds a dedicated "Support & Backup" screen combining:
  - Back Up Your Data (Export/Restore — moved here from Settings)
  - Support EGS (mission blurb, link to Privacy, Founding Members list,
    $21 Founding Member tier adapted for trade workers)
  - Payment method tabs: Interac (real details), Bitcoin, Credit Card,
    PayPal, Wise

Settings now links to this page instead of holding Export/Restore inline.
The Privacy page links here too, and this page links back to Privacy —
matching WFD's cross-linking.

IMPORTANT — before this is genuinely live, edit the PAYMENT_CONFIG block
near the top of index.html and fill in your real BTC address, Stripe
payment link, PayPal link, and Wise link. Interac is already filled in
with your real details (egspay.pay@gmail.com, memo "Notebuilt Donation").

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
MARKER = "CHUNK16_SUPPORT_PAGE"  # already-applied guard

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

    edits = []  # list of (old, new, label)

    # ---------------------------------------------------------------
    # Edit 1: constants — PAYMENT_CONFIG + PAYMENT_TABS, right after APP_NAME
    # ---------------------------------------------------------------
    old1 = 'const APP_NAME = "Notebuilt";   /* <-- change here + in manifest.webmanifest + <title> to rename */'
    new1 = """const APP_NAME = "Notebuilt";   /* <-- change here + in manifest.webmanifest + <title> to rename */
/* CHUNK16_SUPPORT_PAGE
   Fill in your real BTC / Stripe / PayPal / Wise values below.
   Interac is already your real EGS details. */
const PAYMENT_CONFIG = {
  interacEmail: 'egspay.pay@gmail.com',
  interacMemo: 'Notebuilt Donation',
  btc: 'YOUR_BTC_ADDRESS',
  stripe: 'STRIPE_PAYMENT_LINK',
  paypal: 'PAYPAL_DONATE_LINK',
  wise: 'WISE_PAYMENT_LINK'
};
const PAYMENT_TABS = [
  {id:'interac', label:'\\ud83c\\udfe6 Interac'},
  {id:'btc', label:'\\u20bf Bitcoin'},
  {id:'card', label:'\\ud83d\\udcb3 Credit Card'},
  {id:'paypal', label:'PayPal'},
  {id:'wise', label:'Wise'}
];
let supportTab = 'interac';"""
    edits.append((old1, new1, "constants: PAYMENT_CONFIG + PAYMENT_TABS + supportTab"))

    # ---------------------------------------------------------------
    # Edit 2: render dispatch table — add the 'support' view
    # ---------------------------------------------------------------
    old2 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch,
            housenotes:renderHouseNotes,privacy:renderPrivacy})[view.name]||renderToday;"""
    new2 = """  const r=({today:renderToday,houses:renderHouses,house:renderHouse,notes:renderNotes,
            note:renderNote,settings:renderSettings,search:renderSearch,
            housenotes:renderHouseNotes,privacy:renderPrivacy,support:renderSupport})[view.name]||renderToday;"""
    edits.append((old2, new2, "render dispatch: add support view"))

    # ---------------------------------------------------------------
    # Edit 3: renderSettings() — replace inline Export/Restore with a link row
    # ---------------------------------------------------------------
    old3 = """    <div class="sec-head"><span class="label">Your data</span><span class="rule"></span></div>
    <div class="card"><div class="muted" style="font-size:13.5px;line-height:1.5">Everything lives on this device. Nothing is uploaded. Export a backup file you keep — that's your copy forever.</div></div>
    <button class="btn block" data-export>${I.download} Export backup</button>
    <label class="btn block" style="margin-top:10px">${I.upload} Restore from backup<input type="file" accept="application/json,.json" hidden data-import></label>"""
    new3 = """    <div class="sec-head"><span class="label">Support &amp; Backup</span><span class="rule"></span></div>
    <div class="card row" data-go="support" style="cursor:pointer"><div class="grow"><div>Support &amp; Backup</div><div class="muted" style="font-size:13px">Export/restore your data, and support EGS.</div></div><span class="chev">${I.chevronR}</span></div>"""
    edits.append((old3, new3, "renderSettings(): replace inline backup UI with link row"))

    # ---------------------------------------------------------------
    # Edit 4: renderPrivacy() — reciprocal link to Support, then add
    # renderSupport() / paymentDetailHtml() / bindCopyButtons() right after
    # ---------------------------------------------------------------
    old4 = """    <div class="card" style="margin-top:6px;text-align:center;font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--paper-faint)">Enlightened Global Solutions · Built in Canada<br>Read the code · check for yourself</div>
  </div>`;
}"""
    new4 = """    <div class="card row" data-go="support" style="cursor:pointer;margin-top:12px"><div class="grow"><div>Support EGS &amp; back up your data</div><div class="muted" style="font-size:13px">Founding Member perks, payment options, export/restore.</div></div><span class="chev">${I.chevronR}</span></div>

    <div class="card" style="margin-top:6px;text-align:center;font-family:var(--mono);font-size:11px;letter-spacing:.05em;color:var(--paper-faint)">Enlightened Global Solutions · Built in Canada<br>Read the code · check for yourself</div>
  </div>`;
}

/* ============================================================
   SUPPORT & BACKUP
   ============================================================ */
function paymentDetailHtml(tab){
  if(tab==='interac'){
    return `<div class="card">
      <div style="font-weight:600;margin-bottom:10px">Interac e-Transfer (Canada)</div>
      <div class="row" style="margin-bottom:8px"><div class="grow muted" style="font-size:13px">Send to email</div></div>
      <div class="row" style="margin-bottom:8px"><b style="font-size:14px">${PAYMENT_CONFIG.interacEmail}</b><button class="btn sm" data-copy="${PAYMENT_CONFIG.interacEmail}">Copy</button></div>
      <div class="row" style="margin-bottom:6px"><div class="grow muted" style="font-size:13px">Message / memo</div><b style="font-size:13px">${PAYMENT_CONFIG.interacMemo}</b></div>
      <div class="row"><div class="grow muted" style="font-size:13px">Auto-deposit</div><b style="font-size:13px;color:var(--done)">Enabled</b></div>
    </div>
    <div class="muted" style="font-size:12.5px;text-align:center;margin-top:10px;line-height:1.5">Open your Canadian bank app \\u2192 Interac e-Transfer \\u2192 Send to the email above.<br>No password needed if auto-deposit is enabled. \\ud83c\\udf41</div>`;
  }
  if(tab==='btc'){
    return `<div class="card">
      <div style="font-weight:600;margin-bottom:10px">Bitcoin</div>
      <div class="mono" style="font-size:12.5px;word-break:break-all;color:var(--paper-dim)">${PAYMENT_CONFIG.btc}</div>
      <button class="btn sm block" style="margin-top:10px" data-copy="${PAYMENT_CONFIG.btc}">Copy address</button>
    </div>
    <div class="muted" style="font-size:12.5px;text-align:center;margin-top:10px">Send BTC to the address above from your wallet app.</div>`;
  }
  if(tab==='card'){
    return `<a class="btn primary block" href="${PAYMENT_CONFIG.stripe}" target="_blank" rel="noopener">Open secure checkout</a>
    <div class="muted" style="font-size:12.5px;text-align:center;margin-top:10px">Opens a secure checkout page in your browser. Card details never touch this app.</div>`;
  }
  if(tab==='paypal'){
    return `<a class="btn primary block" href="${PAYMENT_CONFIG.paypal}" target="_blank" rel="noopener">Donate via PayPal</a>
    <div class="muted" style="font-size:12.5px;text-align:center;margin-top:10px">Opens PayPal in your browser.</div>`;
  }
  if(tab==='wise'){
    return `<a class="btn primary block" href="${PAYMENT_CONFIG.wise}" target="_blank" rel="noopener">Send via Wise</a>
    <div class="muted" style="font-size:12.5px;text-align:center;margin-top:10px">Best for international transfers.</div>`;
  }
  return '';
}

function bindCopyButtons(scope){
  scope.querySelectorAll('[data-copy]').forEach(b=>b.onclick=async()=>{
    try{ await navigator.clipboard.writeText(b.dataset.copy); toast('Copied'); }
    catch(e){ toast('Could not copy \\u2014 long-press the text to select it instead'); }
  });
}

function renderSupport(){
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
    edits.append((old4, new4, "add renderSupport() + paymentDetailHtml() + bindCopyButtons() + reciprocal Privacy link"))

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
    # Edit 5 (post-pass): goBack() — support returns to Settings
    # ---------------------------------------------------------------
    old5 = "  const to = ({house:'houses', note:'notes', search:'today', privacy:'settings'})[view.name] || 'today';"
    new5 = "  const to = ({house:'houses', note:'notes', search:'today', privacy:'settings', support:'settings'})[view.name] || 'today';"
    count5 = working.count(old5)
    if count5 != 1:
        fail(f"anchor for 'goBack(): support->settings mapping' matched {count5} time(s), expected exactly 1.")
    working = working.replace(old5, new5, 1)

    # ---------------------------------------------------------------
    # Edit 6 (post-pass): bind() — wire payment tabs + copy buttons
    # ---------------------------------------------------------------
    old6 = "  const imp=$app.querySelector('[data-import]'); if(imp) imp.onchange=importData;"
    new6 = """  const imp=$app.querySelector('[data-import]'); if(imp) imp.onchange=importData;
  $app.querySelectorAll('[data-pay-tab]').forEach(b=>b.onclick=()=>{
    supportTab=b.dataset.payTab;
    $app.querySelectorAll('[data-pay-tab]').forEach(x=>x.classList.toggle('primary',x.dataset.payTab===supportTab));
    const detail=document.getElementById('pay-detail'); if(detail){ detail.innerHTML=paymentDetailHtml(supportTab); bindCopyButtons(detail); }
  });
  bindCopyButtons($app);"""
    count6 = working.count(old6)
    if count6 != 1:
        fail(f"anchor for 'bind(): wire payment tabs + copy buttons' matched {count6} time(s), expected exactly 1.")
    working = working.replace(old6, new6, 1)

    # ---------------------------------------------------------------
    # Backup, then write
    # ---------------------------------------------------------------
    backup_path = TARGET.with_suffix(TARGET.suffix + f".bak.{int(time.time())}")
    shutil.copy2(TARGET, backup_path)
    print(f"🗄  Backup saved to {backup_path}")

    TARGET.write_text(working, encoding="utf-8")
    print(f"✏️  Applied 6 edits to {TARGET}")

    # ---------------------------------------------------------------
    # Validate JS syntax with node -c on extracted <script> blocks
    # ---------------------------------------------------------------
    scripts = re.findall(r"<script>(.*?)</script>", working, re.S)
    if not scripts:
        fail("no <script> block found after edit — this shouldn't happen.")
    js_path = Path("/tmp/_notebuilt_chunk16_check.js")
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

    print("\n✅ Chunk 16 applied successfully: Support & Backup page added.")
    print("   ⚠️  Remember to edit PAYMENT_CONFIG near the top of index.html and fill in")
    print("      your real BTC address, Stripe link, PayPal link, and Wise link.")
    print("   Next: bump the service-worker cache name, push, and reopen the installed app twice.")

if __name__ == "__main__":
    main()
