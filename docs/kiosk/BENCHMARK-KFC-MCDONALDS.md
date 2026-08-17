# Kiosk benchmark — McDonald's and KFC

What we are borrowing is **information architecture, ergonomics, customisation UX,
menu discovery, basket building and customer flow**. Not colours, not logos, not trade
dress, not card designs, not artwork. Mezze's visual identity is unchanged: the Mezze
token system, Hanken Grotesk / IBM Plex Sans Arabic, the 4/8 px rhythm and the
terracotta accent.

The observations below come from published UX case studies, teardowns and field
reports, cited at the end. Nothing was traced, screenshotted into the product, or
reproduced.

---

## McDonald's

### 1. The menu is the canvas

**Pattern observed** — the ordering screen gives almost all of its area to food:
large photographed items, name, price, very little else. Navigation and chrome are
thin bands at the edges.

**Why it works** — a customer at a kiosk is choosing food, not operating software.
Every pixel spent on chrome is a pixel not spent on the decision they came to make,
and photography answers "what is this?" faster than any label.

**Mezze adopts** — the menu body is the largest region on every viewport; header and
category rail are thin bands; the order bar is one row. Product cards are
image-first with name and price and nothing else.

**Mezze rejects** — the promotional content that competes with navigation on the
same screen. One job per region.

### 2. Pre-configured meals up front

**Pattern observed** — "popular picks" and ready-made combinations appear early with
photography, so a customer can decide intuitively instead of assembling an order.

**Why it works** — most customers want a normal meal. Making the common case one tap
respects them and shortens the queue.

**Mezze adopts** — combos are ordinary menu cards, and a combo card says *Choose*
rather than *Add* so the customer knows a question is coming. Where a branch
configures a meal, it appears in the menu exactly like a dish.

**Mezze rejects** — an intent-router screen ("I want something healthier") in front of
the menu. It adds a step before any food is visible, and Mezze's menu is a branch's
own categories, which is the honest map of what is for sale.

### 3. Component-by-component meal customisation

**Pattern observed** — a meal is shown as its parts — burger, side, drink — each with
its current choice and a way to change *that part* without rebuilding the meal.

**Why it works** — it matches how a customer thinks about a meal, keeps the whole
order in view, and makes correcting one thing cheap. Teardowns single out the opposite
— "hidden customisation options" and "multi-step processes for simple changes" — as
McDonald's weakest area.

**Mezze adopts** — the meal builder shows one component row per choice group. An
unanswered group shows its options; once answered it becomes a summary line — the
component, the chosen item, its price — with **Change**. A group that can still take
more (Choose up to 2) stays open, because that is where "add another" lives.

**Mezze rejects** — a wizard that hides the other components while one is being
chosen, and any customisation that costs more than one tap to reach.

### 4. Calm, self-paced ordering

**Pattern observed** — no cashier watching, no queue pressure; customers browse longer
and order more confidently.

**Why it works** — the absence of social pressure is most of the value of a kiosk.

**Mezze adopts** — nothing is marked wrong before the customer acts; no countdown, no
scarcity language, no animation that hurries anyone. The inactivity reset exists for
privacy between customers, warns first, and is cancellable.

**Mezze rejects** — pressured selling of any kind. The dark-pattern audit of this exact
flow names scarcity framing, confirmshaming and emotional manipulation; none of it
appears here.

### 5. The basket, and where McDonald's loses it

**Pattern observed** — the add-on screen deliberately does **not** show the running
order or its total, on the reasoning that customers buy more when they cannot recall
what they have already added.

**Why it fails the customer** — it converts a helpful suggestion into a trap, and it is
the single most-criticised behaviour of this kiosk.

**Mezze adopts** — the *persistence* of the basket: an order bar pinned to the bottom
on every menu screen, always showing item count and total.

**Mezze rejects, explicitly** — hiding the total at the moment of an upsell. Mezze's
recommendation appears **with** the order bar visible and the real price on the offer
itself.

### 6. Upselling, and how often

**Pattern observed** — suggestions after nearly every item, "multiple interruptions per
transaction", experienced as aggressive rather than helpful. The teardown's
recommendation is one batched recommendation moment instead.

**Mezze adopts** — at most **one** recommendation per order, priced, relevant, and
declinable with an equally weighted control.

**Mezze rejects** — repeated prompts, a de-emphasised "No thanks", any offer whose
price is not on the offer, and any suggestion the data does not support.

---

## KFC

### 7. Categories are how customers think about food

**Pattern observed** — a clear, short set of food categories with images, so a large
menu never feels like a wall.

