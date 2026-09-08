# Group governance (HQ)

Screen **47 HQ governance** — the second tab of the Group surface (Group console · HQ governance).
The Group console answers "how is the chain trading". This screen answers the three questions a
chain or franchise operator actually has: **what is set here, what is inherited, and what a branch
is allowed to change on its own.**

A franchise is not a branch with a flag. It is a contract, and this screen is the contract.

---

## Organisation hierarchy

**Company → Brand → Region → Branch**, one tree, selectable at every level:

- **Mezze Holding** — one company, two brands
  - **Mezze** (casual dining) — Greater Cairo *(owned)*: Downtown, Zamalek, New Cairo · Delta *(franchised)*: Mansoura, Tanta
  - **Mezze Express** (counter and drive-thru) — Alexandria *(franchised)*: Alexandria · West Cairo *(mixed)*: Sheikh Zayed *(fit-out)*, 6th October

Every row carries its **rolled-up net sales** and its **compliance score**, so the tree is a
diagnostic, not navigation. Selecting a node re-scopes everything to the right of it: the KPI
strip, all nine governance domains, the franchise controls, the fees and the compliance panel.
Sales roll up by sum; labour % and food % roll up **weighted by sales**, never averaged.

The breadcrumb across the header is the same path, clickable back up.

## Central management — nine domains

Each domain is the same shape: what the group sets, what each branch in scope currently does, the
state, and the action that resolves it.

| Domain | What HQ holds | What is measured per branch |
|---|---|---|
| **Global menu** | one versioned menu (live: v12) | version behind, override count, push v12 |
| **Global price** | the price book + the ±8% **band** | multiplier, deviation, inside/outside the band |
| **Promotions** | group campaigns with a funding split | scope, funding, declined-by, local approvals |
| **Recipes** | core recipes locked, sides open | recipes changed without approval, yield variance |
| **Vendors** | 6 mandated / 11 preferred categories | off-list spend in money and as a share of sales |
| **KPIs** | targets set at the brand | labour %, food %, unproved receipts vs target |
| **Device fleet** | firmware and configuration | devices online / total, firmware state |
| **User permissions** | role templates at the company | deviations, risky grants (voids, discounts) |
| **Tax configuration** | one registration per company | receipt series, unproved, filing on time |

**Branch override** is the through-line: a branch never edits the group object, it publishes an
override against a version, and the override names what changed and why. A push keeps overrides
rather than flattening them, and tells you how many branches have a device offline (they take the
push on reconnect).

**Price boundaries** are the whole control. Inside the band a branch moves on its own; outside it,
it asks. Bands are per brand, not per branch — Express carries a tighter band than the casual
brand because its price *is* the promise.

## Franchise controls

**Allowed override** — the agreement as a table, three verdicts only:

- *Allowed*: move a price inside the band, change opening hours
- *Needs approval*: move a price outside the band, run a local promotion, buy off the approved list
- *Blocked*: remove a core dish, change a core recipe, change branding or signage

A blocked request cannot be approved by anybody — the refusal says why: it changes the brand the
franchisee bought.

**Approval queue** — live requests from franchised branches, each with the number that matters
(`Mixed Grill 340 → 395 LE · +16% — outside the 8% band`). Approving writes the change into the
branch price book with an expiry and an audit line; declining leaves the group setting and keeps
the request on the record.

**Royalty and fees** — royalty 5% of net sales, marketing fund 1.5%, technology 450 LE per
terminal per month, supply rebate −0.8% credited back. Each shows its basis, its rate and the
accrued amount for the current scope. All of it reads the same net sales the branch closes its
session on — never a figure the franchisee types in.

**Central purchases** — mandated categories, spend bought centrally, off-list spend, rebate
earned. Off-list spend is stated in money because that is what it is: the rebate the whole group
loses.

**Compliance score** — derived, never typed, from six lines: menu version current, prices inside
the band, core recipes unchanged, buying on the approved list, tax filing on time, training signed
off. At a branch you see every line with the points it costs and the weakest one named; at any
level above you see the branches ranked weakest-first, each with its weakest line. Every point lost
points at a screen that can fix it.

---

## Odoo mapping

Company → brand → region → branch maps to Odoo companies and analytic tags:

- the **company** carries the tax registration and the chart of accounts
- the **brand** carries the menu (`product.template`) and the pricelist
- the **region** carries targets and area management
- the **branch** carries the POS configs, devices and staff

Overrides are pricelist items and product variants scoped to the branch company, not edits to the
group record. Permissions are Odoo access groups: HQ changes the template, the branch inherits it
on next login. Central purchases feed the same Inventory internal transfers a branch already
receives against — there is no parallel purchasing system. Royalty and fees post as intercompany
invoices from the franchisor company to the franchisee company.

## Bilingual

Every string goes through `tr()` / `N()`; the tree, the domain strip and all nine panels are RTL
with Arabic-Indic numerals. Domain names that collide with branch-level surfaces (`Vendors`,
`Recipes`, `Promotions`, `Devices`, `Tax`) reuse the existing key where the meaning matches, per
`docs/AR_KEY_COLLISIONS.md`.
