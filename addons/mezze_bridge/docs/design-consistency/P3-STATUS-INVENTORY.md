# P3-STATUS-INVENTORY (DESIGN-P3B, exact)

Product-wide search (HTML / CSS / QWeb-XML / Owl / JS). Start `1b64d05`.

## Status/badge visual systems found (before P3B)
| System | Where | Kind | Classification |
|---|---|---|---|
| `.status-badge` (+`--ok/--warn/--accent/--violet/--neutral`, `--sm/--md/--bordered/--label`) | pos.html | operational status pill | **OPERATIONAL STATUS** (already semantic; `--accent`=brand-as-status = conflict) |
| `.st-*` (`st-ready/preparing/served/seated/fired/accepted/dispatched/delivered/failed/cancelled/over/no_show/received`) | pos.html | card border/opacity modifier | **CARD state hook → P3G** (not a badge) |
| `.kstate` + `.st-*` | pos.html (KDS) | KDS status badge | **OPERATIONAL STATUS** |
| `.conn` (`.online/.offline` + `.cdot`) | pos.html + cashier | connectivity indicator | **OPERATIONAL STATUS** (Local/Internet/External) |
| `.openpill` (+`.closed`) | shop.html | store open/closed | **OPERATIONAL STATUS** ✅ migrated |
| `.pill` + `.PASS/.WARNING/.FAIL/.NA/.NT` | onboarding.html | Go-Live states | **OPERATIONAL STATUS** ✅ migrated |
| `.tag` (PASS/FAIL + "optional") | onboarding.html | setup-complete status + optional metadata | **STATUS + METADATA BADGE** ✅ migrated |
| `.mz-badge` (b-info/b-ok/b-warn/b-danger) | checkout_templates.xml | payment status message block | **DYNAMIC STATUS MESSAGE** ✅ migrated → `.pay-msg` |
| `.etabadge` | shop / cfd / drivethru | ETA metadata | **METADATA BADGE** (pending) |
| `.rsvchip` | pos.html (reservations) | reservation chips | mixed (state chip) → audit per-use (pending) |
| `.mgrpill` / `.sesspill` / `.dot` / `.flagged` | pos.html | misc pills/dots | per-use (pending) |
| `.b-*` inline | (customer) | — | metadata (pending) |

## Counts
```
Status visual systems before          = ~6  (.status-badge, .kstate, .conn, .openpill, go-live .pill/.tag, .pay .mz-badge)
Badge/tag systems before              = ~4  (.tag, .etabadge, .rsvchip, .mgrpill/.dot)
Unique semantic business states       = 9 canonical (neutral/info/active/success/warning/paused/danger/offline/not-tested)
Distinct business states inventoried  = ~45 (see P3-BUSINESS-STATE-MAP.md: table/order/KDS/reservation/payment/delivery/connectivity/go-live)
```

## Colour-conflict audit (items 9, 10) — findings
- **brand-as-status**: `.status-badge--accent` (terracotta) used brand as a status colour → **resolved** by removing accent from the status language (P3B canonical has no brand variant); pos migration will remap those uses to the correct semantic (info/active).
- **NOT-TESTED = info-blue** (onboarding `.NT`) → was confusable with an active/info state → **resolved**: canonical `not-tested` is dashed neutral (shape-distinct), ✅ migrated.
- No `green = ready AND green = draft` type collision found in the migrated surfaces.

## Migrated this pass (P3B increment)
onboarding Go-Live (`.pill/.tag`), shop store-status (`.openpill`), checkout payment (`.pay-msg`),
+ the canonical `.mz-status`/`.mz-badge` component.

## Inventoried but NOT yet migrated (honest — remaining)
pos.html `.status-badge`/`.kstate`/`.conn` (KDS/floor/delivery/reservation/admin/go-live-in-prototype);
authenticated cashier Owl connectivity + payment status; qr order status; `.etabadge`/`.rsvchip`.
`.st-*` card modifiers stay for **P3G Card**. Filters/chips/tabs stay for **P3I**.
