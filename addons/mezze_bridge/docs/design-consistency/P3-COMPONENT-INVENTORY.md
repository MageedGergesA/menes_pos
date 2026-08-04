# P3 — Component Inventory (measured)

Baseline: rc3 `fb59c79`. Counts are measured from `static/*.html` + `static/src/cashier/`
(Owl cashier) + `views/*.xml` (QWeb) — **exact, not the P1 audit's approximations**.

## P2 carry-over gate — CLOSED (prerequisite for P3)
Both surfaces the P2 report flagged as not-interactively-observed were opened in a real
browser this pass:
- **`/mezze/pos`** (Owl cashier) — authenticated (`/web/session/authenticate`, test admin
  on test DB `mezze_dp2b`, provisioned pos.config+Cash+products): renders, title "Mezze
  Cashier", body font **Hanken Grotesk**, `--mz-brand:#C0602E` (source terracotta),
  `--mz-space-1200:72px` (foundation in cascade via `assets_cashier`), **console 0 errors**.
- **`/checkout/s/<token>`** — real synthetic order (#277) + minted status token: renders
  ("Secure online payment / Amount to pay / Pay securely"), `foundation.css` linked,
  `--mz-radius-xl:16px`, terracotta brand, layout intact, **console 0 errors**.
→ **Unobserved across all 11 production pages = 0.** rc3 caveat resolved.

## Button — the biggest drift
**~12 distinct primary-action class names across ≥3 parallel systems:**
1. **`.btn--*` BEM** (cashier.css / Owl): `btn` (66), `btn--ghost` (26), `btn--primary`
   (10), `btn--confirm` (8), `btn--danger` (4), `btn--sm` (3), `btn--charge` (1).
2. **`.button--*` BEM** (a second system): `button--primary` (17), `button--positive` (6),
   `button--block` (6), `button--sm` (2), `button--strong` (1), `button--secondary` (1).
3. **Per-page ad-hoc**: `.place` (5), `.startbtn` (3), `.langbtn` (3), `.charge` (3),
   `.svcbtn` (2), `.addbtn`, `.cartbtn`, `.promobtn`, `.again`, `.sx`/`.x` (close buttons).

→ **Two full BEM button systems (`btn--` and `button--`) + per-page buttons.** This is the
single largest consolidation target.

## Other families (distinct CSS class implementations)
| Family | Distinct implementations | Notes |
|---|---:|---|
| Status / badge / pill / tag | **15** | `.badge`, `.pill`, `.tag`, `.chip`, `.status`, `.stat*`, `.PASS/.WARNING/.FAIL/.NA/.NT` (go-live), per-surface variants |
| Modal / dialog / sheet / overlay | **8** | `.modal`, `.dialog`, `.sheet`, `.overlay`, `.ov`, `.scrim` — only some carry `role=dialog` (DESIGN-P1 added it to shop/qr/kiosk) |
| Quantity stepper | **4** | `.stepper`, `.step`, cashier `less/more`, `.qty` |
| Input / field | **6** | `.in`, `.fld`, `.input`, `.field`, `.search` variants |

## Consolidation opportunity (report only — no migration this pass)
One canonical set (`.mz-btn`, `.mz-status`, `.mz-dialog`, `.mz-field`, `.mz-stepper`,
`.mz-card`/`.mz-list-row`, `.mz-alert`, `.mz-empty`/`.mz-skeleton`) consuming the
`--mz-` foundation would collapse: **~12 button names → 1 component (5 variants)**,
**15 status → 1**, **8 dialog → 1**, **6 input → 1**, **4 quantity → 1**. Owl cashier can
additionally reuse `@web/core` Dialog where beneficial (see `P3-ODOO-COMPONENT-AUDIT.md`).

## Migration status
**Not started.** This document + the Odoo audit + the canonical contract are the mandated
grounding (P3 Parts 4–6). The actual per-surface migration + RC4 is a large multi-increment
effort (each component family migrated + every one of 11 pages re-verified in light/dark/
Arabic/touch) — to be executed component-by-component, **Button first**, in focused passes.
