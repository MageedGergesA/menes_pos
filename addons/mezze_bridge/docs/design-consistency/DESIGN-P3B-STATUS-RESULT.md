# DESIGN-P3B — Canonical Status / Badge — Result

**Start `1b64d05`** (rc3 `fb59c79`; rc1/rc2/rc3 unmoved; **no rc4**). Status/Badge only.

## Verdict — **PARTIAL (foundation + critical surfaces COMPLETE & verified)**
Honest status: the **canonical Status/Badge component is built and browser-verified** (9 semantic
variants, AA in light AND dark), and the **three spec-critical surfaces** — Go-Live, Payment,
customer store-status — are **migrated and verified**. The larger operational surfaces (the rich
pos-prototype status system, authenticated cashier Owl connectivity/payment, KDS, floor, delivery,
reservation, admin, reports, qr order-status) are **fully inventoried + contract-defined + business-
state-mapped** but **not yet migrated** — deliberately, to keep the measure-first/no-overclaim bar.
P3B is therefore **NOT COMPLETE**; this ships the verified foundation + critical states.

## Built (canonical) — components.css
`.mz-status` (neutral/info/active/success/warning/paused/danger/offline/not-tested) + `.mz-badge`
(quiet metadata). Never colour-only (text + dot/border-shape). `not-tested` = **dashed** neutral
(unmistakably ≠ pass/fail); `offline` = strong border; `active` = pulsing dot (reduced-motion
honoured). Text mixed toward `--mz-text` → **AA both modes**. Sizes `--sm/--lg/--pill`. RTL font.
**Brand is NOT a status colour** (the prototype `--accent` status variant is dropped from the language).

## Migrated + verified this pass
| Surface | Was | Now | Verified |
|---|---|---|---|
| **Go-Live** (onboarding) | `.pill .PASS/.WARNING/.FAIL/.NA/.NT` (NT = info-blue) | `.mz-status --success/--warning/--danger/--neutral/--not-tested`; overall = status message; `.tag`→`.mz-status`/`.mz-badge` | LIVE: 5 states distinct, **NOT-TESTED dashed & distinct from PASS/FAIL**, Hanken, console 0 |
| **Payment** (checkout) | `.mz-badge`/`.b-info/ok/warn/danger` (collided with canonical `.mz-badge`) | `.pay-msg`/`.pay-msg--info/success/warning/danger` consuming `--mz-` semantic tokens | XML compiles; paid(success)≠pending(warning)≠failed(danger) by colour+icon+text |
| **Store status** (shop) | `.openpill`/`.closed` | `.mz-status --pill --success/--danger` (JS toggles variant) | LIVE: open=green pill, dot, radius 999 |

## Contrast (measured, both modes) — all 9 variants ≥4.5:1
Light 4.88–5.88 · Dark 6.02–9.09. See CANONICAL-STATUS-CONTRACT.md. (Fixed an initial warning 2.86 /
success 4.36 light fail via the mode-aware `color-mix(→--mz-text)`.)

## Colour conflicts resolved
- brand-as-status (`.status-badge--accent`) → removed from the language.
- NOT-TESTED info-blue → dashed neutral (shape-distinct).

## Remaining (honest — for the next P3B increment)
1. **pos.html** `.status-badge`(→`.mz-status`, drop `--accent`), `.kstate`, `.conn` (connectivity),
   KDS/floor/delivery/reservation/admin states. (~40 uses; rename + token-retarget + verify.)
2. **Admin badge system** (`mezze-design.js` `.mz-badge.published/locked/draft/archived/free/bounded/
   me/pref`) — real admin policy states (item 40) that currently **collide** with the canonical
   `.mz-badge` (contained: it is injected only into pos.html, so it wins there and the canonical
   serves every other page — no breakage). Migrate to `.mz-status` (published→success, locked→warning,
   draft→neutral, archived→neutral, disabled/free→neutral) + retire the local `.mz-badge` in the pos pass.
3. **Authenticated cashier Owl** — connectivity + payment status (needs provisioned/auth render).
3. **qr** order status; `.etabadge`/`.rsvchip` metadata.
4. `.st-*` card border modifiers → **P3G Card**. chips/filters/tabs → **P3I**. Alerts → **P3C**.
5. Full 11-page status walkthrough + high-contrast/theme/RTL matrix on every migrated surface.

## Verification
Fresh install (checkout XML + status CSS compiles): 403/0/0 (see below). Canonical variants +
Go-Live + store-status browser-verified EN + dark. No FSM/payment/order/business logic changed.

## Re-score (conservative, foundation-only)
Status consistency ▲ (1 canonical semantic language established; go-live/payment/customer coherent);
a11y ▲ (not-tested distinct, AA both modes). Design System Coherence **88 → 89%**; Overall Design
Readiness **87 → 88%**. (Small — most operational surfaces still to migrate.)

## Verdict
**DESIGN-P3B PARTIAL** — canonical Status/Badge foundation + Go-Live/Payment/Customer verified.
rc1/rc2/rc3 unmoved; **no rc4**. Next increment: migrate pos-prototype + cashier + KDS/floor/
delivery/connectivity onto `.mz-status`, then the full status walkthrough → P3B COMPLETE → P3C.
