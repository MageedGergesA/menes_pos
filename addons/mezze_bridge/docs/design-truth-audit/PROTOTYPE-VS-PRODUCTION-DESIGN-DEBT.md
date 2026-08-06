# PROTOTYPE → PRODUCTION DESIGN DEBT

Work designed/mocked in the prototype `static/pos.html` (`/mezze/design/pos`) or the export that has NOT propagated to production Owl/customer surfaces. Prototype adoption metrics: `.mz-btn`×59, `.mz-status`×50, full 11-destination rail, role gating, own @font-face + theme registry.

| Feature / Component | Export / Prototype | Production | Gap | Still valuable? |
|---|---|---|---|---|
| **11-destination nav rail + role gating** | proto `pos.html:1421-1431` + `gateManager()` | none (2 isolated Owl apps, no shell) | **HIGH** | YES — the product's real IA |
| **Floor / Table Map workspace** | export Workspace Library + proto `view-floor` | JSON `/floors` only | HIGH | YES (designed workspace) |
| **Reservations / Waitlist workspace** | export + proto `view-reservations` | JSON `/reservations/*`,`/waitlist/*` only | HIGH | YES |
| **Delivery workspace** | export + proto `view-delivery` | JSON `/delivery/*` + unbridged static boards | MED | YES |
| **Manager / Reports / Ops dashboards** | export Reporting workspace + proto views | JSON `/manager/dashboard`,`/ops/summary`,`/hq/summary` | MED | YES |
| **Coffee-Queue / BDS board** | proto `view-bds` | JSON `/bds/queue` + static | LOW | MAYBE |
| **Central Kitchen board** | proto `view-ck` | JSON `/ck/*` | LOW | MAYBE |
| **Cashier favorites / recent / predictive defaults** | export Restaurant UX + Cashier Workspace Pro | not in Owl cashier | MED | YES (rush-speed law) |
| **Undo-toast "speed without fear"** | export UX law (reversible-for-seconds) | not evident in production | MED | YES (safety+speed) |
| **Keyboard parity (⌘↵ charge, ⌘Z undo, "/" search)** | Cashier Workspace Pro | not in Owl cashier | MED | YES (expert cashiers) |
| **Full component tiers (Alert/Input/Quantity/Dialog/Card/Tabs)** | Primitive/Component/Compound Libraries | bespoke per-surface (P3C–P3I) | HIGH | YES (canonicalization) |
| **Order Line void/refund modes, Course Group headers** | export Tier-4 + proto | partial (KDS courses only) | MED | YES |
| **Density modes (compact/standard/comfortable)** | Foundation Engine `--mz-density` | token exists, no per-context UI selection | LOW | YES (drive-thru/training) |
| **Material Symbols Rounded icon system** | export | inline SVG everywhere | LOW | OPTIONAL |

## Reading
The prototype was a **near-complete visual realization of the export** (all 11 workspaces + nav + role model + registry). Production propagated only **2 of the ~6 staff workspaces** (Cashier, KDS) plus customer surfaces. The single largest "lost" body of work is the **production navigation shell + the 4 un-built staff workspaces + the deeper component tiers** — all designed, none shipped as production. **Prototype → Production design debt: HIGH.**
