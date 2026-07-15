# Mezze — Restaurant POS Feature Matrix

Standard restaurant-POS feature set (what Foodics / Marn / Sapaad / Toast-class
systems ship today), mapped to where **Mezze** stands.

Legend: ✅ have (built & proven) · 🟡 partial (built but gated/incomplete) · ❌ missing

## Order management (front-of-house)
| Feature | Mezze | Note |
|---|---|---|
| Menu grid / categories / search | ✅ | |
| Barcode / scan add | ✅ | HID scanner |
| Order types: dine-in / takeaway / delivery | ✅ | |
| Drive-thru | 🟡 | takeaway covers it, no dedicated lane |
| Table management / floor plan | ✅ | shapes, seats, status, QR glyph |
| Seat-level ordering | ✅ | |
| Course management / coursing | 🟡 | fire carries course #, no explicit course-hold UI |
| Modifiers / options | ✅ | real product attributes, server-priced |
| Combos / meal deals | ✅ | native `product.combo`; parent+child lines, per-component food cost |
| Half-and-half (pizza) | ✅ | two halves, max/avg pricing, per-half BoM food cost, one KDS ticket |
| Item / kitchen notes | ✅ | |
| Hold & fire | ✅ | append-semantics, incremental fire |
| Void / discount | ✅ | |
| Comp (free item) | ✅ | dedicated `order.comp`; manager-approved, audited apart from discounts |
| Split bill (seat / item / equal) | ✅ | |
| Merge / transfer tables | ✅ | lock-safe; lines+KDS re-home, totals recompute |
| Park & recall | ✅ | |
| Quick keys / favorites | ✅ | manager-pinned Favorites strip, per-branch, live; separate from AI-suggested |

## Kitchen (KDS)
| Feature | Mezze | Note |
|---|---|---|
| Kitchen display + station routing | ✅ | Barista/Pastry/Kitchen… |
| Order state machine (fired→ready) | ✅ | concurrency-safe, row-locked |
| Bump / recall | ✅ | |
| Prep-time SLA / late alerts | ✅ | manager dashboard, real timestamps |
| Kitchen printer tickets | ✅ | ESC/POS (needs real printer) |
| Expo / pass / pickup screen | ✅ | coffee-queue pickup board |

## Payments & checkout
| Feature | Mezze | Note |
|---|---|---|
| Cash + drawer | ✅ | |
| Card (Paymob) | 🟡 | wired, no real transaction yet |
| Wallet / Fawry / InstaPay | 🟡 | via Paymob, unproven |
| Split tender (mixed) | ✅ | |
| Service charge | ✅ | 12% |
| Tips / gratuity | ✅ | native `tip_product_id` + `tip_amount`; % chips, on receipt |
| Multi-currency | 🟡 | single EGP today, framework supports it |
| Gift cards / store credit | ✅ | native `loyalty` gift_card; sell (mints on sale, tax-free) + redeem as a tender |
| Loyalty redemption | ✅ | native `loyalty` |
| Pay-at-table / QR pay | 🟡 | QR order yes; QR pay no (staff settle) |

## Menu & inventory
| Feature | Mezze | Note |
|---|---|---|
| Menu management | ✅ | via Odoo |
| Recipe / BoM + live food cost | ✅ | the moat — real MRP |
| Ingredient inventory / stock | ✅ | |
| Burn-rate / low-stock alerts | ✅ | projected stock-out |
| 86 / mark unavailable | ✅ | one-tap long-press, per-branch, live bus push, order-blocked |
| Waste / spoilage tracking | ✅ | native `stock.scrap` + reason tags; live cost, decrements stock, manager panel |
| Purchasing / POs | 🟡 | Odoo has it, not surfaced in POS UI |
| Central kitchen / commissary | ✅ | real production + transfers |
| Multi-location inventory | ✅ | |

## Customer / CRM / channels
| Feature | Mezze | Note |
|---|---|---|
| Customer profiles | ✅ | |
| Loyalty program | ✅ | |
| QR self-ordering | ✅ | per-table token |
| Delivery aggregators (Talabat/Jahez) | 🟡 | ingest built, needs partner creds |
| Online ordering (public web storefront) | ❌ | QR is on-premise only |
| Promotions / coupons engine | 🟡 | loyalty rewards + discount, not a full promo engine |
| Feedback / reviews | ❌ | |
| Email / SMS / WhatsApp marketing | ❌ | receipt-send is a placeholder |

