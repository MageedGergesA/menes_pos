# Sprint 1 — Design System Foundation (engineering record)

**Mission:** strengthen the frontend engineering foundation of `static/pos.html` — centralize design tokens; normalize colours, typography, spacing, radius, shadows, motion, z-index; extract reusable primitives; remove safe duplication — **with pixel-identical rendering and zero behaviour change.** Taxonomy: KEEP > POLISH > REFACTOR > EXTRACT > REPLACE > REWRITE. REWRITE forbidden.

Explicitly **out of scope** (would change pixels/behaviour → later, flag-gated sprints): lossy scale rationalization (snapping the 32 font sizes / 19 radii to a smaller scale); the frozen `--mz-*` terracotta + Hanken/IBM Plex/JetBrains design-system migration; merging the 7 button classes (their heights differ).

---

## Verification methodology (official for Sprint 1)

**PRIMARY oracle — token-resolution / static-diff proof.** Every edit either (a) adds a token *definition* nothing references yet, or (b) replaces a literal with a token whose resolved value **exactly equals** that literal. CSS guarantees `property: var(--x)` renders identically to the literal when `--x` resolves to it — so proving value-equality guarantees pixel-identity for **every** element of that class, **data-independent**. Additive-and-unreferenced tokens cannot affect any computed style.

