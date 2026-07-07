#!/usr/bin/env python3
"""
Notebuilt: rename "Houses" -> "Projects" in all USER-FACING text.
Code identifiers (variables, storage keys, routes like 'houses'/'house') are
left untouched, so existing data keeps working — this changes only what you see:
nav tab, page header, detail eyebrow, buttons, sheet titles, toasts, task picker,
and search result labels.

Run from the Notebuilt repo folder:  python3 fix_nb_projects.py
Targets index.html. Backs up first; aborts if an anchor doesn't match.
"""
import sys, shutil, time

PATH = sys.argv[1] if len(sys.argv) > 1 else 'index.html'

EDITS = [
    # nav tab label
    ("['houses','Houses',I.house]", "['houses','Projects',I.house]"),
    # list page header
    ('<span class="eyebrow">Job sites</span><h1>Houses</h1>',
     '<span class="eyebrow">Job sites</span><h1>Projects</h1>'),
    # detail page eyebrow
    ('<span class="eyebrow">House</span><h1 class="truncate">',
     '<span class="eyebrow">Project</span><h1 class="truncate">'),
    # edit button aria label
    ('aria-label="Edit house"', 'aria-label="Edit project"'),
    # sheet title
    ("sheet(`<h2>${edit?'Edit house':'New house'}</h2>",
     "sheet(`<h2>${edit?'Edit project':'New project'}</h2>"),
    # toasts
    ("toast('House added')", "toast('Project added')"),
    ("toast('House deleted')", "toast('Project deleted')"),
    # task sheet pickers (two)
    ('<div class="field"><label>House (optional)</label>',
     '<div class="field"><label>Project (optional)</label>'),
    ('<div class="field"><label>House</label>',
     '<div class="field"><label>Project</label>'),
    # search result type label
    ("hits.push({t:'House',title:h.name", "hits.push({t:'Project',title:h.name"),
]

with open(PATH, 'r', encoding='utf-8') as f:
    html = f.read()

errs = []
if "['houses','Projects',I.house]" in html:
    errs.append("Projects rename already applied.")
for old, new in EDITS:
    c = html.count(old)
    if c != 1:
        errs.append("anchor found %d times (expected 1): %.55s" % (c, old))
if errs:
    print("ABORT — no changes made:")
    for e in errs:
        print("  -", e)
    print("\nIf an anchor wasn't found, re-upload your current Notebuilt index.html and I'll rebuild.")
    sys.exit(1)

bak = PATH + '.bak.' + time.strftime('%Y%m%d-%H%M%S')
shutil.copy2(PATH, bak)
for old, new in EDITS:
    html = html.replace(old, new, 1)
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(html)

print("OK — user-facing labels renamed Houses -> Projects (data/routes untouched).")
print("Backup saved to:", bak)
