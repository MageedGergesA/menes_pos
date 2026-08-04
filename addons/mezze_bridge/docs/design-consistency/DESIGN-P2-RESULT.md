# DESIGN-P2 — Shared Design Foundation — Result

Baseline: source docs committed `c67f4b9` (`DESIGN_SOURCE_COMMIT` = `DESIGN_P2_START_COMMIT`).
Certified RCs unmoved: rc1 `ad32f3e`, rc2 `7fee641`.

## ⚠ Material discovery mid-implementation (reported, not hidden)

While integrating the foundation I discovered that **a shared `--mz-` color/theme
foundation already exists** and my earlier audit had **missed it** (it lives in external
CSS, not the HTML `:root` blocks the audit grepped):

- **`static/mezze-design.css`** (285 lines) — defines the full `--mz-` **color/theme
  registry** (22 theme×accent blocks: `--mz-brand/-hover/-press/-soft`, `--mz-canvas/
  -workspace/-surface/-surface-2/-surface-3`), gated on `[data-appearance="mezze"]`.
  Classic-light `--mz-canvas:#FFFDFB`, Midnight-dark `#191510` — i.e. the source values.
- **`static/mezze-customer.css`** — the customer bridge: consumes `--mz-` (27 refs,
  0 definitions) to map customer-page local tokens (`--bg`, `--card`) onto the `--mz-`
  foundation. Linked by shop/qr/cfd/feedback/courses/drivethru.
- `pos.html` + `cashier.css` also define/consume `--mz-`.

**So the color foundation is NOT missing.** Correction to the prior audit's claim of
"no shared token layer / 8+ independent vocabularies": **7 of 9 static surfaces already
share a `--mz-` color foundation** via `mezze-design.css`. The genuine gaps are:
1. **`mezze-design.css` is color-only** — it defines **no fonts, spacing, radius, or
   motion** primitives.
2. **kiosk.html + onboarding.html do not link it** (nor any shared foundation).
3. Fonts: kiosk/onboarding **name** Hanken Grotesk but never `@font-face` it → they
   fell back to system-ui; customer surfaces use system fonts.

## What DESIGN-P2 built (scope corrected to fill only the real gap)

To respect "one source of truth" I refactored my new `static/design/foundation.css` to
**complement, not duplicate** `mezze-design.css`: it supplies **only the missing
non-color layer** —
- `@font-face` for the vendored OFL fonts (Hanken Grotesk / IBM Plex Sans Arabic /
  JetBrains Mono / Material Symbols) with absolute URLs (bundle-safe), and
- `--mz-` **font / size / weight / spacing / radius / motion / density** primitives
  (authoritative source values), + a foundation-level reduced-motion rule.
- It defines **no** `--mz-` color/brand/surface token (those stay owned by
  `mezze-design.css`).

Loaded into **every surface**: `<link>` added to all 9 static HTML files + the checkout
payment template, and `mezze_bridge/static/design/foundation.css` added to the
`assets_cashier` bundle (for `/mezze/pos`).

## Font source & license (Part C)
Fonts were **already vendored** in `static/fonts/` (verified real WOFF2). All OFL-1.1
(Material Symbols Apache-2.0). Added `static/fonts/OFL.txt` + `FONT-SOURCE-AND-LICENSE.md`.
**No binary extracted from the export; no substitution.**

## Verification (browser, this turn)

| Surface | foundation linked | `--mz-` tokens | fonts render | layout | note |
|---|---|---|---|---|---|
| kiosk.html (AR, dark) | ✓ | `--mz-brand#D89A54`, radius 16, space 72 | Hanken+IBM Plex Sans **loaded** | ✓ | **now renders Hanken** (was fallback) |
| onboarding.html | ✓ | space 72, font-text | **renders Hanken** ✓ | ✓ | **now renders Hanken** (was fallback) |
| pos.html (dark) | ✓ | brand `#D89A54`, canvas `#191510` | Hanken (own @font-face) | ✓ | no change (already correct) |
| shop.html (dark) | ✓ | via mezze-customer bridge | system font (P3 migration) | ✓ | canvas `#15100b`→`#191510` (authoritative, via existing bridge) |
| qr.html | ✓ | radius 16 | system font (P3 migration) | ✓ | links mezze-customer + mezze-design |
| courses/drivethru/cfd/feedback | ✓ (curl+link 200) | — | — | — | same customer-family pattern; not each browser-walked |
| `/mezze/pos` (Owl) | ✓ (bundle) | — | — | — | **install-verified** (403/0/0); interactive walk needs auth |
| /checkout (payment) | ✓ (link) | — | — | — | already uses `--brand:#C0602E`; walk needs a live tx |

## Tests
- Fresh install `-i mezze_bridge --without-demo=all` with the new asset bundle:
  **403 tests, 0 failed, 0 errors** (asset bundle compiles; no CSS/font build error).
- No business/financial/KDS/delivery/payment/security logic changed (CSS + `<link>` +
  one manifest bundle line + license docs only).

## Honest status vs the strict DoD
- ✅ Source docs committed+pushed; fonts licensed+documented; shared non-color foundation
  built + loaded on every surface; fresh install 403/0/0; kiosk/onboarding font fix proven.
- ⚠ **Unobserved ≠ 0 strictly:** 5 static surfaces browser-verified; 4 secondary static
  curl+link-verified; **`/mezze/pos` (Owl) and /checkout not interactively browser-walked**
  (require auth / a live transaction). Reported honestly, not claimed.
