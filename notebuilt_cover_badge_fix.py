#!/usr/bin/env python3
"""
Notebuilt fix-script #2 — visible "Change cover" badge on the project hero.

RUN THIS *AFTER* notebuilt_sorted_cover_fix.py (the Sorted engine must already
be present). It makes the existing tap-to-change-cover feature discoverable by
adding a small "Change cover" pill on the cover image, shown whenever the
project has photos. Tapping anywhere on the hero (badge included) still opens
the picker — the badge is purely a visual affordance.

SAFETY: backs up first; every anchor must match exactly once or it aborts and
changes nothing; safe to re-run (exits cleanly if already applied).

USAGE:
  python3 notebuilt_cover_badge_fix.py "/Volumes/AI Storage/-notebuilt/index.html"
  (defaults to ./index.html if no path given)
"""

import sys, time, shutil

PATH = sys.argv[1] if len(sys.argv) > 1 else "index.html"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

# ---- prerequisite + idempotency guards --------------------------------------
if "SORTED ENGINE START" not in src:
    print("ABORTED — the Sorted engine isn't in this file yet.")
    print("Run notebuilt_sorted_cover_fix.py first, then this one.")
    sys.exit(1)

if "cover-edit-badge" in src:
    print("Already applied (Change-cover badge present). Nothing to do.")
    sys.exit(0)

edits = []  # (label, old, new)

# ---- 1. CSS for the badge (placed right after the Sorted picker styles) -----
css_anchor = "  .sorted-star svg{width:16px;height:16px}\n"
css_add = css_anchor + """  /* "Change cover" affordance on the project hero */
  .cover-edit-badge{
    position:absolute;right:8px;bottom:8px;
    display:inline-flex;align-items:center;gap:5px;
    padding:5px 10px;border-radius:999px;
    background:rgba(21,24,29,.78);color:var(--brass);
    font-size:12px;font-weight:600;letter-spacing:.02em;
    pointer-events:none;
  }
  .cover-edit-badge svg{width:14px;height:14px}
"""
edits.append(("Change-cover badge CSS", css_anchor, css_add))

# ---- 2. Hero markup: add the badge when the project has photos --------------
hero_anchor = ('    <div class="house-cover" data-edit-cover="${h.id}" '
               'style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px;cursor:pointer" '
               '${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}</div>')
hero_new = ('    <div class="house-cover" data-edit-cover="${h.id}" '
            'style="border-radius:var(--radius);overflow:hidden;margin-bottom:4px;cursor:pointer" '
            '${h.cover?`data-cover="${h.cover}"`:\'\'}>${h.cover?\'\':`<div class="blueprint"></div>${I.house}`}'
            '${(h.photos||[]).length?`<span class="cover-edit-badge">${I.edit}<span>Change cover</span></span>`:\'\'}</div>')
edits.append(("Hero badge markup", hero_anchor, hero_new))

# ---- 3. hydratePhotos: preserve the badge when the cover image loads ---------
# The original cleared the whole hero (el.innerHTML='') when the cover image
# loaded, which would wipe the badge. Clear only the placeholder nodes instead.
hydrate_anchor = "    const u=await photoURL(el.getAttribute('data-cover')); if(u){ el.style.backgroundImage=`url(${u})`; el.innerHTML=''; }"
hydrate_new = "    const u=await photoURL(el.getAttribute('data-cover')); if(u){ el.style.backgroundImage=`url(${u})`; Array.from(el.children).forEach(n=>{ if(!n.classList.contains('cover-edit-badge')) n.remove(); }); }"
edits.append(("hydratePhotos badge-preserving clear", hydrate_anchor, hydrate_new))

# ---- verify every anchor matches exactly once BEFORE writing anything --------
problems = []
for label, old, new in edits:
    n = src.count(old)
    if n != 1:
        problems.append(f"  [{label}] matched {n} times (need exactly 1)")

if problems:
    print("ABORTED — anchors did not match cleanly, nothing was changed:")
    print("\n".join(problems))
    print("\nYour file may differ from the version this script was built against.")
    print("Re-upload the current index.html so the script can be rebuilt to match.")
    sys.exit(1)

# ---- back up, then apply -----------------------------------------------------
backup = f"{PATH}.bak.{int(time.time())}"
shutil.copy2(PATH, backup)

out = src
for label, old, new in edits:
    out = out.replace(old, new, 1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(out)

print("Applied cleanly. All 3 edits landed.")
print(f"Backup saved: {backup}")
print(f"File: {PATH}  ({len(out)} bytes, was {len(src)})")
