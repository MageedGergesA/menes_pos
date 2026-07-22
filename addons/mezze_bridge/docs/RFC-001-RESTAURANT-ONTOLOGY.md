# RFC-001 — The Restaurant Ontology

**Status:** Ratified · Canonical · The permanent language of Mezze
**Descends from:** RFC-000 (Engineering Constitution)
**Scope:** The vocabulary, entities, values, events, invariants, and relationships of the restaurant universe — as *reality*, not software.
**Audience:** Every engineer, designer, product manager, analyst, AI model, integration partner, and support engineer. If two people at Mezze use different words for the same thing, this RFC is wrong and must be corrected.
**Lifespan:** This ontology must remain correct even if Mezze's software is rewritten ten times before 2050, because it describes restaurants, and restaurants do not change when our code does.

---

## How to read this document

RFC-000 established *how* we build. This RFC establishes *what we are talking about.* A domain is not understood through its software; it is understood through its language, and a company that shares one precise language for its domain can build, sell, support, and reason about that domain coherently across every team and every decade, while a company whose teams each invent their own words builds a tower of Babel that no amount of good engineering can rescue. This document is the shared language.

Every definition here obeys three rules, without exception. **It is software-independent** — it describes a thing that would be true in a restaurant with no computers at all, because the restaurant existed before us and will define the terms, not our systems. **It is unambiguous** — one term, one meaning, so that "cover" always means the same thing to a cashier, a forecaster, and an AI. **It is grounded in reality** — a Table is a physical surface guests sit at, an Order is a real commitment a guest made, a Payment is real money that really moved; we model the world as it is, and our software is judged by how faithfully it reflects this ontology, never the reverse.

This is also the map of the Operating Graph — the invariant of the Company Constitution. The graph is the accumulated truth of these entities, related by these edges, changing through these events, constrained by these invariants, across a hundred thousand restaurants over years. To define the ontology is to define the shape of the asset. Every entity is a kind of node, every relationship a kind of edge, every event a change to the graph, and every invariant a law the graph obeys. When you read Part 10, you will see that it is simply Parts 2 through 6 assembled into the single connected structure that is the thing we are building.

A note on words we deliberately distinguish, because their confusion is the most common source of error in this industry: a **Guest** is not a **Customer**; an **Order** is not a **Ticket**; a **Receipt** is not an **Invoice**; a **Recipe** is not a **Menu Item**; a **Location** is not a **Brand**; **Stock** is not **Inventory** as a count versus a discipline; **Price** is not **Cost**; a **Payment** is not a **Tender**; **business time** is not **wall-clock time**. Each distinction is drawn precisely below, and each matters, because a system that conflates them computes the wrong truth with confidence, and confident wrong truth is a lie in the graph.

---

# PART 1 — The Ubiquitous Language

The complete vocabulary. Each definition is one sentence, unambiguous, and independent of any software. This is the dictionary every person and every model at Mezze speaks. Terms are grouped by the part of the restaurant they belong to, but the definitions stand alone.

## The organization: brand, place, and space

**Restaurant** — A business that prepares and serves food and drink to guests for money, considered as a single operating whole.

**Brand** — The identity under which one or more restaurants trade, carrying a name, a concept, a menu style, and a reputation that is the same wherever it appears.

**Location** — A single physical place where a brand operates and serves guests, with its own address, its own staff, its own hours, and its own daily operation.

**Operator** — The legal and commercial owner responsible for one or more locations, who bears their profit, their loss, and their obligations.

**Franchise** — A location operated by an independent operator under a brand owned by another, under an agreement that governs standards, fees, and rights.

**Multi-unit** — Describing an operator or brand that runs more than one location, whose reality is the aggregate of those locations plus the relationships between them.

**Dining Room** — A defined area within a location where guests are seated and served, distinct from other such areas by its layout, its service style, or its purpose.

**Floor** — The arrangement of a location's dining space into areas, tables, and paths, as it physically exists.

**Section** — A group of tables within a dining room assigned to one server or one service unit for the purpose of dividing the work.

**Table** — A physical surface at which one party of guests is seated together and served as a unit.

**Seat** — A single place at a table where one guest sits, to which items may be attributed for the purpose of splitting and service.

**Cover** — One guest served during one visit, counted as the fundamental unit of a location's throughput.

**Turn** — One complete cycle of a table being occupied by a party from seating to departure, after which it becomes available again.

## The people served

**Guest** — A person present at the restaurant being served during a visit, whether or not their identity is known.

**Customer** — A known person with a persistent relationship to the brand across visits, identified and remembered over time.

**Party** — A group of guests who arrive together, are seated together, and are served as one unit sharing one order.

**Host** — The role responsible for greeting guests, managing the waitlist, and seating parties.

**Server** — The role responsible for taking a party's order and attending to them through their visit.

## The commitment to buy

**Order** — The complete record of what a guest or party has committed to buy during one visit or one transaction, as it stands at any moment.

**Line** — One item on an order, being a single product at a chosen quantity with its chosen modifiers and its resulting price.

**Item** — A single unit of something the restaurant sells, as it appears on an order line.

**Menu** — The set of items a location offers for sale, organized for the guest to choose from, valid during defined times.

**Menu Item** — A single product offered for sale on a menu, with a name, a price, and a definition of what it is.

**Category** — A grouping of menu items by kind (starters, mains, drinks) for the purpose of organizing the menu and the reporting.

**Modifier** — A choice or addition that alters a menu item on an order, such as a size, a preparation, an added ingredient, or an omission, possibly changing its price.

**Modifier Group** — A set of related modifiers offered together for an item, governed by rules of how many may or must be chosen.

**Combo** — A bundle of items sold together as one offering at one price, distinct from the sum of its parts.

**Course** — A stage of a meal, being the group of items intended to be prepared and served together at one point in the meal's sequence.

**Coursing** — The act of grouping an order's items into courses and controlling when each course is prepared and served.

**Fire** — The act of releasing a course or an order to the kitchen to begin preparation.

**Hold** — The act of deferring a course's preparation until it is later fired.

**Void** — The removal of an item or an order before it is paid, recorded as a deliberate act with a reason.

**Comp** — An item given to a guest at no charge as a deliberate decision, recorded with a reason and an authorizer.

**Eighty-six (86)** — The state of an item being unavailable for sale because the kitchen has run out of it or removed it, and the act of declaring so.

## The service styles

**Dine-in** — Service where guests are seated at the location and served their order at the table.

**Takeaway** — Service where a guest orders and collects food to consume elsewhere, without being seated.

**Delivery** — Service where an order is transported to a guest at a remote address rather than collected or served on site.

**Drive-through** — Service where a guest orders and collects from a vehicle without entering the location.

**Walk-in** — A guest or party who arrives without a reservation and is served if capacity allows.

**Reservation** — A guest's booking of a table for a stated party size at a stated future time, holding capacity for them.

**Waitlist** — The ordered list of walk-in parties waiting for a table to become available.

**Quote Time** — The estimated wait a host gives a waitlisted party before a table will be ready.

## The kitchen

**Kitchen** — The part of a location where food is prepared, considered as the operation that turns orders into served items.

**Station** — A defined work area in the kitchen responsible for preparing a particular class of items, such as grill, cold, pastry, or bar.

**Ticket** — The instruction to the kitchen to prepare the items of an order or a course, as it appears at the kitchen and drives preparation.

**Bump** — The act of a station marking a ticket or an item as prepared and done.

**Expo** — The role or point that coordinates a ticket's items across stations and releases the completed order for service.

**Prep** — Food preparation done in advance of service, producing components used to assemble items during service.

**Recipe** — The definition of how a menu item or a prep component is made, in terms of its ingredients, their quantities, and its method.

**Yield** — The amount of usable output a recipe or a prep produces from its inputs.

**Ingredient** — A raw or prepared material consumed in making an item, tracked for its cost and its stock.

**Bill of Materials** — The full set of ingredients and their quantities that a menu item consumes when it is sold, used to deduct stock and compute cost.

## Money on the way in

**Price** — The amount of money a location asks a guest to pay for an item, before discounts and taxes.

**Subtotal** — The sum of an order's line prices before discounts, service, and tax.

**Discount** — A reduction of an order's or an item's price, applied for a stated reason under stated rules.

**Promotion** — A defined offer that grants a discount or a benefit to qualifying orders during a defined period.

**Service Charge** — A charge added to a bill for the service provided, as a percentage or amount, distinct from a voluntary tip.

**Tax** — A charge levied by an authority on a sale, computed at a rate on a base, and owed by the operator to the authority.

**Tax Rate** — The proportion at which a tax is applied to its base, as set by an authority for a class of goods.

**Total** — The final amount a guest owes for an order, being subtotal less discounts plus service and tax.

**Tip** — Money a guest gives voluntarily to staff for service, beyond the total owed to the restaurant.

**Gratuity** — A tip added to a bill, whether voluntary or mandatory for large parties, as defined by policy.

**Bill / Check** — The presentation of what a guest owes for their order, as given to them to settle.

**Split** — The division of one order's total across multiple guests, seats, or payments so each pays a part.

## Money moving

**Payment** — An act of settling part or all of an order's total by a means of value, being real money that really moved.

**Tender** — The means by which a payment is made — cash, card, wallet, gift, or other — being the *kind* of a payment.

**Authorization** — A card or wallet issuer's confirmation that funds are available and held for a charge, before capture.

**Capture** — The act of finalizing an authorized charge so the funds are taken.

**Settlement** — The process by which captured charges are transferred from the processor to the operator, in batches, and reconciled.

**Reconciliation** — The act of confirming that what was charged, captured, and settled agrees, and resolving any difference.

**Refund** — The return of money to a guest for a paid order or item, recorded as the reversal of a payment.

**Reversal** — The undoing of a charge that should not stand, whether because a sale did not complete or a payment was made in error.

**Chargeback** — A guest's disputed reversal of a card charge initiated through their issuer rather than the restaurant.

**Change** — The cash returned to a guest who tendered more than the amount owed.

**Drawer** — The cash held at a point of sale, opened, counted, and reconciled across a shift.

## The record of the sale

**Receipt** — The document given to a guest as proof of what they bought and paid, at the moment of the sale.

**Invoice** — The formal, often tax-compliant, demand or record of a sale addressed to a buyer, issued for accounting and regulatory purposes.

**E-invoice** — An invoice issued in a form mandated by a tax authority and reported to it, as required by law.

**Sale** — A completed transaction in which items were sold, paid for, and recorded, being the atomic economic event of the restaurant.

## The people who work

**Employee** — A person who works at a location or for an operator, whose work, pay, and permissions are tracked.

**Role** — The set of responsibilities and permissions an employee holds, such as cashier, server, manager, or owner.

**Manager** — An employee with the authority to approve exceptions, override decisions, and oversee a shift or a location.

**Cashier** — An employee who operates a point of sale, takes orders and payments, and is accountable for a drawer.

**Shift** — A continuous period an employee is scheduled to work or a location is open, bounded by an open and a close.

**Schedule** — The plan of which employees work which shifts over a period.

**Clock-in / Clock-out** — The recorded act of an employee beginning or ending their worked time.

**Labor** — The employees' worked time and its cost, as a factor a location manages against its revenue.

## The supply of goods

**Supplier** — A business from which a location buys ingredients, goods, or services.

**Vendor** — A supplier, considered as a party the operator transacts and settles with.

**Purchase Order** — A location's committed request to a supplier to deliver stated goods at stated quantities and prices.

**Delivery (of goods)** — The arrival of goods from a supplier against a purchase order, received into stock.

**Goods Receipt** — The recorded acceptance of delivered goods into a location's stock, confirming quantity and quality.

**Stock** — The quantity of an ingredient or a good a location holds on hand at a moment.

**Inventory** — The discipline and the record of tracking stock, its movements, its counts, and its value.

**Par Level** — The target quantity of a stock item a location aims to keep on hand, below which it reorders.

**Count** — A physical tally of stock on hand, recorded to establish or correct the tracked quantity.

**Waste** — Stock lost to spoilage, error, or damage rather than sold, recorded with a reason.

**Transfer** — The movement of stock from one location or store to another, deducted from one and received by the other.

**Central Kitchen** — A production location that prepares goods for delivery to and use by other locations rather than serving guests directly.

**Cost of Goods** — The cost of the ingredients consumed to produce what was sold, as a proportion of revenue.

