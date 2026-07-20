# Sprint 2 · Phase 2A — Foundation Corrections & Component Inventory (engineering record)

Baseline / rollback: **`sprint-1-design-foundation`** (immutable). Discipline: Sprint 1 verification methodology (token-resolution proof + targeted computed-style checks, light+dark; whole-view fingerprints informational only). No redesign; no terracotta/type/spacing migration; preserve all behaviour.

**Approved plan decisions:** (1) `--ok` = theme-invariant `#2f9e6b`, no dark adaptation. (2) Implement the semantic z-index ladder exactly as proposed, preserving all numeric values, resolving ADR-0001. (3) Remove only the CSS `--ok` fallback; leave JS fallbacks. (4) Defer all JS z-index tokenization. (5) Component extraction order: Empty State → Number Stepper → Status Badge. (6) Each extracted component documents Purpose / Variants / States / Accessibility / Token dependencies / Current usage / Migration classification.

---

## Step 2A-1 — Fix `--ok` (REFACTOR / bugfix) ✅

**Investigation:** `--ok` was **undefined** (0 definitions) → its fallback `#2f9e6b` rendered in both themes. Used in 3 places: `.lt.free` ("free/comped" line indicator, CSS) and two success form-messages (`#mkt-msg`, `#clock-msg`, JS — the success partner of `var(--crit,#d64545)`). Semantically a **generic success/positive green, distinct from `--pos`** (`#1C9A60`/`#59C48D`, POS operational states). The Bible's success (`#2F7D4A`) is close but not equal — adopting it would change the current colour (deferred to the appearance sprint).

**Change:** define `--ok:#2f9e6b` in the baseline `:root` (theme-invariant — no dark override, so identical in every theme); remove the now-dead CSS fallback (`.lt.free{color:var(--ok,#2f9e6b)}` → `var(--ok)`). The 2 JS-inline fallbacks left untouched (per decision).

**Pixel-identity proof (both themes):** `--ok` resolves to `#2f9e6b`; `.lt.free` computes `rgb(47,158,107)`; the JS path `var(--ok,#2f9e6b)` computes `rgb(47,158,107)` (now via the defined token). Diff scope: 2 CSS lines (max line 205, inside `<style>`); JS lines 3256/3326 unchanged; braces 2581=2581. **Zero visual change; undefined-token bug closed.**

**Deferred:** dark-theme adaptation of `--ok`; convergence of the two success greens (`--ok` vs `--pos`) with the Bible `#2F7D4A`; removal of the 2 JS-inline `--ok` fallbacks — all to a later sprint.
