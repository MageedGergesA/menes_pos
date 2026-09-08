# MEZZE POS — FINAL FROZEN AUDIT

Definitive current-state reconciliation. Supersedes the prior `Mezze POS — Final Integration &
Wiring Audit` wherever the two disagree. Sources: current `Mezze POS v3.dc.html` (unchanged since
that prior audit — file version confirmed identical), `Mezze Online Ordering.dc.html`, all
`docs/*.md`, `docs/CLAUDE_CODE_HANDOFF.md`.

## Executive summary

No product code changed between the prior Final Integration Audit and this one. What changed is
depth of inspection: two items that audit called open gaps are in fact already wired in the current
code, and one it called unbuilt is partially built (frontend simulation exists; only the live
GPS/routing backend is missing). Everything else that audit found holds. This report corrects those
three claims, re-confirms the rest, and is the version to carry into Claude Code.

## Historical audit claims corrected

| Previous audit claim | Current reality | Evidence | Action |
|---|---|---|---|
| "Register tip prompt → Tip Pool — NOT WIRED" | Register's settlement calls `tipPush({k:'capture',sur:'pos',...})` on the tender that clears the check, feeding the same `tipLog`/`tipPool()` Handheld and QR already write to. Code comment: "the tip reaches the pool exactly once, on the tender that clears the check — never per split payment, and never twice for a re-tendered balance." | `tipPush` call at settlement commit; `tipPool()` = `tipCard()+tipCashAll()` reads the one `tipLog` | **REMOVE STALE GAP** |
| "True map-pin interaction — not built" | Delivery board has real zone pins (`dvZonePins`, clickable, selects a zone) and moving rider markers (`dvMapPins`) interpolated along a route by elapsed-time progress. What's missing is real geocoding/live GPS — already backend scope (BE-015), not a frontend gap. | `dvZonePins`/`dvMapPins`/`dvRoutes` construction in the Delivery board renderer | **REMOVE STALE GAP (frontend); reclassify remainder as BACKEND ONLY, already BE-015** |
| "86 & recovery downstream consequences / Plate Cost cost-reason breakdown — not verified" | `lossCatTotals()` aggregates `compLog`/`rfLog`/`wasteLog` into six categories (`COMP, REFIRE_REMAKE, WASTE_DISCARD, SPOILAGE, OVERPRODUCTION, RECOVERY_SUBSTITUTION`) and the 86-impact sheet's comp/refund/refire actions post into those same three ledgers — this was in fact already traced (and marked CODE VERIFIED) in the prior audit's own wiring section; its gap list just wasn't reconciled against its own finding. | `lossCatTotals()`, 86-impact sheet action handlers posting to `compLog`/`rfLog`/`ordRefundCommit` | **REMOVE STALE GAP** |
| "Floor Editor — not re-verified this pass" | Current code has a full editor: add/duplicate/delete table, drag-move, capacity/shape, zones, undo/redo, preview mode, save-as-layout. Not re-clicked live this pass, but the claim "not re-verified" undersold what exists. | `flEditToggle`, `fxDragStart`/`flDragStart`, `flHistReset`, floor editor panel fields (`floorAdd`, `floorDuplicate`, `floorDelete`, `flSaveAs`) | **CURRENT AND CORRECT, upgrade confidence** — code shows a complete feature; still `CODE VERIFIED ONLY` pending a live click pass |
| "Unified guest attachment across Orders + Drive-thru — not verified/unified" | Still accurate. Register/Handheld/Orders all resolve the check's guest through the shared `tenderGuest(surface)`/`tenderCheckKey(surface)` pair. Drive-thru does not — it reads `state.guests` directly via `dtGuest(id)` from a vehicle match, bypassing that shared pair. Same book (no duplicate CRM record), different access path. | No `tenderGuest('dt')` call site exists anywhere in the file | **STILL OPEN** |
| "Host wait quote / ready-to-seat notification — not built" | Still accurate. No `waitQuote`/`estWait`/notification-state computation exists anywhere in the file. Arrival Queue computes stage (Arriving/Waiting/Late/Ready/Seated/No-show) only. | No matching symbol in the file | **STILL OPEN** |
| Everything else in the prior audit (KDS single-fire path, refund single poster, 86/sellability single resolver, cost-ledger single owners, vehicle→guest confirm-before-attach) | Re-confirmed this pass, no change | Same call sites re-checked | **CURRENT AND CORRECT** |

## Current top-level status (affected domains only — all others unchanged from the prior audit)

| Domain | Status |
|---|---|
| Tip → Tip Pool | **FRONTEND COMPLETE** |
| Delivery map/zone/rider markers | **FRONTEND COMPLETE — BACKEND REQUIRED** (real geocoding/GPS is BE-015) |
| 86/recovery → Plate Cost cost-reason breakdown | **FRONTEND COMPLETE** |
| Floor Editor | **FRONTEND COMPLETE** (code-verified; recommend one live click pass before sign-off) |
| Guest unification, Orders + Drive-thru | **PARTIAL FRONTEND** — same data owner, inconsistent access path |
| Host wait quote / ready-to-seat notification | **PARTIAL FRONTEND** — stage computation exists, quote/notification does not |

## Canonical ownership — no change

All owners traced in the prior audit (KDS fire: `fireLinesToKds`; refund: `ordRefundCommit`; guest:
`tenderGuest`/`tenderCheckKey`; sellability: `menuItemState`/`cc86`; tip: `checkTipAmt`/`checkTipSet`
for the order tip, `tipLog`/`tipPool()` for the pool; cost: `compLog`/`rfLog`/`wasteLog`) remain
single-owner with zero accidental duplicates. Drive-thru's guest access is a **path** inconsistency,
not a second Guest record — `dtGuest()` still reads the one `state.guests` array.

## Current frontend gaps

Two, both already known and neither new:

1. Drive-thru's guest attach/replace/remove does not route through the shared
   `tenderGuest`/`tenderCheckKey` pair the other three surfaces use — same data, inconsistent access
   pattern.
2. Host wait quote and ready-to-seat notification states are not computed or sent anywhere in the
   file.

## Backend-only requirements

Unchanged: BE-001 through BE-020 in `docs/CLAUDE_CODE_HANDOFF.md`. BE-015 (delivery routing/
geocoding) now explicitly covers turning the existing simulated pin/route rendering into a real
provider-backed one — the frontend contract for it already exists.

## Final handoff status

# MEZZE POS CLAUDE DESIGN: FROZEN

Two small, already-documented frontend items remain open (drive-thru guest path, host wait quote) —
neither blocks handoff; both are additive, not corrective.

## NEXT PHASE

CLAUDE CODE — EXISTING ODOO IMPLEMENTATION RECONCILIATION
