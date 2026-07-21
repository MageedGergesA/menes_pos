# Rollback Procedure — Mezze Appearance

**Rollback difficulty: trivial.** The redesign is inert unless a flag is set. There is no build step, no schema change, no data migration, and no persisted state beyond a single `localStorage` key.

---

## 0. Decide which rollback you need

| Situation | Action | Time |
|---|---|---|
| Mezze looks wrong on a terminal | **§1** Disable the flag | seconds |
| Mezze looks wrong everywhere | **§2** Disable fleet-wide | minutes |
| The file itself is suspect | **§3** Revert the code | minutes |
| Terminal unusable, staff blocked | **§4** Emergency | seconds |

**In almost every case §1 or §2 is sufficient.** Reverting code (§3) is rarely necessary, because amber is the default and is proven unchanged.

---

## 1. Disable Mezze on one terminal

Any **one** of these reverts that terminal to the certified amber build:

```
# A. Load without the flag
http://<host>/mezze_bridge/static/pos.html

# B. Explicitly force amber
http://<host>/mezze_bridge/static/pos.html?appearance=amber
```

```js
// C. Clear the persisted flag, then reload
localStorage.removeItem('mzAppearance'); location.reload();
```

⚠️ **A reload is required.** Icons are swapped once at boot, so clearing the attribute at runtime reverts colours and spacing but leaves Material Symbols icons in place. Always reload.

## 2. Disable Mezze fleet-wide

Stop emitting the flag from wherever it is set:

- Remove `?appearance=mezze` from the terminal URL / kiosk shortcut / launcher config.
- Remove any server-side code setting `data-appearance` on the root element.
- If `localStorage.mzAppearance` was seeded on terminals, clear it (§1C) or push a one-line clear.

No redeploy of `pos.html` is required — amber is the default state of the shipped file.

## 3. Revert the code

Only if the file itself is implicated (not merely the appearance).

```bash
cd /path/to/mezze

# Full revert of the entire P1–P7 program (returns to the pre-migration build)
git revert --no-commit 1d4a75f^..446e708
git commit -m "Revert P1-P7 Mezze migration"

# Or revert a single phase
git revert <phase-commit>
```

Phase commits, oldest → newest:

| Phase | Commit |
|---|---|
| P1 Colour | `1d4a75f` |
| P2 Typography | `9b7e9e8` |
| P3 Icons | `bc59e78` |
| P4A Surface | `b4059d0` |
| P4B Motion | `a40cb43` |
| P5 Spacing & Density | `b4636cb` |
| P6 Component Library | `be7076e` |
| P7 Convergence + fixes | `446e708` |

⚠️ **Reverting P7 re-introduces two real bugs**: the missing `<meta charset>` (all Arabic mojibakes) and the CSS comment that disables P5/P6. If you must revert P7, keep the two fixes:
- `<meta charset="utf-8">` on line 1
- the comment on ~line 278 must not contain `*/`

⚠️ **Revert order matters** — later phases reference earlier tokens. Revert newest → oldest, or revert the whole range.

**Font assets:** `static/fonts/` (19 files) is only referenced by mezze `@font-face` rules. Leaving the directory in place after a rollback is harmless — amber never requests it.

## 4. Emergency procedure

Staff blocked mid-service, no time to investigate:

1. **Append `?appearance=amber` to the terminal URL and reload.** This is the fastest, most certain path — it forces the certified build regardless of any stored flag.
2. If the screen will not load at all, the cause is *not* the appearance flag (amber is the default). Treat it as an application/network incident.
3. Capture evidence before further changes: browser console, the URL, and `localStorage.mzAppearance`.
4. Escalate with the phase commit list (§3).

**Do not** attempt a code revert on a live terminal during service. Flag-off is faster and safer.

## 5. Rollback verification

After rolling back, confirm the terminal is genuinely on the certified build. Run in the console:

```js
({
  appearance: document.documentElement.getAttribute('data-appearance'),   // null or "amber"
  miIcons:    document.querySelectorAll('span.mi').length,                // MUST be 0
  legacySvg:  document.querySelectorAll('svg').length,                    // ~71
  accent:     getComputedStyle(document.documentElement).getPropertyValue('--accent').trim(),
  radius:     getComputedStyle(document.documentElement).getPropertyValue('--r-lg').trim(),
  bodyFont:   getComputedStyle(document.body).fontFamily.slice(0,20),
  charset:    document.characterSet
})
```

**Expected on a correctly rolled-back terminal:**

| Field | Expected |
|---|---|
| `appearance` | `null` or `"amber"` |
| `miIcons` | **0** — the definitive signal; any non-zero means mezze icons are still live |
| `legacySvg` | ~71 |
| `accent` | `#EFA23C` (dark) or `#E0982B` (light) |
| `radius` | `18px` |
| `bodyFont` | starts `system-ui` |
| `charset` | `UTF-8` |

Then confirm by eye: amber/orange accent, no mojibake, thin-stroke outline icons (not filled Material Symbols).

**Functional check:** ring one test order end-to-end (add item → pay → receipt). Business logic was never modified in any phase, so this should pass unchanged; if it fails, the cause is unrelated to this migration.

## 6. What rollback does *not* affect

- **Orders, payments, shifts, sync state** — no data model was touched.
- **Workflows, navigation, permissions** — unchanged in all seven phases.
- **The charset fix** — if you keep P7, Arabic keeps rendering correctly in amber too. This is a strict improvement and should be retained.
