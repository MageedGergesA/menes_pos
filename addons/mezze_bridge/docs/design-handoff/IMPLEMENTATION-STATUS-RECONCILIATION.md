# BE-001–BE-020 reconciled against the real repo (`MageedGergesA/menes_pos`, `mezze_bridge`)

The design's handoff (`CLAUDE_CODE_HANDOFF.md`) was written before this repo was connected, so it
assumes each BE item is unbuilt. **That assumption is wrong for most of them.** The repo has its own
authoritative status docs (bundled here: `FEATURE_MATRIX.md`, `PROJECT-STATE.md`,
`REMAINING-TO-100.md`, `GO_LIVE.md`) — read those first; this table just maps the design's BE-IDs
onto them so Claude Code doesn't re-ask "is this built?" for things that already are.

| BE-ID | Design feature | Real repo status | Evidence |
|---|---|---|---|
| BE-001 | Deposit → prepayment/accounting | **NEEDS VERIFICATION** — no deposit model spotted in `models/` | check `PROJECT-STATE.md` §7-8 |
| BE-002 | Gift-card capture → ledger | **ALREADY BUILT** — native `loyalty` gift_card, sell + redeem | `FEATURE_MATRIX.md` "Gift cards / store credit ✅" |
| BE-003 | Commissary receive → stock transfer | **ALREADY BUILT** — real production + transfers | `FEATURE_MATRIX.md` "Central kitchen / commissary ✅" |
| BE-004 | Per-terminal drawer/X/Z → session accounting | **ALREADY BUILT** | `models/mezze_terminal.py`, `mezze_terminal_txn.py`; "Cash management ✅", "X/Z shift report ✅" |
| BE-005 | Payment capture → session takings | **ALREADY BUILT** — native `pos.payment`, cash/split/mixed | `FEATURE_MATRIX.md` payments table |
| BE-006 | House account → receivable | **ALREADY BUILT** | `models/mezze_customer_credit.py`; PROJECT-STATE §8 "customer-account = implemented + server-tested" |
| BE-007 | Loyalty ledger persistence | **ALREADY BUILT** — native `loyalty` | `FEATURE_MATRIX.md` |
| BE-008 | Tip capture + Tip Pool distribution | **PARTIAL** — capture built (native `tip_amount`); pool *distribution* not evidenced | `FEATURE_MATRIX.md` "Tips ✅" capture only; "Labor/staff cost 🟡 no scheduling" |
| BE-009 | Inventory/write-off posting | **ALREADY BUILT** — native `stock.scrap` + reason tags | `FEATURE_MATRIX.md` "Waste/spoilage ✅" |
| BE-010 | BoM/modifier consumption | **ALREADY BUILT** — real MRP BoM, live food cost; modifiers = real product attributes | `FEATURE_MATRIX.md` "the moat — real MRP" |
| BE-011 | Comp accounting | **ALREADY BUILT** — dedicated `order.comp`, manager-approved, audited apart from discounts | `FEATURE_MATRIX.md` |
| BE-012 | Refund + loyalty reversal | **BUILT — NEEDS ADAPTATION** — `models/mezze_reversal.py` exists; verify it matches the frozen contract (cumulative refundedQty, proportional loyalty reversal, tip-refund toggle, refund-to-gift-card) | `models/mezze_reversal.py` |
| BE-013 | Tax (ETA) submission | **PARTIAL/MISSING** — B2B e-invoice wired, needs token; B2C e-receipt is a **real gap** (not native) | `FEATURE_MATRIX.md`; `GO_LIVE.md` §0.3 |
| BE-014 | Order state machine, server-authoritative | **ALREADY BUILT** — concurrency-safe, row-locked | `models/pos_order.py`, `kds_ticket.py` |
| BE-015 | Delivery route/geocoding | **PARTIAL** — zones/fee/ETA server-resolved; live GPS/rider position not built (rider = name only, no driver app) | `models/delivery.py`; `FEATURE_MATRIX.md` "Driver/rider 🟡" |
| BE-016 | Ready-to-seat SMS/WhatsApp + wait quote | **NEEDS VERIFICATION** — waitlist auto-quote by occupancy exists; confirm it computes/sends what the design specifies | `FEATURE_MATRIX.md` "Waitlist ✅ auto-quote by occupancy" |
| BE-017 | Device fleet MDM | **BUILT — NEEDS PHYSICAL CERTIFICATION** — edge deploy pack complete in software, 0% physically certified | `models/hardware*.py`, `edge_connectivity.py`, `deploy/edge/`; `PROJECT-STATE.md` §10, §15 |
| BE-018 | Aggregator integrations | **PARTIAL** — ingest/HMAC/idempotency built; needs one real partner cert | `models/aggregator.py`; `REMAINING-TO-100.md` P1 |
| BE-019 | Forecast generation | **NEEDS VERIFICATION** — no forecast model spotted | — |
| BE-020 | Payroll export/send | **PARTIAL/MISSING** — `models/attendance.py` (time clock) exists; no labor-cost/payroll-export model spotted | `FEATURE_MATRIX.md` "Labor/staff cost 🟡" |

## Also already built, beyond the design's BE list
Marketing/campaigns (email/SMS/WhatsApp), public online-ordering storefront, feedback/reviews,
customer-facing display (CFD), waitlist, drive-thru lane board, half-and-half pricing, merge/transfer
tables, quick keys — see `FEATURE_MATRIX.md` in full.

## What actually blocks going live (not a design gap)
Per the repo's own `GO_LIVE.md` and `PROJECT-STATE.md`: production deployment (HTTPS/VPS), one real
Paymob transaction, the Egypt ETA B2C e-receipt decision, Edge physical certification (0% executed),
and an executed browser/UAT pass on the real Owl cashier. None of these are things Claude Code can
close by writing more backend code against the design docs — they need credentials, a host, and a
test pass on the *existing* build.

## Recommended next step for Claude Code
1. Read `FEATURE_MATRIX.md` + `PROJECT-STATE.md` + `REMAINING-TO-100.md` (bundled here) as the real
   baseline — do not re-verify what they already certify.
2. Use the table above to pick off NEEDS VERIFICATION / PARTIAL / MISSING items only.
3. Cross-check each against the frozen design contract in `CLAUDE_CODE_HANDOFF.md` /
   `MEZZE_FINAL_FROZEN_AUDIT.md` before writing code, since the design may specify a shape (e.g. one
   refund poster, one tip ledger) the existing model should be adapted to rather than duplicated.
4. `GO_LIVE.md`'s P0/P1 checklist is the actual path to shipping — treat it as higher priority than
   any remaining design-only gap.
