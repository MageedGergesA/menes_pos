# Workforce workflows

Four chains the workflow audit called out as broken, wired end to end. All four live behind the
**Team admin** tab strip (Requests · Roster · Slots · On shift · Onboarding · Absence · Breaks ·
Reports) and are gated by TEAM_READ like the rest of that surface.

Screens: **44 Onboarding**, **45 Same-day absence**, **46 Break compliance**, plus a global
clock-out guard sheet that can fire from any surface that clocks somebody out.

---

## 1. New employee → first shift (screen 44)

Seven steps, one at a time, with the employee record building in a card beside them:

| Step | What it decides | What blocks it |
|---|---|---|
| Employee | full name → derived short name | needs a first and family name |
| Role | permissions default, pay rate, roster template | none picked |
| Permissions | capability list, each mapped to an Odoo access group | all permissions off |
| PIN | four digits, entered twice | reused, guessable, or mismatched |
| Training | modules for the role, required vs optional | a required module unsigned |
| Roster | shift template + week-one days | no day picked |
| First shift | trainer to shadow, warnings, activate | required training still unsigned |

**The role is the spine.** `WF_ROLES` carries `caps`, `rate`, `tpl` (shift templates) and `train`
(modules). Changing the role reseeds the defaults; every later change is a deviation from them.

**Permissions are Odoo groups, not checkboxes.** `WF_CAPS` maps each capability to its group
(`point_of_sale.group_pos_user`, `pos_restaurant.group_kitchen_display`, …). Risky ones — drawer,
cash bag, discount, void, reports — are marked and shown in accent.

**Two different gates, deliberately:**
- A **required module** for the role blocks activation outright.
- A **capability that depends on a module** (`DRAWER_OPEN` and `CASH_CARRY` need Cash handling) is
  granted but **withheld** until the module is signed — so the person exists, works, and simply
  cannot open the drawer. The toast says how many were withheld and why.

**PIN rules** are enforced at entry, not on the floor: four digits, not already in use (checked
against `HH_STAFF` and anyone hired this session), not a repeat digit or an obvious sequence,
and confirmed twice.

**Activation writes real state:** a `staff` record (clockable), `rosterOv` entries for the chosen
days so the shift appears on the roster and the slot, and an `obHired` entry carrying the PIN, the
granted and withheld capabilities, the signed training and the approver. `wfPeople()` is the roster's
people source — seed staff plus this session's hires — so onboarding ends in a shift, not a toast.

Week one is **shadowing**: the shift lands on the roster but the day still reads short until
somebody else fills it.

---

## 2. Same-day absence → covered roster (screen 45)

Three columns, left to right, in the order the manager works:

1. **Rostered today** — everyone with a shift today plus their live clock state. `Mark absent`
   opens the reason chips (Sick · No-show · Family emergency · Injured at work · Transport).
   Marking absent immediately: clears the shift (`rosterOv[who|0] = null`), writes an
   `absence` request with the shift snapshot and the manager's name, and says what changed —
   the shift is vacant and the roster shows the day short.
2. **Eligible cover** — everyone on the same role, scored and explained rather than filtered
   silently. Eligible means: free today, not on approved leave, and at least **11 hours rest**
   since the previous rostered shift (the week wraps, so Saturday reads Friday). Each candidate
   shows weekly hours, rest gap and the cost of the shift; anyone past 48 hours in the week is
   shown **with** the overtime premium instead of being hidden. Ineligible candidates stay
   visible, dimmed, with the reason named.
3. **Roster result** — who covered it, which slots are still short, and the audit trail.

`Broadcast to everyone eligible` asks all of them at once (first to accept takes it); individual
`Ask` toggles work too. `Accepts` is the reply: it writes the vacant shift onto the coverer
(`rosterOv`), flips the request to `covered`, and moves the name on the day's slot. Nothing else in
the app has to be told — the roster **is** the record.

If nobody is eligible the refusal is specific: everyone on the role is working, on leave or inside
the rest minimum, and the options are the area manager or running short.

---

## 3. Clock-out protection (global sheet)

`stClockOut(p)` refuses in two cases and names both:

- **Open tables.** `stOpen(p)` finds every table still assigned to them that is not free, dirty or
  cleaned. The sheet lists each one — id, zone, party, state, open value — and totals the money:
  *"9 tables are still yours, 6,150.00 LE of open checks. A clock-out does not close them — it just
  leaves them without a server."*
- **A mandatory break neither taken nor recorded** (overdue or violation, see below), with the
  minutes outstanding and the deadline.

Ways out, all real:
- **Transfer the section** to a colleague on the same role who is clocked in and not on break —
  each shown with their current table load. The transfer reassigns every table and the floor
  sections, says how much money moved with them, and then completes the clock-out.
- **Open break compliance** to take or record the break.
- **Stay clocked in.**
- **Clock out anyway** — allowed, but it writes a second log line naming the open tables and the
  unrecorded break against the approver, and the toast says the tables were left without a server.

---

## 4. Break compliance (screen 46)

House rule (`BRK_RULE`), stated on the screen rather than buried: a shift of **6 hours or more**
carries a **30 minute unpaid meal break**, which must start before the end of **hour 5**. Every
**4 hours** rostered adds a **15 minute paid rest break**. Past the deadline it is **overdue**;
**30 minutes** past that it is a **violation**.

The four states the audit asked for, as a strip and as a state per row:

| State | Meaning |
|---|---|
| Entitled | entitlement outstanding, still inside the window |
| Taken | entitlement met |
| Overdue | meal deadline passed, inside the grace period |
| Violation | past the grace period with the meal break untaken |
| Waived | recorded as missed, with a reason and a manager's name |

Entitlement is set by the shift **as rostered**, not by hours worked so far, so it does not shrink
when somebody clocks in late. The table shows worked, entitlement (meal + rest split), taken, the
meal deadline with how late it is, what is outstanding, the state, and the actions: send on break,
back from break, or record as missed.

`Record as missed` needs a reason (service peak, employee declined, cover unavailable, shift ended
early). It is not an eraser: the outstanding minutes are **paid as worked time**, the entry carries
the manager's name, it appears on the labour report and the audit log — and only then does clock-out
unblock.

Seeded so all four states are real on open: the morning line cook (in at 06:30, no break) is a
violation; the runner (in at 10:30) is overdue; the rest are entitled or taken.

---

## Odoo mapping

- **Onboarding** creates `hr.employee` with a `res.users` login, the access groups behind each
  permission, the POS PIN, and Planning slots for week one. Nothing here writes payroll — the rate
  lives on the contract.
- **Absence** is an `hr.leave` (unpaid or sick); the cover writes a Planning slot to the new
  employee and clears the old one. Nothing is deleted — the original shift stays on the record.
- **Breaks** are `hr.attendance` intervals; a recorded miss adds a paid-time adjustment on the
  payslip rather than editing the attendance.
- **Clock-out** is an attendance close; the table transfer is a `pos.order` / restaurant-table
  reassignment, which is why it has to happen first.

## Bilingual

Every new string goes through `tr()` / `N()`. Stage-level bare words that other surfaces already
own (`Training`, `Overdue`, `PIN`, `Employee`, `Shift`, `Worked`, `State`, `Required`, `Optional`)
reuse the existing entry where the meaning matches; anything that would have collided got its own
key, per `docs/AR_KEY_COLLISIONS.md`.
