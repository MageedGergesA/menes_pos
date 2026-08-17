# The Mezze Kiosk experience

> **SUPERSEDED by Kiosk V2.** This page describes the V1 experience, which shipped before
> the approved Claude Design *Mezze Kiosk v2* was implemented. It is kept
> because it is true of the commit it describes; the current kiosk is
> `V2-DESIGN-MAPPING.md` + `KIOSK-V2-EVIDENCE.md`. The DOMAIN contract it
> documents (the shared configuration engine and the server authority) is
> unchanged and still current.


What a customer meets, and why it is shaped this way. The patterns come from the
benchmark (`BENCHMARK-KFC-MCDONALDS.md`); the look is Mezze's own — the Mezze token
system, Hanken Grotesk / IBM Plex Sans Arabic, the 4/8 px rhythm, terracotta accent,
and the same shared component styles the rest of the product uses.

## Screen zones

A 1080×1920 kiosk is a physical machine. Its top edge can sit ~1.7 m above the floor,
which is above the shoulder of a seated customer. So the screen is banded by **reach**,
not by web convention:

```
0 – 30%    INFORMATION ONLY   branch identity · service mode · language
30 – 65%   COMFORTABLE        the menu
65 – 100%  EASY REACH         category rail · order bar · primary CTA
```

Measured at 1080×1920 (`kiosk-reach-zones-1080x1920.jpg`, and asserted by `test_74`):

| Control | Centre | Band |
|---|---|---|
| Branch identity | 46 px | information only |
| Language | 46 px | information only |
| Service mode | 46 px | information only |
| Category rail | 1772 px | **easy reach** |
| Order bar / View order | 1870 px | **easy reach** |

That is why the category rail is **docked at the bottom in portrait** and only rides
under the header in landscape, where the whole screen is within reach. Categories are
switched constantly; putting them at the top of a two-metre machine is the mistake the
benchmark's own accessibility feedback reports.

The first row of product cards begins at 172 px, which is in the top band — but a card
is 660 px tall, so its lower two-thirds are comfortably reachable, and the grid scrolls.
Nothing that *must* be pressed lives up there; only food does.

## Portrait (primary target, 1080×1920)

```
┌──────────────────────────────────────────┐
│  ◧ Branch            Takeaway    ع       │   information band
├──────────────────────────────────────────┤
│  Pizza  11                               │
│  ┌─────────────┐  ┌─────────────┐        │
│  │   image     │  │   image     │        │   the menu — 2 large
│  │             │  │             │        │   image-led columns
│  │ Burger Meal │  │ Classic …   │        │
│  │ USD 100.00  │  │ USD 60.00   │        │
│  │ [ Choose ]  │  │ [ Add ]     │        │
│  └─────────────┘  └─────────────┘        │
│              …scrolls…                   │
├──────────────────────────────────────────┤
│  Make it a meal?  +USD 40   [No] [Yes]   │   (at most once)
├──────────────────────────────────────────┤
│  All · Misc · Desks · Chairs · Bre▌      │   easy reach
├──────────────────────────────────────────┤
│  ① USD 60.00            [ Review order ] │   easy reach
└──────────────────────────────────────────┘
```

Two columns, not four: a card is a *premium* target, ~500 px wide and ~660 px tall, with
a square image, a 24 px name and a 24 px price. Chrome takes under 30 % of the screen
(`test_70`); the menu gets the rest.

## Landscape (1920×1080)

Five columns, the rail under the header, the same order bar. Not stretched portrait
cards — the grid changes column count, and the card's image goes 4:3 (`test_72`).

## The menu

* **Categories are the branch's own** `pos.category` records, in their own order, "All"
  first. Mezze does not invent a taxonomy; if a branch configures Meals / Burgers /
  Chicken / Sharing / Sides / Drinks / Desserts, that is exactly what the rail shows.
* **The rail says it scrolls**: a fade mask at the trailing edge and a chip deliberately
  cut by that edge (`test_73`). This is the single most-reported failure of the
  benchmarked kiosk, and it is a one-line CSS fix.
