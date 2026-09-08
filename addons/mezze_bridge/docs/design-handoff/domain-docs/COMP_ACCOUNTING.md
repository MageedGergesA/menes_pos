# Comp accounting — on the house

Contract between the prototype (`Mezze POS v3.dc.html`, handheld → open table → Pay tab →
*On the house* / *Whole check on the house*) and the Odoo 19 implementation.

**The principle:** a comp is a **deliberate revenue giveaway on food that was consumed**. The guest
ate it. Nothing returns to stock, food cost is real, and the branch chose to earn nothing on it.
That makes it a different accounting event from both a void and a discount, and the workflow audit
called out that the prototype was treating all three the same way.

---

## 1. Why it is not a void

| | Void | Comp |
| --- | --- | --- |
| Was the food made? | No, or wrongly rung | Yes |
| Was it consumed? | No | Yes, by the guest |
| Stock | Never consumed, or returns | **Stays consumed** |
| Food cost | Zero | **Full recipe cost** |
| Revenue | No sale ever existed | Sale exists, recorded at zero |
| Reason vocabulary | Entry error, kitchen error | Service recovery, goodwill |

A void says *this sale should not exist*. A comp says *this sale exists and we are not charging for
it*. Booking a comp as a void understates food cost and hides the recovery entirely — the branch
looks like it sold less rather than like it gave something away.

## 2. Why it is not a discount

A discount reduces the price of a sale the guest still pays for. It is a pricing decision, applies
before payment, and belongs in promotions and margin analysis. A comp is a **100% giveaway after
service has already failed or as deliberate hospitality** — it belongs in service-recovery
reporting, not in pricing.

Practical consequence: a 100% discount and a comp produce the same amount due but must not be the
same record. If comps are booked as discounts, discount reporting becomes meaningless — a
promotional campaign and a kitchen failure land in the same bucket.

## 3. What the design captures

Every comp carries all of it; the sheet refuses to complete without the starred fields.

| Field | Design |
| --- | --- |
| Scope * | One item, or the whole check |
| Revenue given away * | Menu value, computed live |
| Food cost carried * | Recipe cost of the same lines — shown next to the revenue |
| Reason * | 8 fixed reasons, each carrying an owner |
| Owner | Derived from reason: kitchen / service / management |
| Guest link | Optional, from the table's guests — a recovery nobody can find later is not a recovery |
| Manager approval * | PIN always; a second, senior threshold over 400 LE of menu value |
| Audit | Items, table, scope, reason, owner, guest, approver, time, both figures |

**Reasons:** `Late food` (kitchen) · `Quality complaint` (kitchen) · `Wrong order served`
(service) · `Order never arrived` (service) · `Guest recovery` (management) · `VIP or regular`
(management) · `Staff or owner meal` (management) · `Marketing tasting` (management)

Showing **revenue and cost side by side** is the point of the screen. A manager comping a 320 LE
Mixed Grill should see that it also costs the branch 92.30 LE in food that is already gone — the
two numbers answer different questions and both matter.

## 4. Revenue treatment

- The order line stays on the order with its **full price**, plus a comp line of the same value at
  negative, so gross sales are unchanged and the giveaway is explicit. Do **not** simply set the
  line price to zero — that destroys the record of what was given away.
- The offset posts to a **comps / service-recovery expense** account, not to a discount account and
  not to a sales-returns account. Suggested: `5xxx Service recovery — comps`, split by owner if
  finance wants kitchen-caused separated from management goodwill.
- Net revenue falls by the comp value. Gross sales, cover count and item mix are all unaffected —
  the dish was sold and served, and menu-engineering data should keep counting it.
- VAT: a comp is not a taxable supply for consideration. Reverse the output VAT on the comped value
  and confirm treatment with the Egyptian tax adviser — staff meals in particular may be treated as
  a benefit in kind rather than a recovery.
- Tips and service charge calculated on the check should be recomputed on the **net** value, or the
  branch pays service on revenue it never received. State the branch's policy in Settings.

## 5. Stock remains consumed

This is the half most systems get wrong.

- No stock movement is reversed. The BoM was consumed when the dish was made, and that consumption
  stands.
- Food cost for the period **includes** comped dishes. Plate cost, theoretical-vs-actual usage and
  the waste attribution in `docs/INVENTORY_WASTE.md` all see it as normal consumption, because that
  is what it was.
- A comp therefore worsens food-cost percentage twice over: cost is unchanged while the revenue it
  was meant to earn is gone. That is the honest picture and the reason comps need a manager.
- Do **not** write a comp to the waste location. Waste is food that was thrown away; a comp was
  eaten. Filing comps as waste corrupts both numbers — waste reporting inflates and recovery
  reporting disappears.
- Contrast with a **refire** (`docs/REFIRE_COSTING.md`): a refire *does* write waste, because the
  original plate was discarded. A comped refire is both events — waste for the discarded plate,
  comp for the revenue on the remake if the guest is not charged.

## 6. Permissions and control

| Role | Can |
| --- | --- |
| Server | Request; cannot approve |
| Manager | Approve up to the comp limit (400 LE menu value ships as the default) |
| Senior manager / owner | Approve above the limit |
| Accountant | Read the comp report and the journal entries; cannot alter a posted comp |

- A PIN is required for **every** comp, unlike a refire — a refire delays food if you block it, a
  comp only delays a discretionary giveaway.
- No self-approval: the approver must not be the server who requested it. Enforce server-side.
- A posted comp is immutable. A mistaken comp is reversed by a counter-entry with a reason, both
  visible.
- The thresholds belong in Settings per role, and should be reviewed against real data after a
  month — a limit set too low trains managers to split comps into several small ones.

## 7. Reporting

Surfaced in the prototype on 24 Plate cost, beside refires:

- Revenue given away and food cost carried, as two figures.
- By reason and by owner. Owner is the actionable cut: comps owned by `kitchen` are an operations
  problem, `service` a training problem, `management` a policy question.
- Per-incident history with items, table, scope, reason, guest, approver and time.
- Worth adding server-side: comp value as a % of net sales per manager, and comp rate per guest —
  a guest comped repeatedly is either genuinely unlucky or being worked.

## 8. Acceptance

Comp one Mixed Grill on table 4 for `Late food` with a manager PIN: the check drops by 320.00, the
comp report shows 320.00 revenue given away and 92.30 food cost carried, owner `kitchen`, stock is
**unchanged** by the comp itself, food cost for the period still includes the dish, and the incident
carries the approver's name. Comp a whole check over 400 LE: a senior PIN is demanded and the record
shows scope `whole check` with every line named. Confirm that gross sales and cover count are
unaffected in reporting, and that the comp does **not** appear in either discount or waste totals.