**Why it works** — the category is the customer's first decision, and it is a decision
about food, not about software.

**Mezze adopts** — the branch's own `pos.category` records are the rail. Mezze does not
invent a taxonomy: whatever the restaurant configured is what the customer sees, in
that order, with "All" first.

**Mezze rejects** — too many top-level categories, which the McDonald's teardown blames
for items being "buried in unexpected places". That is a branch-configuration warning
in Mezze's product documentation, not a UI invention.

### 8. Scrollability has to be visible

**Pattern observed** — the most-reported single failure in the McDonald's case study is
a carousel with "no indication that it is scrollable"; customers never saw the rest of
the menu.

**Why it matters** — an invisible affordance is not an affordance.

**Mezze adopts** — the category rail always shows a partially-cut chip at its edge and
a fade mask, so there is visible evidence of more.

### 9. The screen is a physical object

**Pattern observed** — KFC's kiosk is praised for putting the screen at a height that
works for a range of statures; McDonald's is reported to place some controls out of
reach for wheelchair users.

**Why it matters** — on a 1080×1920 portrait kiosk the top of the screen can be
1.7 m from the floor. A control there is not "at the top of the page"; it is above the
shoulder of a seated customer.

**Mezze adopts** — three explicit zones. Frequent actions (**Add to order**, **View
order**, category switching) live in the lower half. Infrequent ones (language,
service mode, branch identity) sit in the top band. A separate reach audit measures
this and is committed with the evidence.

**Mezze rejects** — treating 1080×1920 as a tall mobile page, which puts navigation at
the least reachable end of a physical machine.

### 10. A journey a stranger can complete unaided

**Pattern observed** — Start → dine-in or takeaway → browse → customise → review → pay
→ collect, with a large, obvious entry point and one decision per moment.

**Why it works** — nobody reads instructions at a kiosk.

**Mezze adopts** — the same spine, already present, now with the state legible at every
step: the service mode is visible in the header for the whole order rather than only on
the start screen, and the order bar shows where the customer is up to.

### 11. Conversational instructions, never system words

**Pattern observed** — "Choose your burger", "Pick a side", not field names.

**Mezze adopts** — this is already the contract and is enforced by a test that greps
the rendered panel for `qty_max`, `qty_free`, `combo_item_id` and
`attribute_value_id`. The customer reads "Choose up to 2 · 1 included" and
"Add another +25".

---

## Adopted / rejected, at a glance

| Pattern | Source | Mezze |
|---|---|---|
| Menu as the primary canvas | McD | **adopt** |
| Image-first product cards | McD / KFC | **adopt** |
| Persistent category rail from the branch's own categories | KFC | **adopt** |
| Visible scroll affordance on the rail | McD failure | **adopt (fix)** |
| Component-by-component meal builder with per-part Change | McD | **adopt** |
| Persistent basket with count and total | McD | **adopt** |
| Ergonomic zoning for a physical portrait screen | KFC | **adopt** |
| Conversational instructions | KFC | **adopt** |
| One priced, relevant, easily declined recommendation | teardown recommendation | **adopt** |
| Intent-router screen before the menu | McD | reject — a step before any food |
| Suggestion after nearly every item | McD | reject |
| Upsell screen with the running total hidden | McD | **reject — the opposite is a rule here** |
| Omitted comparison (e.g. no small size shown) | McD | reject |
| Confirmshaming / scarcity / pressured selling | McD audit | reject |
| Promotional content competing with navigation | McD | reject |
| Multi-step for a simple change | McD | reject |
| Brand colours, logos, card designs, artwork | both | **never** |

---

## Sources

* [The Psychology Behind McDonald's $2 Billion Self-Serve Kiosks — Growth.Design](https://growth.design/case-studies/mcdonalds-self-serve-ux)
* [McDonald's kiosk ordering system — a UX case study, Chee Seng Leong, UX Collective](https://uxdesign.cc/mcdonalds-kiosk-ordering-system-ui-ux-case-study-fe7b3693f12c)
* [McDonald's vs. Taco Bell Kiosks: A UX Teardown for QSR Operators — Seen Labs](https://seenlabs.com/blog/mcdonalds-vs-taco-bell-kiosks-a-ux-teardown-for-qsr-operators)
* [Redefining Dining: My Experience Using KFC's Self-Service Kiosk — Enakshi Mukhopadhyaya](https://medium.com/@enakshi.mkrj/redefining-dining-my-experience-using-kfcs-self-service-kiosk-884bc455e433)
* [KFC Bulgaria — digitization and self-service in restaurants — Ordering Stack](https://orderingstack.com/case-study/kfc-bulgaria/)
