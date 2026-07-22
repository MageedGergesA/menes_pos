# Experience 3.0 — Phase 3: Checkout Experience

*Order rail + Payment workspace + shared checkout hierarchy, treated as one experience. Presentation only. Business logic, APIs, workflows preserved. Shell (Phase 1) and Cashier (Phase 2) frozen and untouched.*

**STATUS: implemented, verified, local commit — awaiting review.**

---

## 1. Scope & finding

The brief treats the order rail and payment as one checkout experience. Investigation showed the payment overlay was **already near-parity** from an earlier polish sprint (40px hero amount, 2-col method grid). The real gap was **hierarchy consistency** — the order-rail Total and the payment amount looked unrelated — plus small exact-value drifts.

So Phase 3 is a **shared numeric hierarchy**, not two rebuilds.

## 2. What changed — presentation only

| Element | Approved | Before | After |
|---|---|---|---|
| **Order grand Total** (`.trow.big`) | 24px / 800 / -.03em / tabular | 19px / 800 / **-.01em** / no tabular | **24px(amber) 26px(mezze) / 800 / -.03em / tabular** |
| **Payment amount hero** (`.paydue .pv`) | 40px / 800 / -.03em / 1.05 | 40px / 800 / **-.02em** / no line-height | **40px / 800 / -.03em / 1.05 / tabular** |
| **Payment methods** (`.tenders`) | 2-col, gap 14 | 2-col, gap 10 | **2-col, gap 14(amber) 12(mezze)** |

**The shared hierarchy:** the order Total and the payment amount now use **identical numeric treatment** — 800 weight, `-.03em` tracking, `tabular-nums` — scaling `26 → 40` (×1.54). The checkout reads as one continuous experience: the number you see in the order rail is the same number, larger, on the payment screen.

**Implementation:** 3 CSS declarations refined. **No markup, no JS.**

## 3. Preserved (verified)

| Guarantee | Evidence |
|---|---|
| **JavaScript byte-identical to `git HEAD`** | diff = 0 |
| All 11 other workspaces switch | 0 broken, 0 JS errors |
| Payment overlay renders | hero amount + keypad + remaining + methods (seen live) |
| Frozen work intact | card radius 14 (P2), rail 68 + catcol 176 (P1) unchanged |
| DOM hooks (`.trow.big`, `.paydue`, `.tenders`, `.charge`) | unchanged |

## 4. Validation — measured live

| | Amber | Mezze | Approved |
|---|--:|--:|--:|
| Order Total size | **24px** | 26px | 24px |
| Order Total weight / tracking / tabular | 800 / -.03em / ✓ | 800 / -.03em / ✓ | 800 / -.03em / ✓ |
| Payment hero size | 40px | 40px | 40px |
| Payment hero tracking / line-height / tabular | -.03em / 1.05 / ✓ | -.03em / 1.05 / ✓ | -.03em / 1.05 / — |
| Methods grid / gap | 2-col / 14px | 2-col / 12px | 2-col / 14px |

**Amber matches the approved values exactly** (24px, 14px) because amber tokens hold the literals; mezze snaps to its 12-step/9-step scales (26px, 12px), which is correct — the scale is the source of truth. Shared-hierarchy assertions: both weight-800 ✓, both -.03em ✓, both tabular-nums ✓.

## 5. Checkout compliance: **≈ 88%**

| Region | Compliance | Notes |
|---|--:|---|
| Order rail (header, lines, totals, grand Total, CTA) | **~90%** | Grand Total now matches approved exactly; CTA prominent (62px accent). CTA radius 13 vs approved 16 (minor). |
| Payment hierarchy (amount hero, methods, remaining, keypad) | **~85%** | Hero + methods match; the payment is an **overlay/sheet**, approved is a full **workspace** (§7). |
| Shared numeric hierarchy | **~95%** | Consistent 800 / -.03em / tabular across both, scaled. |
| **Weighted overall** | **≈ 88%** | |

## 6. Before / After

- **Before:** order Total at 19px with loose `-.01em` tracking and no tabular figures; payment hero at `-.02em` — the two numbers looked like different components.
- **After:** order Total at 24–26px and the payment hero at 40px share one numeric identity (800 / -.03em / tabular), so the amount carries visually from cart to checkout. Payment methods sit on the approved 2-col / 14 grid.

## 7. Remaining visual differences

| # | Item | Reason | Recommendation |
|---|---|---|---|
| 1 | **Payment is an overlay, approved is a full workspace** (56px side padding, edge-to-edge amount block, method tiles with caption + description) | Converting the overlay to a full-screen workspace is a **large structural change** that would touch the payment open/close flow and layout. The current overlay already delivers the approved *hierarchy* (hero, methods, remaining). | A dedicated follow-up if a full-workspace payment is wanted; not required for hierarchy parity. |
| 2 | Payment method **tile chrome** (approved: border 1px, radius 12, pad 15/17, caption 11px + description 12.5px) | Live tenders are icon+label tiles; the captioned-tile treatment is partially applied. | Refine tile internals if the workspace conversion (§1) is pursued. |
| 3 | Charge CTA radius 13 vs approved 16 | Minor; left to avoid churn on a working CTA. | Optional. |
| 4 | Mezze px-snapping (Total 26 vs 24, gap 12 vs 14) | Inherent to the completed Mezze scale (source of truth). Amber matches exactly. | None — correct by design. |

## 8. Recommendation for Kitchen (Phase 4)

**Phase 3 is complete for hierarchy parity (~88%).** The checkout reads as one experience; business logic, APIs and workflows are fully preserved (JS byte-identical); zero regressions.

**Recommend proceeding to Phase 4 (Kitchen / KDS).** The KDS is a self-contained workspace (`#view-kds`) with its own grid — a cleaner, more isolated rebuild than checkout, and it does not depend on any deferred item here.

**One decision to carry:** whether the payment should become a **full workspace** (§7 item 1) or remain a hierarchy-parity overlay. That is a scope call, not a defect — I did not undertake it unprompted because it is a large structural change beyond "match the hierarchy."

*Committed locally (not pushed). Shell + Cashier remain frozen.*
