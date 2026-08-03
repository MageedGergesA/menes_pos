# 03 — Screen Inventory

Every production screen found by source reading + `read_page` on the running app.
`pos.html` carries 11 `data-view` screens + 35 modal/overlay blocks; customer/kiosk
surfaces switch views by JS state within one file. **Observation status** column:
`OBSERVED` (browser `read_page`) / `SOURCE` (read in code) / `NOT OBSERVED` (route
not executed — no visual PASS inferred).

## Staff — `pos.html` shell + `/mezze/pos` Owl cashier

| Area | Screen | File | Obs |
|---|---|---|---|
| Cashier | Login / open-shift | `pos.html` / Owl | OBSERVED |
| Cashier | Catalog + category rail + search | `pos.html` / `product_grid` | OBSERVED |
| Cashier | Cart / order lines + qty stepper | `pos.html` / `cart` | OBSERVED |
| Cashier | Customer select / account | `pos.html` / Owl | SOURCE |
| Cashier | Payment (numeric keypad) | `pos.html` / `payment_screen` | OBSERVED |
| Cashier | Cash / Manual card / mixed tender | `manual_tender`, `payment_screen` | SOURCE |
| Cashier | Payment QR / integrated terminal / cash machine | `qr_pay`, `integrated_terminal`, `cash_machine` | SOURCE |
| Cashier | Receipt | `receipt` | SOURCE |
| Cashier | Refund / reversal | `pos.html` Refunds | SOURCE |
| Cashier | Session close | `pos.html` Close shift | OBSERVED (button) |
| Restaurant | Floor plan | `pos.html` Floor plan | SOURCE |
| Restaurant | Table detail / order / guest count / transfer / merge / courses | `pos.html`, `courses.html` | SOURCE |
| Restaurant | Reservations / waitlist / booking modal | `pos.html` | OBSERVED (modal) |
| Kitchen | KDS (new/preparing/ready/completed, course, cancel, add) | `pos.html` Kitchen Display | SOURCE |
| Delivery | Delivery dashboard (stages, courier, COD, tracking) | `pos.html` Delivery | SOURCE |
| Ops | Live Ops / Manager Dashboard / HQ / Reports / Central Kitchen / Coffee Queue / Drive-thru | `pos.html`, `drivethru.html` | SOURCE |

## Customer — off-premise `shop.html`

| Screen | Obs |
|---|---|
| Menu landing / category / product | SOURCE |
| Modifier / combo picker | SOURCE |
| Cart | SOURCE |
| Pickup flow | SOURCE |
| Delivery flow (address / zone / fee / ETA) | SOURCE |
| Payment (pay-at-counter / online) | SOURCE |
| Payment pending / success / failure (`checkout/s/<token>`) | SOURCE |
| Order status / tracking | SOURCE |

## Customer — table `qr.html`

| Screen | Obs |
|---|---|
| QR menu | SOURCE |
| Place order (append to table draft) | SOURCE |
| Bill | SOURCE |
| Pay / pay-online | SOURCE |

## Kiosk — `kiosk.html`

| Screen | Obs |
|---|---|
| Start / home | OBSERVED (Arabic tab was open) |
| Language toggle | SOURCE |
| Menu / product / modifiers | SOURCE |
| Cart / service mode | SOURCE |
| Checkout (pay-at-counter) / confirmation / order number | SOURCE |
| Inactivity reset / privacy clear | SOURCE |

## Admin — `onboarding.html` (S5) + Owl settings API

| Screen | Obs |
|---|---|
| Onboarding steps (13-step, resumable) | OBSERVED |
| Go-Live readiness (profile picker, PASS/WARN/FAIL/NOT TESTED/NA) | OBSERVED |
| Release identity / version | OBSERVED |
| Support bundle | OBSERVED |
| Settings / templates / locks / permissions / audit (API-backed; UI is the settings console) | NOT OBSERVED |

## Secondary

| Screen | File | Obs |
|---|---|---|
| Customer-facing display (CFD) | `cfd.html` | SOURCE |
| Feedback | `feedback.html` | SOURCE |

## Counts

- Distinct staff screens: ~25 (11 shell views + payment/modal family + ops).
- Customer: ~12 (shop 8 + qr 4). Kiosk: ~6. Admin: ~5. Secondary: 2.
- **Total distinct production screens inventoried: ~50.**
- **Browser-observed (read_page/visual structure): ~10.** Remaining **SOURCE** or
  **NOT OBSERVED** — no visual PASS inferred (screenshots blocked by tooling
  instability during this audit; see main report PART 7 note).
