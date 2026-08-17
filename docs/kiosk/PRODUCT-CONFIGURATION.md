# Kiosk product configuration

> **SUPERSEDED by Kiosk V2.** This page describes the V1 configuration contract, which shipped before
> the approved Claude Design *Mezze Kiosk v2* was implemented. It is kept
> because it is true of the commit it describes; the current kiosk is
> `V2-DESIGN-MAPPING.md` + `KIOSK-V2-EVIDENCE.md`. The DOMAIN contract it
> documents (the shared configuration engine and the server authority) is
> unchanged and still current.


The Kiosk can sell a configurable product. Before this phase it could not: a required
choice was skipped silently at base price, and a combo could be put in the cart but
never ordered.

## Architecture — one engine, two presentations

```
        design/product-config.js          ← the RULES (canonical, shared)
        groups · defaultSelection · toggle · isOn · countOf · roomLeft
        chosen · comboSelectionFrom · extraPrice · missingRequired · lineKey · comboIds
                  │                                   │
      ┌───────────┴───────────┐             ┌─────────┴──────────┐
      │ STAFF presentation    │             │ CUSTOMER presentation │
      │ design/product-config │             │ design/customer-config │
      │   .css                │             │   .js + .css           │
      │ Register (Owl) ·      │             │ Kiosk (kiosk.html)     │
      │ Drive-Thru lane       │             │ QR — able to adopt it  │
      └───────────────────────┘             └────────────────────────┘
```

No kiosk-specific configuration engine exists, and the kiosk file contains no mention
of `qty_max`, `qty_free`, `base_price` or `extra_price` — a test asserts that. What the
kiosk owns is the *question as a customer meets it*: a full-height touch panel, one
question per section, 68 px option rows, an explicit quantity control, a running price
and one large button.

`design/customer-config.js` is a renderer, not a second engine. It takes a product, a
money formatter, a translator and a direction, and calls the shared rules for every
decision. It is deliberately surface-agnostic so QR can adopt it later without a copy
— **QR is not wired to it in this phase**.

## The customer's path

| | |
|---|---|
| Plain product | one tap → in the order. The card's button says **Add**. |
| Configurable | tap → the panel. The card's button says **Choose**. |
| Combo | tap → the same panel; the groups are the meal's questions. |

The panel opens on the *implied* answer where there is one (a single-select attribute
pre-selects its first value, which is the canonical rule) and on nothing at all for a
combo group — "which burger" is the question being asked, and answering it for the
guest is how a wrong plate gets made.

## What the customer is told, and how

| System fact | What is on screen |
|---|---|
| single-select attribute | **Required** |
| multi-select attribute | **Optional** |
| combo group, `qty_max = 1` | **Choose 1** |
| combo group, `qty_max = 2, qty_free = 1` | **Choose up to 2 · 1 included** |
| `extra_price` | `+USD 5.00` on the option, and nothing at all when it is zero |
| beyond `qty_free` | the running total moves the moment the second one is taken |

`qty_max`, `qty_free`, `combo_item_id` and `attribute_value_id` never reach the screen
— a test greps the rendered panel for them.

## Interaction rules

* **Choose-one replaces.** Tapping another option in a required group swaps it; the
  customer never has to deselect first, and tapping the option they already chose does
  nothing (the shared toggle allows emptying a group — a cashier sometimes needs that —
  but a customer would be walking into a dead end they did not cause).
* **More than one uses a stepper.** Where `qty_max > 1`, a chosen option grows a
  `− n +` control beside it. Tapping the option again does not silently add a second.
  At the ceiling the `+` and the remaining options are disabled rather than hidden.
* **Nothing is called wrong before the customer acts.** The "Required" chip states the
  rule; only pressing **Add to order** with a question unanswered marks the group,
  writes a message and scrolls to it.
* **Selection is never colour alone** — the check mark fills, the border changes, and
  `aria-checked` says so.
* **A long configuration says where you are.** From four questions up, each group's
  header carries "3 of 6"; below that it would be noise.
