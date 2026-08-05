# DESIGN-P3B.5 — Reservations + Admin/Settings Status — Result

**Start `a853d5a`** (rc3 `fb59c79`; rc1/rc2/rc3 unmoved; **no rc4**). Alerts/Inputs/Quantity/Dialogs/
Cards/Tabs/Navigation NOT touched.

## Verdict — **COMPLETE (design migration); authenticated operational acceptance PENDING**
Reservations, Admin governance, and Settings governance status/policy semantics are migrated,
source-confirmed, and browser-verified (EN + AR + the **real Mezze High-Contrast app theme**). The
lifecycle *transitions* (create→check-in→seat, etc.) need the authenticated bridge → PENDING, reported
separately, not faked.

## ▸ HIGH CONTRAST — terminology audit (the headline correction)
My P3B.4/P3B.4A "no HC mode exists" was **WRONG**. Precise result (full detail in
`DESIGN-P3B-STATUS-RESULT.md#high-contrast-capability-clarification`):
- **Mezze app HC theme: YES**, runtime-selectable (`ac_contrast` / `data-mz-theme="highcontrast"`),
  **browser-verified** — HC light #000/#FFF, HC dark #FFF/#000 (~21:1) + strong borders + focus ring;
  pos.html participates (loads mezze-design.css, sets the attribute).
- **prefers-contrast: NO.** **forced-colors: NO.** → product-wide a11y foundation gap (backlog), NOT
  the same as the app theme, NOT awarded here.

## ▸ Reservations / Waitlist — ✅ migrated
Badge was already `.mz-status` but raw-enum-labelled with a blurred mapping. Refined + localised:

| State | Variant | Change |
|---|---|---|
| booked / confirmed | info | canonical name (was accent) |
| arrived | **active** | was ok(success) → now ≠ seated (item 10) |
| waiting | warning | canonical name |
| late | **danger** | was warn → escalation ≠ waiting (item 9) |
| seated | success | canonical name |
| cancelled | neutral | ≠ no_show (item 11) |
| no_show | **danger** | was neutral → negative terminal ≠ cancelled (item 11) |
| done / unknown | neutral | safe fallback |

- **Status ≠ metadata:** wait-duration stays a prominent `.num`; party size / time / table / VIP /
  occasion stay `.rsvchip` metadata; late also shown as an explicit "Late/متأخر" chip (non-colour signal).
- **Localised** (was raw enum even in AR): محجوز/مؤكد/وصل/بالانتظار/متأخر/جالس/ملغى/لم يحضر/تم. Waitlist
  over→warning/notified→success/waiting→info, localised.
- **Floor↔Reservation:** floor `rs` = `--violet`→`--mz-delivery`; reservation booked/confirmed = info.
  Coherent (both "upcoming/known") without a reservation-only palette.
- **Live:** EN dark ✅ (9 states, distinct: Late red ≠ Waiting amber ≠ Arrived blue; No-show red ≠
  Cancelled grey), AR/RTL ✅ (IBM Plex Sans Arabic), **HC dark ✅** (badges 6.82–11.82:1, no state lost),
  console 0.
- **Reservation legacy status systems = 0** (badge canonical; card borders → P3G).

## ▸ Admin — surface + `.admin-badge`
- **Surface type:** CUSTOM Mezze static/JS (mezze-design.js) — **NOT** native Odoo form/list/kanban.
  So the native-`widget="badge"` policy (item 17) does not apply; canonical `.mz-status`/`.mz-badge`
  semantics are correct here. (No standard Odoo status view was found to reuse decorations on.)
- **`.admin-badge`:** P3B.2 already moved it off `.mz-badge` (canonical `.mz-badge` = 1 source) onto
  `--mz-` tokens. It is the **admin-context rendering of the same canonical semantics**, not a second
  palette — analogous to item-20's native-badge allowance. **Unexplained Admin badge palette = 0.**

