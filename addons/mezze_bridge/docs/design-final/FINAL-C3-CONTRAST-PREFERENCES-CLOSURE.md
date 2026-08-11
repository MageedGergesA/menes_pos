# FINAL-C3 — FORCED-COLORS / PREFERS-CONTRAST CLOSURE

Bounded closure of one certification condition:

> "`forced-colors` / `prefers-contrast`: NOT SUPPORTED — the browser supports the queries;
> the product declares **0** rules."

C3 adds standards-based support for the **user-agent** contrast preferences. It is **not**
another Mezze theme: Mezze High Contrast (`data-mz-theme="highcontrast"`) remains a separate,
explicit product theme and was not touched.

---

## Phase 1 — audit of current HEAD

| Query | Occurrences before C3 |
|---|---|
| `forced-colors` | **0** |
| `forced-color-adjust` | **0** |
| `prefers-contrast` | **0** |
| system colors (`Canvas`, `ButtonFace`, `Highlight`, …) | **0** |

Risk surface — state expressed as a fill or an elevation, both of which a forced palette
erases: `box-shadow` appears 5× in `components.css`, 6× in `cashier.css`, 2× in `kds.css`,
1× in `floor.css`.

## Phase 2 — what actually broke (measured, not predicted)

Before writing a single rule, the real Chrome forced-colors palette was emulated over CDP and
computed styles were dumped from `/mezze/pos`:

| Element | Measured in forced colors | Verdict |
|---|---|---|
| body | `rgb(0,0,0)` / `rgb(255,255,255)` | fine — UA palette owns it |
| product tile | 1px `rgb(255,255,255)` border, `boxShadow:none` | fine — border survives |
| search input | 1px border, visible text | fine |
| nav — non-current `<a>` | `rgb(255,255,0)` (LinkText) | fine |
| **nav — current** | bg `rgb(0,0,0)`, color white | **same as non-current** |
| **category chip — selected** | bg `rgb(0,0,0)`, border white, `boxShadow:none` | **byte-identical to unselected** |

So exactly one class of failure: **selection expressed as a brand fill (or an inset shadow
ring) is flattened away**. Everything else the UA already handled correctly.

That diagnosis was re-proved after implementation by temporarily disabling the fix and
re-running the suite — `test_02` fails with
`selected chip must differ from unselected in the forced palette (bg rgb(0, 0, 0) vs rgb(0, 0, 0))`
and passes with it. The test has teeth.

## Phase 3 — forced-colors architecture

**The user's palette owns colour.** `forced-color-adjust` stays `auto` everywhere —
**0 occurrences of `forced-color-adjust: none` in the entire production tree**, enforced by
`test_10`, which additionally fails outright if one ever lands on `html`, `body`, `:root`,
`*`, `.mz-app` or `.mz-kds-app`.

Only meaning the forced palette necessarily erases is restored:

| Restored | How | Where |
|---|---|---|
| **Selection / current** | the system selection pair `Highlight` / `HighlightText` | `components.css` |
| **Focus, distinct from selection** | `outline: 3px solid CanvasText; outline-offset: 2px` — drawn *outside* the box, so focused-and-selected still reads as both | `components.css` |
| **Elevation-only boundaries** | `border: 1px solid CanvasText` on dialog / modal / toast | `components.css` |
| **Disabled** | `GrayText` for colour and border | `components.css` |
| **Status dot** | `outline: 1px solid currentColor` (a pure background circle otherwise vanishes) | `components.css` |
| **Selected table** | `outline: 3px solid Highlight` — its ring was a `box-shadow` and was the *only* cue | `floor.css` |
| **KDS late / ready** | `outline` (solid vs dashed) — the inset rings were shadows | `kds.css` |

### One implementation note worth recording

The generic selected-toggle rule is written as
`[aria-pressed="true"][aria-pressed][aria-pressed]`. The attribute is repeated purely to
reach specificity **(0,3,0)**: the normal-mode rules are `.mz-filter-chip[aria-pressed="true"]`
and the customer pages' own `.cat.on`, both **(0,2,0)**, and a page's inline `<style>` also
loads *after* `components.css`. A plain `[aria-pressed="true"]` measurably lost — the first
implementation left the customer chips flattened, which `test_13` caught. **No `!important`
was needed.**

