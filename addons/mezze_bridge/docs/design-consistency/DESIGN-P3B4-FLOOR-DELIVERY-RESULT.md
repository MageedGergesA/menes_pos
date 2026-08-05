# DESIGN-P3B.4 — Floor + Delivery Status — Result

**Start `e8d8328`** (rc3 `fb59c79`; rc1/rc2/rc3 unmoved; **no rc4**). Reservations OUT OF SCOPE.

## Verdict — **PARTIAL**
The design-system work for both surfaces is done and **live-verified in the prototype** (Floor: EN + AR/RTL,
dark; Delivery: all 9 stages, dark). Two things this pass's DoD demands are **NOT** performed by me and are
reported honestly, not as PASS:
1. **Functional lifecycle** (seat→send→bill; create→accept→prepare→ready→dispatch→delivered) — requires
   `BRIDGE.connected` (the authenticated Odoo bridge). Entering a password to authenticate is prohibited by
   my safety policy → **BLOCKED** (same boundary as P3B.3). Not weakened; no debug-login route added.
2. **Light-mode + High-Contrast live browser** re-run — the shipped `[data-appearance="mezze"]` palette is
   media-query-driven and I could not reliably force it in-browser this pass. Light-mode contrast is
   **computed** (below) and the canonical `.mz-status` variants are AA in both modes from P3B/P3B.3.

## What changed (measured; no FSM / business logic)
`git diff` = **5 line-changes in `static/pos.html`**, pure design/status:

### Floor (spatial widget — fill/border colour, NOT badges)
- **Bill-requested (`bl`) was communicated by colour + pulse ONLY** → added explicit text label
  **"BILL" / "الحساب"** (item 12/13). No longer colour/motion-only.
- **Contrast fix:** bill text was **white on amber = 1.97:1 (AA FAIL)**. Now **dark ink** (`--on-accent`,
  like Occupied) = **9.3 / 9.2 dark**, **4.75 computed light** → AA PASS. Available 13.5/6.7, Occupied
  7.6/7.5 already PASS. Table **number stays dominant** over status.

### Delivery (badge already `.mz-status--md` from an earlier sprint; mapping corrected)
- **cancelled / rejected / failed: neutral → danger** (item 29 — terminal-negative must read as danger).
- **preparing: warn(amber) → info** (KDS-consistent; amber "caution" was wrong for a normal in-progress
  state — items 24, 40). **ready = success** matches KDS (item 39/40).
- **delivered = neutral** (deliberately NOT success — keeps it distinct from ready, item 28).
- **out_for_delivery = active** (live/en-route; distinct from ready & delivered, item 26).
- Canonical variant names (accent→info, ok→success, violet→active).
- `.dlvcard.st-preparing` card-accent token realigned warn→info so it doesn't contradict the badge;
  full card-border family (`.dlvcard/.bqcard/.rsvcard .st-*`) still → **P3G**.

## Live verification (prototype, no auth)
| Check | Result |
|---|---|
| Floor EN dark | ✅ 12 tables, 4 states render; number dominant; legend correct; console 0 |
| Floor AR/RTL dark | ✅ rail flips right; legend متاحة/مشغولة/طلب الحساب/محجوزة; bill="الحساب" 9.2:1 |
| Floor contrast (dark) | ✅ bill 9.30 / occupied 7.57 / available 13.52 (all ≥4.5) |
| Floor contrast (light, computed) | ✅ bill 4.75 / occupied ~7.5 (≥4.5) |
| Delivery all 9 stages dark | ✅ info/info/success/info/active/neutral/danger/danger/danger; distinct; terminals red |
| Console (both surfaces) | ✅ 0 errors |
| Channel / driver = metadata | ✅ not styled as status (item 22/25) |
| Delivered ≠ Ready | ✅ neutral vs success (item 28) |
| Delayed color-only | N/A — no discrete "delayed" state in this implementation |

## NOT done (honest — BLOCKED / deferred)
- Floor functional lifecycle (seat/send/bill), Delivery functional lifecycle (accept→…→delivered),
  cancellation/failure transitions — all need the authenticated bridge → **BLOCKED**.
- Fully-live authenticated Floor/Delivery matrix; light + high-contrast **live** re-run → not performed.
- Deterministic state→semantic QUnit tests (item 48) — front-end test harness not run this pass.

## Residuals (surfaced, not hidden)
- **Terracotta-as-status = 1** (Floor Occupied = brand). Deliberate primary-occupancy retention from P2;
  source inconclusive. Flagged for design-owner sign-off (item 45 strict reading).
- Delivery card-border family (`.st-*`) → **P3G**; stage filters/counts → **P3I**.

## Backend
Fresh install `-i mezze_bridge --without-demo=all --test-tags mezze_runtime,mezze_invariants` on the
canonical community path (`odoo/odoo/addons,odoo/addons,mezze/addons`): **0 failed, 0 error(s) of 403
tests · INSTALL_EXIT=0** ✅. No Python/XML touched; the edits are client-side JS/CSS on a static asset
(inert during server-side tests).

> **Attribution note (honest):** a first run using the *full workstation* addons-path (which includes
> `enterprise2`) showed **0 failed, 7 error(s)** — ALL in `TestCustomerCredit`, root-caused to
> `enterprise2/pos_settle_due/models/res_partner.py:61 get_total_due → "Expected singleton: res.users()"`
> firing during the credit-pay flush. `pos_settle_due` is `auto_install:True` and only present because
> `enterprise2` was on the path; the failing frame is Enterprise code, not mezze_bridge and not this
> change. Re-run without `enterprise2` = clean **403/0/0**. Not my regression; flagged for Mageed as a
> pre-existing enterprise-module/env interaction.

## Re-score (conservative)
Floor status clarity ▲ (bill no longer colour/motion-only; AA fixed). Delivery status consistency ▲
(terminals danger; preparing KDS-consistent). Authenticated/functional gates NOT certified.
**Design System Coherence 90 → 91%** · **Overall Design Readiness 89 → 89%** (unchanged — the
functional/authenticated matrix, a DoD requirement, is not certified).

## Verdict
**DESIGN-P3B.4 PARTIAL** — Floor + Delivery status **design migration done & prototype-verified**
(incl. a real AA contrast fix the label surfaced); functional lifecycle + fully-authenticated + light/HC
**live** matrix **not performed** (password-auth safety boundary + media-query palette). rc1/rc2/rc3
unmoved; **no rc4**. Next: **DESIGN-P3B.5 — Reservations + Admin/Settings**.
