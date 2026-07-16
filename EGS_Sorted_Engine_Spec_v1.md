<!--
=============================================================================
  EGS Sorted Engine — Design Spec v1
  A product of Enlightened Global Solutions (EGS)
  Copyright (c) 2026 Enlightened Global Solutions. All rights reserved.
  For Edwin's master reference library. Paste into a new session to resume.
=============================================================================
-->

# EGS Sorted Engine — Design Spec v1

*Session date: July 2026 · Status: v1 engine SHIPPED in Notebuilt (cover-photo picker) · Author context: Edwin / EGS*

**First host:** Notebuilt (`/Volumes/AI Storage/-notebuilt/index.html`)
**Standalone product name:** **Sorted** (the engine and the future standalone app share the name)
**Related:** `EGS_Security_and_Durability_Checklist_v2.md`, `EGS_Brand_Reference.md`, `SKILL.md` (phone-app-builder)

---

## What Sorted is

**Sorted** is a reusable, app-agnostic media-sorting engine shared across EGS apps — Notebuilt, Kept, and a future standalone app also called Sorted. It is *not* a storage system. It never holds the media and never touches persistence. It is the **sorting brain** that rides on top of whatever storage the host app already has.

The whole reason it exists: EGS keeps rebuilding the same photo-organizer logic per vertical (Notebuilt = jobsite photos, Kept = memories, the standalone = personal media). Build that logic **once**, harden it once, and wear three skins.

### The bigger product (context)
The standalone **Sorted** is a **100% offline organizer**, not a vault: it sorts media *wherever the files already live* and never holds the only copy. Long-term it also targets a **thumb-drive edition** that carries only the *tool*, not the files — plug in, sort your own photos/videos in place, unplug, and nothing irreplaceable ever lived on the stick. That's a v2+ concern; the engine below is what everything is built on.

---

## The one principle that makes it reusable

**The engine holds references, never files, and never touches storage directly.**

- It works on an abstract list of **media-item refs** (opaque ids the host understands).
- It gets pixels only by calling a host-supplied **`resolve(ref) → Promise<url|null>`**.
- It hands changes **back** to the host via callback; the **host** persists them through its *own* `safeSave` discipline.

Consequence: the engine physically cannot corrupt an app's data, and dropping it into a new app costs ~one small adapter (a `list`, a `resolve`, and per-feature `onChange` callbacks).

---

## v1 API surface (as shipped)

Delivered as a marker-delimited block so it lifts out cleanly:

```
// ===== SORTED ENGINE START =====
const Sorted = (function(){
  // Open a picker sheet: a grid of media thumbnails, the current pick starred, tap to choose.
  // opts = { items:[ref,...], resolve:ref=>Promise<url|null>, current:ref|null, title, onPick:ref=>void }
  function pickGrid(opts){ ... }
  return { pickGrid };
})();
// ===== SORTED ENGINE END =====
```

`pickGrid` renders a 3-col thumbnail grid into the host's existing bottom-sheet, hydrates each cell through `resolve()`, stars the `current` ref, and calls `onPick(ref)` on tap. That's the entire v1 spine: **list → resolve → grid → pick → host persists.**

### Host contract (what an app provides)
- **`list()`** — the collection's refs (Notebuilt: `project.photos`, an array of photo ids).
- **`resolve(ref)`** — ref → displayable URL (Notebuilt: its existing `photoURL(pid)`, which pulls a blob from IndexedDB and returns an object URL).
- **`onPick` / `onChange`** — engine hands back the user's choice; host writes it. The engine never calls `localStorage`/IndexedDB itself.

Drop-in cost for a new app = those few functions.

---

## First feature built on it — the Notebuilt cover-photo picker

**Why cover-photo first:** it exercises the entire spine and nothing more. Once it works through the engine, every later feature is a variation on the same spine.

**What shipped (two fix-scripts, July 2026):**
1. `notebuilt_sorted_cover_fix.py` — the engine block + `openCoverPicker()` + `setViewerCover()`, plus entry points:
   - **Tap the project hero image** → `Sorted.pickGrid()` grid, current cover starred, tap to set.
   - **Star button in the photo viewer** (top-left) → set the currently-viewed photo as cover without leaving the viewer.
