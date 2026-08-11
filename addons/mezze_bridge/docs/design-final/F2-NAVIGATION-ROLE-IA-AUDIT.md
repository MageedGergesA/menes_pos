# F2 — NAVIGATION / ROLE IA AUDIT

Audit of the navigation that **actually ships**, before any redesign. Evidence = source + a live
authenticated run (verification server 8088, DB `mezze_ui`, admin session, computed styles measured).

## 1. Navigation systems that exist today

| System | Where | Markup | Destinations | Current cue |
|--------|-------|--------|--------------|-------------|
| **Workspace nav (Register)** | `cashier/root.xml:14-30` | `<nav class="mz-nav">` + 1 `<a>` + 3 `<button>` | Floor · Register · Orders · Reservations | `.mz-nav__item--active` + `aria-current="page"` |
| **Workspace nav (Floor)** | `floor/root.xml:15-18` | `<nav class="mz-nav">` + 1 `<span>` + 1 `<a>` | Floor · Register | same |
| **KDS** | `kds/root.xml` | — | **none** | — |

`.mz-nav`/`.mz-nav__item` is **defined twice** — `cashier.css:384-390` and `floor.css:20-25` — i.e. navigation
is the one component family the P3 program never canonicalised (P3I correctly classified it as *navigation,
not tabs*, and then left it un-owned).

## 2. Measured defects (live, computed styles)

| ID | Defect | Evidence | Severity |
|----|--------|----------|----------|
| **N-1** | Register's `<button>` nav items keep the UA `buttonface` background: `.mz-nav__item` never resets `appearance`/`background`/`border` for buttons, so `<a>` renders transparent and `<button>` renders `rgb(239,239,239)` — **same class, two renderings**. Text stays theme-coloured → illegible. | Orders/Reservations measured **1.37:1** (Classic dark), **1.19:1** (light), **1.02:1** (High Contrast dark). AA needs 4.5:1. | **CRITICAL** |
| **N-2** | Nav item `min-height:36px` — below the 44px operational touch minimum, on the primary workspace switch of a touch POS. | measured `h:36` on all 6 nav items across both apps | HIGH |
| **N-3** | Floor has **no `.mz-nav__item:focus-visible` rule** (cashier.css has one, floor.css does not) → the focusable "Register" link shows no visible focus. | `navFocusVisibleRulePresent: false` on `/mezze/floor` | HIGH |
| **N-4** | The whole app shell drifted between the two staff workspaces: 6 of 8 shell classes differ — topbar background `--mz-surface` vs `--mz-surface-2` (measured `rgb(42,37,29)` vs `rgb(51,45,35)`), padding `12/20` vs `8/16`, logo `20px` vs `18px`, plus `.mz-branch`/`.mz-topbar-right`/`.mz-user`. Floor↔Register visibly jumps. | computed styles both apps | HIGH |
| **N-5** | Nav destination set is not stable: Floor shows 2, Register shows 4. Orders/Reservations require going through Register first. | source + live | MEDIUM |
| **N-6** | KDS is not reachable from any product navigation. | route grep + live | MEDIUM (see §4) |

## 3. Role workflows (from CP1–CP12 production behaviour, not the prototype)

| Role | Needs frequently | One tap away | Must NOT see | Manager-gated |
|------|------------------|--------------|--------------|---------------|
| **Cashier** | Register, active Orders, Payment | Register, Orders, Floor | admin/go-live, support bundle | reversals, refunds beyond ceiling (already enforced server-side) |
| **Host** | Reservations, Waitlist, table availability | Reservations, Floor | payment internals | — |
| **Waiter/server** | Floor map, table assign/transfer, coursing | Floor, Register | admin | — |
| **Kitchen** | KDS board + station filter only | station filters | **financial nav, totals, payment** | — |
| **Manager** | everything above + go-live/settings | — | — | onboarding/go-live console |
| **Customer** | one linear ordering flow | — | all staff surfaces | — |

## 4. Answers to the required IA questions

- **Duplicated?** Yes — the shell/nav vocabulary is duplicated across two CSS files and has drifted (N-4).
- **Dead destinations?** **0.** Every destination in production navigation resolves to a real, implemented screen.
- **Unauthorized destinations exposed?** **0.** All three pages are `auth='user'`; API capability/branch scope is
  enforced server-side per route (`domain/authz.py`, `route_scope.py`) and is unchanged by this program.
- **Prototype-only destinations exposed?** **0.** Reports / Manager / HQ / Live-Ops / Central-Kitchen exist only
  inside `static/pos.html` and are correctly absent from production nav.
- **Awkward backtracking?** Yes, mild — Orders and Reservations are 2 clicks from Floor instead of 1 (N-5).
- **Unreachable?** KDS (N-6).

## 5. Decisions

1. **Canonicalise navigation** into `design/components.css` as the missing component family, and delete both
   per-app copies. This is a *genuine omission* of the P3 program, not a new family invented for aesthetics.
2. **Fix N-1/N-2/N-3/N-4** — all pure CSS, no logic.
3. **N-5:** give Floor the same destination set as Register via deep-links (`?view=orders` / `?view=reservations`)
   plus a minimal, boot-time-only param handler in the cashier. Covered by new tests.
4. **N-6: KDS stays out of staff workspace navigation — deliberate.** The brief requires that kitchen staff not
   get financial/navigation clutter, and KDS runs on a dedicated always-on kitchen display, not on a device that
   roams between workspaces. Adding KDS to the cashier nav would put a kitchen destination on the money screen
   and a money destination one tap from the kitchen. Recorded as an accepted product decision, not a defect.
5. **No role-based nav filtering is introduced.** The only role distinction that exists today is Odoo's native
   `point_of_sale.group_pos_user` / `group_pos_manager`; every production page is `auth='user'` with no group
   gate. Inventing nav-level roles would *replace* access rules rather than reflect them — explicitly forbidden.
   Role appropriateness is therefore achieved by **which workspace you open**, not by hiding items.