## Delivery and its logistics

**Delivery Order** — An order to be transported to a guest at a remote address.

**Driver** — The person who transports a delivery order from the location to the guest.

**Dispatch** — The act of assigning a delivery order to a driver and sending it for delivery.

**Aggregator** — A third-party platform through which guests place delivery orders that arrive at the location for fulfillment.

**Zone** — A defined delivery area a location serves, with its own fee, its own time, and its own boundary.

## The relationship over time

**Loyalty** — The program and the record by which a brand rewards customers for their repeated patronage.

**Loyalty Account** — A customer's standing in a loyalty program, holding their points, their tier, and their history.

**Points** — Units a customer earns for patronage and spends for rewards under a loyalty program's rules.

**Reward** — A benefit a customer may claim by meeting a loyalty program's conditions.

**Tier** — A level of a loyalty program that a customer reaches by their patronage, granting them defined benefits.

**Gift Card** — A prepaid instrument of stored value that a bearer may spend at a brand toward purchases.

**Campaign** — A planned marketing effort to reach customers with an offer or a message over a period.

**Segment** — A group of customers defined by shared characteristics for the purpose of understanding or reaching them.

## Understanding and truth

**Forecast** — A prediction of a future quantity — demand, sales, labor need, stock depletion — stated with the moment and method that produced it.

**Benchmark** — A measure of how one location or item compares to a population of peers on some dimension.

**Menu Engineering** — The analysis of a menu's items by their popularity and their margin to guide what to promote, keep, or remove.

**Restaurant Intelligence** — The understanding of a restaurant's reality derived from its data and the data of its peers.

**Audit (record)** — The immutable, attributed record of what happened, especially of money-affecting and privileged actions.

**Event** — An immutable statement that something meaningful happened at a time, caused by an actor, in a part of the restaurant.

**Operating Graph** — The complete, connected, ground-truth record of how a population of restaurants operates, being the sum of their entities, relationships, and events over time.

---

# PART 2 — The Entity Catalog

An **entity** is a thing in the restaurant world with a distinct identity that persists through change — the same Table today as yesterday even though a different party sits at it, the same Order even as lines are added to it, the same Customer across a hundred visits. For each entity we define: what it *is*, how its *identity* is established, its *lifecycle* through the states it passes, who *owns* it (which bounded context is the single source of its truth, per RFC-000), its *relationships* to other entities, the *invariants* that must always hold of it, its *deletion policy* (how, or whether, it may cease to exist), and an *example* to make it concrete.

## 2.1 Brand

**Definition.** The identity under which restaurants trade, carrying a name, concept, menu style, and reputation consistent wherever it appears.
**Identity.** A brand has a stable identity independent of any single location; it is the same brand whether it has one location or a thousand.
**Lifecycle.** Created when a concept is established → active while it trades → may be retired when it ceases to trade; a brand rarely dies while any location bears it.
**Ownership.** Identity context (as an organizational fact), referenced by every context that scopes truth to a brand.
**Relationships.** A brand *has* one or more Locations; *defines* one or more Menus; *owns* Loyalty programs, Campaigns, and Customer relationships that span its locations.
**Invariants.** A brand must have a name; a location belongs to exactly one brand; brand-scoped truth (loyalty, customer history) is shared across the brand's locations and not confused with another brand's.
**Deletion policy.** A brand is never deleted while any location, order history, or customer relationship references it; it is retired (marked inactive), preserving its history forever, because its history is part of the graph.
**Example.** "Zamalek Roastery" is a brand under which three café locations trade, sharing one menu concept and one loyalty program.

## 2.2 Location

**Definition.** A single physical place where a brand operates and serves guests, with its own address, staff, hours, and daily operation.
**Identity.** A location has a stable identity tied to its physical existence and its operation; it remains the same location across days, staff changes, and menu changes.
**Lifecycle.** Opened (begins operating) → operating (serves guests day to day, opening and closing each service) → may be temporarily closed → permanently closed (ceases operation); its history persists after closure.
**Ownership.** Identity context for its existence and configuration; every operational context (Operations, Kitchen, Inventory, Payments) scopes its truth to a location.
**Relationships.** A location *belongs to* one Brand and one Operator; *contains* Dining Rooms, Tables, Stations; *employs* Employees; *holds* Stock; *serves* Guests; *produces* Orders, Sales, Tickets; *buys from* Suppliers.
**Invariants.** A location belongs to exactly one brand at a time; all operational truth (orders, stock, shifts) is scoped to exactly one location; a location has an address and defined operating hours.
**Deletion policy.** Never deleted while it has any operating history; a closed location is retained forever with all its history, because its past is ground truth.
**Example.** The Zamalek Roastery branch at "Cairo · Terminal 02" is a location: one address, one staff, one kitchen, one drawer, opening at 7 a.m.

## 2.3 Dining Room

**Definition.** A defined area within a location where guests are seated and served, distinct by layout, service style, or purpose.
**Identity.** Identified within its location by its role and layout; the same dining room persists as its tables are rearranged.
**Lifecycle.** Defined → in use → may be reconfigured or retired as the location's layout changes.
**Ownership.** Operations context (as part of the floor).
**Relationships.** A dining room *belongs to* one Location; *contains* Tables and Seats; *is divided into* Sections for service.
**Invariants.** A dining room belongs to exactly one location; a table belongs to exactly one dining room at a time.
**Deletion policy.** Retired, not deleted, while historical orders reference tables that were in it; the layout's history is retained.
**Example.** A location's "Terrace" and "Main Hall" are two dining rooms with different table counts and service styles.

## 2.4 Table

