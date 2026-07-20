# Sprint 2 · Phase 2A — Foundation Corrections & Component Inventory (engineering record)

Baseline / rollback: **`sprint-1-design-foundation`** (immutable). Discipline: Sprint 1 verification methodology (token-resolution proof + targeted computed-style checks, light+dark; whole-view fingerprints informational only). No redesign; no terracotta/type/spacing migration; preserve all behaviour.

**Approved plan decisions:** (1) `--ok` = theme-invariant `#2f9e6b`, no dark adaptation. (2) Implement the semantic z-index ladder exactly as proposed, preserving all numeric values, resolving ADR-0001. (3) Remove only the CSS `--ok` fallback; leave JS fallbacks. (4) Defer all JS z-index tokenization. (5) Component extraction order: Empty State → Number Stepper → Status Badge. (6) Each extracted component documents Purpose / Variants / States / Accessibility / Token dependencies / Current usage / Migration classification.

---

## Step 2A-1 — Fix `--ok` (REFACTOR / bugfix) ✅

**Investigation:** `--ok` was **undefined** (0 definitions) → its fallback `#2f9e6b` rendered in both themes. Used in 3 places: `.lt.free` ("free/comped" line indicator, CSS) and two success form-messages (`#mkt-msg`, `#clock-msg`, JS — the success partner of `var(--crit,#d64545)`). Semantically a **generic success/positive green, distinct from `--pos`** (`#1C9A60`/`#59C48D`, POS operational states). The Bible's success (`#2F7D4A`) is close but not equal — adopting it would change the current colour (deferred to the appearance sprint).

**Change:** define `--ok:#2f9e6b` in the baseline `:root` (theme-invariant — no dark override, so identical in every theme); remove the now-dead CSS fallback (`.lt.free{color:var(--ok,#2f9e6b)}` → `var(--ok)`). The 2 JS-inline fallbacks left untouched (per decision).

**Pixel-identity proof (both themes):** `--ok` resolves to `#2f9e6b`; `.lt.free` computes `rgb(47,158,107)`; the JS path `var(--ok,#2f9e6b)` computes `rgb(47,158,107)` (now via the defined token). Diff scope: 2 CSS lines (max line 205, inside `<style>`); JS lines 3256/3326 unchanged; braces 2581=2581. **Zero visual change; undefined-token bug closed.**

**Deferred:** dark-theme adaptation of `--ok`; convergence of the two success greens (`--ok` vs `--pos`) with the Bible `#2F7D4A`; removal of the 2 JS-inline `--ok` fallbacks — all to a later sprint.

## Step 2A-2 — Semantic z-index ladder (REFACTOR) ✅ · resolves ADR-0001

CSS-only, value-preserving. Removed the 4 unused/mislabelled aspirational tokens (`--z-base/dropdown/sticky/modal`, 0 refs); renamed `--z-toast(120)`→`--z-notification`; added `--z-toast:80`; introduced semantic tokens and migrated 13 selectors.

| Selector | Old value | Token | Computed (light/dark) |
|---|--:|---|--:|
| `.chair` | 1 | `--z-floor-object` | 1 / 1 |
| `.railtip` | 20 | `--z-tooltip` | 20 / 20 |
| `.hintbar` | 30 | `--z-hintbar` | 30 / 30 |
| `.paidflash` | 49 | `--z-flash` | 49 / 49 |
| `#ov-pay` | 55 | `--z-overlay-pay` | 55 / 55 |
| `#ov-receipt` | 56 | `--z-overlay-receipt` | 56 / 56 |
| `.branchmenu` | 60 | `--z-menu` | 60 / 60 |
| `.login` | 70 | `--z-login` | 70 / 70 |
| `.toast` | 80 | `--z-toast` (new) | 80 / 80 |
| `.welcome` | 90 | `--z-onboarding` | 90 / 90 |
| `.tour-spot` | 95 | `--z-tour-spot` | 95 / 95 |
| `.tour-pop` | 96 | `--z-tour-pop` | 96 / 96 |
| `.waiterbell` | 120 | `--z-notification` (renamed) | 120 / 120 |

