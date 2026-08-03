# 02 — Information Architecture

## Two products, one brand

Mezze is really **two apps** sharing a brand:

1. **Staff product** — the `pos.html` shell (and the `/mezze/pos` Owl cashier),
   plus KDS/floor/delivery/admin surfaces. Landscape, dense, operational.
2. **Customer product** — `shop.html` (off-premise), `qr.html` (table), `kiosk.html`.
   Portrait/touch, warmer, fewer decisions.

Plus **secondary surfaces**: `cfd.html` (customer-facing display), `feedback.html`,
`courses.html`, `drivethru.html`, and the S5 `onboarding.html` admin/Go-Live console.

## Staff shell navigation (observed via `read_page` on `pos.html`)

The staff shell exposes **~14 top-level workspace destinations** in one nav:

```
Point of Sale · Floor plan · Live Ops · Kitchen Display · Coffee Queue ·
Manager Dashboard · Reports · Reservations · Delivery · HQ · Central Kitchen ·
Refunds · Settings · Close shift
```
plus utilities: Switch role, Toggle offline (demo), EN/ع, Replay tour, Toggle theme.

**IA finding (P1): too many co-equal top-level destinations.** 14 flat workspaces
with equal visual weight forces the operator to scan a long list for the 3–4 they
use per shift. There is no primary/secondary tiering (e.g. sell-flow vs
management vs config). "Coffee Queue", "Central Kitchen", "HQ", "Drive-thru" are
vertical/format-specific and should be **role/format-gated**, not always present.

## Entry / exit model

- Staff: single-shell, JS view-switch (11 `data-view` screens + 35 modal/overlay
  blocks in `pos.html`). Good — one shell, no full reloads.
- Customer: each channel is a **separate HTML file** with its own shell — a customer
  moving pickup→delivery, or a table guest hitting the QR then a payment page, crosses
  file boundaries with different token vocabularies (visible seam).
- Admin: `onboarding.html` is a **standalone** console reachable by URL, not linked
  from the staff shell's Settings — a discoverability gap for a new operator.

## IA problems (ranked)

| # | Problem | Evidence | Severity |
|---|---|---|---|
| IA-1 | 14 flat, co-equal staff destinations; no primary/secondary tiering | `pos.html` nav | P1 |
| IA-2 | Format/vertical workspaces (Coffee Queue, Drive-thru, Central Kitchen, HQ) always visible regardless of what the branch sells | `pos.html` nav | P1 |
| IA-3 | Customer journey crosses separate files with different token systems (visible seam pickup↔delivery↔payment) | `shop/qr/checkout` files | P2 |
| IA-4 | Go-Live/Onboarding console not linked from the staff Settings — new admin can't find it | `onboarding.html` standalone | P2 |
| IA-5 | "Toggle offline demo" / "Replay tour" (demo affordances) sit in the production shell chrome | `pos.html` nav | P2 |
| IA-6 | KDS, CFD, kiosk are separate destinations/files (correct) but share no shell chrome, so they read as separate products | files | P2 |

## Recommended IA direction (not implemented)

- Tier the staff nav: **Sell** (POS, Floor, KDS, Delivery) primary; **Manage**
  (Reports, Live Ops, Manager, HQ, Refunds, Reservations) secondary; **Configure**
  (Settings, Onboarding/Go-Live) tertiary — with format-specific workspaces gated by
  the commercial profile already defined in S5 (`counter`/`restaurant`/`delivery`/…).
- Give the customer channels one shared shell/token layer so the journey feels like
  one product.
- Surface Onboarding/Go-Live inside Settings.

See `03-SCREEN-INVENTORY.md` for the full screen map.
