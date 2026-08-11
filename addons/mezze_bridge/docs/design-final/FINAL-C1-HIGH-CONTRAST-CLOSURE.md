# FINAL-C1 — KIOSK + ONBOARDING HIGH-CONTRAST CLOSURE

Bounded closure of exactly one certification condition from
`F11-UIUX-CERTIFICATION-REPORT.md`:

> "Kiosk and onboarding are off the theme registry; Mezze High Contrast does not apply there."

Nothing else was expanded. Arabic translation coverage, courses/drivethru localisation,
`forced-colors` and `prefers-contrast` all remain exactly as they were.

---

## Phase 1 — Theme truth audit

### How the theme is represented (canonical, unchanged)

`static/mezze-design.css` is the registry. Every theme is a token block keyed on **root
attributes**:

```
:root[data-appearance="mezze"][data-mz-theme="<name>"]                 /* light families */
:root[data-appearance="mezze"][data-mz-theme="highcontrast"][data-mz-mode="light"]
:root[data-appearance="mezze"][data-mz-theme="highcontrast"][data-mz-mode="dark"]
:root[data-appearance="mezze"][data-mz-mode="<m>"][data-mz-accent="<a>"]  /* accent overlay */
```

Each block sets the `--mz-*` semantic tokens (`--mz-canvas`, `--mz-surface`, `--mz-surface-2`,
`--mz-border`, `--mz-border-strong`, `--mz-text`, `--mz-text-2`, `--mz-text-mut`, `--mz-brand`,
`--mz-on-brand`, `--mz-focus`, `--mz-ok`, `--mz-warn`, `--mz-danger`, `--mz-info`, …).

The nine passing surfaces load `mezze-design.css` and run a small **FOUC guard** in `<head>`
that stamps `data-appearance` / `data-theme` / `data-mz-mode` / `data-mz-theme` /
`data-mz-accent` before first paint, honouring `?mzmode` / `?mztheme` / `?mzaccent` and
`localStorage['mzSettings.v1']`.

High Contrast is a **theme name**, not a mode: `data-mz-theme="highcontrast"` with a
light or dark ramp selected by `data-mz-mode`.

### What kiosk / onboarding did instead — all five problems, on both

| # | Problem | kiosk | onboarding |
|---|---|---|---|
| 1 | **Never loaded `mezze-design.css`** → the registry did not exist on the page, so `[data-mz-theme=highcontrast]` had nothing to match | YES | YES |
| 2 | Declared their **own palette** on bare `:root` (`--bg/--card/--card2/--line/--txt/--mut/--acc/--acc2/--ok/--warn/--danger/--info`) and painted the entire UI from it | YES | YES |
| 3 | **Mapped LOCAL → CANONICAL** (`--mz-brand:var(--acc)`, `--mz-surface:var(--card)`, …). Being a later inline `<style>` at the same `:root` specificity, these declarations would have **shadowed** the registry even once it was loaded | YES | YES |
| 4 | Used an **incompatible local theme selector** `:root[data-mz-mode="light"]` with no `[data-appearance]`/`[data-mz-theme]`, and **no High-Contrast branch at all** | YES | YES |
| 5 | **Never received the theme attributes** — kiosk set only `data-mz-mode` (late, after paint); onboarding's `#theme` toggle also flipped only `data-mz-mode` | YES | YES |

So High Contrast could not apply for two independent reasons at once (not loaded **and**
shadowed), which is why forcing the attribute measurably changed nothing.

---

## The fix — one shared registry, zero per-page HC CSS

**Theme ownership was inverted.** The local names are now *aliases that consume* the
canonical tokens, instead of definitions that shadow them:

```css
:root{
  --r:22px;                                   /* geometry stays local */
  --bg:var(--mz-canvas);   --card:var(--mz-surface);  --card2:var(--mz-surface-2);
  --line:var(--mz-border); --txt:var(--mz-text);      --mut:var(--mz-text-mut);
  --acc:var(--mz-brand);   --acc2:var(--mz-brand-hover);
  --ok:var(--mz-ok);       --danger:var(--mz-danger); /* + --warn/--info on onboarding */
}
```

