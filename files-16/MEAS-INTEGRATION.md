# EGS Measurement Widget — integration guide

Shared ft/in/fraction + metric input for Notebuilt and Stagger. Proven 25/25.
Stores INCHES internally; unit mode only changes entry/display. Engines untouched.

## Files
- meas_widget.js — the module (conversions, render, read-back, echo).

## How to wire a field (the pattern)
Replace a single measurement `<input>` with a widget container, then read it
back with measRead() instead of parsing a string.

BEFORE:  `<input id="f-len" ...>`  ... `readInputs(){ var len = measIn("f-len"); }`
AFTER:   inject `measWidget("f-len", currentInches, mode)` into the markup,
         then `var el=$app.querySelector('[data-meas="f-len"]'); var len=measRead(el);`

## Unit mode
- Global default: store on settings.units ("imperial"|"metric"), set MEAS_MODE_DEFAULT on load.
- Per-screen override: a small toggle that re-renders the screen's widgets with the other mode.
- The widget carries its own data-mode, so mixed screens are fine.

## CSS (add to each app, themed to match)
```css
.meas{display:flex;gap:8px}
.meas-cell{flex:1;display:flex;flex-direction:column;align-items:center}
.meas-cell input{text-align:center;width:100%}
.meas-cell label{font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted,#888);margin-top:3px}
```

## Rules kept
- Blank widget reads as null (never a silent 0).
- Bad fraction reads as null (echo can show "can't read that").
- Site-measure precedence, honest-failure, all unchanged — this is entry only.

## Wiring order (recommended)
1. Notebuilt calculator fields first (self-contained, fast to verify on device).
2. Notebuilt any other measurement inputs.
3. Stagger: readInputs() for both paneling + flooring, and the inside-dims screen.
   Stagger has the most fields — do it as its own session.