**Definition.** A physical surface at which one party of guests is seated together and served as a unit.
**Identity.** Identified within its dining room by a stable label (a number or name) that staff and guests recognize across turns.
**Lifecycle.** Available (empty, ready) → occupied (a party is seated) → in service (the party's order is open) → to be cleared (party has left) → available again; this cycle is a *turn*.
**Ownership.** Operations context.
**Relationships.** A table *belongs to* one Dining Room; *has* Seats; *is assigned to* a Section and a Server; *hosts* at most one active Party and its Order at a time; *is booked by* Reservations.
**Invariants.** A table hosts at most one active party at a time; a table's occupancy state reflects reality (it is occupied if and only if a party is seated); a table belongs to exactly one dining room.
**Deletion policy.** A table label may be retired when the floor changes, but its identity is retained wherever historical orders reference it; no order's history is orphaned by a table change.
**Example.** "Table 12" seats four, is currently occupied by a party of four in the Main Hall, assigned to server Mariam.

## 2.5 Seat

**Definition.** A single place at a table where one guest sits, to which items may be attributed for splitting and service.
**Identity.** Identified within its table by position (Seat 1, Seat 2) for the duration of a turn.
**Lifecycle.** Exists as a position while a party occupies the table; items are attributed to it; it is released when the turn ends.
**Ownership.** Operations context (within the order).
**Relationships.** A seat *belongs to* one Table; *is occupied by* one Guest during a turn; *is attributed* zero or more order Lines for the purpose of a seat-based split.
**Invariants.** A seat belongs to exactly one table; an item attributed to a seat is part of exactly one order; seat attributions are consistent with the order's total (the parts sum to the whole).
**Deletion policy.** A seat is ephemeral to a turn; its attributions are retained as part of the order's immutable history.
**Example.** On Table 12, Seat 2's guest ordered the Shakshuka; when the bill splits by seat, Seat 2 pays for it.

## 2.6 Guest

**Definition.** A person present at the restaurant being served during a visit, whether or not their identity is known.
**Identity.** A guest may be *anonymous* (identified only by their presence and seat during a visit) or *linked to a Customer* if their identity becomes known.
**Lifecycle.** Arrives → is seated or served → orders → pays → departs; the guest's role exists for the duration of a visit.
**Ownership.** Operations context for the visit; Guests context if linked to a known Customer.
**Relationships.** A guest *occupies* a Seat (if dine-in); *belongs to* a Party; *places* an Order or part of one; *may be* a Customer.
**Invariants.** A guest is served within exactly one location per visit; a guest's order attributions are part of exactly one order.
**Deletion policy.** An anonymous guest leaves no persistent entity beyond the visit's order history; a guest linked to a customer is subject to the Customer deletion policy (2.7).
**Example.** The person in Seat 2 at Table 12 is a guest; if they present their loyalty account, they become a known customer for this visit.

## 2.7 Customer

**Definition.** A known person with a persistent relationship to the brand across visits, identified and remembered over time.
**Identity.** A stable identity tied to a person (by phone, account, or loyalty membership), persisting across visits and locations of the brand.
**Lifecycle.** Created when first identified → active across visits, accumulating history and loyalty → may be dormant → may exercise the right to be forgotten (erased under law).
**Ownership.** Guests context (the single owner of customer truth, and the context most bound by privacy law).
**Relationships.** A customer *is* a Guest on visits; *has* a Loyalty Account; *belongs to* Segments; *is targeted by* Campaigns; *accumulates* Order history across the brand.
**Invariants.** A customer belongs to exactly one brand's relationship (customer identity is brand-scoped, not shared across unrelated brands); consent governs what may be held and used; a customer's personal data is handled per privacy law.
**Deletion policy.** A customer may exercise erasure; upon a lawful erasure request, personal data is deleted by an explicit, audited act, while the *anonymized* economic facts (a sale occurred) are retained as ground truth with the personal link removed.
**Example.** "Ahmed," identified by his phone and loyalty account, has visited eleven times across two branches, holds Gold tier, and consented to marketing.

## 2.8 Party

**Definition.** A group of guests who arrive together, are seated together, and are served as one unit sharing one order.
**Identity.** Identified by its occupancy of a table during a turn and its shared order.
**Lifecycle.** Forms on arrival → is seated → shares an order through the visit → settles → disperses on departure.
**Ownership.** Operations context.
**Relationships.** A party *comprises* Guests; *occupies* a Table; *shares* one Order; *may hold* a Reservation.
**Invariants.** A party occupies exactly one table at a time (unless explicitly merged); a party shares exactly one order per visit; the party size is consistent with the seats and covers counted.
**Deletion policy.** Ephemeral to the visit; its order and cover count are retained as history.
**Example.** A party of four holds a reservation, is seated at Table 12, shares one order, and splits the bill four ways at the end.

## 2.9 Reservation

**Definition.** A guest's booking of a table for a stated party size at a stated future time, holding capacity for them.
**Identity.** A stable identity from creation, referencing the booking guest, the location, the time, and the party size.
**Lifecycle.** Requested → confirmed → (guest arrives) seated / (guest late) held or released / (guest absent) no-show / (guest cancels) cancelled → completed after the visit.
**Ownership.** Reservations context.
**Relationships.** A reservation *belongs to* one Location; *is for* a Party of a stated size; *reserves* a Table (or a table-class) at a Time Range; *may require* a deposit (a Payment).
**Invariants.** A reservation belongs to exactly one location; it holds capacity for exactly one party at one time; a confirmed reservation for a time must not exceed the location's capacity for that time together with other bookings.
**Deletion policy.** A cancelled or no-show reservation is retained with its outcome (the fact of the no-show is valuable ground truth for prediction); never silently deleted.
**Example.** A reservation for four at 8 p.m. Friday at the Zamalek branch, confirmed, with a card held as a no-show deposit.

## 2.10 Order

**Definition.** The complete record of what a guest or party has committed to buy during one visit or transaction, as it stands at any moment.
**Identity.** A stable, globally-unique identity from the moment it is opened, persisting through every change until it is finalized, and forever after in history.
**Lifecycle.** Opened → items added/removed/modified (draft) → sent to kitchen (committed to preparation) → served → billed → paid (settled) → closed; alternatively voided before payment. A paid order is final.
**Ownership.** Operations context (the heartbeat of the graph).
**Relationships.** An order *belongs to* one Location; *is placed by* a Party or Guest; *occupies* a Table (if dine-in) or has a fulfillment (takeaway/delivery); *comprises* Lines; *generates* Tickets; *is settled by* Payments; *may carry* Discounts, Service, Tax, Tips; *results in* a Sale, a Receipt, and an Invoice; *deducts* Stock through its items' recipes.
**Invariants.** An order belongs to exactly one location; its total equals subtotal less discounts plus service plus tax; every payment against it belongs to it and only it; the sum of its payments settles exactly its total (no more, no less, allowing for tips as separate); a paid order cannot become unpaid; an order's items, once sent to the kitchen, are recorded even if later voided.
**Deletion policy.** Never deleted; a voided order is retained with the void and its reason; a paid order and its history are permanent ground truth.
**Example.** Order #A-9812 at Table 12: three lines, subtotal EGP 340, 12% service, 14% VAT, split three ways, paid in full, closed — permanent.

## 2.11 Line (Order Line)

**Definition.** One item on an order, being a single product at a chosen quantity with its chosen modifiers and its resulting price.
**Identity.** Identified within its order; a distinct line even if it is the same product as another (two separate lines of the same item are two lines).
**Lifecycle.** Added → modified (quantity, modifiers) while the order is a draft → sent to kitchen → served → paid; may be voided or comped before payment.
**Ownership.** Operations context (within the Order aggregate).
**Relationships.** A line *belongs to* exactly one Order; *references* one Menu Item; *carries* chosen Modifiers; *may be attributed to* a Seat; *consumes* Stock via the item's Bill of Materials; *generates* a Ticket instruction.
**Invariants.** A line belongs to exactly one order; a line's price derives from its item's price, its modifiers, its quantity, and applicable discounts; a line's modifiers are all valid for its item; a voided line is retained with its void reason.
**Deletion policy.** Never deleted; voided lines are retained as history.
**Example.** A line on Order #A-9812: "2 × Flat White, oat milk, extra shot — EGP 156."

## 2.12 Menu Item

**Definition.** A single product offered for sale on a menu, with a name, a price, and a definition of what it is.
**Identity.** A stable identity within a brand or location's catalog, persisting across price changes and menu revisions.
**Lifecycle.** Created → available for sale → may be 86'd (temporarily unavailable) → may be delisted (removed from the menu) → retired; its sales history persists.
**Ownership.** Operations context (catalog) for its sale definition; Inventory context for its cost via recipe.
**Relationships.** A menu item *belongs to* a Menu and a Category; *has* Modifier Groups; *is defined by* a Recipe / Bill of Materials; *appears on* Order Lines; *has* a Price that may vary by menu, time, or location.
**Invariants.** A menu item has a name and at least one price context; its modifiers belong to it; its recipe defines its stock consumption and cost; the same item's identity is stable across price changes (a price change is a new fact, not a new item).
**Deletion policy.** Delisted, not deleted, while any order line references it; its history is retained forever.
**Example.** "Flat White" is a menu item in the Coffee category, priced EGP 78, with a size and milk modifier group, defined by a recipe consuming espresso and milk.

## 2.13 Modifier

**Definition.** A choice or addition that alters a menu item on an order — a size, a preparation, an added ingredient, or an omission — possibly changing its price and its stock consumption.
**Identity.** Identified within its modifier group and item.
**Lifecycle.** Defined → offered → chosen on an order line → may be revised in the catalog.
**Ownership.** Operations context (catalog).
**Relationships.** A modifier *belongs to* exactly one Modifier Group, which belongs to one Menu Item; *when chosen, alters* an Order Line's price and its Bill of Materials.
**Invariants.** Every modifier belongs to exactly one menu item (through its group); a modifier's price effect and stock effect are defined; a chosen modifier is valid for its line's item.
**Deletion policy.** Retired, not deleted, while order lines reference its having been chosen.
**Example.** "Oat milk" is a modifier in the "Milk" group of "Flat White," adding EGP 10 and substituting oat for dairy in the recipe.

## 2.14 Combo

**Definition.** A bundle of items sold together as one offering at one price, distinct from the sum of its parts.
**Identity.** A stable identity as an offering.
**Lifecycle.** Defined → offered → chosen on an order (expanding to its component items for the kitchen) → retired.
**Ownership.** Operations context (catalog).
**Relationships.** A combo *comprises* Menu Items; *appears as* an Order Line that expands to component tickets; *has* its own price distinct from its components' sum.
**Invariants.** A combo's components are all valid menu items; a combo's price is defined independently; a combo on an order deducts the stock of all its components.
**Deletion policy.** Retired, not deleted, while order history references it.
**Example.** "Breakfast Combo" bundles a Flat White and a Croissant for EGP 130, less than their EGP 138 sum.

## 2.15 Course

**Definition.** A stage of a meal — the group of items intended to be prepared and served together at one point in the meal's sequence.
**Identity.** Identified within an order by its sequence position (first course, second course).
**Lifecycle.** Defined on the order → fired to the kitchen → prepared → served; may be held before firing.
**Ownership.** Operations context (within the Order), reflected into Kitchen context on firing.
**Relationships.** A course *groups* Order Lines; *is fired to* the Kitchen as Tickets; *is served* as a stage of the meal.
**Invariants.** A course's lines belong to its order; a course is fired before it is prepared; coursing controls preparation timing without changing what was ordered.
**Deletion policy.** Retained as part of the order's history.
**Example.** On Order #A-9812, the appetizers are Course 1 (fired immediately) and the mains are Course 2 (held until Course 1 is served).

## 2.16 Ticket

**Definition.** The instruction to the kitchen to prepare the items of an order or a course, as it appears at the kitchen and drives preparation.
**Identity.** A stable identity from the moment an order or course is fired, linked to its order.
**Lifecycle.** Created on fire → routed to stations → accepted → in preparation → bumped (done) at each station → completed → expedited for service.
**Ownership.** Kitchen context.
**Relationships.** A ticket *derives from* an Order or Course; *is routed to* one or more Stations; *comprises* items to prepare; *is bumped by* stations; *is coordinated by* Expo.
**Invariants.** A ticket derives from exactly one order or course; a ticket is never silently lost (RFC-000: "a ticket is never silently lost"); a ticket's completion reflects all its items being prepared; a ticket's timing is measured from fire to bump.
**Deletion policy.** Never deleted; a ticket's lifecycle including its timing is retained as ground truth (it feeds kitchen capacity intelligence).
**Example.** Ticket for Order #A-9812 Course 1 routes the salad to the cold station and the eggs to the grill; both bump; expo releases it.

## 2.17 Recipe

**Definition.** The definition of how a menu item or a prep component is made, in terms of its ingredients, their quantities, and its method.
**Identity.** A stable, versioned identity; a recipe change is a new version, not a new recipe.
**Lifecycle.** Created → versioned as it is refined → used in production and costing → retired.
**Ownership.** Inventory context (for its stock and cost meaning); Kitchen context references it for preparation.
**Relationships.** A recipe *defines* a Menu Item or a Prep component; *consumes* Ingredients at stated quantities (its Bill of Materials); *produces* a Yield; *determines* the item's Cost of Goods.
**Invariants.** Every recipe has exactly one owner; a recipe's ingredients and quantities determine the stock deducted when its item is sold; a recipe version's cost is the sum of its ingredients' costs at their quantities; changing a recipe versions it, preserving the old.
**Deletion policy.** Versioned and retired, never deleted; historical costing and stock deduction referenced the version in effect at the time, which is retained.
**Example.** The "Flat White" recipe v3 consumes 18g coffee and 150ml milk, yielding one cup, costing EGP 9.

## 2.18 Ingredient

**Definition.** A raw or prepared material consumed in making an item, tracked for its cost and its stock.
**Identity.** A stable identity within a location's or operator's catalog of materials.
**Lifecycle.** Defined → purchased → received into stock → consumed by production → depleted → reordered.
**Ownership.** Inventory context.
**Relationships.** An ingredient *is consumed by* Recipes; *is held as* Stock; *is bought via* Purchase Orders from Suppliers; *is lost to* Waste; *is moved by* Transfers.
**Invariants.** An ingredient's stock is the net of receipts, consumption, waste, and transfers; an ingredient has a cost derived from its purchases; stock movements conserve quantity (what leaves one place arrives at another or is accounted as waste/consumption).
**Deletion policy.** Retired, not deleted, while any recipe, stock movement, or purchase references it.
**Example.** "Oat milk" is an ingredient, held at 24 liters on hand, consumed 0.15 L per oat-milk drink, bought from a supplier at EGP 40/liter.

## 2.19 Bill of Materials

**Definition.** The full set of ingredients and their quantities that a menu item consumes when it is sold.
**Identity.** Identified as the composition of a recipe version.
**Lifecycle.** Defined with the recipe → applied on each sale to deduct stock → versioned with the recipe.
**Ownership.** Inventory context.
**Relationships.** A bill of materials *belongs to* a Recipe version; *lists* Ingredients and quantities; *drives* the Stock deduction on a Sale and the Cost of the item.
**Invariants.** A bill of materials belongs to exactly one recipe version; the stock deducted on a sale equals the bill of materials of the sold items; the cost of an item equals the sum of its bill of materials at ingredient costs.
**Deletion policy.** Retained with its recipe version.
**Example.** The Flat White's bill of materials: 18g coffee + 150ml milk (or oat milk if the modifier is chosen).

## 2.20 Discount

**Definition.** A reduction of an order's or an item's price, applied for a stated reason under stated rules.
**Identity.** Identified by its application to an order or line, referencing its rule or its authorizer.
**Lifecycle.** Defined (as a rule or an ad-hoc authority) → applied to an order/line → carried into the total → retained in history.
**Ownership.** Operations context (application); its rules may derive from Promotions or manager authority.
**Relationships.** A discount *applies to* an Order or a Line; *derives from* a Promotion, a loyalty Reward, or a manager's authority; *reduces* the subtotal before tax.
**Invariants.** A discount runs *before* tax (tax is computed on the discounted base); a discount has a reason and, if beyond policy, an authorizer; a discount cannot make a line's price negative.
**Deletion policy.** Retained in the order's history with its reason and authority.
**Example.** A 10% loyalty discount applied to Order #A-9812's subtotal before the 14% VAT is computed.

## 2.21 Promotion

**Definition.** A defined offer that grants a discount or a benefit to qualifying orders during a defined period.
**Identity.** A stable identity as a marketing rule.
**Lifecycle.** Defined → scheduled → active during its period → applied to qualifying orders → ended → retained.
**Ownership.** Guests/Marketing context (definition); applied through Operations.
**Relationships.** A promotion *grants* Discounts or benefits; *qualifies* Orders by conditions; *is targeted at* Segments; *runs during* a Time Range.
**Invariants.** A promotion applies only to orders meeting its conditions within its period; its benefit is defined and bounded; its combinability with other promotions is defined (not left ambiguous).
**Deletion policy.** Ended and retained; the record of which orders it applied to is ground truth.
**Example.** "MEZZE10 — 10% off orders over EGP 200, weekdays, this month" is a promotion applied at checkout when conditions hold.

## 2.22 Tax

**Definition.** A charge levied by an authority on a sale, computed at a rate on a base, owed by the operator to the authority.
**Identity.** Identified by the authority, the rate, and the base it applies to.
**Lifecycle.** Defined by an authority → applied to sales → computed on each order → reported and remitted to the authority.
**Ownership.** Finance context (its computation and reporting); applied through Operations.
**Relationships.** A tax *applies to* an Order's taxable base; *is set by* an Authority at a Tax Rate; *is reported via* Invoices and E-invoices; *is owed to* the authority.
**Invariants.** Tax is computed on the correct base (after discounts, per jurisdiction rules); the tax on an order equals its base times its applicable rate(s); tax collected is owed to the authority and not the operator's revenue; the tax computation is auditable and reproducible.
**Deletion policy.** Never deleted; tax records are retained for the legally-mandated period and beyond as ground truth.
**Example.** 14% VAT computed on Order #A-9812's discounted subtotal plus service, reported to the tax authority via an e-invoice.

## 2.23 Payment

**Definition.** An act of settling part or all of an order's total by a means of value — real money that really moved.
**Identity.** A stable, globally-unique identity from initiation, persisting through its lifecycle and in history.
**Lifecycle.** Initiated → (for cards) authorized → captured → settled → reconciled; or (for cash) tendered → change given; may be refunded or reversed.
**Ownership.** Payments context.
**Relationships.** A payment *settles* exactly one Order (in whole or part); *is made by* a Tender; *for cards, involves* Authorization, Capture, Settlement; *may be undone by* a Refund or Reversal; *is recorded in* the Audit.
**Invariants.** Every payment belongs to exactly one order; a payment is applied exactly once (idempotent — a retried charge does not double-charge); the sum of an order's payments settles its total; a captured payment corresponds to real moved money that must reconcile; a payment, once made, is not silently altered — it is refunded or reversed by a new recorded act.
**Deletion policy.** Never deleted; refunds and reversals are new records, not deletions; payment history is permanent, audited ground truth.
**Example.** A card payment of EGP 130 against Order #A-9812, authorized and captured through the processor, settled in the day's batch, reconciled.

## 2.24 Refund

**Definition.** The return of money to a guest for a paid order or item, recorded as the reversal of a payment.
**Identity.** A stable identity referencing the original payment and order.
**Lifecycle.** Requested → authorized (by policy or manager) → processed → settled → reconciled.
**Ownership.** Payments context.
**Relationships.** A refund *reverses* a Payment (in whole or part); *belongs to* the original Order; *requires* an authority and a reason; *is recorded in* the Audit.
**Invariants.** A refund cannot exceed the original payment; a refund belongs to exactly one payment and order; a refund is a new record that does not erase the original payment (a paid order that is refunded shows both the payment and the refund, not the absence of the payment); a refund has a reason and an authorizer.
**Deletion policy.** Never deleted; retained as the permanent record of money returned.
**Example.** A EGP 78 partial refund on Order #A-9812 for a comped Flat White, authorized by the manager, reason "quality."

## 2.25 Employee

**Definition.** A person who works at a location or for an operator, whose work, pay, and permissions are tracked.
**Identity.** A stable identity as a person employed, persisting across shifts and role changes.
**Lifecycle.** Hired → active (working shifts) → may change role → may be suspended → terminated; their work history persists.
**Ownership.** Identity context (for authentication and role); a Staff/Labor context for scheduling and pay.
**Relationships.** An employee *works at* one or more Locations; *holds* a Role with Permissions; *works* Shifts; *authors* actions (as the actor on events); *is scheduled by* a Schedule; *is paid for* their Labor.
**Invariants.** An employee's actions are attributed to them (every privileged action has an actor); an employee has exactly one active role per location context at a time; an employee's clock-in/out define their worked time; a terminated employee retains their historical attribution.
**Deletion policy.** Never deleted while any action, shift, or pay record references them; personal data subject to privacy law and erasure, with economic/audit facts retained anonymized.
**Example.** "Mariam," a server at the Zamalek branch, holds the server role, worked the evening shift, and is the actor on the orders she took.

## 2.26 Role

**Definition.** The set of responsibilities and permissions an employee holds, such as cashier, server, manager, or owner.
**Identity.** Identified by its name and its permission set within an operator's policy.
**Lifecycle.** Defined → assigned to employees → may be revised in policy.
**Ownership.** Identity context.
**Relationships.** A role *grants* Permissions; *is held by* Employees; *authorizes* certain actions (voids, discounts, refunds) that others cannot perform.
**Invariants.** A role's permissions are least-privilege (RFC-000); an action requiring a permission is performed only by an actor whose role grants it, or is elevated with an audited authorization; role definitions are auditable.
**Deletion policy.** Retired, not deleted, while any employee or historical action references it.
**Example.** The "manager" role grants the permission to authorize a discount beyond 10% and to approve a refund, which the "cashier" role does not.

## 2.27 Shift

**Definition.** A continuous period an employee is scheduled to work or a location is open, bounded by an open and a close.
**Identity.** A stable identity referencing the location (or employee), the day, and the open/close bounds.
**Lifecycle.** Opened → active (work and sales occur) → closed (counted and reconciled); a location shift bounds a business day's operation.
**Ownership.** Operations context (for a location's service shift); Staff context (for an employee's work shift).
**Relationships.** A shift *belongs to* a Location or Employee; *contains* Orders, Sales, Payments, drawer movements; *is reconciled at* close; *defines* a boundary for cash and reporting.
**Invariants.** A shift has a definite open and close; sales and payments belong to the shift in which they occurred; a shift's drawer reconciles (counted cash agrees with expected within a recorded variance); shift boundaries define the business day for reporting (Part 9).
**Deletion policy.** Never deleted; a closed shift with its reconciliation is permanent ground truth.
**Example.** The Zamalek branch's Friday shift opened at 7 a.m., took 214 orders, and closed at midnight with the drawer reconciled to a EGP 20 variance.

## 2.28 Supplier

**Definition.** A business from which a location buys ingredients, goods, or services.
**Identity.** A stable identity as a vendor the operator transacts with.
**Lifecycle.** Onboarded → active (fulfilling purchase orders) → may be deactivated; transaction history persists.
**Ownership.** Supplier Network context.
**Relationships.** A supplier *fulfills* Purchase Orders; *delivers* goods received into Stock; *is settled with* by Finance; *offers* a catalog of goods at prices; *participates in* the Marketplace's demand aggregation.
**Invariants.** A purchase order is placed with exactly one supplier; goods received against an order are attributed to its supplier; a supplier's prices and terms are defined; supplier transactions are auditable.
**Deletion policy.** Deactivated, not deleted, while any purchase, delivery, or settlement references them.
**Example.** "Cairo Dairy Co." is a supplier fulfilling the location's milk purchase orders, delivering weekly, settled monthly.

## 2.29 Purchase Order

**Definition.** A location's committed request to a supplier to deliver stated goods at stated quantities and prices.
**Identity.** A stable identity from creation, referencing the location, the supplier, and its lines.
**Lifecycle.** Drafted → placed (committed to the supplier) → fulfilled (goods delivered) → received (into stock) → settled (paid); may be partially fulfilled or cancelled.
**Ownership.** Supplier Network context.
**Relationships.** A purchase order *is placed with* one Supplier; *belongs to* one Location; *comprises* lines of Ingredients/goods at quantities and prices; *results in* Goods Receipts into Stock; *is settled by* Finance.
**Invariants.** A purchase order belongs to exactly one location and one supplier; goods received update the stock and the cost basis of the ingredients; the received quantity reconciles against the ordered quantity (with recorded variance); a settled purchase order corresponds to real money owed and paid.
**Deletion policy.** Never deleted; cancelled orders retained with their status; fulfilled orders are permanent ground truth feeding cost and demand.
**Example.** Purchase Order #P-441 to Cairo Dairy for 60 liters of milk at EGP 40/L, delivered, received into stock, settled.

## 2.30 Stock (Stock Level)

**Definition.** The quantity of an ingredient or a good a location holds on hand at a moment.
**Identity.** Identified by the ingredient and the location (and store within it).
**Lifecycle.** Established by a count or receipt → decremented by consumption, waste, transfer → incremented by receipt, transfer-in → corrected by counts.
**Ownership.** Inventory context.
**Relationships.** Stock *is of* an Ingredient *at* a Location; *is increased by* Goods Receipts and Transfers-in; *is decreased by* Sales (via recipes), Waste, and Transfers-out; *is corrected by* Counts; *drives* reorder against Par Levels.
**Invariants.** Stock is the net of all its movements (conservation: every unit is received, consumed, wasted, or transferred, and accounted for); stock does not go negative except under a defined policy (which records "sold past zero" as a business event — RFC-000 reconcile flags); a count corrects stock by a recorded adjustment, not a silent overwrite.
**Deletion policy.** Stock levels are a running truth derived from immutable movements; the movements are never deleted; the current level is always reconstructible from them.
**Example.** Milk stock at the Zamalek branch: 46 liters on hand, decremented ~0.15 L per drink, reordered when it falls below its 20-liter par.

## 2.31 Waste

**Definition.** Stock lost to spoilage, error, or damage rather than sold, recorded with a reason.
**Identity.** Identified as a stock movement with a waste reason at a time.
**Lifecycle.** Recorded when stock is lost → included in the stock net and the cost analysis.
**Ownership.** Inventory context.
**Relationships.** Waste *decreases* Stock; *is attributed to* an Ingredient, a reason, and often an Employee; *feeds* cost and forecasting.
**Invariants.** Waste is a recorded stock decrement with a reason; waste conserves the accounting (the lost quantity leaves stock and is booked as waste, not silently vanished); waste is auditable.
**Deletion policy.** Never deleted; waste is ground truth for cost control and forecasting.
**Example.** 3 liters of milk recorded as waste at close, reason "expired," reducing stock and adding to the day's food-cost variance.

## 2.32 Transfer

**Definition.** The movement of stock from one location or store to another, deducted from one and received by the other.
**Identity.** A stable identity referencing the source, the destination, and the goods.
**Lifecycle.** Initiated at source → dispatched → received at destination → reconciled.
**Ownership.** Inventory context (spanning two locations; often mediated by Central Kitchen).
**Relationships.** A transfer *decreases* Stock at the source and *increases* it at the destination; *moves* Ingredients/goods; *is often from* a Central Kitchen.
**Invariants.** A transfer conserves quantity (what leaves the source arrives at the destination, with any discrepancy recorded); a transfer belongs to exactly one source and one destination; both sides reconcile.
**Deletion policy.** Never deleted; retained as the movement record.
**Example.** 20 kg of dough transferred from the Central Kitchen to the Maadi branch, dispatched and received, both stock levels updated.

## 2.33 Delivery Order

**Definition.** An order to be transported to a guest at a remote address.
**Identity.** A stable identity as an order with a delivery fulfillment.
**Lifecycle.** Placed → accepted → prepared → dispatched (assigned to a driver) → in transit → delivered → settled; may fail or be returned.
**Ownership.** Operations context (as an order); Delivery/Logistics for its dispatch.
**Relationships.** A delivery order *is* an Order with a delivery fulfillment; *is for* a Guest at an Address in a Zone; *is prepared by* the Kitchen; *is dispatched to* a Driver; *may originate from* an Aggregator.
**Invariants.** A delivery order has a destination address in a served zone; it is dispatched to exactly one driver at a time; its lifecycle from placement to delivery is tracked; its payment settles its total including any delivery fee.
**Deletion policy.** Never deleted; retained with its outcome (delivered/failed) as ground truth for logistics and forecasting.
**Example.** A delivery order for a guest in the Zamalek zone, prepared, dispatched to driver Karim, delivered in 28 minutes.

## 2.34 Driver

**Definition.** The person who transports a delivery order from the location to the guest.
**Identity.** A stable identity as a delivery person.
**Lifecycle.** Onboarded → available → assigned to deliveries → completes them → off-shift.
**Ownership.** Delivery/Logistics context (within Operations).
**Relationships.** A driver *is assigned* Delivery Orders via Dispatch; *transports* them to Guests; *may be* an Employee or a third-party (aggregator) driver.
**Invariants.** A driver is assigned deliveries they can carry; a delivery is with exactly one driver at a time; a driver's delivery outcomes are recorded.
**Deletion policy.** Retained while any delivery references them; personal data subject to privacy law.
**Example.** Driver Karim, available at the Zamalek branch, assigned three deliveries in his run, all delivered.

## 2.35 Loyalty Account

**Definition.** A customer's standing in a loyalty program, holding their points, their tier, and their history.
**Identity.** A stable identity tied to a Customer within a brand's program.
**Lifecycle.** Enrolled → earns points on visits → redeems rewards → progresses tiers → may lapse.
**Ownership.** Guests context.
**Relationships.** A loyalty account *belongs to* one Customer within one brand's program; *earns* Points from Orders; *redeems* Rewards (as Discounts); *holds* a Tier.
**Invariants.** A loyalty account belongs to exactly one customer and one program; points earned and redeemed conserve (the balance is the net of earnings and redemptions); a redemption cannot exceed the balance; tier is derived from qualifying activity by the program's rules.
**Deletion policy.** Retained with the customer; subject to the customer's erasure rights (personal link removed, anonymized economic facts retained).
**Example.** Ahmed's loyalty account holds 340 points and Gold tier, earning 1 point per EGP 10 spent, redeeming a free drink at 200 points.

## 2.36 Gift Card

**Definition.** A prepaid instrument of stored value that a bearer may spend at a brand toward purchases.
**Identity.** A stable identity by its card number/token, independent of any customer (it is a bearer instrument).
**Lifecycle.** Issued (loaded with value) → active → spent down (redeemed against orders) → depleted or expired.
**Ownership.** Payments/Finance context (as stored value); Guests if linked to a customer.
**Relationships.** A gift card *holds* a balance; *is redeemed as* a Tender against Orders; *may be* reloaded.
**Invariants.** A gift card's balance is the net of loads and redemptions; a redemption cannot exceed the balance; stored value is a liability owed by the operator until redeemed; the balance is auditable.
**Deletion policy.** Never deleted; retained with its full load/redemption history as a financial instrument.
**Example.** A gift card loaded with EGP 500, redeemed EGP 130 against an order, balance EGP 370.

## 2.37 Campaign

**Definition.** A planned marketing effort to reach customers with an offer or a message over a period.
**Identity.** A stable identity as a marketing initiative.
**Lifecycle.** Planned → scheduled → active (reaching customers) → measured → ended.
**Ownership.** Guests/Marketing context.
**Relationships.** A campaign *targets* Segments of Customers; *may deliver* Promotions; *runs during* a Time Range; *is measured by* its effect on orders.
**Invariants.** A campaign targets a defined audience with a defined message/offer over a defined period; its results (reach, redemption, lift) are measurable and attributed.
**Deletion policy.** Ended and retained; its results are ground truth for marketing intelligence.
**Example.** A "Weekend Brunch" campaign targeting Gold-tier customers with a 10% promotion, run for one month, its lift measured.

## 2.38 Invoice

**Definition.** The formal, often tax-compliant, record of a sale addressed to a buyer, issued for accounting and regulatory purposes.
**Identity.** A stable, often legally-sequenced identity (an invoice number) referencing the sale and the parties.
**Lifecycle.** Issued at the sale → reported to the authority (e-invoice) → retained for the legal period.
**Ownership.** Finance context.
**Relationships.** An invoice *records* a Sale/Order; *itemizes* lines, discounts, service, and Tax; *is issued by* the operator *to* the buyer; *is reported to* the tax Authority.
**Invariants.** An invoice corresponds to exactly one sale; its amounts agree with the order's total and tax; its numbering is sequenced and gap-free per legal requirement; it is immutable once issued (a correction is a credit note, not an edit).
**Deletion policy.** Never deleted; retained for the legally-mandated period and as permanent ground truth.
**Example.** A sequenced e-invoice for Order #A-9812, itemizing the sale and its 14% VAT, reported to the tax authority.

## 2.39 Sale

**Definition.** A completed transaction in which items were sold, paid for, and recorded — the atomic economic event of the restaurant.
**Identity.** Identified with its order; a sale is the settled, finalized economic fact of an order.
**Lifecycle.** Comes into being when an order is paid and closed; is permanent thereafter.
**Ownership.** Operations context (the fact); reflected into Finance, Inventory, Guests, Intelligence.
**Relationships.** A sale *finalizes* an Order; *generates* an Invoice and a Receipt; *deducts* Stock; *earns* Loyalty; *records* Tax owed; *feeds* the Operating Graph as its highest-frequency fact.
**Invariants.** A sale is final (a paid, closed order does not un-sell); a sale's money, stock, tax, and loyalty effects are all consistent with each other; a sale is permanent ground truth.
**Deletion policy.** Never deleted; the atomic unit of the graph's economic history.
**Example.** Order #A-9812, paid and closed, is a sale of EGP 431 that deducted stock, owed EGP 53 VAT, and earned Ahmed 43 points.

## 2.40 Audit Record

**Definition.** The immutable, attributed record of what happened, especially of money-affecting and privileged actions.
**Identity.** Identified as an entry in the append-only trail, timestamped and attributed.
**Lifecycle.** Written when an auditable action occurs; never changed thereafter.
**Ownership.** Every context writes to a shared audit; the Audit is cross-cutting.
**Relationships.** An audit record *attributes* an action (a void, refund, discount override, login, config change) to an Actor at a Time in a Context.
**Invariants.** Append-only and immutable (RFC-000); every money-affecting and privileged action produces one; it cannot be altered after the fact; it is the foundation of trust and regulatory authority.
**Deletion policy.** Never deleted; retained for the legal period and beyond as the tamper-evident record.
**Example.** An audit record: "manager Mariam authorized a 15% discount on Order #A-9812 at 8:42 p.m., reason: regular guest."

---

# PART 3 — Value Objects

A **value object** is a thing defined entirely by its attributes, with no identity of its own — two amounts of the same money in the same currency are the same, and interchangeable, in a way that two Orders never are. Value objects are the vocabulary of *measurement and description* in the restaurant world, and getting them exactly right prevents a whole class of errors — the wrong currency, the negative quantity, the ambiguous time — that corrupt the truth quietly.

**Money.** An amount in a specific currency; it is meaningless without its currency, it is never a bare number, and arithmetic on it respects the currency's rules (its smallest unit, its rounding). *Money of different currencies is never added directly; a conversion is an explicit act at a stated rate and time.* Invariant: money has an amount and a currency; the amount is exact to the currency's minor unit; no computation silently loses or invents a fraction of the minor unit.

**Quantity.** An amount of something measured in a stated unit — two cups, 0.15 liters, three portions — meaningless without its unit. Invariant: a quantity has a value and a unit; quantities are combined only in compatible units (liters with liters, converted explicitly across units); a physical quantity of stock or sale is non-negative except under the defined "sold past zero" policy.

**Percentage.** A proportion expressed per hundred, applied to a base to yield an amount — a 14% tax on a base, a 10% discount. Invariant: a percentage applied to a Money base yields Money, rounded by the currency's rule; percentages compose in a defined order (discount before tax) and are never silently reordered.

**Tax Rate.** A percentage set by an authority for a class of goods, applied to a defined base. Invariant: a tax rate belongs to an authority and a jurisdiction; it applies to a defined base (inclusive or exclusive as the jurisdiction specifies); the applicable rate is the one in effect at the time of the sale (rates are time-versioned).

**Price.** The Money a location asks for an item before discounts and tax, valid in a context (a menu, a time, a location). Invariant: a price is Money; the same item may have different prices in different contexts, and the applicable price is the one for the sale's context; a price change is a new fact, and the price in effect at a sale's time is retained with the sale.

**Cost.** The Money an item's ingredients cost to produce, derived from its bill of materials at ingredient costs. Invariant: cost is Money; it is distinct from price (cost is what we pay, price is what we charge); food-cost percentage is cost over price and is a managed ratio.

**Address.** A description of a physical place sufficient to locate it — for a location, a delivery destination, a supplier. Invariant: an address locates a real place; a delivery address must fall in a served zone; an address may carry coordinates for routing.

**Coordinates.** A point on the earth by latitude and longitude, used to locate and route. Invariant: coordinates are a precise point; they are used for delivery routing and zone determination; personal location data is subject to privacy law.

**Phone.** A telephone number in a form that can be dialed, used to identify and reach a customer, driver, or supplier. Invariant: a phone number is stored in a normalized, dialable form with its country context; it is personal data subject to privacy and consent.

**Working Hours.** The times a location is open to serve, by day and by exception (holidays), against which service and reservations are validated. Invariant: working hours are defined per location per day, with exceptions; a reservation or an open shift is validated against them; hours are stated in the location's time (Part 9).

**Time Range.** A span from a start to an end instant, used for reservations, promotions, shifts, and menus' validity. Invariant: a time range has a start no later than its end; ranges are compared and combined explicitly; a range's meaning respects the relevant kind of time (Part 9).

**Duration.** A length of time without a fixed start — a ticket's prep time, a table's turn, a delivery's transit. Invariant: a duration is non-negative; it is measured between two instants of the same kind of time; it feeds timing intelligence.

**Rating / Score.** A bounded measure of quality or standing — a benchmark position, a prediction accuracy, a loyalty progress. Invariant: a score has a defined scale and meaning; it is derived, dated, and reproducible; it is never confused with the ground truth it measures.

**Contact.** A means of reaching a party — a phone, an email, an address — bundled as the ways to contact a customer, supplier, or driver. Invariant: contact information is personal data governed by consent and privacy law; it is used only for the purposes consented to.

---

# PART 4 — Aggregates

An **aggregate** is a cluster of entities and values that must be kept consistent *together*, treated as a single unit with a single root through which all changes pass. The aggregate is the boundary of *transactional consistency* — inside it, invariants hold at every moment; across aggregate boundaries, consistency is achieved *eventually*, through events, not instantly. Choosing aggregate boundaries correctly is how the restaurant's reality stays coherent without requiring the whole world to be consistent in one instant, which at a hundred thousand restaurants is neither possible nor necessary.

The permanent law of aggregates: **an aggregate is changed only through its root, its invariants hold whole at every commit, and it references other aggregates only by identity — never by reaching inside them.** Two aggregates are made consistent with each other by the events one publishes and the other consumes, not by a shared transaction, because the restaurant's reality is naturally partitioned — the kitchen need not be instantaneously consistent with the accounting for either to be correct.

**The Order aggregate.** Root: Order. Contains: its Lines, their Modifiers, its Discounts, its Service and Tax, its Seat attributions, its coursing. Why: an order's total, its lines, its discounts, and its tax must be consistent *at every moment* — you cannot have a line without its effect on the total, or a discount applied but not reflected. The order is the tightest consistency boundary in the restaurant, because it is the guest's commitment and it must always add up. Consistency boundary: everything that determines what the guest owes is inside the order aggregate and consistent instantly; everything downstream (the kitchen ticket, the stock deduction, the loyalty points) is a *consequence* reconciled by events.

**The Payment aggregate.** Root: Payment. Contains: its authorization, capture, and settlement states for a card; its tender and change for cash; its refunds. Why: a payment's state machine must be consistent within itself — an authorization, its capture, and its reversal are one coherent story that must never be half-applied, because it is money. The payment references its order by identity but is its own aggregate, because the money's lifecycle (authorize, capture, settle, reconcile) has its own consistency that outlives the order's closing. Consistency boundary: the movement and reconciliation of one payment's money is whole within the payment aggregate.

**The Ticket aggregate.** Root: Ticket. Contains: its items, their station routing, their prepared/bumped states, its timing. Why: a ticket's preparation state across stations must be coherent — a ticket is complete only when all its items are bumped, and this is a single consistent truth in the kitchen. The ticket references its order by identity but is its own aggregate, because the kitchen's reality (what is being prepared, by whom, how long) has its own consistency separate from the order's money. Consistency boundary: the preparation state of one ticket is whole within it.

**The Stock aggregate.** Root: the Stock of one ingredient at one location. Contains: its running level and its movements (receipts, consumption, waste, transfers, counts). Why: an ingredient's stock at a location must be consistent — its level is the net of its movements, and a movement and its effect on the level are one act. Stock references sales, purchases, and transfers by identity but its own level is its own consistency. Consistency boundary: the level and movements of one ingredient at one location are whole together; cross-location transfer is two aggregates reconciled by events.

**The Reservation aggregate.** Root: Reservation. Contains: its party, its table hold, its time, its deposit. Why: a reservation's hold on capacity must be consistent — you cannot confirm a reservation and not hold its table. Consistency boundary: one reservation's hold is whole within it; the location's overall capacity across reservations is reconciled at the reservations-context level, not inside one reservation.

**The Shift aggregate.** Root: Shift. Contains: its open and close, its drawer movements, its reconciliation. Why: a shift's cash reconciliation must be consistent — the drawer's expected and counted amounts and their variance are one coherent close. Consistency boundary: one shift's reconciliation is whole within it.

**The Customer/Loyalty aggregate.** Root: Customer (with their Loyalty Account). Contains: their identity, consent, points balance, tier. Why: a customer's loyalty balance must be consistent — points earned and redeemed net to a balance that cannot be overspent. Consistency boundary: one customer's loyalty state is whole within it; earning from an order is a consequence reconciled by an event (the sale), so a brief lag between the sale and the points is acceptable and correct.

**The Purchase Order aggregate.** Root: Purchase Order. Contains: its lines, its supplier, its fulfillment and receipt states. Why: a purchase order's commitment and receipt must be consistent within the order. Consistency boundary: one purchase order is whole within it; its effect on stock is a consequence reconciled by the goods-receipt event.

The reason aggregates matter, stated once: **the restaurant's reality is naturally partitioned into things that must be true together and things that must merely become true together, and modeling that partition correctly is what lets a hundred thousand restaurants operate without a single global lock. Inside an aggregate, the truth is always whole; across aggregates, the truth is reconciled by events, exactly as the real restaurant reconciles its kitchen, its drawer, and its books — not in one instant, but reliably, over the short time that separates a sale from its consequences.**

---

# PART 5 — Domain Events

An event is the record that something meaningful happened, and the events are the truth from which all state derives (RFC-000). Here is the catalog of the restaurant's important events, each with its **meaning** (what really happened in the world), its **producer** (the context that owns the fact and emits it), its **consumers** (the contexts that react), and its **immutable fields** (the facts that, once recorded, define the event forever). This catalog is representative, not exhaustive — new events are added under RFC-000's evolution rules — but it names the events that constitute the spine of the graph.

## Operations & the order lifecycle

**OrderOpened** — *Meaning:* a guest or party began an order. *Producer:* Operations. *Consumers:* Kitchen (awaits), Reporting, Intelligence. *Immutable fields:* order identity, location, time, service type, table/party (if dine-in), opening actor.

**LineAdded / LineModified / LineVoided** — *Meaning:* an item was added to, changed on, or removed from an order before payment. *Producer:* Operations. *Consumers:* Kitchen (if sent), Inventory (on sale), Reporting. *Immutable fields:* order identity, line identity, item, quantity, modifiers, price, actor, time; for a void, the reason and authorizer.

**OrderSent (Fired)** — *Meaning:* an order or course was released to the kitchen to prepare. *Producer:* Operations. *Consumers:* Kitchen (creates tickets). *Immutable fields:* order identity, course, items, time, actor.

**DiscountApplied** — *Meaning:* a discount was applied to an order or line. *Producer:* Operations. *Consumers:* Finance (tax base), Reporting, Audit. *Immutable fields:* order identity, discount amount/rate, reason, rule or authority, time.

**OrderBilled** — *Meaning:* the bill was presented for settlement. *Producer:* Operations. *Consumers:* Payments (awaits), Reporting. *Immutable fields:* order identity, total, time.

**OrderSplit** — *Meaning:* an order's total was divided for separate settlement. *Producer:* Operations. *Consumers:* Payments. *Immutable fields:* order identity, split structure (by seat/item/amount), time.

**OrderPaid** — *Meaning:* an order was settled in full. *Producer:* Operations (on the last payment). *Consumers:* Finance, Inventory (sale confirmed), Guests (loyalty), Intelligence. *Immutable fields:* order identity, total, payments, time.

**OrderClosed** — *Meaning:* an order was finalized and became a permanent sale. *Producer:* Operations. *Consumers:* everyone downstream; this is the sale fact. *Immutable fields:* order identity, final total, time.

**OrderVoided** — *Meaning:* an order was cancelled before payment. *Producer:* Operations. *Consumers:* Kitchen (cancel), Audit. *Immutable fields:* order identity, reason, authorizer, time.

**TableOccupied / TableCleared** — *Meaning:* a party was seated at / departed a table. *Producer:* Operations. *Consumers:* Reservations, Reporting, Intelligence (turns). *Immutable fields:* table identity, party size, time.

## Kitchen

**KitchenAccepted** — *Meaning:* the kitchen acknowledged a ticket and began work. *Producer:* Kitchen. *Consumers:* Operations (status), Intelligence (timing). *Immutable fields:* ticket identity, order, station(s), time.

**ItemBumped / TicketCompleted** — *Meaning:* a station finished an item / all a ticket's items were finished. *Producer:* Kitchen. *Consumers:* Operations (ready to serve), Intelligence (prep timing). *Immutable fields:* ticket identity, item/station, time.

**ItemEightySixed** — *Meaning:* an item became unavailable. *Producer:* Kitchen/Operations. *Consumers:* Operations (menu availability), Inventory, Intelligence. *Immutable fields:* item identity, location, time, actor.

## Inventory & supply

**StockReceived** — *Meaning:* goods arrived and were received into stock. *Producer:* Inventory (from a goods receipt). *Consumers:* Finance (payable), Intelligence. *Immutable fields:* ingredient, quantity, location, purchase order, cost, time.

**StockConsumed** — *Meaning:* stock was consumed by a sale's production. *Producer:* Inventory (on a sale, via bill of materials). *Consumers:* Intelligence (food cost), reorder. *Immutable fields:* ingredient, quantity (delta), location, order, time.

**StockWasted** — *Meaning:* stock was lost to waste. *Producer:* Inventory. *Consumers:* Intelligence, Reporting. *Immutable fields:* ingredient, quantity, reason, location, actor, time.

**StockCounted** — *Meaning:* a physical count corrected the tracked stock. *Producer:* Inventory. *Consumers:* Intelligence, Audit. *Immutable fields:* ingredient, counted quantity, prior quantity, variance, location, actor, time.

**StockTransferred** — *Meaning:* stock moved between locations. *Producer:* Inventory. *Consumers:* both locations, Intelligence. *Immutable fields:* ingredient, quantity, source, destination, time.

**PurchaseOrderPlaced** — *Meaning:* a location committed an order to a supplier. *Producer:* Supplier Network. *Consumers:* Finance, Supplier, Intelligence. *Immutable fields:* purchase order identity, supplier, location, lines, time.

**SupplierAssigned** — *Meaning:* a supplier was designated to fulfill a need. *Producer:* Supplier Network. *Consumers:* Finance, Marketplace. *Immutable fields:* need/order, supplier, terms, time.

## Payments & finance

**PaymentInitiated** — *Meaning:* settlement of an order began by some tender. *Producer:* Payments. *Consumers:* Operations, Audit. *Immutable fields:* payment identity, order, tender, amount, time.

**PaymentAuthorized** — *Meaning:* a card/wallet issuer confirmed and held funds. *Producer:* Payments. *Consumers:* Operations, Finance. *Immutable fields:* payment identity, amount, processor reference, time.

**PaymentCaptured** — *Meaning:* an authorized charge was finalized and funds taken. *Producer:* Payments. *Consumers:* Finance (settlement), Operations. *Immutable fields:* payment identity, amount, processor reference, time.

**PaymentSettled** — *Meaning:* captured funds were transferred to the operator in a batch. *Producer:* Payments/Finance. *Consumers:* Finance (reconciliation). *Immutable fields:* payment identity, settlement batch, amount, time.

**PaymentFailed** — *Meaning:* a payment attempt did not succeed. *Producer:* Payments. *Consumers:* Operations (retry), Audit. *Immutable fields:* payment identity, reason, time.

**RefundIssued** — *Meaning:* money was returned to a guest. *Producer:* Payments. *Consumers:* Finance, Operations, Audit. *Immutable fields:* refund identity, original payment, amount, reason, authorizer, time.

**ReversalOpened** — *Meaning:* a charge that should not stand was flagged for reversal. *Producer:* Payments. *Consumers:* Finance, Manager surface. *Immutable fields:* transaction reference, amount, reason, time.

## Identity, staff, and audit

**EmployeeClockedIn / ClockedOut** — *Meaning:* an employee began/ended worked time. *Producer:* Staff/Identity. *Consumers:* Labor, Reporting. *Immutable fields:* employee, location, time.

**ShiftOpened / ShiftClosed** — *Meaning:* a location's service period began/ended, the drawer counted and reconciled. *Producer:* Operations. *Consumers:* Finance, Reporting, Audit. *Immutable fields:* shift identity, location, open/close time, drawer counts and variance (on close).

**PrivilegedActionAuthorized** — *Meaning:* a manager authorized an exception (discount override, void, refund, elevation). *Producer:* Identity/Audit. *Consumers:* Audit, Reporting. *Immutable fields:* action, authorizer, target, reason, time.

**ConfigChanged** — *Meaning:* a location's or brand's configuration (a price, a menu, a rule) was changed. *Producer:* the owning context. *Consumers:* Audit, affected contexts. *Immutable fields:* what changed, prior and new value, actor, time.

## Guests, loyalty, and reservations

**CustomerIdentified** — *Meaning:* a guest was linked to a known customer. *Producer:* Guests. *Consumers:* Operations, Loyalty. *Immutable fields:* customer identity, visit/order, time (with consent).

**PointsEarned / RewardRedeemed** — *Meaning:* a customer earned loyalty points / redeemed a reward. *Producer:* Guests. *Consumers:* Operations (discount), Reporting. *Immutable fields:* customer, points/reward, order, time.

**ReservationConfirmed / Seated / NoShow / Cancelled** — *Meaning:* a reservation reached the stated state. *Producer:* Reservations. *Consumers:* Operations, Intelligence (demand, no-show rate). *Immutable fields:* reservation identity, party, time, outcome.

## Delivery

**DeliveryDispatched** — *Meaning:* a delivery order was assigned to a driver and sent. *Producer:* Delivery/Operations. *Consumers:* Operations (status), Intelligence (logistics). *Immutable fields:* delivery order, driver, time.

**DeliveryCompleted / DeliveryFailed** — *Meaning:* a delivery arrived / could not be delivered. *Producer:* Delivery. *Consumers:* Operations, Finance (settle/refund), Intelligence. *Immutable fields:* delivery order, outcome, time.

The law of every event, restated from RFC-000 so it governs this catalog: each event is immutable, ordered, idempotent, attributed, versioned, and readable forever, because each event is a fact added to the Operating Graph, and the graph is the sum of these facts across a hundred thousand restaurants over time.

---

# PART 6 — Invariants

An **invariant** is a truth about the restaurant world that must *always* hold — a law the domain obeys, which our systems must never violate and must actively defend. These are the rules that keep the truth coherent; a system that breaks one is not merely buggy, it is *lying* about the world. What follows are the invariants of the restaurant universe, grouped by domain. They are stated as absolutes because they are absolutes.

## Orders & sales
1. An order belongs to exactly one location.
2. An order's total equals its subtotal, less discounts, plus service, plus tax — always, exactly.
3. A discount is computed before tax; tax is computed on the discounted base.
4. A paid order cannot become unpaid.
5. A closed order is a permanent sale and cannot be un-sold.
6. Every line on an order belongs to exactly one order.
7. A line's price derives deterministically from its item, modifiers, quantity, and applicable discounts.
8. Every modifier on a line is valid for that line's item.
9. A voided line or order is retained with its void reason and authorizer; a void never erases history.
10. The sum of an order's payments settles exactly its total (tips excepted, as separate).
11. An order's covers (guests served) are consistent with its seats and party size.
12. An item sent to the kitchen is recorded even if the order is later voided.

## Payments & money
13. Every payment belongs to exactly one order.
14. A payment is applied exactly once — a retry never double-charges (idempotency).
15. A captured payment corresponds to real money that must reconcile with settlement.
16. A refund cannot exceed its original payment.
17. A refund is a new record; it never erases the original payment.
18. Money of different currencies is never added without an explicit conversion at a stated rate and time.
19. A payment, once made, is never silently altered — only refunded or reversed by a new recorded act.
20. Stored value (a gift card) is a liability owed until redeemed; its balance is the net of loads and redemptions and cannot be overspent.
21. Cash tendered, change given, and the drawer's expected and counted amounts reconcile within a recorded variance.
22. Tax collected is owed to the authority and is never the operator's revenue.

## Inventory & supply
23. Stock is the exact net of its movements: receipts plus transfers-in, minus consumption, waste, and transfers-out.
24. Stock does not go negative except under the defined "sold past zero" policy, which records the event as a business fact.
25. A count corrects stock by a recorded adjustment, never a silent overwrite.
26. A sale deducts exactly the bill of materials of its sold items.
27. A transfer conserves quantity: what leaves the source arrives at the destination, with any discrepancy recorded.
28. A purchase order belongs to exactly one location and one supplier.
29. Goods received update stock and the cost basis; the received quantity reconciles against the ordered quantity.
30. An ingredient's cost derives from its purchases; an item's cost equals the sum of its bill of materials at ingredient costs.
31. Every recipe has exactly one owner and is versioned; the version in effect at a sale's time is retained.
32. Waste is a recorded decrement with a reason; lost stock is never silently vanished.

## Menu & catalog
33. A menu item belongs to exactly one brand/location catalog and has at least one price context.
34. Every modifier belongs to exactly one menu item (through its group).
35. A modifier group's selection rules (how many may/must be chosen) are defined and enforced.
36. A combo's price is defined independently of its components' sum; a combo deducts the stock of all its components.
37. A price change is a new fact; the item's identity is stable across it, and the price in effect at a sale is retained.
38. An 86'd item cannot be added to a new order until it is un-86'd.

## Tables, reservations, & service
39. A table hosts at most one active party at a time (unless explicitly merged).
40. A table belongs to exactly one dining room, which belongs to exactly one location.
41. A reservation belongs to exactly one location and holds capacity for exactly one party at one time.
42. Confirmed reservations for a time do not, together, exceed the location's capacity for that time.
43. A no-show or cancellation is retained with its outcome; a reservation's history is never silently deleted.
44. A party shares exactly one order per visit; a seat's attributions are part of exactly one order and sum consistently with the whole.

## Kitchen
45. A ticket derives from exactly one order or course.
46. A ticket is never silently lost; every ticket reaches a terminal state (completed, or explicitly failed/cancelled) that is recorded.
47. A ticket is complete only when all its items are bumped.
48. A ticket's timing (fire to bump) is recorded as ground truth.

## Identity, staff, & authorization
49. Every privileged and money-affecting action is attributed to an authenticated actor.
50. An action requiring a permission is performed only by an actor whose role grants it, or under an audited elevation.
51. An employee has exactly one active role per location context at a time.
52. A shift has a definite open and close; sales and payments belong to the shift in which they occurred.
53. Every audit record is immutable and cannot be altered after the fact.

## Guests, loyalty, & consent
54. A customer belongs to exactly one brand's relationship; identity is brand-scoped, not shared across unrelated brands.
55. Loyalty points earned and redeemed conserve to a balance that cannot be overspent.
56. A loyalty tier is derived from qualifying activity by the program's defined rules.
57. Personal data is held and used only per the customer's consent and privacy law.
58. On a lawful erasure, personal data is deleted by an audited act while anonymized economic facts are retained.

## Finance & tax
59. An invoice corresponds to exactly one sale; its amounts agree with the order's total and tax.
60. Invoice numbering is sequenced and gap-free per legal requirement.
61. An issued invoice is immutable; a correction is a credit note, never an edit.
62. The applicable tax rate is the one in effect at the sale's time (rates are time-versioned).
63. Tax is computed on the correct base per the jurisdiction's inclusive/exclusive rules, and the computation is reproducible.

## Delivery
64. A delivery order has a destination address in a served zone.
65. A delivery order is dispatched to exactly one driver at a time.
66. A delivery order reaches a recorded terminal outcome (delivered or failed).

## The graph & truth (cross-cutting, from RFC-000)
67. Every important action produces an immutable, ordered, idempotent, attributed event.
68. State is a projection of events; any state is reproducible by replay.
69. Any past state of any entity can be reconstructed for any moment (time-travel).
70. No derived, predicted, or analytical value is ever treated as the ground truth it is derived from.
71. Ground truth is never silently destroyed; deletion is explicit, lawful, and audited.
72. A prediction is never written into the operational record as a fact.
73. Each fact has exactly one owning context; no other context holds or mutates it.
74. Old events remain readable and meaningful forever; their meaning, once recorded, never changes.

These invariants are not preferences; they are the shape of a coherent restaurant reality, and a system that upholds them tells the truth while a system that breaks them lies. Every feature, every migration, and every AI action is checked against them, and where a new part of the domain reveals a new invariant, it is added here under RFC-000's evolution rules, because the list of what must always be true is itself part of the permanent language.

---

# PART 7 — The Bounded Context Map

The restaurant's reality is one connected whole, but no single mind or system can hold it all coherently, so it is divided into **bounded contexts**, each the sovereign owner of one coherent region of the truth, each speaking its own precise dialect of this ontology, and each communicating with the others through explicit events and contracts rather than by reaching into their internals (RFC-000, Part 2). Here is the map — the contexts and how they interact — described as the flow of truth through the restaurant, not as software.

```
   GUEST arrives ─▶ ┌────────────┐ reservation ┌──────────────┐
                    │RESERVATIONS│────────────▶│              │
                    └────────────┘  seated     │  OPERATIONS  │◀── the heartbeat
                                    ───────────▶│  (order,     │    (highest-frequency truth)
   GUESTS ◀── identify ─────────────────────────│   floor,     │
   (customer,                                    │   service)   │
    loyalty) ── points/rewards ─────────────────▶│              │
                                                 └──┬───┬───┬──┘
                             order fired ──────────┘   │   └────────── order paid
                                    ▼                  │                    ▼
                             ┌────────────┐    line sold│            ┌──────────────┐
                             │  KITCHEN   │             ▼            │   PAYMENTS   │
                             │  (tickets, │      ┌────────────┐      │ (auth,capture│
                             │  routing)  │      │ INVENTORY  │      │  settle,     │
                             └────────────┘      │ (stock,    │      │  refund)     │
                                                 │  recipes,  │      └──────┬───────┘
                                                 │  cost)     │             │ settled
                             ┌────────────┐  buy │            │             ▼
                             │  SUPPLIER  │◀─────┤            │      ┌──────────────┐
                             │  NETWORK   │ deliver──────────▶│      │   FINANCE    │
                             └─────┬──────┘      └────────────┘      │ (ledger,tax, │
                                   │ demand                          │  reconcile,  │
                                   ▼                                 │  credit)     │
                             ┌────────────┐                          └──────────────┘
                             │ MARKETPLACE│◀── liquidity ──▶ (suppliers/lenders/guests)
                             └────────────┘
                                          all contexts' events ──▶ ┌──────────────┐
   IDENTITY ── who may act ──▶ (every context)                     │ REPORTING &  │
   (authn, roles, devices)                                         │ INTELLIGENCE │──▶ DECISION
                                                                   │ (read/predict)│    ENGINE
                                                                   └──────────────┘    (act)
```

**Operations** is the heart, where the guest's visit and order live, and it is the origin of most of the restaurant's truth. It receives seated parties from **Reservations**, identifies known guests through **Guests**, fires orders to the **Kitchen**, deducts stock through **Inventory**, settles through **Payments**, and closes into sales that feed **Finance**, **Guests** (loyalty), and **Intelligence**. Every action within it is authorized by **Identity**.

**Kitchen** receives fired orders as tickets, routes them across stations, and reports their preparation and timing back to Operations and forward to Intelligence (which learns capacity and timing). It owns the fulfillment truth; it does not own the money or the menu.

**Inventory** owns stock, recipes, and cost. It is decremented by Operations' sales (through recipes), replenished by the **Supplier Network**'s deliveries, and it feeds cost and depletion truth to **Finance** and **Intelligence**. It is one of the thickest data surfaces — the difference between a sales-node and a whole-business-node.

**Payments** owns the movement and reconciliation of money. It settles Operations' orders and feeds settled, reconciled money to **Finance**. It is the highest-fidelity truth of cash flow — the input to credit — and it holds the strictest correctness bar.

**Finance** owns the financial position: the ledger boundary to the outside accounting world (integrated, not rebuilt), tax computation and reporting, reconciliation, and the credit relationship. It consumes sales, payments, purchases, and labor, and it is where the graph's economic truth is made whole at the business level.

**Guests** owns the customer relationship, loyalty, consent, and segmentation — the most personal truth, most bound by privacy law. It identifies guests for Operations, awards and redeems loyalty, and feeds customer understanding to Intelligence and Marketing.

**Reservations** owns the seat over time — bookings, waitlist, capacity — feeding Operations its seated parties and Intelligence its demand and no-show truth.

**Supplier Network** owns the supply side — suppliers, purchase orders, deliveries — feeding Inventory its stock and the **Marketplace** its aggregated demand.

**Identity** owns *who may act* — humans, devices, systems — and it is the authority every other context trusts for authentication and authorization. It holds the least data and the most power.

**Reporting** owns the human-readable *read* of the truth — aggregations, dashboards, exports — built as projections from every context's events. It owns no source truth.

**Intelligence** owns *understanding* — benchmarking, forecasting, prediction — consuming every context's events and producing derived knowledge and predictions (never confused with the ground truth they derive from). It measures itself by prediction accuracy (RIS).

**Marketplace** owns the *clearing of the two-sided economy* — matching and transacting restaurant demand with suppliers, lenders, and guests — where the graph becomes a market and liquidity becomes measurable.

**Decision Engine** is where Intelligence, Marketplace, and Finance combine into *agency* — forecasting demand and ordering stock, scheduling labor, pricing within guardrails, extending credit, routing the kitchen — acting on the graph with human oversight (RFC-000, Part 8: AI proposes, humans decide, bounded authority acts, all audited).

The law of the map, restated: **each context is the single source of truth for its region of the restaurant's reality; contexts learn of each other's truth only through the events their owners publish; and the whole coherent restaurant emerges not from one system knowing everything at once, but from many sovereign contexts each knowing their part truly and reconciling through events — exactly as a real restaurant's kitchen, drawer, floor, and books are separate realities that reconcile into one business.**

---

# PART 8 — Canonical Identity

Identity is how the restaurant world knows that *this* is the same thing as *that* — the same order across a network partition, the same customer across two branches, the same ingredient across a transfer. Getting identity right is the foundation of a coherent graph, because a graph is nodes and edges, and a node without a stable identity is a node that fragments or collides, either of which corrupts the truth. This part defines how identity works across the peculiar realities of a restaurant: many locations, frequent offline operation, and the need for both machines and humans to refer to the same things.

**Every entity has a global identity that is unique across all of Mezze, forever.** No two orders, payments, tables, or customers anywhere in the world share an identity, and an identity, once assigned, is never reused. This global identity is the true name of a thing in the graph — the key by which every context, every event, and every relationship refers to it — and it is what makes it possible to relate a payment in one context to an order in another, or to merge a customer's history across two branches, without ambiguity. Global identity is opaque and permanent: it carries no meaning that could change, so that it never becomes wrong.

**Every entity also has a human-readable identity for the people who must speak about it.** A cashier says "Order A-9812," a guest reads "Table 12," a manager references "Invoice 2024-0451" — these are the names humans and printed documents use, and they are chosen to be memorable, speakable, and meaningful within their scope. A human-readable identity is unique *within its scope* (an order number within a location's day, a table number within a dining room, an invoice number within a legal sequence) but not necessarily globally, and it may be structured to carry useful meaning (a date, a sequence, a location prefix). The human-readable identity always maps to exactly one global identity, but the global identity is the truth and the human-readable one is the convenience.

**Offline identity: a thing born offline must have an identity the instant it is born, before it can reach any central authority.** Because a restaurant operates without a network (RFC-000, Part 6), an order taken during an outage, a payment captured in a blackout, a ticket fired offline — each must have a globally-unique identity *at the moment it happens*, generated locally, without coordination, and guaranteed not to collide with any identity generated anywhere else. This is a hard requirement of the restaurant's reality: the truth is born at the edge, often offline, and it must be identifiable and un-collidable from birth, so that when connectivity returns and the offline events sync into the graph, each is recognized as the distinct thing it is and none is mistaken for another. An identity that requires a central authority to assign is an identity that cannot exist offline, and is therefore forbidden for anything that can be born offline.

**Merge rules: when two identities are discovered to name the same real thing, they are merged by a defined, recorded act — never silently.** The common case is a customer: a guest identified by phone at one branch and by loyalty card at another may be the same person, discovered later. When two identities are found to be one, the merge is an explicit, audited event that establishes one as the surviving identity and records the other as an alias pointing to it, preserving every fact attributed to either, so that no history is lost and the graph now knows they were always one. A merge never deletes; it unifies. And a merge is reversible in principle (if it was wrong, it can be split again by another recorded act), because a mistaken merge that could not be undone would be an irreversible corruption of the truth.

**Conflict rules: when the same identity is claimed by two different real things, it is a conflict, and conflicts are resolved by a rule decided in advance, never by whichever arrived last.** This is the inverse of a merge, and it should be nearly impossible by construction (globally-unique, un-collidable identities prevent it), but where it can occur — two offline terminals, a restore from backup, a bad integration — the resolution is deterministic and recorded, and the conflict is surfaced as a business event a human can inspect, never silently resolved by last-write-wins (RFC-000, Part 6). A silent identity conflict is a silent corruption of the graph, and the ontology forbids it.

**Identity of the actor, always.** Beyond entities, every *event* carries the identity of the actor who caused it — the employee, the device, the system, or the AI under whose authority it happened (RFC-000, Part 7). This is not a convenience; it is the foundation of the audit, the authorization, and the trust, and it means that identity is not only how we name *things* but how we attribute *actions*, so that the graph knows not just what happened but who made it happen.

The law of identity, stated once: **every thing and every action in the restaurant world has one true, global, permanent identity, born the instant the thing is born (even offline, without coordination, un-collidable), spoken of by humans through a scoped readable name, unified when two names are found to be one thing (by a recorded, reversible act), and never silently collided or reused — because the graph is a structure of identified nodes and attributed edges, and an identity that fragments, collides, or is reused is a tear in the fabric of the truth.**

---

# PART 9 — Time

Time in a restaurant is not one thing, and the single most common and most damaging category of error in restaurant software is treating the many kinds of time as if they were one. A sale at 1 a.m. belongs to the *previous* business day; a kitchen ticket's clock runs differently from the wall clock; an accounting period closes on a boundary that is neither midnight nor the shift's end; and a hundred thousand restaurants span many time zones while their operators think only in local time. This part defines the kinds of time and the law of each, because a system that confuses them reports the wrong day's sales, computes the wrong shift's labor, and files the wrong period's taxes — each a lie in the graph told with a clock.

**Wall-clock time** is the ordinary civil time on the wall of the restaurant — the local time the staff and guests live in. It is what a human means by "8 p.m.," it is always expressed in the *location's* time zone, and it is the time humans schedule, reserve, and speak in. Wall-clock time is a *presentation and human-coordination* time; it is not, by itself, the time the graph reasons in, because it is ambiguous across zones and it jumps (daylight changes, zone differences). Every human-facing time is wall-clock time in the location's zone; every stored time is not.

**Event time** is the true, unambiguous instant a thing actually happened, recorded to the precision the fact demands, in a form that is the same instant everywhere on earth regardless of zone. Event time is what the graph reasons in: the ordering of events (RFC-000, Part 3), the "when did this really happen" that no zone or clock-change can distort. Every event carries its event time as an absolute instant, and this is the time the graph trusts, because it is the one time that means the same thing everywhere and never jumps. Event time is converted to wall-clock time only for humans, and only against the relevant location's zone.

**Business time** is the *operational* time the restaurant lives by, and its central concept is the **business day**, which is *not* the calendar day. A restaurant that closes at 2 a.m. considers those late sales part of the day that began the previous morning — the business day runs from the location's *open* to its *close*, across the midnight boundary, and a sale at 1 a.m. belongs to the business day that began yesterday morning. Business time is defined by the shift boundaries (Part 2.27): a location's business day is bounded by its shift's open and close, and every sale, payment, and labor hour is attributed to the business day in which it operationally occurred, not the calendar day the wall clock showed. This is the time reporting and daily reconciliation use, because it matches how an operator actually thinks about "today's sales" — everything from this morning's open until we close tonight, whenever tonight ends. To attribute a 1 a.m. sale to the calendar day it fell in, rather than the business day it belonged to, is to report the wrong day's numbers, and the ontology forbids it.

**Kitchen time** is the *elapsed, relative* time the kitchen operates by — a ticket's age since it fired, a station's preparation duration, the time a dish has been waiting. Kitchen time is measured as durations from event to event (fire to bump), not as points on a clock, because what the kitchen cares about is "how long has this been cooking," not "what time is it." Kitchen time feeds the capacity and timing intelligence, and it is computed from event times' differences, which is why event time must be precise: an imprecise event time yields a wrong duration, and a wrong duration mis-teaches the capacity model.

**Accounting time** is the time the *books* run on — the fiscal periods, the settlement batches, the tax periods — which have their own boundaries defined by law and policy, and which are neither the calendar day nor necessarily the business day. A settlement batch closes when the processor closes it; a tax period closes on the authority's boundary; a fiscal month closes on the operator's boundary. Accounting time attributes financial facts to the periods the books and the law recognize, and it may differ from business time (a sale's business day and its accounting period can diverge, e.g., a sale near a period boundary). Finance reasons in accounting time; a fact is attributed to the accounting period defined by law and policy, not assumed to match the business day.

**The timezone philosophy, stated as law:** *every stored time is an absolute event-time instant that means the same thing everywhere; every human-facing time is converted to the relevant location's wall-clock zone for display and coordination; every operational attribution ("today's sales," "this shift") uses business time and the business day bounded by the location's open and close, never the calendar day; every kitchen measure is an elapsed duration between event times; and every financial attribution uses the accounting period defined by law and policy.* We never store a time without knowing which kind it is; we never compare times of different kinds as if they were the same; we never assume the business day equals the calendar day; and we never present an absolute instant to a human without converting it to their location's wall clock. A restaurant spans zones, crosses midnight to close, cooks in durations, and books in fiscal periods, and the graph tells the truth about *when* only if it keeps these kinds of time distinct — because a number attached to the wrong kind of time is a wrong number wearing a right one's clothes.

---

# PART 10 — The Operating Graph

Everything in this ontology assembles into one structure: the Operating Graph, the invariant of the Company Constitution and the asset the whole company exists to build. This part describes the graph as *reality* — the nodes that are the restaurant world's things, the edges that are their relationships, and the rules that govern who owns what — so that an engineer, an analyst, or an AI can see the whole shape of the truth we hold. It is not a database schema; it is the map of the restaurant economy as it actually is, and our software is judged by how faithfully it reflects this map.

## The nodes

A node in the graph is a thing with identity that persists through change — every entity of Part 2 is a kind of node. At the largest scale, the nodes are the **organizations and places**: Operators, Brands, Locations, Dining Rooms, Tables, Seats — the physical and organizational structure within which everything happens. At the scale of the moment, the nodes are the **acts and records of operation**: Orders, Lines, Tickets, Sales, Payments, Refunds — the high-frequency truth of what was sold, made, and paid, which is the heartbeat of the graph and the bulk of its mass. At the scale of what is offered and consumed, the nodes are the **catalog and supply**: Menus, Menu Items, Modifiers, Combos, Recipes, Ingredients, Stock, Purchase Orders, Suppliers — what the restaurant sells and what it takes to make it. At the scale of people, the nodes are the **actors and relationships**: Employees, Roles, Guests, Customers, Loyalty Accounts, Drivers — who works, who is served, and who is remembered. And spanning all of them, the nodes of **understanding and money-over-time**: Forecasts, Benchmarks, Invoices, Financial positions, Credit relationships — the derived and financial truth built atop the operational base.

A single restaurant is a dense cluster of these nodes — its one location, its dozens of tables, its hundreds of menu items and ingredients, its thousands of orders a month, its staff, its customers, its suppliers — connected into the complete picture of *that restaurant's operation*. This is what we mean by a **thick node** in the Company Constitution's terms: not a single point, but a whole connected sub-graph of one restaurant's reality, and the depth of that sub-graph — how much of the restaurant's operation is captured as connected nodes rather than left in a spreadsheet or a rival tool — is the *depth* that turns a POS-node into a whole-business-node.

## The edges

An edge is a relationship between nodes — every relationship named in Part 2 is a kind of edge — and the edges are what make the graph a graph rather than a pile of records. The **structural edges** are the enduring relationships: a Location *belongs to* a Brand, a Table *is in* a Dining Room, a Menu Item *is defined by* a Recipe, an Ingredient *is consumed by* a Recipe, a Modifier *belongs to* an Item. The **transactional edges** are the relationships born of operation: an Order *occupies* a Table, a Line *references* an Item, a Payment *settles* an Order, a Sale *deducts* Stock, a Sale *earns* Loyalty for a Customer, a Ticket *derives from* an Order and *routes to* Stations. The **supply edges** connect the restaurant to its supply side: a Purchase Order *is placed with* a Supplier, a Goods Receipt *increases* Stock, a Transfer *moves* Stock between Locations. And the **network edges** — the ones that make the graph two-sided and, per the Constitution, most valuable — connect restaurants to each other and to the other side of the market: many Locations *aggregate demand to* a Supplier, a Location *borrows from* a Lender against its cash-flow, Locations *benchmark against* each other through the Intelligence that spans them.

It is the network edges that make the whole graph worth more than the sum of its restaurants. A single restaurant's sub-graph is a diary; the edges *between* restaurants — the benchmarks that compare them, the aggregated demand that gives them collective buying power, the credit models that learn from all of them — are what turn a hundred thousand diaries into a map of an economy. These cross-restaurant edges cannot exist for a competitor with a few restaurants, because they require the population, and they are the structural reason the graph compounds (Company Constitution, Part 2).

## The relationships that carry meaning

Beyond structure, the edges carry the *meaning* that makes the graph intelligent. The edge from a Sale to the Stock it deducted, multiplied across a year, *is* the food-cost truth. The edge from Payments to the cash-flow they constitute, watched over time, *is* the underwriting model. The edges from many Locations' demand to a Supplier *are* the buying power. The edges from a Customer's Sales across visits *are* the relationship that loyalty and marketing act on. The graph is not a static structure; it is a living record in which the *patterns of edges over time* are the knowledge — and this is why time (Part 9) and events (Part 5) are inseparable from the graph: the graph is the accumulation of events (each a new edge or a change to a node) over time, and its value is precisely that it is longitudinal, that it holds not just the current structure but the whole history of how the structure came to be.

## The ownership rules

The graph has one law of ownership, inherited from RFC-000 and made concrete here: **every node and every fact has exactly one owning context (Part 7), which is the single source of its truth; every other context that needs it references it by identity and learns of its changes through events; and no context ever holds or mutates another context's truth.** An Order is owned by Operations; Payments references it by identity to settle it but never rewrites its lines; Intelligence references it to learn from it but never asserts a new fact about it. This is what keeps the graph coherent at a hundred thousand restaurants: not one system that knows everything, but many contexts each owning their region of the truth absolutely, reconciled through events into one connected whole. A fact with two owners is a fact with no truth; a fact with one owner and many subscribers is a fact the whole graph can trust.

And the graph obeys one law of ownership *at the edge of the company*: **the ground truth belongs to the graph, and through the graph, in trust, to the restaurants whose reality it is.** We hold the truth of a hundred thousand restaurants because they let us (Company Constitution, Part 2.8), and the graph's ownership rules include the customer's and the operator's rights over their own data — their right to it, their consent to its use, their right to its erasure — because the graph is a thing our customers *let us hold*, and an ownership model that forgot whose reality it ultimately is would forfeit the trust that is the graph's precondition.

## The graph as the thing we build

Assembled, the Operating Graph is this: a hundred thousand thick, connected sub-graphs — one per restaurant, each the complete operational reality of that restaurant as nodes and edges — woven together by the network edges of benchmarking, demand-aggregation, and shared learning, accumulated as events over years so that it holds not just what is but everything that was, owned context by context so that every fact has one truth, and held in trust for the restaurants whose reality it is. It is the map of the restaurant economy, and it is the only thing about Mezze that no competitor can buy or copy, because it is accumulated time across a live network, and time is the one input that capital cannot compress.

Every entity in Part 2 is a node in this graph. Every value in Part 3 measures or describes those nodes. Every aggregate in Part 4 is a cluster of nodes kept consistent together. Every event in Part 5 is a change to the graph — a node born, an edge formed, a fact recorded. Every invariant in Part 6 is a law the graph obeys. Every context in Part 7 owns a region of the graph. Every identity in Part 8 is a node's or an actor's true name. Every kind of time in Part 9 is a dimension along which the graph is measured and ordered. **This RFC is the description of the graph, and the graph is the company.** To speak this ontology precisely is to describe reality precisely; to build software faithful to it is to capture reality faithfully; and to capture reality faithfully, losslessly, immutably, and in trust, across a hundred thousand restaurants over the years — that is to build the one asset that lasts.

---

## Closing

This is the canonical language of Mezze. Every engineer, designer, product manager, analyst, AI model, integration partner, and support engineer speaks it, and speaks it the same, because a company that shares one precise language for its domain can build that domain coherently across every team and every decade, and a company that does not builds confusion with great effort. When two people at Mezze use different words for the same thing, this RFC is consulted and one of them is corrected — and if this RFC itself is found to name the same thing two ways, or to leave a real thing unnamed, it is amended under RFC-000's evolution rules, because the language of reality must stay faithful to reality as we come to understand it more deeply.

The software will be rewritten many times before 2050. This ontology will not, because it describes not our software but the restaurant world our software serves — and the restaurant world, in its essentials, does not change when our code does. A guest will still be a guest, an order still a commitment, a payment still real money that really moved, a recipe still the truth of how a dish is made, and the graph still the accumulated, connected, longitudinal truth of it all. Build every system to reflect this reality faithfully, and the systems may come and go while the truth they captured endures — which is the whole point, because the truth is the asset, and this document is its description.

*Speak this language. Model this reality. Build the graph.*

*The restaurant is the truth. The graph is the record. Everything else is implementation.*