Because every existing rule on those pages already read `var(--bg)` / `var(--card)` /
`var(--line)` / `var(--acc)`, the whole surface now follows Light, Dark **and** High Contrast
automatically. **No `kiosk` High-Contrast CSS and no `onboarding` High-Contrast CSS was
written — the word `highcontrast` does not appear in either page's stylesheet.**

Also done, and only what was necessary:

1. `mezze-design.css?v=d3` linked on both (same as the other nine surfaces).
2. The **canonical FOUC guard** added to both, extended only to keep honouring the kiosk's
   legacy `?mode=` parameter alongside `?mzmode=`.
3. The kiosk's late `data-mz-mode`-only script removed — re-stamping only the mode would have
   dropped the theme name and silently disabled High Contrast.
4. Onboarding's `#theme` toggle now flips **theme + mode** (classic ↔ lounge) and, when High
   Contrast is active, switches its light/dark ramp instead of dropping the user out of HC.
5. Onboarding's second reverse-mapping block (`--mz-ok:var(--ok)`, `--mz-surface-2:var(--card2)`,
   …) removed: with the locals now consuming `--mz-*` it was both a shadow *and* a cycle.
6. Four theme-owned literals re-pointed (these would have inverted in HC):
   `.cat.on`, `.cartbar .n`, `.logo` → `var(--mz-on-brand)`; the kiosk image placeholder →
   `var(--mz-surface-3/-2)`; onboarding `.dot` (glyph on a saturated status fill) →
   `var(--mz-canvas)`, the ink that tracks the mode.

---

## Verification — computed styles, real browser

### High Contrast materially applies

| Surface / state | body background | body colour | `--mz-border` |
|---|---|---|---|
| kiosk Light (classic) | `rgb(255,253,251)` | `rgb(42,36,32)` | `#EAE2D6` |
| kiosk Dark (lounge) | `rgb(25,21,16)` | `rgb(245,241,235)` | `#453E33` |
| **kiosk HC light** | **`rgb(255,255,255)`** | **`rgb(0,0,0)`** | **`#1A1A1A`** |
| **kiosk HC dark** | **`rgb(0,0,0)`** | **`rgb(255,255,255)`** | **`#FFFFFF`** |
| onboarding Light | `rgb(255,253,251)` | — | `#EAE2D6` |
| onboarding Dark | `rgb(25,21,16)` | — | `#453E33` |
| **onboarding HC light** | **`rgb(255,255,255)`** | — | **`#1A1A1A`** |
| **onboarding HC dark** | **`rgb(0,0,0)`** | — | **`#FFFFFF`** |

Light is distinct from HC light (`#FFFDFB` ≠ `#FFFFFF`) and Dark from HC dark
(`#191510` ≠ `#000000`) — HC is not "dark mode with a different name".

Token ownership proven at runtime: `--bg === --mz-canvas`, `--card === --mz-surface`,
`--txt === --mz-text`, `--acc === --mz-brand` in every state.

### Contrast (measured)

**Kiosk**

| Pair | Light | Dark | HC light | HC dark |
|---|---|---|---|---|
| Heading | 15.09 | 16.14 | 21.00 | 21.00 |
| Muted text | 5.18 | 8.03 | 13.58 | 13.48 |
| Primary button | 5.09 | 6.08 | 5.09 | 6.08 |
| Service button (secondary) | 14.22 | 12.12 | 19.09 | 18.42 |
| Language button | 15.31 | 13.52 | 21.00 | 19.80 |
| Glyph on brand fill (large text) | 4.24 | 7.57 | 4.24 | 7.57 |

**Onboarding**

| Pair | Light | Dark | HC light | HC dark |
|---|---|---|---|---|
| Heading | 15.09 | 16.14 | 21.00 | 21.00 |
| Muted text | 5.18 | 8.03 | 13.58 | 13.48 |
| Primary button | 5.09 | 6.08 | 5.09 | 6.08 |
| Secondary button | 15.31 | 13.52 | 21.00 | 19.80 |
| Input / select text | 15.09 | 16.14 | 21.00 | 21.00 |
| Panel title | 15.31 | 13.52 | 21.00 | 19.80 |
| Status message | 4.88 | 6.02 | 12.35 | 11.82 |
| Input border vs surface | 1.63 | 2.25 | **21.00** | **21.00** |