**Verification (both themes):** all 15 z-tokens resolve to exact values (`ALL_MATCH`); computed z-index on every present element (`.overlay 50, .sheet 52, .branchmenu 60, .railtip 20, .toast 80, .waiterbell 120, #ov-pay 55, #ov-receipt 56, .paidflash 49`) equals baseline; absent elements covered by token-resolution proof. **Toast/notification mislabel fixed.** 0 residual literals on scoped selectors; 4 old tokens removed; braces 2581=2581; all diff hunks inside `<style>`; no HTML/JS/backend change. **ADR-0001 → Resolved.**

**Deferred (scope-honest):** JS-created overlays (90/92/93/94/95) + JS `z-index:200`; floor sub-objects (`.tabletop 2/.tbadge 3/.tqr 4`) and chrome (`.topbar 4/.rail 5`) — outside the approved 2A-2 selector set / require JS edits.

---

# Phase 2B — Component Extraction

## Step 2B-1 — Empty State primitive `.empty-state` (EXTRACT + REFACTOR) ✅

- **Purpose:** one reusable centered muted status-message primitive (empty / no-data / inline-error). The illustrated icon+text `.empty` stays a separate primitive.
- **Variants:** base `.empty-state{text-align:center;color:var(--ink-3);font-size:14px}`; `.empty-state--grid{grid-column:1/-1}` (for grid-placed empties). Padding stays per-use (contextual) — full padding normalization deferred (appearance).
- **States:** stateless container; caller supplies text/glyph/i18n (unchanged).
- **Accessibility:** none added yet (per decision); `role=status`/`aria-live` recommended for a later a11y pass.
- **Token dependencies:** `--ink-3`.
- **Current usage (migrated, 11 sites):** `bdsempty`×2, `ckempty`×2, `dlvempty`×3 (`+--grid`), `rsvempty`×6 → markup now `class="empty-state <domain>"`; domain rules slimmed to padding/grid delta.
- **Migration classification:** EXTRACT (primitive) + REFACTOR (repoint 4 identical instances).

**Deferred (untouched, verified unchanged):** `favempty` (13.5px + line-height — appearance), `mgrempty` (positive `--pos`/bold "all-clear" — different semantic), illustrated `.empty`.

**Verification (both themes, probe vs Sprint-1/2A baseline, 11 computed props):** all 4 migrated empties compute `center | --ink-3 | 14px | 400 | 19.6px` + original padding/grid — **byte-identical to baseline** (`lightMatchesBaseline: true`); `fav`/`mgr` unchanged (dark `mgr` = `--pos` `rgb(89,196,141)`). **DOM structure invariant** — git diff shows every JS change is only an added class token (surrounding logic/i18n/error paths identical); 0 logic/structural changes. Braces 2583=2583 (+2 new rules). No backend change.

## Step 2B-2 — Number Stepper size variant `.stepper--lg` (REFACTOR) ✅

- **Purpose:** one integer ±1 stepper; the two "steppers" are one component (identical DOM/interaction — plain `onclick` −/+, native-button keyboard/focus, no hold/repeat/pointer/keyboard-value/animation) differing only in *size* (variant) + *min/max/callback* (per-instance config: denom min0, cart remove-at-0, split min2/**max8**).
- **Change:** convert context selector `.equalrow .stepper` / `button` → modifier `.stepper--lg` / `button` (same values 40px/r11/38px/font18), **kept in place after base `.stepper`** so the same-specificity (0,1,0) override still wins by source order. Apply `class="stepper stepper--lg"` to the **split-ways** stepper only. `.equalrow` container rule retained. Denomination + cart-line steppers untouched.
- **Consumers:** denom (open/close shift) + cart-line qty = `.stepper`; split-ways = `.stepper--lg`.
- **Per scope:** no JS factory, no a11y/hit-area/keyboard/hold changes.
- **Migration classification:** REFACTOR (internal restructure, identical external behaviour/rendering).

**Verification (both themes, probe vs baseline):** standard `.stepper` unchanged (`30/9/28/16`); `.stepper stepper--lg` == old `.equalrow .stepper` (`40/11/38/18`) — `lightStdMatch/lightLgMatch/darkStdMatch/darkLgMatch: true`. **DOM/behavior/business invariant** — git diff shows only the added `--lg` class token; `equalWays` handlers (min2/max8) + `renderSplit` logic byte-identical; 0 non-stepper changes. `.equalrow .stepper` selector removed (0 refs). Braces 2583=2583. No backend change.