**SECONDARY oracle — targeted computed-value sample.** After each migration, measure the **specific edited property** on representative migrated elements and confirm it equals the exact old literal (data-independent, measures the CSS rule's output).

> **Step-3 finding (methodology revision):** the nav-chrome fingerprint (`.rail .railbtn, .topbar, .langtog button`, 18 props) was shown to be **reload-noisy** — its hash differs across reloads of a *byte-identical* file (proven by a git-stash control: the pre-edit and post-edit files both hashed `e30abcc8/9c57c254`, ≠ the Step-2 value `ae400de9`). So **whole-set computed-style fingerprints are informational only, NOT a pixel oracle** — some computed property in the rail chrome varies sub-perceptibly per load. The **authoritative oracle is the token-resolution proof** (token defined == old literal → CSS guarantees identical render) confirmed by **targeted per-element computed-value samples**. A fingerprint mismatch alone is not a STOP trigger; a *targeted* computed-value mismatch is.

> **Step-1/2 finding that set this methodology:** a full-union whole-view fingerprint changed hash across a reload with the file byte-identical — caused by product-grid async load variation, not CSS. Hence data-driven elements are excluded from the oracle and the token-resolution proof is authoritative.

If a step cannot preserve pixel-identity → **STOP, explain, wait for approval.**

---

## Baseline reference (captured at commit `59b5605` working tree)

**Braces:** `{` 2581 = `}` 2581.

**Stable-subset anchor** (42 static nav-chrome elements): light `ae400de9`, dark `ea004bd5` (self-consistent across reloads).

**Context fingerprints (full-union — informational only, NOT the oracle; include data-driven elements):** pos-view 142 els `3718fc68`/`4638d80a`; close-modal 171 `d8a11c05`/`5dce5404`; hq-view 195 `85181695`/`ed958c01`.

**Resolved token tables** — see `scratchpad/sprint1_baseline.json` for the full light+dark values. Key invariants tokens must equal after migration:
- Light: `--accent #E0982B`, `--pos #1C9A60`, `--warn #C46A16`, `--crit #C1402A`, `--ink #1E1A12/-2 #5B5343/-3 #8B8370`, `--surface #FFFFFF/-2 #F6F3ED/-3 #EDE8DE`, `--canvas #EBE8E0`, `--border #E1DBCC`, radius `--r-sm 8 / --r-md 12 / --r-lg 18 / --r-xl 24 / --r-pill 999`.
- Dark: `--accent #EFA23C`, `--pos #59C48D`, `--warn #E9A54D`, `--crit #EA6A4C`, `--ink #F4EFE3`, `--surface #1C1810`, `--border rgba(255,240,210,.09)`, `--backdrop rgba(0,0,0,.6)`.

**Source literals to migrate (only where value-identical):**
- **Radius** (19 distinct, ~188 occ): on-scale `8px×14 · 12px×27 · 24px×1 · 999px×10 · 50%×23` migrate cleanly (→ `--r-sm/md/xl/pill` + a `--r-circle`); **off-scale** `4,5,6,7,9,10,11,13,14,15,16,20,22,26,99px` (~113 occ) are **drift** — left as literals in Sprint 1, tracked for the appearance-changing rationalization sprint (snapping them would move pixels).
- **z-index** (20 values): `50/52/60/120/20/30` map to `--z-overlay/sheet/modal/toast/dropdown/sticky`; `49/55/56/70/80/90/95/96/200/1–5` stay literal (no exact token) — tracked.
- **Motion:** dominant `.14s`/`.15s` do **not** equal the additive `--dur-fast .13 / --dur-base .16` scale, so migrating them would change timing → motion tokenization is **deferred/minimal** in Sprint 1 (only exact matches). Easing `cubic-bezier(.2,.8,.3,1)` ×9 == `--ease-standard` (exact) — safe.
- **Dead code:** 51 stale `var(--token,#oldhex)` fallbacks (token always defined → fallback never renders) — safe to remove (POLISH).

---

## Step log

### Step 1 — Baseline snapshot ✅
Read-only. Captured token tables, stable anchor, context fingerprints, source-literal inventory. Established the verification methodology above.

### Step 2 — Fold token foundation (EXTRACT) ✅
Added an additive `:root` token block: `--r-pill`, `--space-1..8`, `--text-xs..4xl`, `--dur-fast/base/slow`, `--ease-standard/spring`, `--z-base/dropdown/sticky/overlay/sheet/modal/toast`, `--warn-soft` (theme-adaptive via `color-mix`), `--on-color`.
**Pixel-identity proof:** `git diff HEAD` = purely additive (8 lines; no existing rule modified); **all 17 new token families have 0 `var()` references** → cannot affect any computed style. Braces 2581=2581. Guaranteed pixel-identical by CSS semantics.

### Step 3 — Radius → tokens (REFACTOR) ✅
Added `--r-circle:50%` (additive). Migrated **value-identical** radii inside the `<style>` block only (lines 1–1070) via `sed`: `border-radius:8px→var(--r-sm)` (14), `12px→var(--r-md)` (26), `24px→var(--r-xl)` (1), `999px→var(--r-pill)` (9), `50%→var(--r-circle)` (23) = **73 literals migrated** (+ 2 already-tokenized). **Off-scale radii** (4,5,6,7,9,10,11,13,14,15,16,20,22,26,99px) **left untouched** (snapping would move pixels — tracked for the appearance sprint). **2 inline/JS occurrences** (`12px`, `999px` outside the style block) left as literals to preserve HTML/JS.
**Pixel-identity proof:** each token resolves to its exact old literal (live-verified: `--r-sm 8px, --r-md 12px, --r-xl 24px, --r-pill 999px, --r-circle 50%`); sampled migrated elements compute the old radius (`.chip` 999px; off-scale `.verb` 11px / `.railbtn` 14px / `.prod` 18px unchanged). Residual target literals inside style = 0. Braces 2581=2581. The nav-chrome fingerprint "changed" but the git-stash control proved it was reload-noise, not this edit (see methodology revision above).

### Step 4 — z-index → tokens (REFACTOR) ✅
Migrated only the **value-identical AND semantically-correct** z-indexes inside the `<style>` block: `.overlay 50→var(--z-overlay)`, `.sheet 52→var(--z-sheet)`, `.waiterbell 120→var(--z-toast)`.
**Pixel-identity proof:** tokens resolve exactly (`--z-overlay 50, --z-sheet 52, --z-toast 120`); computed z-index on migrated elements equals the old literal (`.overlay 50, .sheet 52, .waiterbell 120`); held elements unchanged (`.branchmenu 60, .railtip 20`); braces 2581=2581. Stacking order invariant.

> **z-ladder finding (open decision):** the aspirational z-tokens from Step 2 (`--z-base 1, --z-dropdown 20, --z-sticky 30, --z-modal 60`) match some literals by *value* but NOT by *usage* — actual layering is `.chair 1 · .railtip(tooltip) 20 · .hintbar 30 · .overlay 50 · .sheet 52 · .branchmenu(menu) 60 · .waiterbell 120`; there is **no** dedicated modal z-index (modals sit inside `.overlay` at 50). So `.chair→--z-base`, `.branchmenu→--z-modal`, `.hintbar→--z-sticky`, `.railtip→--z-dropdown` are **held** — migrating them would mislabel the system. **Options:** (a) leave them literal; (b) rename the ladder tokens to reflect real usage then migrate; (c) strict value-only migration accepting the misleading names. **Resolved: option (b) conceptually — recorded as [ADR-0001](adr/ADR-0001-z-index-ladder.md), deferred to Sprint 2. Sprint 1 leaves them literal.**

### Step 5 — Motion → tokens (REFACTOR) ✅
Migrated **value-identical** motion inside the `<style>` block, **excluding the token-definition lines (12–13)** to avoid self-reference: easings `cubic-bezier(.2,.8,.3,1)→var(--ease-standard)` (9), `cubic-bezier(.2,1.4,.4,1)→var(--ease-spring)` (1); durations `.13s→var(--dur-fast)` (8), `.16s→var(--dur-base)` (3). **21 usages migrated.**
**Not normalized / left literal:** the dominant durations `.14s`(22), `.15s`(16), `.12s`(7), `.2s`(12), `.18/.24/.25/.26/.3/.32/.34s` — none equals a token, and snapping them would change timing. `--dur-slow .22s` has **no** real usage (definition only). Keyword easings (`ease`) untouched.
**Pixel/behaviour-identical proof:** tokens resolve exactly (`--dur-fast .13s, --dur-base .16s, --ease-standard cubic-bezier(.2,.8,.3,1), --ease-spring cubic-bezier(.2,1.4,.4,1)`); computed timing on migrated elements equals old literals (`.modal` ease `cubic-bezier(0.2, 0.8, 0.3, 1)`; `.railbtn` dur `0.16s, 0.16s`); untouched elements unchanged (`.verb .14s`, `.chip .15s`, `.overlay .2s`); token defs intact; braces 2581=2581.