**Lowest important HC pair: 5.09:1** (primary button, HC light) — equal to, not below, the
existing certification floor of 5.09. Everything else in HC is ≥ 11.8. Nothing on another
surface was touched, so no other certified pairing moved.

The `4.24` glyph-on-brand pair applies only to **large text** (24px/800 logo glyph, 19px/700
category chip), where AA requires 3:1. The canonical `.mz-btn--primary` is separately
measured at 5.09/6.08 because it darkens the brand fill (P3A treatment).

### Focus in High Contrast — real keyboard, `:focus-visible` confirmed true

| Surface / state | control | outline | vs page |
|---|---|---|---|
| onboarding HC dark | `.mz-input` | solid 3px `rgb(216,154,84)` | **8.67** |
| onboarding HC dark | `.mz-select` | solid 3px | **8.67** |
| onboarding HC dark | `.mz-btn--secondary` | solid 3px | **8.17** |
| onboarding HC light | `.mz-input` | solid 3px `rgb(192,96,46)` | **4.24** |
| kiosk HC dark | `.mz-btn--primary` (hero) | solid 3px, offset 2px | **8.67** |

All ≥ 3:1 (non-text contrast). Driven with actual `Tab` key presses — `element.focus()`
does not satisfy `:focus-visible` and was not relied on.

### Arabic / RTL — not regressed

`dir="rtl"` and computed **IBM Plex Sans Arabic** on both surfaces in **all four** theme
states (8/8 checks). The `'IBM Plex Arabic'` typo fixed in `6528815` remains fixed and is
now locked by a test. Onboarding's language toggle still works after the theme-toggle change.

### Responsive — 36 / 36 cases

kiosk at 360 / 390 / 430 / 768 / 1024 / 1280 and onboarding at 768 / 1024 / 1280, each in
Light, Dark, HC light and HC dark:

**Page-level horizontal overflow defects: 0. Controls under 44px: 0. Theme-related layout
shift: none** (theming changes token values only; no geometry token was touched).

*(kiosk was additionally exercised at 360/390/430 — below its documented 768 minimum — and is
clean there too. Its supported minimum is unchanged.)*

---

## Honest observations (no action taken — out of C1 scope)

1. **The accent overlay outranks the High-Contrast brand.** The registry's HC-light block sets
   `--mz-brand:#9A3D18`, but the later `[data-mz-accent="terracotta"][data-mz-mode="light"]`
   overlay resets it to `#C0602E`. This is pre-existing shared behaviour affecting **all**
   surfaces equally, not something C1 introduced, and it causes **no measured failure**
   (large-text pairings stay ≥3:1 and `.mz-btn--primary` darkens to 5.09). Recorded for a
   future shared-theme pass; changing overlay precedence would be a P3-scope edit.
2. `forced-colors` and `prefers-contrast` remain **NOT SUPPORTED** (0 product rules), exactly
   as before. C1 deliberately did not widen into them.

---

## Regression

| Run | Result |
|---|---|
| C1 targeted (`mezze_floor`, fresh install) | **85 tests · 0 failed · 0 errors** (was 83) |
| **Full module, fresh install** | **523 tests · 1 failed · 0 errors** (was 521) |

The single failure is `TestRateLimit.test_atomic_under_real_concurrency`, the known flake that
**reproduces identically on the pristine baseline** `2a8fcb6`. It was not modified.

**New failures: 0.** **Tests added: +2** (test_66, test_67).

HOOT cashier **40 tests / 146 assertions**, KDS **30 / 91** — unchanged.
Invariants: EndpointCoverage 1/0 · RouteScope 1/0 · P61Structural 1/0 · Authz 2/0 ·
CashierHoot 1/0 — all green.
Browser suites: CashierBrowser 16 · FloorRegister 26 · ReservationsWaitlist 35 (+2) ·
KdsBrowser 11 — all 0 failed.

No shared design/theme CSS was modified (`components.css`, `foundation.css` and
`mezze-design.css` are untouched), so cashier / KDS / floor could not be affected by a shared
change; the full suite confirms it.

**Business behaviour changed: NO.** No API, route, order, payment, tax, kiosk ordering,
onboarding admin behaviour, authentication or security path was touched. The kiosk's ordering
flow and the onboarding console's admin calls are byte-identical.
