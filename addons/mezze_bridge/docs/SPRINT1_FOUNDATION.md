# Sprint 1 — Design System Foundation (engineering record)

**Mission:** strengthen the frontend engineering foundation of `static/pos.html` — centralize design tokens; normalize colours, typography, spacing, radius, shadows, motion, z-index; extract reusable primitives; remove safe duplication — **with pixel-identical rendering and zero behaviour change.** Taxonomy: KEEP > POLISH > REFACTOR > EXTRACT > REPLACE > REWRITE. REWRITE forbidden.

Explicitly **out of scope** (would change pixels/behaviour → later, flag-gated sprints): lossy scale rationalization (snapping the 32 font sizes / 19 radii to a smaller scale); the frozen `--mz-*` terracotta + Hanken/IBM Plex/JetBrains design-system migration; merging the 7 button classes (their heights differ).

---

## Verification methodology (official for Sprint 1)

**PRIMARY oracle — token-resolution / static-diff proof.** Every edit either (a) adds a token *definition* nothing references yet, or (b) replaces a literal with a token whose resolved value **exactly equals** that literal. CSS guarantees `property: var(--x)` renders identically to the literal when `--x` resolves to it — so proving value-equality guarantees pixel-identity for **every** element of that class, **data-independent**. Additive-and-unreferenced tokens cannot affect any computed style.

**SECONDARY oracle — stable-subset computed-style fingerprint.** A DJB2 hash over 18 sprint-relevant computed properties, restricted to **static nav-chrome elements only** (`.rail .railbtn, .rail .railtip, .rail .rllbl, .topbar, .langtog button`) — data-driven elements (`.prod` cards, order lines, live badges/tickets, timers) are **excluded** because their DOM/state varies between loads and would flip the hash for non-CSS reasons (proven in Step 2). Captured paired before/after within one session.

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
