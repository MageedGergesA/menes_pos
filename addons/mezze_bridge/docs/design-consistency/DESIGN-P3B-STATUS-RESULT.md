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

## Verdict (P3B.1 — foundation)
**DESIGN-P3B PARTIAL** — canonical Status/Badge foundation + Go-Live/Payment/Customer verified.

---

# DESIGN-P3B.2 — operational migration (advanced; still PARTIAL)

Start `b442cea`. Migrated the biggest operational status vocabularies + resolved the badge collision:

| Item | Done | Verified |
|---|---|---|
| **pos.html `.status-badge`** (reservation / delivery / waitlist / session states) → `.mz-status` | base + variant CSS removed; markup+JS-maps renamed; legacy suffixes `--ok/--warn/--accent/--violet/--neutral` map to canonical via documented compat aliases | LIVE: aliases resolve — ok→success 6.64, warn→warning 9.09, **accent→INFO 7.01 (NOT brand: accent≠#D89A54)**, violet→info, neutral 6.02; all AA dark |
| **pos.html `.conn`** connectivity | online→`--success`, offline→`--warning` (state hook + dot kept, pulse preserved) | LIVE: `#conn` = `mz-status--success` "Online", green pill, Hanken, radius 999, console 0 |
| **mezze-design.js `.mz-badge`** admin collision (item 12/43) | renamed → `.admin-badge` (canonical `.mz-badge` now the SOLE `.mz-badge` source); retargeted to `--mz-` semantic tokens; **`.me` brand→info** (brand-as-status removed) | compiles; pos renders, console 0 |

**Brand-as-status = 0** on pos (accent alias resolves to info teal, verified ≠ brand terracotta).
pos.html renders (bodyLen 320k), console 0, no overflow.

## Still remaining (P3B NOT COMPLETE — honest)
1. **pos `.kstate`** KDS badge (uses `.st-*` for colour) → `.mz-status --lg`.
2. **Authenticated Owl cashier** — connectivity (3-signal) + payment status (needs auth render).
3. **Floor / Delivery** — ✅ **P3B.4 (advanced)**: Floor state colours reconciled to the canonical
   foundation + bill-requested given an explicit "BILL"/"الحساب" label and an AA contrast fix (white→dark
   ink on amber, 1.97→9.3); Delivery badge mapping corrected (terminals→danger, preparing→KDS-consistent
   info, delivered≠ready). Prototype live-verified (EN + AR/RTL, dark). Functional-lifecycle + fully-
   authenticated + light/HC **live** matrix still BLOCKED (auth boundary). **Reservations** → P3B.5.
4. **`.st-*` card border modifiers** stay for **P3G**; `.rsvchip`/`.sesspill`/`.mgrpill` per-use audit.
5. Full **11-page** status walkthrough + **Arabic live** + **High-Contrast** + **theme/accent** sweep.
6. Dedicated deterministic **state→semantic frontend tests**.
7. Full admin-state canonicalization (`.admin-badge` → `.mz-status` with a state→semantic helper).

## Verdict (P3B.2)
**DESIGN-P3B still PARTIAL (advanced)** — canonical component + Go-Live/Payment/Customer +
pos-prototype status system + connectivity + admin `.mz-badge` collision all migrated & verified;
cashier-Owl / KDS-live / floor-reservation-delivery live-state / full-sweep / deterministic-tests
remain. rc1/rc2/rc3 unmoved; **no rc4**. Next: cashier Owl + KDS + the full walkthrough → P3B COMPLETE.