`aria-pressed="true"` is the product-wide semantic for a selected toggle (P3I), so one rule
covers the cashier chips, the KDS station filters and the shop / QR / kiosk category strips
without naming page classes.

## Phase 4 — prefers-contrast architecture

Three genuinely distinct branches:

| Branch | Behaviour |
|---|---|
| `prefers-contrast: more` | `--mz-border` → `--mz-border-strong`; `--mz-text-mut` → `--mz-text-2` (muted operational text stops being muted); control borders `2px`; focus outline `3px`; selection gains an inset `outline` so it never rests on colour alone; floor tables `3px`; KDS cards `3px`. **Same palette, same semantics — no new brand colours.** |
| `prefers-contrast: less` | Only decorative depth is removed (`box-shadow:none` on tiles / payment methods). Borders, focus, status and alert contracts are **untouched** — a comfort preference, never an accessibility regression. |
| `prefers-contrast` (unqualified) | Carries **only** the simplification correct for more / less / custom alike: decorative depth on dialogs, modals and toasts. It never changes contrast, because it also reaches users who asked for **less**. |
| `prefers-contrast: custom` | Receives the shared simplification and **nothing from the `more` branch** — verified by measurement, not by reading the CSS. |

`test_11` structurally forbids the shared branch from ever gaining `border-width: 2–9` or
`outline-width: 3–9`, so a future edit cannot silently push `more` behaviour onto `less` users.

## Phase 5 — emulation method

Chrome exposes these features only through the DevTools Protocol. `HttpCase.browser_js`
builds its own `ChromeBrowser` per call, so `tests/test_media_preferences.py` wraps
`ChromeBrowser.navigate_to` to issue `Emulation.setEmulatedMedia` on the freshly-created
browser *before* the page loads.

**Every test proves the feature is genuinely active with `matchMedia` before asserting
anything about it** — `test_01` does this for all six states
(`forced-colors: active|none`, `prefers-contrast: more|less|custom|no-preference`).
Nothing in this closure is inferred from the stylesheet.

## Machine-readable artifacts

The payment QR is a **raster `<img>`** produced by `/report/barcode`, and `.mz-qr-holder`
applies no colour, filter or blend mode. Forced colors recolours CSS-authored colour, never
image pixels, so the code stays scannable **with no opt-out at all**.

`test_16` locks this: if the QR ever becomes CSS-drawn (background-image, SVG `fill`,
`currentColor`) the test fails, forcing the narrow-opt-out decision to be made explicitly
rather than by accident. Physical scan verification remains under the separate
physical-device condition.

## Results

| Check | Result |
|---|---|
| Production documents observed under forced colors | Register, Orders, Floor, KDS, dialogs, kiosk, onboarding, feedback, CFD, shop, QR |
| Essential content lost | **0** |
| Focus defects | **0** |
| Selection defects | **1 found → 0** (nav current + every selected toggle) |
| Boundary defects | **3 found → 0** (dialog/modal/toast, floor selected table, KDS late/ready) |
| Colour-only critical states | **0** (P3B's "never colour-only" contract is what makes forced colors safe; re-verified — every `.mz-status` carries a text label) |
| `forced-color-adjust: none` occurrences | **0** |
| Horizontal overflow introduced | **0** |
| Arabic / RTL under forced colors and `more` | **PASS** (dir=rtl, IBM Plex Sans Arabic, nav still Arabic) |
| Mezze HC product theme | **11/11 maintained** — independent of the UA preference |

## Limitations, stated plainly

1. **One system palette was exercised.** Chrome's emulated forced-colors palette is dark
   (`Canvas` black / `CanvasText` white). Real users run many palettes. The implementation
   deliberately uses *system colour keywords* rather than fixed RGB, so it follows whatever
   palette is in force, but only one palette was measured here.
2. **`prefers-contrast` semantics are honoured as CSS, not as a colour audit.** Under `more`
   the tokens shift to the existing strong variants; no new contrast ratios were computed for
   every pair in that mode.
3. **Page-local button vocabularies** on `courses.html` / `drivethru.html` / `feedback.html`
   (`.btn`, `.act`, `.newbtn`) get forced-colors treatment from the UA and the shared
   selection rule, but not the `prefers-contrast: more` border strengthening, which targets
   the canonical families. Documented, not hidden.
4. **No physical assistive-technology testing** — that stays under the existing
   screen-reader and physical-device conditions.
