# Refire costing

Contract between the prototype (`Mezze POS v3.dc.html`, handheld → open table → Refire) and the
Odoo 19 implementation.

**The principle:** a refire is **two events, not one**. The kitchen issues the ingredients a second
time, and the original plate is thrown away. The remake is free to the guest; it is never free to
the branch. A refire that only reprints a ticket loses the entire cost of the incident.

---

## 1. The chain

```
refire a sent line
  ↓
reason                 8 fixed reasons, each carrying an owner and a waste category
  ↓
responsible station    the KDS stations, plus Service and Not attributable
  ↓
cost shown             the original plate priced from its recipe, line by line
  ↓
confirm                ticket refires · discarded plate posts to waste · incident logged
```

Nothing is charged to the guest at any point. The only money that moves is stock leaving the branch.

## 2. Reasons, owners and waste categories

The reason determines both who owns the cost and how the discarded food is classified, so the two
can never be set inconsistently:

| Reason | Owner | Waste category |
| --- | --- | --- |
| Sent back by the guest | guest | Returned |
| Wrong item made | kitchen | Wrong preparation |
| Cooked wrong | kitchen | Burnt |
| Cold on arrival | service | Wrong preparation |
| Dropped in service | service | Dropped |
| Allergen risk | kitchen | Wrong preparation |
| Never reached the table | kitchen | Wrong preparation |
| Long wait — remade | kitchen | Over-prepared |

Picking a reason **pre-selects** the station: service reasons default to `Service`, a guest change of
mind to `Not attributable`. The user can override — the default is a suggestion, not a lock.

`Not attributable` is a first-class answer, not an escape hatch. A guest changing their mind is not
the grill's fault, and forcing a station in that case corrupts station reporting, which is the whole
reason the field exists.

## 3. Cost derivation

- The remake cost is the dish's **recipe cost**: every BoM line priced at its product's cost. The
  sheet shows the breakdown before confirming, so the server sees what the incident costs.
- On confirm, each recipe line becomes its own **waste record** — same ledger, same shape as a
  manual write-off — carrying the reason's waste category, the responsible station, the employee,
  the table as the related order, and a `refire` tag naming the dish.
- Writing per ingredient rather than one lump sum is deliberate: plate cost attributes variance per
  ingredient, so a lump-sum refire would be invisible in the usage table.
- Verified remake costs in the prototype: Mixed Grill 92.30 (4 lines), Kofta 84.75, Shish Tawook
  51.25, Falafel Sandwich 41.93, Baklava 24.00, Tabbouleh 16.58, Turkish Coffee 10.64.
- A dish with no recipe on file shows "cost cannot be derived" rather than a zero. Zero would read
  as free.

## 4. Odoo mapping

- The refire is a new `pos.order.line` flagged as a remake at **zero price**, linked to the original
  line — not a duplicate of the paid line. Revenue must not double-count.
- The discarded plate is a `stock.move` per BoM component to the branch waste location, exactly as
  `docs/INVENTORY_WASTE.md` specifies, with the refire's reason as the move reference.
- The remake's own consumption comes through the normal sale-consumes-BoM path, so the ingredients
  leave stock twice for one sale. That is correct and is the point.
- Store the incident as `mezze.refire`: original line, dish, reason, owner, station, employee,
  table, derived cost, timestamp. This is the record the reports read.
- KDS: the refired ticket should print marked as a remake with its reason, so the line knows why it
  is cooking it again. Priority handling is a separate decision — see open questions.

## 5. Permissions

| Role | Can |
| --- | --- |
| Server | Refire a line they sent, with reason and station |
| Shift lead / manager | Refire anything; reassign a station after the fact |
| Accountant | Read the cost, not change it |

A refire is not a void and not a comp: it needs no manager PIN by default, because blocking it
delays the guest's food. Control is **after the fact** through reporting — a server or station with
an outlying refire rate is the signal, not an approval gate. If a branch wants a threshold, put it
on value per shift rather than per incident.

## 6. Reporting — the reason this exists

- Refire cost by station, by reason, by employee, by day-part.
- Refire rate per dish: one dish refired far more than others is a recipe or spec problem, not a
  cook problem.
- Guest-owned vs kitchen-owned vs service-owned split. A branch where most refires are
  `Not attributable` is under-recording, the same failure mode as under-logged waste.
- Refire cost belongs **next to** waste in food-cost reporting, not inside it — same account, but
  reportable separately, because the management action is different.

## 7. Acceptance

Refire a Mixed Grill from table 4 with `Cooked wrong` and station Grill: the guest's bill is
unchanged, four waste records appear against Grill totalling 92.30 LE with reason `Burnt` and the
table as the related order, on-hand falls by each recipe quantity, plate cost's per-ingredient
attribution moves by the same amounts, and the incident appears in refire reporting owned by the
kitchen. Refire the same dish with `Sent back by the guest`: station defaults to
`Not attributable`, the waste category is `Returned`, and station reporting is untouched.