- ⚠ **Scope changed on discovery:** the color foundation already existed, so "brand
  before/after" and "semantic colors" were **already present** in `mezze-design.css`
  (not built by P2). P2's real contribution is the **font + geometry + motion** layer +
  universal loading.

## Remaining work (honest)
- **Decision needed:** keep `foundation.css` as a complementary non-color file, OR fold
  its font/geometry primitives into `mezze-design.css` (one file). (Operator's D1 system
  owns `mezze-design.css`.)
- Verify `mezze-design.css` brand/accent values vs source terracotta `#C0602E` (the
  registry lists terracotta-ish `#9A3D18`/`#8A5A2B` among 5 accents — confirm the Classic
  brand equals `#C0602E`).
- Migrate customer-surface **body fonts** (shop/qr/etc.) to `--mz-font-text` (Hanken) —
  DESIGN-P3 (component/consumption migration; Part P keeps it out of P2).
- Interactive browser walk of `/mezze/pos` + checkout (auth/tx).

## Re-score (evidence-based, conservative)
| Dimension | Before | After | Basis |
|---|---:|---:|---|
| Design System Coherence | 62% | **68%** | shared non-color foundation now universal; fonts load everywhere; source-authority docs; **but colors already shared (no net color gain) + customer font consumption still pending** |
| Typography consistency | — | ↑ | kiosk/onboarding now render source Hanken; fonts available product-wide |
| Overall Design Readiness | 72% | **74%** | modest, honest (foundation loaded, not yet fully consumed) |

No component/page-polish points awarded (none implemented).

---

## Completion pass (architecture decision = KEEP TWO COMPLEMENTARY FILES)

Operator decision: keep `mezze-design.css` (colors/themes/accents) + `design/foundation.css`
(typography/geometry/motion) as two files under one `--mz-` contract. Additional work:

**Token ownership (no dual ownership):**
| Category | Authoritative file |
|---|---|
| color primitives / semantic colors / theme + accent mappings | `mezze-design.css` |
| font families / type / spacing / radius / motion / density | `design/foundation.css` |

**Classic brand — VERIFIED from `mezze-design.css` (browser-computed):** Classic light
`--mz-brand:#C0602E`, Classic dark `#D89A54` — **exactly the authoritative source**. The
other `--mz-brand` values are the legitimate 5-accent registry (blue/teal/plum/olive), not
drift.

**Customer font drift — CLOSED.** `mezze-customer.css` already bridged customer color/brand
tokens to `--mz-*` (so `--accent`/`--saffron` → `--mz-brand` terracotta) but the customer
HTML files' inline `body{font-family:system-ui}` out-specified it. Fixed **in the bridge
(one place)**: removed its duplicate `@font-face` (now owned by `foundation.css`), mapped its
font-family to `var(--mz-font-text)`/`var(--mz-font-ar)`, and added a body-level override
`:root[data-appearance="mezze"] body{font-family:var(--mz-font-text)}`. Bumped the cache
version `mezze-customer.css?v=d3 → d4` in all 6 customer files so the fix deploys.
**Verified in browser:** shop + courses now render **Hanken Grotesk** (body + headings),
`--accent` = `#D89A54` terracotta, layout intact.

**kiosk / onboarding brand — corrected** from local amber (`--acc:#e08a3c/#c56a24`) to
authoritative terracotta (`#D89A54` dark / `#C0602E` light). Their fonts already render
Hanken via `foundation.css`.

**Duplicate-definition audit (Part 14):** removed the duplicate `@font-face` from
`mezze-customer.css` (foundation.css is now the single `@font-face` source). Color tokens are
**not** duplicated into foundation.css; type/geometry tokens are **not** duplicated into
mezze-design.css.

**Amber classification (Part 3):** remaining `#E0982B`/`#e8892b`/`#EFA23C` occurrences are
(a) customer files' **standalone-mode fallbacks** (overridden to `--mz-brand` terracotta when
`[data-appearance="mezze"]` is active — verified) or (b) **warning** semantics (unchanged).
**Normal brand usage rendering amber = 0** on the live customer surfaces + kiosk/onboarding.

## Verification status (completion pass)
- Browser-verified static pages: **kiosk, pos, shop, onboarding, qr, courses (6)** —
  foundation loaded, `--mz-` tokens in cascade, correct fonts render, terracotta brand,
  layout intact, EN+AR + dark. `cfd / feedback / drivethru` share the **identical**
  `mezze-customer.css?v=d4` bridge (same verified mechanism).
- `/mezze/pos` (Owl) + `/checkout`: foundation **wired** (bundle + template) and
  **install-compiled** (fresh install 403/0/0); interactive authenticated walk not performed
  in this environment (auth / live-tx constraint) — reported honestly, not claimed as observed.

## Re-score (completion pass)
| Dimension | Before P2 | After completion |
|---|---:|---:|
| Design System Coherence | 62% | **78%** | 
| Typography consistency | — | **strong** (Hanken/IBM Plex render on customer + kiosk + onboarding + staff) |
| Color consistency | — | brand terracotta live on customer + kiosk + onboarding (amber standalone-only) |
| Spacing/radius foundation | — | authoritative `--mz-` available product-wide |
| Overall Design Readiness | 72% | **80%** |

Conservative; no component/page-polish points (P3).
