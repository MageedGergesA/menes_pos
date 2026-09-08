# Handoff: Mezze POS → Claude Code / Odoo 19 implementation

## Overview
Mezze POS is a frozen HTML design prototype (`Mezze POS v3.dc.html`, plus a standalone
`Mezze Online Ordering.dc.html`) for a restaurant platform built on Odoo 19.

**Important — the backend is not greenfield.** A real Odoo module (`mezze_bridge`, repo
`MageedGergesA/menes_pos`) already implements most of this design and has its own extensive,
independently-tested status docs. `current-build-status/` bundles its own `FEATURE_MATRIX.md`
(~86% of a 79-item industry feature set built & proven), `PROJECT-STATE.md` (forensic audit),
`REMAINING-TO-100.md` (real backlog), and `GO_LIVE.md` (the actual path to shipping — mostly
deployment/credentials, not code). Read `IMPLEMENTATION-STATUS-RECONCILIATION.md` first: it maps
the design's BE-001–BE-020 onto that real status so Claude Code fixes only what's genuinely
missing/partial instead of re-implementing what's already built and tested.

## About the design files
The `.dc.html` files in this bundle are **design references**, not production code — they are
React-like prototypes with all state held in memory (no persistence, no server). The task is to
**recreate the behavior they define inside the existing Odoo 19 codebase** — extending native POS,
Restaurant, Self-Order, Loyalty, Inventory, HR, and Accounting modules wherever they already cover
the fact, and adding custom models only where a domain doc says the restaurant-specific state has
no Odoo home. Do not port the HTML/JS directly.

## Fidelity
High-fidelity. Every interaction, state transition, ledger, and edge case referenced in the docs is
already fully specified and click-through-verified in the prototype at the frontend layer — treat
copy, states, and business rules as final, not as placeholders to redesign.

## Read in this order
1. **`CLAUDE_CODE_HANDOFF.md`** — master index. Lists BE-001–BE-020 (every backend/integration
   item), which Odoo models each maps to, and which domain doc has the full contract. Read its
   "Native Odoo first" note before creating any custom model.
2. **`MEZZE_FINAL_FROZEN_AUDIT.md`** — current-state reconciliation: canonical owner for every
   domain (one function/ledger per concept, confirmed no duplicates), the two remaining known
   frontend gaps (drive-thru guest attach path, host wait-quote), and confirmation the design is
   frozen.
3. **Domain docs** (`*.md`, one per BE area — Menu, Kitchen, Payments, Loyalty, Refunds, Delivery,
   Session/EOD, etc.) — each specifies the exact contract: user action, inputs/outputs, accounting/
   inventory impact, permission gating, offline behavior, idempotency, audit trail.
4. **The two `.dc.html` files** — the executable reference for exact copy, states, and flows when a
   doc doesn't spell out a UI-level detail.

## Required first step in Claude Code
**Do not assume any BE item is missing — most are already built and tested.** Read, in order:
1. `current-build-status/FEATURE_MATRIX.md`, `PROJECT-STATE.md`, `REMAINING-TO-100.md`, `GO_LIVE.md`
   — the repo's own authoritative status. Treat these as ground truth for "is it built".
2. `IMPLEMENTATION-STATUS-RECONCILIATION.md` — the BE-001–BE-020 mapping onto that status.
3. Only then touch the domain docs below, and only for items marked NEEDS VERIFICATION / PARTIAL /
   MISSING / BUILT—NEEDS ADAPTATION. For those, cross-check the existing model against the frozen
   design contract (exact ledger shape, single-owner functions) before adapting it — don't build a
   second parallel implementation next to the real one.

## Canonical ownership (must not be duplicated server-side either)
One function/ledger per concept in the frontend — the backend must mirror this, not fragment it:
KDS ticket creation, refund, guest identity, 86/sellability, tip, and the three cost ledgers
(comp/refire/waste feeding Plate Cost) each have exactly one owner. Full list and evidence in
`MEZZE_FINAL_FROZEN_AUDIT.md`.

## Known open frontend items (not blockers, but not yet specified — flag before building around them)
1. Drive-thru guest attach/replace/remove uses a separate accessor (`dtGuest`) instead of the
   shared guest-resolution pair every other surface uses — same data, different access path.
2. Host wait quote and ready-to-seat notification are not computed anywhere in the frontend —
   Arrival Queue only derives stage (Arriving/Waiting/Late/Ready/Seated/No-show).

## Files in this bundle
- `current-build-status/` — the real repo's own status docs — **read first**
- `IMPLEMENTATION-STATUS-RECONCILIATION.md` — design BE-IDs mapped onto that real status
- `CLAUDE_CODE_HANDOFF.md`, `MEZZE_FINAL_FROZEN_AUDIT.md` — the design's own backend index/audit
- `domain-docs/` — all other `docs/*.md` design contracts
- `Mezze POS v3.dc.html` — main prototype (all POS/restaurant screens)
- `Mezze Online Ordering.dc.html` — standalone online-ordering storefront prototype