* **Arrow keys work inside a choose-one group**, which is what a radiogroup is
  expected to do and the only way a keyboard or switch user can move between
  alternatives without tabbing through all of them.
* **The validation message is an instruction, said once.** A group already phrased as
  a question ("Choose your burger") is shown as it stands; a group called "Sides" gets
  the verb in front of it.

## Money

The panel's running total uses the shared `extraPrice`, which is Odoo's own
`computeComboExtraPrice`:

```
extra = max(0, taken − qty_free) × combo.base_price + Σ(qty × item.extra_price)
```

and the server re-derives the same number independently. The customer never sends a
price: `_sanitize_customer_lines` strips `price_unit`/`discount`, and combo children
are priced by `_combo_child_vals` from Odoo's `computeComboItems`. **Preview = server =
POS order = amount due at the counter = receipt.**

## The two things a public terminal needs

### Available in Self Order

`pos_self_order` puts `self_order_available` on `product.template` (default `True`) and
ANDs it onto its own self-order product domain. Mezze now does the same, in two places:

* `/shop/menu` with `channel='kiosk'` filters on it — the storefront's menu is
  deliberately unchanged, because Shop is not a self-order channel here;
* the kiosk order path refuses an excluded product outright, because a hand-made
  request never went through the menu.

Combo *choice* products are not gated, which matches Odoo: its own self-order loader
adds combo choices to the payload regardless of the domain.

The gate is soft — where `pos_self_order` is not installed the field does not exist and
POS availability is the only truth there is.

### An untrusted client

Before a row is written, the kiosk path re-derives:

| Check | Where |
|---|---|
| product exists, not 86'd | `_assert_available` |
| allowed in self-order | `_assert_selforder_allowed` |
| every chosen option is offered by THIS product | `_assert_customer_config` |
| quantity is a real one (`0 < qty ≤ 99`) | `_assert_customer_config` |
| single-select group not over-selected | `_validate_modifiers` |
| combo item belongs to this combo, `qty_free ≤ taken ≤ qty_max` | `_resolve_combo` |
| price | recomputed from the pricelist + real `price_extra` |

A refusal therefore leaves **no** order, no line and no kitchen ticket — the same rule
the staff combo phase established after finding the opposite.

The server's messages are rules, not sentences ("Combo X needs 1 item(s) from Y"). The
kiosk maps them to customer language and never puts an internal message on the screen.

## Cart

* Identity is the canonical `lineKey`: product + attribute values + combo items **and
  their quantities**, sorted, so `[A,B]` and `[B,A]` are one line and Fries ×1 and
  Fries ×2 are not.
* The line reads back what was chosen (`K Double Burger · K Coke Zero · K Fries x2`),
  not "3 options".
* **Edit** reopens the panel on exactly that configuration, including a repeated unit,
  and saves in place — same slot, new price, no twin line. If the correction happens to
  match another line already in the order, the two merge.
* An identical configuration added again increments the quantity, which is the
  behaviour every other Mezze surface already has.
* **Back / Escape leaves the order untouched** — no half-configured line, no server
  artifact.
* A reset (idle timeout or *New order*) also closes an open configurator: a panel left
  mid-question is previous-customer state too.

## Deliberately not done

| | |
|---|---|
| Customer kitchen notes | The kiosk has never had a free-text note box and does not get one here. A customer-entered note is an operational and allergen-safety decision, not a UI gap. Recorded as a product decision. |
| Allergen / dietary labels | No product metadata supports them; nothing is inferred from option names. |
| Variant selector on one card | Variant-creating attributes produce separate `product.product` records, which are already separate cards with their own prices. The kiosk orders the canonical resolved variant — it never composes one from labels. Grouping them behind one card is a different data contract. |
| QR | Can adopt `customer-config.*` unchanged. Not wired here. |
| Shop / QR `qty_max > 1` | Still choose-one pickers. Correct for the default, wrong above it. **Open debt.** |
