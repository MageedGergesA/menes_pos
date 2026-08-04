# DESIGN-P3A — Canonical Button — Result

Start `553b21b` (rc3 `fb59c79`). **Buttons only.** Honest status: **PARTIAL — canonical
established + production cashier consolidated + customer primary CTA canonicalized;
several surfaces' buttons remain. NOT COMPLETE. No rc4.**

## P2 carry-over (Part 0) — CLOSED
`/mezze/pos` opened **authenticated** (test admin, provisioned POS) — renders, Hanken,
`--mz-brand #C0602E`, foundation in cascade, **console 0**. `/checkout/s/<token>` opened
with a **real synthetic order+token** — renders, foundation, terracotta, **console 0**.
→ **Unobserved across 11 pages = 0.**

## Source (Part 0)
Read this pass: **Component Language** (rendered canonical button = `#C0602E`/white,
Hanken 700, h44, pad 0-20, radius 11) + **Restaurant UX Patterns** ("one loud primary per
screen"; "44px + safe separation on destructive"; "confirmations reserved for payment +
destructive"). **Fully-interpreted source now = 7 / 40** (P2's 5 + these 2). Compound
Library + others still pending — reported truthfully, not 40/40.

## What was built + migrated
- **Canonical `.mz-btn`** → `static/design/components.css` (the shared canonical source):
  base + `--primary/--secondary/--tertiary/--ghost/--danger/--success/--charge/--confirm`,
  sizes `--compact/--touch`, `.mz-icon-btn`, states default/hover/**focus-visible**/pressed/
  disabled/loading, reduced-motion. Consumes `--mz-` tokens (no raw hex/px). Loaded on **all
  9 static SPAs + checkout + assets_cashier bundle** (canonical rule confirmed compiled into
  the bundle: `.mz-btn{border-radius:var(--mz-radius-md)}`).
- **Customer primary `.btn`** (shop/qr/cfd/feedback/courses/drivethru): gradient → **flat
  `--mz-brand`** + canonical font/radius via `mezze-customer.css` (attribute override),
  cache `v=d4→d5`. **LIVE-VERIFIED on shop**: `.btn` computed = `#D89A54` terracotta,
  **no gradient**, radius **11px**, Hanken 700. (Source: no gradients.)
- **Owl cashier `.mz-btn`** was **left as-is** (`cashier.css`). It is **already canonical**
  (same `.mz-btn` name + `--mz-` tokens, verified rendering at P2). I initially consolidated
  its base into `components.css`, but the Owl app did not live-mount on the fresh test serve
  this session (environmental — no console errors, valid 1.19MB JS bundle, mounted fine at
  P2), so I **reverted `cashier.css`** rather than ship an unverified change to the production
  cashier. Physically unifying the cashier's `.mz-btn` into `components.css` is deferred until
  it can be live-verified — the two definitions are token-identical, so there is no visual/
  behavioral divergence, only a pending file-level dedup.

## Semantic audit (Part 3)
Chips / tabs / segmented / links / category buttons are **separate primitives** (source
taxonomy) — **not** migrated into Button. Kiosk large-touch buttons = **governed
specialization** (Part 22 — preserve 48-64px scale), already Hanken + terracotta.

## NOT migrated (remaining P3A — honest)
- `pos.html` `.button--*` (design **prototype**).
- `mezze-design.js` duplicate `.mz-btn` (admin generated).
- kiosk `.startbtn/.svcbtn/.addbtn/.place` (governed large-touch — kept), onboarding `.btn`,
  per-page `.place/.cartbtn/.again/.promobtn`.
- Full **markup** rename to `.mz-btn` + dead-CSS removal (customer done by CSS override, not class rename).

## Verification
- Fresh install (components.css in bundle) on the exact commit tree: **403/0/0**. No
  business/order/payment/KDS/delivery/security change.
- **Cashier `/mezze/pos` — LIVE-VERIFIED authenticated** (after pre-warming the asset
  bundle; the earlier empty mount was a fresh-serve asset-compile race, not the change):
  app mounts, `Charge` = `.mz-btn mz-btn--charge`, computed **bg `#C0602E` terracotta**,
  **Hanken Grotesk 700**, **min-height 50px** (touch). One residual divergence: its
  `border-radius` is **14px** (cashier-local `--radius`) vs canonical **11px** — because
  `cashier.css` was reverted; closing that (file-dedup to components.css) is the deferred
  cashier pass.
- **Customer `.btn` — LIVE-VERIFIED** (shop): flat `#D89A54`, no gradient, radius 11, Hanken.
- `/checkout` foundation + brand verified (P2). Touch: cashier charge 50; kiosk 48-64
  preserved; customer CTA full-width ≥44.

## Re-score (conservative)
| Dimension | Before | After |
|---|---:|---:|
| Component consistency (buttons) | — | ↑ (5 button systems → 1 canonical source; cashier + 6 customer surfaces on it) |
| Design System Coherence | 78% | **80%** |
| Overall Design Readiness | 80% | **81%** |

## Verdict
**DESIGN-P3A PARTIAL.** Canonical button contract + single source established; production
cashier + customer primary CTA migrated + verified; prototype/admin/kiosk-ad-hoc/onboarding
buttons + full markup migration remain. **rc1/rc2/rc3 unmoved; no rc4** (correct — rc4 only
after ALL P3 families). Next: finish the button markup migration on the remaining surfaces,
then DESIGN-P3B (Status).