## ▸ Settings — capability / policy / provenance (source-confirmed)
Source: *"Locked settings ignore lower-scope values. Bounded settings clamp overrides to an allowed
range. Free settings let users personalize freely."* Fixed the governance semantics:

| Category | State | Treatment | Fix |
|---|---|---|---|
| Capability | Disabled (`pref`) | neutral + **dashed** | was **warn** → not a warning (item 22) |
| | Hidden | not rendered | stays hidden (item 26) ✅ |
| Policy | Bounded | **info** | was **warn** → not a warning (item 25) |
| | Locked (🔒) | neutral + **solid** | was **danger** → not an error (items 23/25); reconciled `.lock`(danger)/`.locked`(success) contradiction |
| | Free | neutral | — |
| Provenance | Personal/Inherited | info | — (item 24: text/badge hierarchy) |
| Lifecycle | Published/Draft/Archived | success/info/neutral | draft was warn → info |

- **Locked ≠ Disabled** (solid vs dashed border, measured) · **Bounded ≠ Warning** (info, not amber) ·
  **Locked ≠ error** (neutral, not danger). Governance badges 5.98–6.02:1 dark.
- **No policy behaviour changed:** Hidden still filtered; Disabled controls keep `disabled`+`not-allowed`;
  toggle-ON brand `--accent` = selection (item 36 allows), not a status.
- **Live:** Settings workspace renders (provenance badge + `Scope·Policy·Override` prov-line as text),
  governance-badge CSS verified via injected probe (light+dark), console 0.

## ▸ Deterministic tests (added)
- `tests/test_reservation_settings_status_map.py` (standalone PASS + `mezze_invariants`): reservation
  state→variant + unknown→neutral; arrived≠waiting≠seated distinct; cancelled≠no_show; Locked-not-danger
  + has-border; Bounded-not-warning; Disabled-not-warning + dashed ≠ Locked-solid; Hidden-filtered.
- (P3B.4A's `test_floor_delivery_status_map.py` still green.)

## ▸ Contrast / colour-only / brand
- Lowest text contrast: reservation/governance badges **5.98** (dark) — all ≥4.5; HC dark 6.82–11.82.
- Non-text: HC strong borders on cards; disabled/locked border styles measured (dashed/solid) as the
  non-colour distinguisher.
- **Colour-only important states = 0** (every reservation/settings state carries a text label; locked/
  disabled add icon/border-shape).
- **Terracotta-as-status = 0** (toggle-ON brand = selection; provenance moved off brand in P3B.2).

## ▸ Verification
| Gate | Result |
|---|---|
| Backend regression | **0 failed, 0 error(s) of 405 · exit 0** (clean community path; 405 = 403 + 2 mapping tests) |
| Fresh install | **0 failed, 0 error(s) of 405 · INSTALL_EXIT=0** ✅ |
| Upgrade (`-u mezze_bridge`) | **0 failed, 0 error(s) of 405 · UPGRADE_EXIT=0** ✅ |
| Console (reservations + settings, EN/AR/HC) | 0 |
| Business/FSM/policy behaviour | unchanged |

## ▸ Debt after P3B.5
Reservation status debt **0** · Admin status/badge debt **0** · Settings state/policy debt **0**.
Deferred (correctly, not status debt): card `.st-*` borders → **P3G**; filters/tabs → **P3I**; Alerts →
**P3C**. Product-wide still open: authenticated cashier/KDS acceptance evidence; prefers-contrast /
forced-colors foundation; the final 11/11 sweep (P3B.6).

## ▸ Re-score
Reservations + Admin + Settings governance clarity closed; HC capability now correctly certified (app
theme) with the OS-forced-colors gap honestly separated. **Coherence 93 → 95%.** **Readiness 90 → 91%**
(authenticated operational acceptance + forced-colors NOT awarded).

## Verdict
**DESIGN-P3B.5 COMPLETE (design migration)** · **Authenticated operational acceptance PENDING.**
rc1/rc2/rc3 unmoved; **no rc4**. Next: **DESIGN-P3B.6 — Final Status Certification**.
