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