## Reservations / delivery
| Feature | Mezze | Note |
|---|---|---|
| Table reservations | ✅ | conflict-checked |
| Waitlist | ✅ | host-stand queue; auto-quote by occupancy, seat→free-table picker→table service |
| Delivery dispatch board | ✅ | |
| Driver / rider management | 🟡 | rider name only, no driver app |
| Delivery zones / dynamic fees | ✅ | per-zone fee + min-order + ETA; server-resolved fee, min enforced both sides |

## Reporting & back office
| Feature | Mezze | Note |
|---|---|---|
| X / Z shift report | ✅ | close-shift Z-report |
| Product mix / best sellers | ✅ | |
| Hourly sales | ✅ | |
| Cash management / drawer reconciliation | ✅ | |
| Financial / GL + accounting | ✅ | GL bridge, trial balance |
| Tax reports | ✅ | |
| Multi-branch consolidation (HQ) | ✅ | |
| Labor / staff cost reports | 🟡 | cashier leaderboard; no labor cost/scheduling |

## Staff / management
| Feature | Mezze | Note |
|---|---|---|
| Roles / permissions | ✅ | role gating + Odoo groups |
| Cashier PIN login | ✅ | |
| Manager approvals (void/refund) | ✅ | HMAC-signed approval tokens |
| Shift management / cash count | ✅ | |
| Immutable audit trail | ✅ | |
| Time clock / attendance | ✅ | `mezze.attendance` on the cashier; PIN clock in/out, worked hours, manager panel |

## Compliance (MENA) & platform
| Feature | Mezze | Note |
|---|---|---|
| Egypt ETA e-invoice (B2B) | 🟡 | wired, needs token+setup |
| Egypt ETA e-receipt (B2C POS) | ❌ | real gap |
| KSA ZATCA / Fatoora | ❌ | not wired (modules exist) |
| VAT / tax config | ✅ | |
| Offline mode | ✅ | sync engine (for .exe track) |
| Multi-device sync | ✅ | |
| Multi-language / RTL | ✅ | EN + Arabic |
| Hardware (printer / drawer / scanner) | 🟡 | built, needs real device |
| Customer-facing display (CFD) | ✅ | second-screen `cfd.html`; live cart mirror via push+poll, branded, bilingual |

---

## Coverage summary (~68 industry features)

| | Count | Share |
|---|---|---|
| ✅ Have (built & proven) | ~61 | ~77% |
| 🟡 Partial (built but gated/incomplete) | ~13 | ~16% |
| ❌ Missing | ~5 | ~6% |

_Wave 3A (front-of-house) closed 7 gaps: tips, combos, merge/transfer tables,
comp flow, one-tap 86, quick keys, and half-and-half._
_Wave 3B (back-office) closed 5 gaps: gift cards, waste tracking, waitlist,
delivery zones, and the customer-facing display._
_All tested on real Odoo (curl + DB + in-browser) and money/inventory-balanced._

**The 5 that remain** are larger builds or external-gated, not quick fills:
online-ordering storefront, feedback/reviews, WhatsApp/SMS marketing, Egypt ETA
e-receipt (B2C), and KSA ZATCA.

**Where Mezze is strong (often deeper than competitors):** table service, KDS
with real SLA analytics, modifiers, split/refund/exchange, loyalty, reservations,
multi-branch + HQ, central kitchen, **live BoM food-cost + burn-rate**, and a
**real accounting/GL bridge** + immutable audit trail.

**Gaps a restaurant would notice (feature-fill, not re-plumbing):**
- **Tips / gratuity** — table-service standard, absent
- **Combos / meal deals** — very common in QSR
- **Merge / transfer tables** — expected in full-service
- **Gift cards, waitlist, customer-facing display, time clock** — standard back-of-box
- **Public online-ordering storefront** + real **marketing** (WhatsApp/SMS)
- **KSA ZATCA** — needed for the Saudi market (Egypt ETA is wired)

None of these require architectural change — they layer onto the existing Odoo +
`mezze_bridge` foundation. See `docs/GO_LIVE.md` for the launch checklist and the
strategy report for market positioning.