2. `notebuilt_cover_badge_fix.py` — a visible **"Change cover"** pill on the hero so the tap target is discoverable (the first version was an unlabeled tap-the-image gesture — too hidden, against EGS's "no hidden gestures" rule).

**Key discovery:** Notebuilt's data model *already had* an unused `cover` field (`cover:null` on project creation), already hydrated via `[data-cover]`, with a delete-fallback already resetting cover to the first remaining photo. The only thing missing was UI to *change* it — the cover had been silently locked to whichever photo was added first. So this was purely additive; **no data migration.**

**Design note — entry points:** dropped the originally-planned *long-press-a-thumbnail* in favour of the viewer star button. Long-press fights the mobile browser's own image-save/context menu and is inconsistent across browsers; a visible button is more discoverable and can't misfire. (General lesson for EGS apps: prefer a visible affordance over a hidden gesture.)

**Design note — hydration gotcha:** the hero cleared its whole innerHTML when the cover image loaded, which would wipe the new badge. Fix preserves the badge and clears only the placeholder nodes. Any future overlay on the hero must account for this.

---

## What's next on the same spine (not yet built)

Build order: **engine first (done) → corruption features → dedupe → standalone/desktop/thumb-drive skins.**

### Corruption handling (prioritized; honest split)
The honest split Edwin agreed to — **detection & prevention: yes. Repair: mostly no.**

1. **Detection (first-class engine feature).** The thumbnailer already decodes each image to make a thumbnail — *decoding to thumbnail is the same act as checking the file opens*. So `ensureThumb()` records **`decodeOK`** per item essentially for free. Also catch: truncated files (JPEG missing its end marker), zero-byte files, extension/format mismatches. Surface a plain list: "these N files are damaged and won't open" — while other copies may still be good.
2. **Integrity manifest (first-class).** A per-file fingerprint (checksum) stored in a **separate cache key** from the source of truth. Two payoffs: **verified copies** (a copy is bit-for-bit identical to its source — catches corruption during sloppy copies/transfers, the #1 cause) and **early bit-rot warning** (re-check fingerprints on later runs; if a file's contents changed when nothing should have touched it, warn *while a good copy may still exist*). This is a genuine differentiator — Google Photos won't tell you a file is silently rotting.
3. **Best-effort partial salvage (clearly-labelled extra, NOT "repair").** Recover whatever's readable of a damaged image (e.g. the top portion that decoded before the corruption). Always labelled "best-effort salvage," never marketed as repair — once image data is gone to bit rot, it's gone.

**The blunt truth to keep in the marketing:** corruption is a *storage* problem, not an app problem. The tool detects and warns and verifies copies; it cannot stop a failing drive. The real cure is boring — more than one copy, on more than one drive, checked periodically. Sorted makes that discipline automatic and legible. "We repair your corrupted photos" is a promise EGS will not make.

### Data-model fields to carry now (forward-compat)
Per the SKILL's forward-compatible-data rule, a media item should carry these from the start even while unused, so later features are a switch-on not a migration:
- `decodeOK` (bool|null) — set by the thumbnailer
- `hash` (string|null) — set by the fingerprinter
- tags/flags — for album membership, "junk"/screenshot/blurry marking, etc.

### Other features on the same spine
- **Dedupe / cleanup** — group by `hash`; surface duplicates, screenshots, blurry/near-identical burst frames for batch deletion.
- **Album / swipe-triage sort** — set a tag instead of the cover role; fast swipe-to-file.
- **Standalone Sorted skins** — phone library, desktop folders, plugged-in drive as *input sources* feeding the same proven engine. Note the browser wall: a sandboxed browser can't move files around a computer, so the desktop/thumb-drive "sort in place" version needs either modern File System Access API (Chrome/Edge only) or a real packaged program — decide when the flow itself earns it.

---

## Reuse checklist (dropping Sorted into a new app, e.g. Kept)

1. Copy the `// ===== SORTED ENGINE START/END =====` block verbatim into the app's single `index.html`.
2. Provide `resolve(ref)` (the app's existing photo-URL function) and pass the collection's refs as `items`.
3. Wire an entry point + an `onPick`/`onChange` that writes through the app's own `safeSave`/persist.
4. Style `.sorted-grid` / `.sorted-cell` / `.sorted-star` to the app's theme; **every inline icon gets an explicit width/height** (SKILL rule — the star badge already does).
5. Fix-script discipline for any live app: backup, exact-match anchors, abort-on-mismatch, `node --check`, test-apply before delivery.

---

## Cross-app conventions this must honour

- **Delete confirmation everywhere, no exceptions** (EGS standing rule).
- **Backup-durability nudge + app-named backups** (`<app>-backup-<date>.json`) — engine features that touch data must not bypass the host's durability guards.
- **Never rename an internal storage key to match a public name** — Notebuilt's IndexedDB is still `punchlist` from an earlier name; leave internal identifiers alone forever or write an explicit migration. (Same failure class as overwriting good data with an empty default.)
- **Local-first / offline / no third-party calls** — Sorted must work fully offline; it's the structural privacy difference from every centralized competitor.

---

*Copyright © 2026 Enlightened Global Solutions. All rights reserved.*
*Keep this in the EGS reference library. Upload at the start of any session that touches Sorted, Notebuilt photos, Kept, or the corruption/dedupe features.*