* **The chosen category is scrolled into view**, so the rail never shows a different
  category from the heading.
* **A heading names where you are** — the category and how many items are in it.
* **The whole card is the target.** A small button inside a large card is a small target
  inside a big one. The card is a `<button>`; the pill inside it is a `<span>` that says
  *Add* for a plain item and *Choose* for one with questions.

## The meal builder

A meal is shown as its parts. An unanswered component shows its options; an answered one
becomes a single line — the component, what was chosen, what it added — with **Change**.

```
K Choose your burger
┌────────────────────────────────────────────────────┐
│ K Double Burger                +USD 20.00 [Change] │
└────────────────────────────────────────────────────┘
K Choose your drink
┌────────────────────────────────────────────────────┐
│ K Coke Zero                     +USD 5.00 [Change] │
└────────────────────────────────────────────────────┘
K Choose your sides       Choose up to 2 · 1 included
  ○ K Fries          ○ K Salad +3.00   ○ K Rings +10.00
────────────────────────────────────────────────────
ITEM TOTAL                                USD 125.00
[            Add to order · USD 125.00              ]
```

Rules, each with a reason:

| Behaviour | Why |
|---|---|
| A component collapses only once the **customer** answers it | a pre-selected size that hides the other sizes is a choice made for them |
| A component that can still take more (*Choose up to 2* at one) **stays open** | that is where "add another" lives; collapsing it hides the second helping |
| **Change** reopens exactly one component | changing the drink must not cost you the burger |
| A failed **Add** reopens the component it is complaining about and scrolls there | the message and the fix are in the same place |
| A single-question product is never collapsed | there is nothing to summarise; the panel *is* the question |
| Header and foot stay put, the questions scroll | the price and the button never leave the screen (`test_51`) |

Taps are unchanged by the summary: a three-group meal is still **Choose → 3 answers →
Add** = 5.

## The basket

The order bar is pinned to the bottom of every menu screen and never disappears. Empty,
it says *Tap an item to start your order* and the **Review order** button is disabled;
with items, it shows the count and the running total.

The benchmarked kiosk deliberately hides the running total on its add-on screen so the
customer cannot recall what they have already spent. Mezze does the opposite, and
`test_81` asserts it: while a recommendation is on screen, the order bar is still there,
still showing the total, and the offer sits **above** it.

## The recommendation

At most **one** per order.

* **Relevant** — derived from the branch's own data: a combo that genuinely contains the
  item just added. If no meal contains it, no offer exists (`test_85`).
* **Priced** — the real difference (`meal price − item price`) is on the offer before
  the customer touches anything.
* **Declinable** — *No thanks* and *Make it a meal* are the same size, the same height,
  side by side (`test_80`).
* **Once** — the budget is spent when the offer is **shown**, not when it is answered, so
  a customer who ignores it is not asked again on the next item (`test_82`).
* **Honest about the swap** — accepting opens the meal with their item already in it;
  the single item is replaced by the meal, not added alongside it (`test_84`).
* **No scarcity, no confirmshaming, no hidden decline.**

Declining leaves the order exactly as it was (`test_83`).

## Journey

```
START ─ Order here ─ eat in / takeaway
  └─ MENU ─ category rail ─ card
        ├─ plain item → in the order (1 tap)
        └─ configurable → the builder → Add to order
  └─ REVIEW ─ lines with their configuration, Edit, quantity
  └─ PLACE ─ order number ─ pay at the counter
```

The service mode is stated in the header for the whole order, not only on the screen
where it was chosen, and can be changed there.

## Would a McDonald's or KFC customer understand it immediately?

Yes: menu-as-canvas, image-first cards, a category rail, a meal shown as its parts with
a way to change each one, a persistent basket, one big button at the bottom.

## Does it still look like Mezze?

Yes: Mezze's palette and type, Mezze's radii and spacing, the same `mz-btn`, stepper and
alert components as the Register and the Drive-Thru, and the same shared configuration
engine underneath. Nothing about it is borrowed from either brand's visual identity.
