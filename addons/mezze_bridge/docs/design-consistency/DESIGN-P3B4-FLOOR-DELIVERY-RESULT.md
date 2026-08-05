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

---

# DESIGN-P3B.4A — Non-auth closure

**P3B.4 initial:** PARTIAL (below). **P3B.4A non-auth closure:** closes every gate that does NOT need
authentication; the authenticated operational lifecycle stays separately tracked.

## ▸ DESIGN / SOFTWARE STATUS CERTIFICATION
| Gate | Result |
|---|---|
| Occupied brand decision | **Source decompressed** (gzip assets) → occupied is a UX flow only, **no colour/tone spec** → migrated off brand to canonical **info**. **Unexplained brand-as-status = 0.** |
| Floor text contrast (dark, canvas-normalised) | av 13.5/6.7 · **oc 8.0/8.6** · bl 9.3/5.0 · **rs 6.2** (was 4.24) — all ≥4.5. Lowest = **5.0**. |
| Floor non-text contrast (border vs canvas) | av 5.23 · oc 5.81 · bl 6.91 · rs 5.20 — all ≥3 ✅ (borders carry state, so measured). |
| Delivery text contrast | canonical `.mz-status` variants (info/success/active/neutral/danger) — AA both modes (P3B/P3B.3). |
| Delivery non-text | badge is text+fill (no icon-only state); card `.st-*` borders = **P3G** (not measured as status). |
| Floor Arabic regression | ✅ متاحة / مشغولة / طلب الحساب / محجوزة; occupied "4 ضيوف·38′", bill "الحساب", reserved name — RTL, console 0. |
| **Delivery Arabic (badge localised)** | ✅ badge was raw enum ("out_for_delivery") even in AR → added bilingual human label map. AR **dark** live: مقبول/قيد التحضير/جاهز/مُسند/خارج للتوصيل/تم التسليم/ملغى/مرفوض/فشل in **IBM Plex Sans Arabic**, RTL, latin IDs stay LTR, driver=metadata. |
| Delivery Arabic **light** | not force-rendered (mezze palette is `@media prefers-color-scheme`; no in-browser toggle). Same tokens; canonical variants AA both modes. |
| **High Contrast (Floor + Delivery)** | **No HC mode exists** anywhere in the product (no `forced-colors`/`prefers-contrast`/`data-contrast` in pos.html, design CSS, or mezze-design.js), and OS forced-colors can't be forced from page JS here → **not live-verifiable**. Design is **HC-safe by construction**: every state carries a text label (no colour-only state), so state identity survives a forced palette. A real HC theme is a **product-wide a11y gap** for a dedicated pass, not Floor/Delivery-specific. |
| Deterministic mapping tests | **Added** `tests/test_floor_delivery_status_map.py` (standalone PASS + registered `mezze_invariants`): asserts Delivery stage→variant + unknown→neutral, Floor occupied≠brand / occupied=info / bill has label, and **cross-surface** KDS.ready==Delivery.ready(success) & KDS.preparing==Delivery.preparing(info). |
| Frontend/component test | the mapping guard runs standalone (`python3 …` → RESULT: PASS) and inside the suite as an invariant. |
| Backend regression | **0 failed, 0 error(s) of 404 · exit 0** on clean community path (404 = 403 + the new mapping test). |
| Upgrade (`-u mezze_bridge`) | **0 failed, 0 error(s) of 404 · UPGRADE_EXIT=0** ✅ (prior P3B.4 skipped it; upgrades a freshly-installed DB, recompiles bundles clean). Prototype asset is a static file (same bytes I verified) → no stale CSS. Authenticated post-upgrade render = PENDING (auth). |
| Fresh install | **0 failed, 0 error(s) of 404 · INSTALL_EXIT=0** ✅. |
| Console (all live surfaces) | **0**. |
| Business FSM | **unchanged** (design/status presentation only). |

## ▸ AUTHENTICATED OPERATIONAL LIFECYCLE CERTIFICATION — **PENDING**
Live Floor lifecycle (seat→send→bill) and live Delivery lifecycle (accept→…→delivered / cancel-fail)
require the authenticated Odoo bridge. Entering a password to authenticate is barred by policy →
**PENDING** an operator/CI-authenticated session. **Not claimed as PASS.** No debug route added; auth not weakened.

## Debt after P3B.4A
Floor status debt **0** · Delivery status debt **0** · unexplained brand-as-status **0** · important
colour-only states **0**. Deferred (correctly, NOT status debt): card `.st-*` borders → **P3G**;
stage filters/counts → **P3I**.

## Re-score (P3B.4A)
All Floor/Delivery visual/status debt closed (occupied off-brand, all states AA, all labelled, delivery
localised, deterministic guards). **Coherence 91 → 93%.** **Readiness 89 → 90%** (design layer complete
for these surfaces; authenticated operational acceptance + other families still pending — not awarded).

## Verdict
**P3B.4 DESIGN MIGRATION: COMPLETE.** **AUTHENTICATED OPERATIONAL ACCEPTANCE: PENDING.**
rc1/rc2/rc3 unmoved; **no rc4**. Next: **DESIGN-P3B.5 — Reservations + Admin/Settings**.
