# RFC-002 — The Operating Graph

**Status:** Canonical · **Supersedes:** nothing · **Descends from:** RFC-000 (Engineering Constitution), RFC-001 (Restaurant Ontology) · **Amends:** nothing · **Author:** Chief Systems Architect · **Horizon:** 20 years

> RFC-000 gave Mezze its laws. RFC-001 gave Mezze its language. RFC-002 gives Mezze its **shape**. This is the description of the one structure into which every API, every event, every model, every payment, every report, and every integration ultimately resolves. It is the heart of the company, and it is not a piece of software.

---

## Preamble — What this document is, and what it forbids itself

The Operating Graph is the canonical model of the restaurant economy as it actually is. It is not a database. It is not a graph database. It is not storage, not a schema, not a product, not an implementation. It is the **shape of reality** — the restaurants, the people, the food, the money, the time, and the relationships between them — described so precisely that any competent system, in any decade, built on any technology, could be checked against it and found either faithful or wrong.

This distinction is the entire point, so it is stated as a law before anything else:

> **Reality exists. Software observes it. The graph is the canonical model of that reality — and reality is the authority, never the model, and never the software.**

Because of this, RFC-002 obeys a vow of abstinence. It will not name a storage engine, a query language, a framework, a protocol, a vendor, a data structure, or a physical mechanism of any kind. Not because those things do not matter — they matter enormously — but because they are **replaceable**, and this document must outlive every one of them. If in 2045 Mezze has rewritten its systems four times, changed its programming languages twice, and replaced its entire data infrastructure, this document must still be true, word for word. The only way to guarantee that is to describe reality and refuse to describe the machine.

Everything technological is deferred to documents that descend from this one — implementation RFCs, which are mortal by design. RFC-002 is not mortal. It is the specification of the terrain; the implementations are maps drawn of it, and maps are redrawn while the terrain stays.

A reader looking for how anything is *built* will not find it here and should not. A reader looking for what is *true* — what a node is, what it means for an order to exist, what history is, why a deleted restaurant is still real, why the graph cannot be bought — will find all of it, and will find it stated the same way in twenty years.

---

# PART 1 — FIRST PRINCIPLES

Before cataloguing the graph, we must agree on what the graph is *made of*. These are the eleven primitives. Every later part is built from them, and every engineer, analyst, and executive at Mezze must hold the same meaning for each, forever. If two people mean different things by "truth" or "node," they are building two different companies.

## 1.1 What is a Node?

A **node** is a thing in the restaurant economy that has an identity of its own and persists through change.

The test for nodehood is not "is it important" or "is it stored somewhere." The test is: **does it remain the same thing while its attributes change, and can other things refer to it across time?** A restaurant is a node: it renovates, renames, changes owners, changes menus — and remains the same restaurant, referred to by the same identity through all of it. A specific guest is a node: they visit a hundred times over five years, and every visit refers to the same person. An order is a node: it opens, grows, is paid, is closed, and can be referred to forever after as *that order*.

A node is not its current state. A restaurant that is "open today, closed tomorrow" is one node with a changing condition, not two nodes. This is the difference between an entity and a snapshot. **The node is the identity; the state is what is true of it right now.** Confusing the two is the most common and most corrupting error a system can make, because it destroys history the moment state changes.

Nodes correspond, one-to-one, to the entities catalogued in RFC-001. RFC-001 named forty of them. RFC-002 does not add or remove any — it would be a violation of this document's mandate to redefine the ontology. What RFC-002 does is describe each entity *as a node in the graph*: what refers to it, what it refers to, who owns it, how it lives and dies, and how it grows.

Some things that feel important are **not** nodes, and the discipline to recognize this matters as much as recognizing nodehood. A price is not a node — it is a *value* that a menu item *has* at a location for a period; it has no identity of its own and nothing refers to "that price" independently. A quantity is not a node. An address is not a node. These are **value objects** (RFC-001, Part 3): they describe nodes, they travel with nodes, but they do not stand alone and nothing points at them. The line between node and value object is the line between "a thing" and "a description of a thing," and the graph keeps it sharp.

## 1.2 What is an Edge?

An **edge** is a relationship between two nodes that is itself real.

The word "itself real" is load-bearing. An edge is not a convenience of description, not a foreign reference bolted on for lookup. It is a fact about the world that is as true as the nodes it joins. *This employee works at this location.* *This order contains this menu item.* *This payment settles this order.* *This supplier supplies this ingredient.* Each of these is a fact you could verify by standing in the restaurant, and each exists independently of any system that records it.

Every edge has:

- A **direction** — relationships are rarely symmetric. A restaurant *owns* a location; the location does not own the restaurant. An order *contains* a menu item; the menu item does not contain the order. Direction encodes which node is the subject and which is the object of the relationship, and getting it backward inverts meaning.
- A **type** — the *kind* of relationship. OWNS, WORKS_AT, CONTAINS, USES, SUPPLIES, PLACED, SETTLES, OPERATES, STORED_AT, PREDICTS, COMPARES, and the others catalogued in Part 3. The type is the verb of the sentence the edge asserts.
- A **temporal character** — some edges are true forever once true (an order *was placed by* a customer — permanent), some are true for a bounded interval (an employee *works at* a location — until they leave), and some are true only at an instant (a payment *settled* an order — at the moment of settlement). Part 1.7 develops this; it is one of the deepest properties of an edge and the one systems most often get wrong.

An edge is **not** a node. It joins nodes; it does not have its own web of relationships to third things. When a relationship *does* start to accumulate its own attributes, its own lifecycle, its own references — when you find yourself wanting to point *at the relationship* — that is the signal that the relationship has become a node in its own right. An order line is the clearest example: "this order contains this menu item" sounds like an edge, but the moment it carries a quantity, a price at time of sale, modifiers, a preparation state, and a place in the kitchen queue, it has become a node (the Order Line) that *connects to* both the order and the menu item. The graph promotes relationships to nodes exactly when reality gives them a life of their own, and not before.

## 1.3 What is Ownership?

**Ownership** is the answer to the question: *which node is responsible for this node's existence and truth?*

Every node in the graph belongs to exactly one owning node — its **root of responsibility**. Ownership is not about permission or possession in the legal sense; it is about **consistency authority**. The owner is the node through which this node changes, the node whose existence justifies this node's existence, and the node whose disappearance determines this node's fate.

An order line is owned by its order. A payment is owned by the order it settles — or, more precisely, it belongs to the order's consistency boundary. A location is owned by the restaurant. A shift is owned by the location. The chain of ownership always terminates at a small number of **root nodes** — the restaurant, the guest, the supplier — nodes that own themselves and answer to nothing above them within the graph.

Ownership matters because it defines **where a change is allowed to originate and what must stay consistent together**. You do not modify an order line by reaching into it directly; you modify it *through its order*, because the order is responsible for keeping all its lines consistent with each other and with itself (the total must equal the sum of the lines — RFC-001 invariant). This is the aggregate principle from RFC-001, Part 4, seen from the graph's side: **an aggregate is a node and everything it owns, changed only through the owning root.**

Ownership is singular and non-overlapping. A node with two owners is a contradiction, because two owners means two authorities means no authority. When reality seems to present shared ownership — a menu item that belongs to a brand but is served at many locations — the resolution is always that one relationship is *ownership* (the brand owns the menu item's definition) and the others are *references* (locations refer to it, may override its price, but do not own it). Untangling ownership from reference is one of the central acts of modeling the graph correctly.

## 1.4 What is Truth?

**Truth** in the graph is what actually happened in the restaurant — no more, no less.

This is the most important principle in the document, so it is stated with maximum severity:

> **The graph records what happened. It does not record what someone wishes had happened, what a system assumed, what a model predicted, or what would be convenient. A fact enters the graph because it occurred in reality, and once it occurred it is true forever.**

Truth has three properties that together define it and separate it from everything that merely resembles it:

**Truth is observed, not decided.** A sale is true because a guest bought food, not because someone typed it. The typing is an *observation* of the truth (Part 1.5); the truth is the transaction in the world. When observation and reality disagree, reality wins and the observation was an error to be corrected — never the other way around.

**Truth is durable.** What was true stays true. An order that was paid was paid; no later event un-happens it. If money is returned, that is a *new* truth (a refund occurred) layered on top of the old one (a payment occurred) — both are true, in sequence. The graph never edits the past into a different past. This is RFC-001's invariant "a paid order cannot become unpaid," generalized: **no truth is ever deleted or altered; truths only accumulate.**

**Truth is distinguishable from derivation.** A great deal of what the graph is *used* for is not truth but *derived from* truth: this recipe is unprofitable, this supplier causes waste, these restaurants behave alike, this guest is becoming loyal. None of these are things that "happened." They are conclusions drawn from things that happened. They are enormously valuable — they are most of the graph's economic output — but **they are never truth, and the graph must never let a derivation harden into a fact.** Part 8 is devoted entirely to this boundary. Here it is enough to plant the flag: truth is what occurred; everything else, however useful, is interpretation, and interpretation is disposable while truth is permanent.

## 1.5 What is Observation?

**Observation** is the act by which a truth in the world becomes a fact in the graph.

The restaurant is real whether or not anyone records it. Food is cooked, money changes hands, staff arrive and leave — all of this happens in the physical world, continuously, as reality. Observation is the moment a system *notices* one of these happenings and writes it down. The written-down fact is not the truth itself; it is a **record of** the truth, and the quality of the graph depends entirely on the fidelity of observation.

Three things follow, and each is a discipline the company must keep:

**Observation can be imperfect, and the graph must know it.** A cook forgets to mark a dish ready; a guest pays cash that is under-rung; a network drops a transaction. Reality happened correctly; the observation was lossy. A faithful graph distinguishes "this did not happen" from "we did not observe this happening" — the two are completely different, and collapsing them is how systems lie by omission. **Losslessness of observation is therefore not a technical nicety; it is the first duty of any system that feeds the graph.** A transaction that occurs must be captured — this is why the North Star names "never lose a transaction" as graph integrity, not hygiene.

**Observation has a moment, and that moment is itself a fact.** *When* something was observed can differ from *when* it occurred — an order taken offline and recorded an hour later occurred at the table but was observed later. The graph records both times because both are true, and confusing them corrupts every time-based conclusion (Part 1.7, Part 9).

**Observation is one-directional.** The world informs the graph; the graph does not inform the world. When the graph says a dish is 86'd, that is a *record* that the kitchen ran out — it does not *cause* the kitchen to run out. Systems that forget this — that treat the record as the reality and start "correcting" the restaurant to match the database — have inverted the whole relationship and will destroy trust. The restaurant is the truth; the graph is the record; the record serves the restaurant and never rules it.

## 1.6 What is Projection?

A **projection** is a view of the graph shaped for a particular use — and it is disposable.

The graph itself is vast, permanent, and use-agnostic: it holds everything that ever happened, related to everything else, without regard for who is looking. But no one uses "everything." A line cook needs the small, urgent slice about *what to cook next*. An owner needs the slow, wide slice about *how the business is doing this month*. A lender needs the slice about *cash flow over years*. A supplier needs the slice about *what will be ordered next week*. Each of these is a **projection**: the same underlying truth, filtered, arranged, and summarized into the shape that one audience needs.

The defining property of a projection, stated as a law:

> **Every projection is disposable. The graph is permanent. Any projection can be thrown away and rebuilt from the graph, because it contains no truth of its own — only a rearrangement of truth that lives in the graph.**

This is liberating and it is strict. It means the company can build, discard, and reinvent views freely — a new report, a new dashboard, a new AI lens — without any fear, because none of them are load-bearing for truth; the truth is safe in the graph. And it means the reverse is forbidden: **a projection must never become the only place a fact lives.** The moment a view holds a truth that the graph does not, the view has stopped being a projection and become an unauthorized second source of truth — a corruption. Part 6 catalogues the standard projections; every one of them obeys this law.

## 1.7 What is History?

**History** is the graph's memory — the complete, ordered, permanent record of everything that ever became true.

The graph is not a picture of *now*. It is the accumulation of *all nows*. Every state a node ever held, every edge that ever existed, every event that ever occurred — all of it is retained, in order, forever. "The current state" is merely the latest layer of history, computed by reading all of history forward; it is an output, not the substance.

History has properties that make it the graph's most valuable and most protected quality:

**History is append-only.** New truth is added; old truth is never removed or rewritten. To "change" the past is a contradiction; what actually happens is that a *new* truth is recorded that supersedes the old one *going forward*, while the old one remains, still true of the moment it described. A price was $10 last year and is $12 now — both are permanently true, each of its own time. RFC-001's append-only audit invariants are this principle enforced.

**History is ordered.** Truths happen in a sequence, and the sequence is itself a fact. That an order was opened *before* it was paid, that a shift started *before* a sale rang, that a refund followed *after* a payment — these orderings carry meaning, and the graph preserves them. Without order, causation is unknowable and the graph degrades into a bag of disconnected facts.

**History is why the graph compounds.** A competitor can copy the present — take a photograph of every restaurant today. No one can copy the past, because the past is *elapsed time*, and elapsed time cannot be manufactured. The graph's decade of history is the one asset (North Star) that capital cannot buy, precisely because history is made only of time that has actually passed. Every day the graph runs, its history deepens by one day that no rival can ever go back and acquire. Part 10 develops this into the full asset thesis; here it is the seventh first principle: **history is not old data, it is accumulated time, and accumulated time is the moat.**

## 1.8 What is Identity?

**Identity** is what makes a node *itself* — the property that stays constant while everything else about the node changes, and that lets the world refer to it across time and across distance.

Identity is not a name (names change and repeat), not an address (addresses change and are shared), not any attribute (attributes are exactly the things that vary). Identity is the bare fact of *being this one and not another* — the thing that lets us say a restaurant is the same restaurant after it renames, that a guest is the same guest on their fiftieth visit, that an order recorded on a phone with no signal is the same order when it later rejoins the network.

The graph's identity model, developed fully in RFC-001 Part 8 and carried here without change, rests on properties the restaurant world actually demands:

**Identity is global.** Two nodes anywhere in the graph — across a hundred thousand restaurants — never accidentally share an identity. Sameness of identity always means sameness of thing.

**Identity is born at the edge.** A restaurant on the far side of a network outage must be able to create a new order, a new guest, a new payment — real nodes with real identities — while completely disconnected, and those identities must be guaranteed not to collide with any other identity created anywhere else in the world at the same moment. The restaurant does not stop being real when the network stops; therefore identity cannot depend on any central authority being reachable. This is non-negotiable in a world where restaurants operate through outages, and it shapes the entire model.

**Identity survives merges.** Sometimes the world reveals that two nodes we thought were different are the same — the same guest recorded twice, two supplier records for one supplier. When this happens, the graph **merges** them, and the merge is itself a recorded, reversible event (Part 5): the two identities are joined, the history of both is preserved and unified, and the fact that they were once separate is never lost. Merging is a truth, not an erasure.

**Identity resolves conflict by rule, not by accident.** When two disconnected observations of the same node disagree — the offline table and the online record both changed the same order — the graph does not silently let the last one win. It resolves the conflict by a *rule* grounded in the meaning of the nodes (Part 5), and it records that a conflict occurred. Truth is too important to be decided by timing.

## 1.9 What is Time?

**Time** in the graph is not one thing. It is several distinct kinds of time, each real, each different, and each catastrophic to confuse with the others.

RFC-001 Part 9 named them; RFC-002 adopts them as graph primitives because *nearly every question asked of the graph is a question about time*, and a number attached to the wrong kind of time is a wrong number wearing a right one's clothes.

- **Wall-clock time** — the ordinary time of the world, when a thing occurred in the physical day. When the guest actually paid.
- **Event time** — the time a truth *belongs to*, which may differ from when it was observed. An offline order occurred at the table at 8pm even though it was recorded at 9pm; its event time is 8pm.
- **Business-day time** — the restaurant's *operating* day, which is not the calendar day. A bar's business day may run until 4am; a sale at 2am belongs to the *previous* business day even though the calendar has ticked over. Revenue, shifts, and reconciliation are counted in business-day time, and counting them in calendar time produces confident nonsense.
- **Kitchen time** — *elapsed* time, the time of preparation and waiting. How long since this ticket fired, how long this guest has waited. Kitchen time is measured in durations from a start, not in clock positions.
- **Accounting time** — the time a truth is *recognized* for financial purposes, which may be a period (a month, a quarter) rather than an instant, and which may lag the event by design. When a sale *counts* on the books.

The graph holds all of these because all of them are true, and it never silently converts one into another. **Every time-bearing fact in the graph knows which kind of time it carries**, and every question asked of the graph must state which kind of time it means. This discipline is the difference between analytics that can be trusted with a loan decision and analytics that merely look precise.

## 1.10 What is Trust?

**Trust** is the graph's measure of *how much a given fact deserves to be relied upon* — and it is a property the graph tracks explicitly, never assumes.

Not all facts in the graph are equally certain. A sale confirmed by a completed payment is bedrock. A quantity of inventory counted by hand three weeks ago is softer. A supplier's stated lead time is a claim, not an observation. A forecast is not a fact at all. The graph does not flatten these into a single undifferentiated "data"; it carries, with each fact, an understanding of **where it came from and how much weight it can bear**.

Trust derives from provenance — *how the fact was observed*:

- Facts **observed directly** at the point of truth (a payment that settled, an item that rang) carry the highest trust.
- Facts **asserted by a party** (a supplier's promised price, a manager's manual count) carry the trust of that party and are subject to being contradicted by direct observation.
- Facts **derived** from other facts (a computed food cost, an inferred table turn) carry only as much trust as their weakest input and their method, and are always re-derivable, never authoritative.
- Facts **predicted** (a forecast, a risk score) carry no truth-trust at all — they are explicitly marked as not-yet-real and are forbidden from ever being relied upon as though they occurred (Part 1.4, Part 8).

Trust is directional in the sense that **direct observation outranks assertion, assertion outranks derivation, and nothing outranks reality.** When facts conflict, the graph prefers the more trusted provenance, records that a conflict existed, and never lets a low-trust fact silently overwrite a high-trust one. Trust is how the graph stays honest about its own certainty — and honesty about certainty is what lets the graph underwrite loans, benchmark peers, and advise decisions without lying.

## 1.11 What is Authority?

**Authority** is the answer to: *who is allowed to assert a given fact into the graph, and whose assertion the graph accepts.*

Truth is observed, but observation is done by *someone* — a system acting on behalf of a restaurant, an employee, a payment processor, a supplier, a regulator. Authority is the graph's understanding of **which party is entitled to speak about which nodes**. A restaurant is authoritative about its own menu, its own prices, its own staff. A payment processor is authoritative about whether a payment cleared. A regulator is authoritative about a compliance status. A guest is authoritative about their own contact details and consent. No party is authoritative about everything, and the graph never lets a party assert facts outside its authority.

Authority is bounded by **ownership** (Part 1.3): the party that owns a node is, by default, the party authoritative over it. A restaurant owns its locations and is authoritative over them; it is *not* authoritative over what a peer restaurant does, over what a benchmark concludes, or over whether its own loan was approved — those belong to other authorities. This is why one restaurant can never see or alter another's truth (a governance law, Part 9): authority does not cross ownership boundaries.

Authority also governs **the cross-restaurant layer**, and here it is subtle. Individual restaurants are authoritative over their own facts. But *aggregate* truths — the benchmark that says "you overpay for tomatoes relative to your peers," the demand pool that clears procurement — are authored by **Mezze as the steward of the graph**, derived from many restaurants' facts under strict rules that never expose any one restaurant's private truth to another (Part 8, Part 9). Authority over the aggregate belongs to the steward; authority over the particular belongs to each restaurant; and the two never leak into each other. Getting this boundary exactly right is what makes the graph both *trustworthy to each restaurant* (no one sees my books) and *valuable to all* (everyone benefits from the pattern) — the balance on which the entire asset rests.

---

*These eleven principles — node, edge, ownership, truth, observation, projection, history, identity, time, trust, authority — are the alphabet of the graph. Everything that follows is written in them. If a later part ever seems to contradict one of them, the principle wins and the later part is in error, because the principles are the description of reality and reality does not bend to convenience.*

---

# PART 2 — NODE CATALOG

Every entity in RFC-001 is a node in the graph. This catalogue describes all forty, each along twelve dimensions:

- **Purpose** — what this node *is* in the restaurant world, in one breath.
- **Identity** — what makes it itself and lets the world refer to it across time.
- **Owner** — the root of responsibility through which it changes (Part 1.3).
- **Lifecycle** — the states it moves through from birth to rest.
- **Visibility** — who is authoritative to see it, and where its truth may and may not travel.
- **Relationships** — the principal edges it participates in (detailed in Part 3).
- **Authority** — who may assert facts about it (Part 1.11).
- **Versioning** — how change accumulates on it without destroying its past (Part 1.7).
- **Deletion Policy** — what happens when the world says it is gone. In almost every case the answer is the same and it is stated as a standing law below.
- **Expected Growth** — how the count and depth of this node scales as the graph grows, so the company knows which nodes are rare and which are oceanic.
- **Examples** — concrete instances.

Two standing laws govern the whole catalogue and are stated once here rather than forty times:

> **Standing Deletion Law.** No node is ever destroyed. A node that leaves the world is *retired* — marked as no longer active, from a stated moment — and its identity, its history, and every edge it ever participated in remain permanently in the graph. A closed restaurant, a departed employee, a discontinued dish, a deleted guest (by their own right to erasure) — each is *retired*, and retirement is a new truth layered on top, never an erasure of the old ones. The sole and narrow exception is legally-mandated erasure of a specific person's private data (Part 9), which removes the person's private attributes while preserving the skeletal, anonymized fact that a node existed — because the orders they placed still happened and the restaurant's truth must not be falsified by their departure.

> **Standing Versioning Law.** Every node accumulates change as history, never as overwrite. "The current version" of any node is the latest layer of its history, computed by reading its changes in order (Part 1.7). Any past version of any node is always recoverable, because no past version is ever discarded.

The catalogue proceeds in eight families: the organizational spine, the internal people, the external people, the menu and product, the ordering core, the money, the supply and inventory, and the intelligence and governance nodes.

---

## Family A — The Organizational Spine

### Node 1 — Restaurant (Business)

- **Purpose.** The sovereign economic actor: the business that operates one or more locations under one ownership, whose truth the graph exists to record. This is a root node — it owns itself and answers to nothing above it inside the graph.
- **Identity.** A globally unique identity assigned at first registration, permanent through every rename, sale, rebrand, and reorganization. The restaurant is the same restaurant after new owners buy it; the identity carries the history across the transfer.
- **Owner.** Itself (root of responsibility). It is the top of an ownership chain that descends to locations, shifts, stations, orders, and nearly everything operational.
- **Lifecycle.** Prospective → Registered → Active → (Suspended ↔ Active) → Retired. A restaurant may be suspended (temporarily non-operating) and revived; retirement (permanent closure) is a recorded truth that never deletes the node.
- **Visibility.** A restaurant sees its own full truth and *never* another restaurant's. It sees the *aggregate* truths derived across restaurants (benchmarks) but never the particulars behind them (Part 1.11, Part 9). This boundary is absolute.
- **Relationships.** OWNS locations; OWNS (or licenses) brands; EMPLOYS employees; PLACES purchase orders (through locations); IS_COMPARED_BY benchmarks; QUALIFIES_FOR financing (derived).
- **Authority.** Authoritative over everything within its ownership. Not authoritative over aggregates, over peers, or over externally-adjudicated facts (a loan approval, a compliance status).
- **Versioning.** Every change to its profile, ownership, and structure is a dated layer. The transfer of ownership is a first-class historical event, not a silent field change.
- **Deletion Policy.** Standing Deletion Law: retired, never destroyed. A decade later, "the restaurant that used to be here" is still a real, queryable node with a complete history — this is essential for longitudinal truth and for the asset (Part 10).
- **Expected Growth.** Linear in customers won; the *rarest* node relative to activity. Tens of thousands, then hundreds of thousands. Each one is a "node" in the North Star's density sense — the count of restaurants *is* the graph's density dimension.
- **Examples.** A single-location shawarma shop in Cairo; a twelve-branch coffee chain in Riyadh; a cloud-kitchen operator running eight brands from three locations.

### Node 2 — Brand

- **Purpose.** A market-facing identity under which food is sold — the name, concept, and menu a guest experiences — which may or may not correspond one-to-one with the business that owns it. One restaurant may operate several brands; one brand may (in franchising) span many restaurants.
- **Identity.** A globally unique identity, distinct from both the restaurant that owns it and the locations that serve it. This separation is what lets a cloud kitchen run five brands from one location, and lets a franchise brand exist above many franchisee restaurants.
- **Owner.** The restaurant (or franchisor) that owns the brand's *definition*. Locations that serve the brand *reference* it; they do not own it (Part 1.3 — ownership vs reference).
- **Lifecycle.** Conceived → Launched → Active → (Paused ↔ Active) → Retired.
- **Visibility.** Visible to its owning restaurant and to the locations licensed to serve it. A franchise brand's *standards* are visible to franchisees; each franchisee's *operating truth* remains private to that franchisee.
- **Relationships.** OWNED_BY restaurant; DEFINES menus; SERVED_AT locations; COMPARED_BY benchmarks (brand-level).
- **Authority.** The owner is authoritative over the brand's definition, standards, and canonical menu. Franchisees are authoritative over their own execution of it.
- **Versioning.** Brand identity, positioning, and canonical menu evolve as dated layers; a rebrand is history, not erasure.
- **Deletion Policy.** Retired, never destroyed — a discontinued brand's past sales remain forever attributable to it.
- **Expected Growth.** Slightly more numerous than restaurants (multi-brand operators), still rare relative to activity.
- **Examples.** "Beit Zaman" grill concept; a virtual "Midnight Wings" delivery-only brand; a regional franchise brand with forty franchisees.

### Node 3 — Location

- **Purpose.** A physical (or virtual, for delivery-only) place where the restaurant operates — where food is made, guests are served, staff work, stock is held, and money is taken. The location is where most operational truth is *generated*.
- **Identity.** A globally unique identity, permanent through renovation, renaming, and re-fit. A location that closes and reopens under the same roof with the same operation is the same location; a genuinely new site is a new location.
- **Owner.** The restaurant.
- **Lifecycle.** Planned → Opening → Active → (Temporarily-Closed ↔ Active) → Permanently-Closed (Retired).
- **Visibility.** Visible within its owning restaurant. Its aggregate behavior contributes to benchmarks; its particulars never leave the restaurant.
- **Relationships.** OWNED_BY restaurant; SERVES brand(s); HOSTS shifts, stations, tables, cash sessions; STORES stock; ORIGINATES orders; PLACES purchase orders; RECEIVES inventory (fulfilment priority — Part 7).
- **Authority.** Authoritative over its own operating facts. Prices, menu availability, and staffing at the location are asserted by the location (within brand standards).
- **Versioning.** Operating hours, layout, capacity, and served brands change as dated layers.
- **Deletion Policy.** Retired, never destroyed. A closed location's years of sales, costs, and staffing remain the historical bedrock of the restaurant's trend and the region's benchmark.
- **Expected Growth.** A small multiple of restaurants (average locations-per-restaurant). Grows with chain expansion; still counted in the same order of magnitude as restaurants.
- **Examples.** The Maadi branch of a coffee chain; a ghost-kitchen bay serving three brands; a seasonal beach-front outlet open only in summer.

### Node 4 — Device / Terminal

- **Purpose.** A point through which observation enters the graph — a station where staff ring orders, take payment, and record operational events. The device is the *instrument of observation* (Part 1.5); it is not itself a source of truth, but the conduit through which a location's truth is captured.
- **Identity.** A globally unique identity per device, so that every observation can be traced to the instrument that captured it — essential for reconciliation, audit, and trust (Part 1.10, Part 1.11).
- **Owner.** The location it operates in.
- **Lifecycle.** Provisioned → Active → (Offline ↔ Active) → Decommissioned (Retired). Crucially, a device in the *Offline* state is still fully real and still generating true observations that will rejoin the graph when connectivity returns (Part 1.8 — identity born at the edge).
- **Visibility.** Visible within its location. Which device captured a fact is part of that fact's provenance and never leaves the restaurant except as anonymized aggregate.
- **Relationships.** OPERATES_IN location; CAPTURES orders, payments, events; OPERATED_BY employees (through shifts and cash sessions).
- **Authority.** Not authoritative over any business fact; it is the *carrier* of observations authored by employees and processes. Its own health/status (online, offline) it is authoritative over.
- **Versioning.** Configuration and assignment change as dated layers.
- **Deletion Policy.** Retired, never destroyed — every past observation remains attributed to the device that captured it.
- **Expected Growth.** A multiple of locations (several devices per location). Numerous, but bounded by physical footprint — not oceanic.
- **Examples.** A front-counter terminal; a handheld used for table-side ordering; a kitchen display that captures ready-events; a self-order kiosk.

---

## Family B — The Internal People

### Node 5 — Employee

- **Purpose.** A person who works for the restaurant — the human whose labor turns ingredients into service. The employee is the actor behind an enormous share of the graph's observations: they ring the orders, cook the tickets, take the cash, count the stock.
- **Identity.** A globally unique identity for the *person*, permanent across role changes, transfers between locations, departures, and returns. An employee who leaves and is rehired is the same person; a manager promoted from server is the same person. Identity tracks the human, not the job.
- **Owner.** The restaurant (the employing business), with working assignment to locations.
- **Lifecycle.** Candidate → Hired → Active → (On-Leave ↔ Active) → Departed (Retired). A departed employee is retired, never destroyed — their historical shifts, sales, and actions remain permanently attributed.
- **Visibility.** Visible within the employing restaurant. An employee's identity and actions never leak to other restaurants; aggregate labor patterns contribute to benchmarks without exposing individuals.
- **Relationships.** EMPLOYED_BY restaurant; WORKS_AT location(s); HOLDS role(s); WORKS shifts; OPERATES stations and cash sessions; AUTHORS operational events (rang this order, voided this line, approved this discount).
- **Authority.** Authoritative over the actions they personally take, bounded by their role's permissions (Part 1.11). An action attributed to an employee is a claim that *this person did this thing* — a claim of the highest audit importance (RFC-001 audit invariants).
- **Versioning.** Roles, pay, location assignments, and status change as dated layers; each promotion or transfer is history.
- **Deletion Policy.** Retired, never destroyed — subject only to lawful erasure of private personal attributes (Standing Deletion Law exception), which preserves the anonymized fact that *an employee* performed past actions so the restaurant's audit trail stays intact.
- **Expected Growth.** A large multiple of locations (staff per location, plus turnover accumulating retired employees over time). One of the faster-growing person-nodes because turnover means the *historical* count climbs continuously even when headcount is flat.
- **Examples.** A line cook; a shift manager; a cashier who worked one summer three years ago and is now retired-in-graph but historically present.

### Node 6 — Role

- **Purpose.** A named bundle of responsibilities and permissions — what a *kind* of worker is allowed to do and expected to do. The role is the bridge between a person and their authority (Part 1.11): an employee's permissions come from the roles they hold, not from the person directly.
- **Identity.** A globally unique identity per role definition within its owning scope. "Shift Manager" at one restaurant is a different role-node from "Shift Manager" at another, because each restaurant defines its own responsibilities.
- **Owner.** The restaurant (or brand, for franchise-standard roles).
- **Lifecycle.** Defined → Active → (Revised) → Retired.
- **Visibility.** Visible within its owning restaurant.
- **Relationships.** DEFINED_BY restaurant/brand; HELD_BY employees; GRANTS permissions (the basis of authority checks).
- **Authority.** The owner defines the role. The role, in turn, is the *source* of employees' authority to assert certain facts (approve a discount, void a sale, open a drawer).
- **Versioning.** Permission sets and responsibilities change as dated layers — a change to what "Manager" may do is history, so that a past action can always be judged against the permissions that were in force *at the time* (Part 1.7, Part 9).
- **Deletion Policy.** Retired, never destroyed — past actions taken under a now-retired role remain judgeable against it.
- **Expected Growth.** Small and slow — a handful per restaurant. One of the least numerous nodes.
- **Examples.** Owner; General Manager; Shift Lead; Cashier; Line Cook; Server; Delivery Runner.

### Node 7 — Shift

- **Purpose.** A bounded interval during which the restaurant operates and specific people work — the unit of *operating time* that ties labor, sales, and cash together. The shift is where business-day time (Part 1.9) is made concrete: a shift belongs to a business day, and the business day is defined by its shifts, not by the calendar.
- **Identity.** A globally unique identity per shift instance.
- **Owner.** The location.
- **Lifecycle.** Scheduled → Opened → Active → Closed → Reconciled. A closed shift is *settled truth*; its sales, labor, and cash are counted and cannot be un-happened.
- **Visibility.** Visible within the location and restaurant.
- **Relationships.** BELONGS_TO location; STAFFED_BY employees; OPERATES stations; CONTAINS cash sessions; ATTRIBUTES orders and sales to a business day; BOUNDS labor cost.
- **Authority.** The location and its managers are authoritative over the shift's opening, closing, and reconciliation.
- **Versioning.** Staffing changes within a shift (someone clocks in late, leaves early) are dated layers within the shift's history.
- **Deletion Policy.** Retired, never destroyed — historical shifts are the substance of every labor and staffing-stability analysis (Part 7).
- **Expected Growth.** Oceanic in the slow sense — a few per location per day, accumulating forever. The first node whose *historical* count grows without bound at a steady operational rate.
- **Examples.** The Friday dinner shift; a split morning shift; an overnight shift whose late hours belong to the prior business day.

### Node 8 — Station

- **Purpose.** A functional post within a location where a specific kind of work happens — the grill, the fryer, the bar, the front counter, the expo pass. Stations are how a location's work is *divided*, and how kitchen tickets are routed (Part 4).
- **Identity.** A globally unique identity per station within a location.
- **Owner.** The location.
- **Lifecycle.** Configured → Active → (Idle ↔ Active) → Retired.
- **Visibility.** Visible within the location.
- **Relationships.** BELONGS_TO location; OPERATED_BY shifts/employees; RECEIVES ticket items (routing); PRODUCES prepared items.
- **Authority.** The location is authoritative over its station configuration.
- **Versioning.** Configuration changes as dated layers.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** A small multiple of locations; bounded by physical layout.
- **Examples.** Hot line; cold station; bar; barista station; expediting pass; delivery-dispatch post.

### Node 9 — Cash Session (Drawer Session)

- **Purpose.** A bounded period during which one person is responsible for one cash drawer — opened with a starting float, closed with a count, and reconciled against the sales taken through it. The cash session is the atom of cash accountability: it answers "who was responsible for this money, and did it balance?"
- **Identity.** A globally unique identity per session.
- **Owner.** The location (and, within it, tied to a shift and an employee).
- **Lifecycle.** Opened (float declared) → Active → Closed (counted) → Reconciled (compared to expected). A discrepancy at reconciliation is itself a recorded truth, never silently absorbed (Part 1.4).
- **Visibility.** Visible within the location and restaurant; cash-handling accountability is sensitive and never leaves the restaurant.
- **Relationships.** BELONGS_TO location; WITHIN shift; ASSIGNED_TO employee; ACCUMULATES cash tenders; RECONCILES_TO an expected amount.
- **Authority.** The assigned employee is authoritative over the count they declare; the manager is authoritative over reconciliation and over recording a discrepancy.
- **Versioning.** Pay-ins, pay-outs, and drops within the session are dated layers of its history.
- **Deletion Policy.** Retired, never destroyed — cash sessions are audit bedrock.
- **Expected Growth.** A few per location per day, accumulating forever — oceanic in the slow sense, like shifts.
- **Examples.** The morning cashier's drawer; a manager's banking session; a discrepancy session where the count came up short and the shortfall was recorded as truth.

---

## Family C — The External People

### Node 10 — Guest

- **Purpose.** A person who is *served* by the restaurant — the human who eats. The guest is distinct from the customer (Node 11): the guest experiences the meal; the customer pays for it. Often they are the same person; frequently — a corporate account, a parent ordering for a family, a host paying for a table — they are not, and the graph refuses to confuse them (RFC-001: Guest ≠ Customer).
- **Identity.** A globally unique identity for the *person*, when the person is known. A great many guests are anonymous (a walk-in who pays cash and is never identified), and the graph honestly represents this: an anonymous guest is a real but un-individuated presence, not a fabricated identity. When a guest becomes known — through loyalty, reservation, or repeated recognition — their identity persists across every future visit.
- **Owner.** The guest owns themselves conceptually, but within a restaurant's private view, the *relationship* to the guest is owned by the restaurant. Across restaurants, a guest is never shared without the guest's own consent (Part 9, privacy).
- **Lifecycle.** Anonymous → Recognized → Known → (Dormant ↔ Active) → Erased-on-request. A guest may exercise a right to erasure of private data (Standing Deletion Law exception).
- **Visibility.** A guest's identity and history are visible to the restaurant that knows them and *never* to another restaurant, except as the guest's own consent explicitly permits. This is the strictest visibility boundary in the graph.
- **Relationships.** DINES_AT locations; EXPERIENCES orders; MAY_BE the same person as a customer; MAY_HOLD a loyalty account; MAKES reservations.
- **Authority.** The guest is authoritative over their own identity, contact details, and consent. The restaurant is authoritative over the fact of the visit.
- **Versioning.** Recognition, preferences, and consent state change as dated layers.
- **Deletion Policy.** Retired on dormancy; *erased* only on lawful request, which strips private attributes while preserving the anonymized skeletal fact that a guest was present (so past orders remain true).
- **Expected Growth.** Oceanic — the most numerous person-node by far, growing with every served cover, most of them anonymous, a growing minority known.
- **Examples.** An anonymous lunch walk-in; a regular recognized by name; a birthday guest for whom a host paid; a loyalty member on their sixtieth visit.

### Node 11 — Customer

- **Purpose.** The party *responsible for payment* of an order — who the bill is *to*. Usually a guest, but distinctly the payer role: a company, an event host, a delivery platform acting as intermediary, a parent. The graph keeps Customer separate from Guest because financial responsibility and consumption are different facts with different consequences (invoicing, credit, loyalty attribution).
- **Identity.** A globally unique identity for the paying party. A corporate customer is one identity across all the meals it pays for; a delivery platform is one customer identity across thousands of orders.
- **Owner.** Within a restaurant's view, the restaurant owns the customer relationship; across restaurants the customer is never shared without consent.
- **Lifecycle.** New → Active → (Dormant ↔ Active) → Retired/Erased.
- **Visibility.** Visible to the restaurant that transacts with them; private across restaurants.
- **Relationships.** PLACED orders (the canonical edge: Customer PLACED Order); RESPONSIBLE_FOR invoices; MAY_BE a guest; MAY_HOLD credit terms (for account customers).
- **Authority.** Authoritative over their own billing identity and details; the restaurant is authoritative over the amounts owed.
- **Versioning.** Billing details, terms, and status change as dated layers.
- **Deletion Policy.** Retired/erased under the standing law and its privacy exception.
- **Expected Growth.** Large but smaller than guests — many guests share a customer (a corporate account), and many anonymous guests are also anonymous customers who never individuate.
- **Examples.** A company with a monthly account; a food-delivery platform as intermediary payer; a walk-in who is both guest and customer at once.

### Node 12 — Loyalty Account

- **Purpose.** A standing relationship between a known guest and a restaurant (or brand) that accrues recognition, points, tiers, or benefits over time. The loyalty account is the graph's record of a *relationship deepening* — the substance behind "which guests are becoming loyal" (Part 7).
- **Identity.** A globally unique identity per account, tied to a known guest and to the restaurant/brand that offers the program.
- **Owner.** The restaurant or brand that runs the program owns the account's benefit terms; the guest owns their participation and consent.
- **Lifecycle.** Enrolled → Active → (Dormant ↔ Active) → Closed.
- **Visibility.** Visible to the offering restaurant/brand and to the guest; private across unrelated restaurants.
- **Relationships.** HELD_BY guest; OFFERED_BY restaurant/brand; ACCRUES from orders; CONFERS discounts/benefits; EVIDENCES loyalty trend (derived).
- **Authority.** The restaurant/brand is authoritative over the program's rules and the balance; the guest is authoritative over their participation.
- **Versioning.** Balance, tier, and terms change as dated layers — the *accrual history* is the valuable part, never collapsed to a mere current balance.
- **Deletion Policy.** Retired on closure; private data erasable on request.
- **Expected Growth.** Grows with the known-guest population; a large and strategically central node because it is where guest depth concentrates.
- **Examples.** A points card at a coffee chain; a tiered membership at a fine-dining group; a punch-card equivalent tracked digitally.

### Node 13 — Reservation

- **Purpose.** A *promise* about the future: a commitment that a guest will arrive at a location at a time and be given a table. The reservation is one of the few nodes that is fundamentally *about a time that has not happened yet* — it lives in anticipation and is either fulfilled, honored-late, or broken.
- **Identity.** A globally unique identity per reservation.
- **Owner.** The location that will host it.
- **Lifecycle.** Requested → Confirmed → (Seated | No-Show | Cancelled). A no-show is a recorded truth with consequences (it informs guest reliability and demand forecasting), never a silent nothing.
- **Visibility.** Visible within the hosting location and to the guest who made it.
- **Relationships.** MADE_BY guest; AT location; FOR a time (future); ASSIGNED_TO a table (on seating); BECOMES an order (on arrival and ordering); INFORMS demand forecast.
- **Authority.** The guest is authoritative over the request and cancellation; the location is authoritative over confirmation and seating.
- **Versioning.** Party size, time, and status change as dated layers; the *history of changes* to a reservation matters for reliability analysis.
- **Deletion Policy.** Retired, never destroyed — a broken or cancelled reservation is data, not noise (it predicts future no-shows).
- **Expected Growth.** Grows with reservation-taking locations; substantial but far below order volume.
- **Examples.** A dinner-for-four confirmed for Friday; a large-party event booking; a repeatedly-rescheduled reservation whose churn is itself informative.

---

## Family D — The Menu & Product

### Node 14 — Menu

- **Purpose.** The organized set of things a brand offers for sale at a location during a period — breakfast menu, dinner menu, Ramadan menu, delivery-only menu. The menu is the *frame* within which menu items are offered; the same item may appear on several menus at different prices and availabilities.
- **Identity.** A globally unique identity per menu.
- **Owner.** The brand (definition) or location (local menu), depending on scope.
- **Lifecycle.** Drafted → Published → Active → (Seasonal-Inactive ↔ Active) → Retired.
- **Visibility.** Visible within its owning brand/restaurant.
- **Relationships.** DEFINED_BY brand; ACTIVE_AT location(s); ORGANIZES categories; OFFERS menu items (with menu-specific price/availability).
- **Authority.** The brand is authoritative over the canonical menu; the location over local availability within brand standards.
- **Versioning.** Menu composition and timing change as dated layers — a menu's *history of what it contained when* is essential to interpret past sales correctly (an item's absence from a period explains zero sales in that period).
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** A small multiple of brands; not numerous.
- **Examples.** The all-day menu; a limited Ramadan menu; a delivery-platform-specific menu with adjusted prices.

### Node 15 — Category

- **Purpose.** A grouping of menu items by kind — appetizers, mains, beverages, desserts — used to organize menus, structure kitchen routing, and aggregate analysis. The category is a lens of organization, not a thing sold.
- **Identity.** A globally unique identity per category within its scope.
- **Owner.** The brand or menu that defines it.
- **Lifecycle.** Defined → Active → Retired.
- **Visibility.** Visible within its owning scope.
- **Relationships.** ORGANIZES menu items; PART_OF menu; AGGREGATES sales for analysis.
- **Authority.** The owner defines it.
- **Versioning.** Membership and naming change as dated layers.
- **Deletion Policy.** Retired, never destroyed — historical category groupings must survive so past reports remain interpretable.
- **Expected Growth.** Small; a handful per menu.
- **Examples.** Appetizers; Grills; Cold Beverages; Kids' menu; Add-ons.

### Node 16 — Menu Item

- **Purpose.** A thing a guest can order — the sellable unit as the guest understands it. The menu item is *what is sold*; it is distinct from the recipe (Node 18) that *produces* it and from the price (a value object) at which it is *offered*. RFC-001's Recipe ≠ Menu Item and Price ≠ Cost distinctions both live here: the item is sold at a price; it is made by a recipe at a cost; the two numbers are different facts and the gap between them is margin.
- **Identity.** A globally unique identity per item, permanent across price changes, recipe revisions, and menu moves. A dish that gets cheaper ingredients is the same menu item with a new recipe version, not a new item.
- **Owner.** The brand (canonical definition); locations reference it and may hold local price/availability.
- **Lifecycle.** Created → Available → (86'd/Unavailable ↔ Available) → Discontinued (Retired). "86'd" — temporarily unavailable — is an operational state, distinct from discontinued.
- **Visibility.** Visible within its owning brand/restaurant.
- **Relationships.** DEFINED_BY brand; OFFERED_ON menus (at a price); PRODUCED_BY recipe; ORDERED_AS order lines; ACCEPTS modifiers; CATEGORIZED_BY category; ANALYZED for profitability (derived — Part 7).
- **Authority.** The brand is authoritative over the item's definition and canonical price; the location over local price and availability.
- **Versioning.** Price is *not* an attribute overwritten in place — each price is a dated fact, so the graph always knows what the item cost the guest on any past day (essential for interpreting historical margin). Recipe linkage, name, and availability likewise version as history.
- **Deletion Policy.** Retired, never destroyed — a discontinued dish's entire sales history remains attributable to it forever (the substance of "which items were most/least profitable over five years").
- **Expected Growth.** Grows with menu breadth × brands; substantial but bounded per brand.
- **Examples.** Chicken shawarma sandwich; a seasonal mango dessert; a combo meal; a delivery-only wings platter.

### Node 17 — Modifier

- **Purpose.** A choice or addition that alters a menu item as ordered — extra cheese, no onions, spice level, size. Modifiers are how the guest's specific intent is captured on an order line, and they affect both what the kitchen makes and what the guest pays.
- **Identity.** A globally unique identity per modifier definition.
- **Owner.** The brand (definition); referenced on order lines.
- **Lifecycle.** Defined → Active → Retired.
- **Visibility.** Visible within its owning brand/restaurant.
- **Relationships.** APPLIES_TO menu items; ALTERS order lines; MAY_ADJUST price and recipe (consumption).
- **Authority.** The brand defines it; the guest (via the employee) asserts its application on a specific line.
- **Versioning.** Definition and price impact change as dated layers.
- **Deletion Policy.** Retired, never destroyed — past order lines that used it remain interpretable.
- **Expected Growth.** Moderate; bounded per brand.
- **Examples.** Extra cheese (+price); no onions (no price); large size (+price, +consumption); well-done.

### Node 18 — Recipe

- **Purpose.** The specification of *how a menu item is produced* — which ingredients, in what quantities, by what method. The recipe is the bridge between selling (menu item) and supply (ingredients, stock). It is the source of *cost* (what the item consumes) as opposed to *price* (what the item earns), and it is what makes food-cost, waste, and margin computable at all.
- **Identity.** A globally unique identity per recipe, permanent across revisions. A recipe that is reformulated is the same recipe with a new version, so that the history of "what this dish consumed when" survives.
- **Owner.** The brand (canonical recipe); locations may hold approved local variations.
- **Lifecycle.** Drafted → Approved → Active → (Revised) → Retired.
- **Visibility.** Visible within its owning brand/restaurant; recipes are competitively sensitive and never leave the restaurant except as anonymized cost aggregates.
- **Relationships.** PRODUCES menu item; USES ingredients (the canonical edge: Recipe USES Ingredient, with quantity); DETERMINES consumption on sale; DRIVES food cost and waste analysis (derived).
- **Authority.** The brand is authoritative over the canonical recipe; the location over approved variations.
- **Versioning.** Every reformulation is a dated version — so that a sale two years ago is costed against the recipe *as it was then*, not as it is now. This is one of the most important versioning disciplines in the graph, because collapsing recipe history silently falsifies every historical margin.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Tracks menu items (roughly one active recipe per item, plus versions accumulating). Substantial with historical depth.
- **Examples.** The shawarma recipe (bread, chicken, garlic sauce, pickles, in stated quantities); a sauce sub-recipe used by several dishes; a reformulated version switching to a cheaper oil.

### Node 19 — Ingredient

- **Purpose.** A raw or intermediate input consumed to produce food — the atoms of cost and supply. Ingredients are what recipes use, what suppliers supply, what inventory tracks, and what waste destroys. They are the hinge on which the entire cost side of the restaurant turns.
- **Identity.** A globally unique identity per ingredient within its scope, permanent across supplier and price changes. "Tomatoes" is one ingredient node even as its supplier and price change weekly.
- **Owner.** The restaurant/brand that defines its ingredient catalogue.
- **Lifecycle.** Defined → Active → (Substituted ↔ Active) → Retired.
- **Visibility.** Visible within its owning restaurant; ingredient-level *pricing* contributes to benchmarks in anonymized aggregate ("you overpay for X relative to peers" — Part 7) without exposing any restaurant's specific supplier deals.
- **Relationships.** USED_BY recipes; SUPPLIED_BY suppliers (the canonical edge: Supplier SUPPLIES Ingredient); TRACKED_AS stock; CONSUMED by sales (through recipes); WASTED in waste events; PRICED over time (each purchase a dated cost).
- **Authority.** The restaurant is authoritative over its own ingredient definitions and the prices it actually pays; suppliers are authoritative over their *quoted* prices (a claim, not an observation — Part 1.10).
- **Versioning.** The *price paid over time* is the crucial versioned history — never a single current cost, always the full series, because margin analysis and benchmarking depend entirely on knowing what was paid when.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Substantial per restaurant; the ingredient catalogue is broad and its *price history* deepens continuously — a thick-node contributor in the North Star sense.
- **Examples.** Tomatoes; chicken breast; olive oil; a proprietary spice blend (itself possibly a sub-recipe); disposable packaging counted as a consumable.

---

## Family E — The Ordering Core

### Node 20 — Order

- **Purpose.** The central act of the restaurant economy: a guest's request for food and the commitment to pay for it. Almost every other node exists to feed, fulfil, cost, settle, or analyze orders. The order is the aggregate root (Part 1.3, RFC-001 Part 4) that owns its lines and is the anchor of payment, receipt, and analysis. RFC-001's Order ≠ Ticket distinction lives here: the order is the *commercial* fact (what was bought and owed); the ticket (Node 22) is the *operational* fact (what the kitchen must make).
- **Identity.** A globally unique identity, **born at the edge** (Part 1.8) — an order created on a disconnected device is a real order with a real, non-colliding identity from the instant it opens, and remains the same order when it rejoins the network. This is the single most important place the edge-born identity principle is exercised, because orders are created constantly, everywhere, including offline.
- **Owner.** Itself as an aggregate root; attributed to a location, a shift, a customer, and (optionally) a table and guest.
- **Lifecycle.** Opened → (Building: lines added/changed) → Placed/Fired → (Served) → Settled (paid) → Closed → (possibly Refunded, as a *new* layered truth). Once Settled, RFC-001's invariant holds absolutely: a paid order cannot become unpaid; a return is a new refund truth, not an un-payment.
- **Visibility.** Visible within its originating restaurant; its aggregate shape contributes to benchmarks; its particulars never leave.
- **Relationships.** PLACED_BY customer; EXPERIENCED_BY guest; ORIGINATED_AT location; WITHIN shift; AT table (optional); CONTAINS order lines (the canonical edge: Order CONTAINS Menu Item, realized through lines); GENERATES ticket(s); SETTLED_BY payment(s) (the canonical edge: Payment SETTLES Order); PRODUCES receipt/invoice; SUBJECT_TO discounts and taxes.
- **Authority.** The restaurant (through its employees) is authoritative over the order's contents; the payment authority (Node 25/26) is authoritative over whether it was settled.
- **Versioning.** Every line added, changed, voided, comped, or discounted is a dated layer of the order's history — the order's *build history* is retained, so voids and comps are visible truths, never silent edits (critical for audit and for detecting patterns of abuse).
- **Deletion Policy.** Retired/closed, never destroyed. A voided order is a *recorded void*, not an absence — it happened and is retained.
- **Expected Growth.** The most oceanic transactional node — the primary measure of graph activity, growing with every sale across every location forever. When the North Star speaks of the graph's activity, orders are the pulse.
- **Examples.** A dine-in order for a table of four; a single delivery order; a bar tab that grows over an evening; a voided order retained as an audit fact.

### Node 21 — Order Line

- **Purpose.** One item within an order — a specific menu item, in a quantity, with modifiers, at the price in force when it was rung. The order line is where the abstract "order contains menu item" becomes a concrete, costed, prepared thing. It is a node (not a mere edge) because it carries its own life: a quantity, a captured price, modifiers, a preparation state, a place in the kitchen queue, and possibly its own void or comp (Part 1.2 — when a relationship earns a life, it becomes a node).
- **Identity.** A globally unique identity per line, edge-born like its order.
- **Owner.** The order (aggregate root). A line is never changed except through its order, so the order can keep its total equal to the sum of its lines (RFC-001 invariant).
- **Lifecycle.** Added → (Modified) → Fired → Prepared → Served → (possibly Voided/Comped, as recorded truths).
- **Visibility.** Within the originating restaurant.
- **Relationships.** PART_OF order; FOR menu item; CARRIES modifiers; CAPTURES price-at-sale (a dated value, not a live lookup); CONSUMES ingredients (through the item's recipe version at time of sale); ROUTES_TO station (through the ticket).
- **Authority.** The restaurant's employees, bounded by role.
- **Versioning.** Quantity changes, modifier changes, voids, and comps are dated layers. Crucially, the line **captures the price and the recipe version at the moment of sale** — it does not point at a live price that could later change, because the historical truth of *what the guest paid and what it cost to make* must be immune to later edits to the menu (a foundational versioning discipline).
- **Deletion Policy.** Retired/voided, never destroyed.
- **Expected Growth.** Even more oceanic than orders (several lines per order) — the single largest transactional node by count.
- **Examples.** "2× shawarma, extra garlic, no pickles, at 45 each"; a comped dessert line retained with its comp reason; a voided line kept as an audit fact.

### Node 22 — Ticket (Kitchen Ticket)

- **Purpose.** The kitchen's instruction to make food — the operational projection of an order (or part of one) routed to the stations that must produce it. RFC-001's Order ≠ Ticket: one order may spawn several tickets (starters now, mains later; hot line and cold station); a ticket exists to be *made*, timed, and cleared, and it lives in *kitchen time* (elapsed — Part 1.9), not commercial time.
- **Identity.** A globally unique identity per ticket.
- **Owner.** The order that generated it (for provenance) and the location/station that works it (for operation).
- **Lifecycle.** Fired → In-Progress → Ready → Served/Cleared. Its whole life is measured as *elapsed duration* (how long since fired), which is the substance of kitchen performance analysis.
- **Visibility.** Within the originating location.
- **Relationships.** GENERATED_BY order; ROUTED_TO station(s); CONTAINS the items to prepare; TIMED in kitchen time; INFORMS prep-time and bottleneck analysis (derived).
- **Authority.** The kitchen (employees at stations) is authoritative over its progress and completion.
- **Versioning.** State transitions with their elapsed times are the retained history.
- **Deletion Policy.** Retired/cleared, never destroyed — historical tickets are the substance of every kitchen-speed and bottleneck study.
- **Expected Growth.** Oceanic, roughly proportional to orders (often more, via splitting).
- **Examples.** A hot-line ticket for the mains; a bar ticket for drinks; a rush-hour ticket whose long elapsed time flags a bottleneck.

### Node 23 — Table

- **Purpose.** A seat-able place within a location where guests are hosted — the physical unit of dine-in capacity, the thing a reservation is assigned to and an order is seated at. The table is where turn-time and capacity utilization become measurable.
- **Identity.** A globally unique identity per table within a location, permanent across floor rearrangements (a table moved across the room is the same table).
- **Owner.** The location.
- **Lifecycle.** Configured → Available → (Occupied ↔ Available) → Retired.
- **Visibility.** Within the location.
- **Relationships.** BELONGS_TO location; SEATS orders; ASSIGNED reservations; MEASURES turn-time and utilization (derived).
- **Authority.** The location is authoritative over its floor and table state.
- **Versioning.** Configuration and capacity change as dated layers.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** A multiple of locations; bounded by physical capacity.
- **Examples.** Table 12; the corner booth; a merged large-party table for the evening; a patio table used only seasonally.

### Node 24 — Course

- **Purpose.** A stage of a meal's service — starters, mains, dessert — used to *pace* the kitchen and the guest's experience. The course is how an order's lines are grouped in *time of service*, so that the kitchen fires mains after starters are cleared rather than all at once. It is a node because it organizes lines across kitchen time and carries its own fire/hold state.
- **Identity.** A globally unique identity per course within an order.
- **Owner.** The order.
- **Lifecycle.** Planned → Held → Fired → Served → Cleared.
- **Visibility.** Within the originating location.
- **Relationships.** PART_OF order; GROUPS order lines; PACES tickets; SEQUENCED in service time.
- **Authority.** The service staff (employees) are authoritative over pacing.
- **Versioning.** Fire/hold/clear transitions with their times are retained.
- **Deletion Policy.** Retired/cleared, never destroyed.
- **Expected Growth.** Proportional to dine-in orders; modest relative to lines.
- **Examples.** The starters course held until guests arrive; the mains fired on clearing starters; a dessert course added mid-meal.

---

## Family F — The Money

### Node 25 — Payment

- **Purpose.** The act of settling what is owed on an order — money moving from the customer's side to the restaurant's. The payment is the truth that turns an owed order into a settled one, and it is one of the highest-trust nodes in the graph (Part 1.10) because it is directly observed at the point of truth and is the input to the graph's most valuable derived output, underwriting (Part 7, Part 10). RFC-001's Payment ≠ Tender lives here: the payment is the *settlement of the order*; the tender (Node 26) is the *instrument and amount* by which some of it was paid. One payment may comprise several tenders (split across cash and card).
- **Identity.** A globally unique identity per payment, edge-born (a payment taken offline is real from the instant it occurs).
- **Owner.** The order it settles (it belongs to the order's consistency boundary — Part 1.3, RFC-001 aggregate).
- **Lifecycle.** Initiated → Authorized → Settled → (possibly Refunded, as a *new* refund truth — never an un-settlement). RFC-001's "every payment belongs to exactly one order" and "a paid order cannot become unpaid" both bind here absolutely.
- **Visibility.** Within the originating restaurant; aggregate cash-flow shape feeds underwriting and benchmarks; particulars never leave.
- **Relationships.** SETTLES order (the canonical edge: Payment SETTLES Order); COMPRISES tenders; EVIDENCED_BY receipt; CONTRIBUTES to cash flow (the underwriting input); RECONCILES_TO cash session (for cash tenders).
- **Authority.** The relevant settlement authority — the processor for card, the cash session for cash — is authoritative over whether the payment cleared. The restaurant is authoritative over which order it applies to.
- **Versioning.** A payment's states are retained; a refund is a *separate* layered truth referencing it, so both the payment and the refund are permanently, independently true.
- **Deletion Policy.** Retired, never destroyed — payments are the bedrock of the graph's financial truth and can never be removed.
- **Expected Growth.** Oceanic, roughly one-or-more per settled order — a primary pulse of the graph and *the* input to its financial intelligence.
- **Examples.** A card payment settling a dinner; a split payment (half cash, half card) comprising two tenders; a payment later partially refunded.

### Node 26 — Tender

- **Purpose.** A single instrument-and-amount by which part or all of a payment is made — this much in cash, that much on this card, some on a wallet. The tender is the granular *how* of settlement, distinct from the payment's *that-it-settled*. It matters because different tenders have different truth, cost, and reconciliation: cash reconciles to a drawer; card carries a processing cost and clears through a processor; a wallet is different again.
- **Identity.** A globally unique identity per tender.
- **Owner.** The payment it is part of.
- **Lifecycle.** Presented → Accepted → Cleared → (possibly Reversed).
- **Visibility.** Within the originating restaurant.
- **Relationships.** PART_OF payment; OF a tender type (cash/card/wallet/account); RECONCILES_TO cash session (cash) or processor (card); CARRIES processing cost (card).
- **Authority.** The corresponding settlement authority (drawer for cash, processor for card).
- **Versioning.** Clearing and reversal states are retained.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Oceanic, at least one per payment, more where split.
- **Examples.** 30 in cash; 45 on a card; a 20 wallet balance; an account charge tendered to a corporate customer.

### Node 27 — Receipt

- **Purpose.** The record *given to the guest* evidencing what they bought and paid — the guest-facing proof of a transaction. RFC-001's Receipt ≠ Invoice: the receipt evidences a *completed* consumer transaction; the invoice (Node 28) is a *demand for payment* on account. Conflating them is a classic error with tax and legal consequences, and the graph keeps them apart.
- **Identity.** A globally unique identity per receipt.
- **Owner.** The order/payment it evidences.
- **Lifecycle.** Issued → (Reprinted/Reissued as needed) → Permanent.
- **Visibility.** Within the originating restaurant and to the guest who holds it.
- **Relationships.** EVIDENCES order and payment; ITEMIZES lines; STATES taxes and discounts; MAY_SATISFY a fiscal/compliance obligation (regulator-facing).
- **Authority.** The restaurant issues it; a fiscal authority may be authoritative over its required form (compliance).
- **Versioning.** Reissues are dated layers referencing the original; the original is never altered.
- **Deletion Policy.** Retired, never destroyed — receipts are legal and fiscal records.
- **Expected Growth.** Oceanic, roughly one per completed transaction.
- **Examples.** A printed dine-in receipt; a digital delivery receipt; a fiscally-compliant receipt bearing required tax identifiers.

### Node 28 — Invoice

- **Purpose.** A *demand for payment* issued to a customer who pays on account rather than at the point of sale — the formal statement of what is owed, by whom, by when. Invoices belong to the account-customer world (corporate accounts, events, platforms with terms), and they carry credit and aging that point-of-sale receipts never do.
- **Identity.** A globally unique identity per invoice.
- **Owner.** The customer relationship and the order(s) it bills.
- **Lifecycle.** Draft → Issued → (Partially-Paid) → Paid → (or Overdue → Written-Off). Aging is a first-class fact.
- **Visibility.** Within the issuing restaurant and to the billed customer.
- **Relationships.** ISSUED_TO customer; BILLS order(s); SUBJECT_TO terms; SETTLED_BY payment(s); AGES over time (credit signal).
- **Authority.** The restaurant issues and is authoritative over the amount; the customer is authoritative over their remittance.
- **Versioning.** Issuance, partial payments, and status are dated layers.
- **Deletion Policy.** Retired, never destroyed — including write-offs, which are recorded truths, not erasures.
- **Expected Growth.** Far below receipts (only account customers); strategically important for credit signals.
- **Examples.** A monthly invoice to a corporate lunch account; an event invoice with net-30 terms; a written-off overdue balance retained as truth.

### Node 29 — Refund

- **Purpose.** The return of money to the customer — a *new* truth that partially or wholly reverses the economic effect of a payment while leaving the original payment permanently true. The refund is the graph's mechanism for honoring "a paid order cannot become unpaid" (RFC-001): money coming back is not the un-happening of money going out; it is a distinct, later, recorded event.
- **Identity.** A globally unique identity per refund.
- **Owner.** The payment/order it references.
- **Lifecycle.** Requested → Approved → Executed → Settled. Approval authority is role-bounded and audited (a refund is a common abuse vector; its authorship is a high-trust audit fact).
- **Visibility.** Within the originating restaurant; refund rates feed anomaly detection (Part 8) and benchmarks in aggregate.
- **Relationships.** REVERSES payment (partially/wholly); AGAINST order; AUTHORED_BY employee (audited); REDUCES net revenue (as a layered truth, not an edit).
- **Authority.** A role-authorized employee approves; the settlement authority executes.
- **Versioning.** Its states are retained; it references but never mutates the original payment.
- **Deletion Policy.** Retired, never destroyed — refunds are audit-critical and never removable.
- **Expected Growth.** A small fraction of payments; disproportionately important for integrity.
- **Examples.** A full refund for a wrong order; a partial refund for a missing side; a refund whose unusual frequency flags an anomaly.

### Node 30 — Discount / Promotion

- **Purpose.** A reduction in what the guest pays, applied by a rule or a decision — a percentage off, a combo price, a loyalty reward, a manager comp. Discounts are where *pricing intent* meets the order, and where a great deal of margin is deliberately (or carelessly) given away. Their history is essential to answering "which promotions improved retention" and "where is margin leaking" (Part 7).
- **Identity.** A globally unique identity per discount/promotion definition; each *application* is recorded on the order line/order it touched.
- **Owner.** The brand/restaurant (definition); applications belong to their orders.
- **Lifecycle.** Defined → Active → (Paused ↔ Active) → Retired.
- **Visibility.** Within the owning restaurant; promotion effectiveness feeds derived retention analysis.
- **Relationships.** DEFINED_BY brand/restaurant; APPLIES_TO orders/lines; REDUCES price; MAY_REQUIRE role authorization (comps); LINKED_TO loyalty (rewards); ANALYZED for retention impact (derived).
- **Authority.** The brand defines the promotion; a role-authorized employee approves discretionary comps (audited).
- **Versioning.** Definitions and their applications are dated — so a past order's discount is interpreted against the promotion *as it was then*.
- **Deletion Policy.** Retired, never destroyed — past applications remain attributable.
- **Expected Growth.** Moderate definitions; oceanic *applications* (recorded on orders).
- **Examples.** 15% off before noon; a buy-one-get-one; a loyalty free-coffee reward; a manager comp for a complaint.

### Node 31 — Tax

- **Purpose.** A mandated addition to (or component of) what the guest pays, owed onward to an authority — the restaurant collecting on behalf of the state. Tax is a first-class node because it must be computed, itemized, reported, and remitted with legal precision, and because compliance is the wedge that forces sales-truth into the graph (North Star). RFC-001 treats the *rate* as a value object; the *tax obligation and its applications* are the node.
- **Identity.** A globally unique identity per tax definition within a jurisdiction.
- **Owner.** Defined by the jurisdiction/regulator; applied by the restaurant.
- **Lifecycle.** Enacted → Active → (Amended) → Superseded.
- **Visibility.** Within the restaurant; aggregate remittance data may be reported to authorities (Government projection — Part 6).
- **Relationships.** APPLIES_TO orders/lines; COMPUTED into receipts/invoices; REMITTED to authority; GOVERNED_BY jurisdiction.
- **Authority.** The regulator is authoritative over the rate and rule; the restaurant is authoritative over correct application and remittance.
- **Versioning.** Rate and rule changes are dated — a past sale is taxed at the rate that was law *then*, never retroactively restated.
- **Deletion Policy.** Retired/superseded, never destroyed — historical tax facts are legally permanent.
- **Expected Growth.** Few definitions per jurisdiction; oceanic *applications* on transactions.
- **Examples.** A value-added tax at the prevailing rate; a municipal service levy; a zero-rated item; an amended rate whose old value still applies to past sales.

---

## Family G — The Supply & Inventory

### Node 32 — Supplier

- **Purpose.** A party that provides ingredients or goods to the restaurant — the other side of the cost equation and, at scale, the other side of the graph's two-sided marketplace (North Star liquidity). The supplier is where procurement truth originates and where demand-aggregation clears.
- **Identity.** A globally unique identity per supplier, permanent across the restaurant's changing relationship with them.
- **Owner.** Within a restaurant's view, the restaurant owns its supplier relationship; the supplier is a shared *kind* of node across the graph in the aggregate (the same physical supplier may serve many restaurants — and recognizing that sameness is what enables demand aggregation, done under strict privacy — Part 8, Part 9).
- **Lifecycle.** Prospective → Active → (Suspended ↔ Active) → Retired.
- **Visibility.** A restaurant's *specific* dealings with a supplier (prices, terms) are private to that restaurant. The *aggregate* demand across restaurants is stewarded by Mezze to create buying power, without exposing any one restaurant's deal (the marketplace's foundational privacy rule).
- **Relationships.** SUPPLIES ingredients (the canonical edge: Supplier SUPPLIES Ingredient); FULFILS purchase orders; QUOTES prices (claims — Part 1.10); CAUSES waste (derived: "which suppliers create the most waste" — Part 7); AGGREGATED into demand pools.
- **Authority.** The supplier is authoritative over its own quotes and fulfilment; the restaurant is authoritative over what it actually received and paid.
- **Versioning.** Terms, reliability, and price history versioned as dated layers.
- **Deletion Policy.** Retired, never destroyed — supplier performance history is essential to procurement intelligence.
- **Expected Growth.** Substantial; grows with both restaurants and the ingredient economy; strategically central to liquidity.
- **Examples.** A produce wholesaler; a meat distributor; a packaging vendor; a supplier whose late deliveries correlate with waste.

### Node 33 — Purchase Order

- **Purpose.** A restaurant's request to a supplier to deliver goods — the commitment to buy. It is the mirror of the sales order on the cost side: where the sales order records what the restaurant *sold*, the purchase order records what it *bought* to be able to sell.
- **Identity.** A globally unique identity per purchase order.
- **Owner.** The location/restaurant that places it.
- **Lifecycle.** Drafted → Placed → (Partially-Received) → Received → Reconciled (against what was ordered and invoiced). Discrepancies between ordered, received, and billed are recorded truths.
- **Visibility.** Within the placing restaurant; aggregate demand feeds the marketplace.
- **Relationships.** PLACED_BY location (the canonical edge: Location PLACES Purchase Order); TO supplier; ORDERS ingredients (with quantities and agreed prices); RECEIVED_INTO inventory (generating stock movements); BILLED_BY invoice.
- **Authority.** The restaurant is authoritative over what it ordered and received; the supplier over what it shipped.
- **Versioning.** Order, partial receipts, and reconciliation are dated layers.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Substantial; proportional to procurement cadence across locations.
- **Examples.** A weekly produce order; an emergency top-up order; a partially-received order whose short shipment was recorded.

### Node 34 — Stock Item (Inventory)

- **Purpose.** The record of *how much of an ingredient is on hand at a location* — the standing quantity that sales deplete and purchases replenish. RFC-001's invariant binds here with full force: **stock is the exact net of its movements** — it is never an independently-typed number, always the sum of everything that came in minus everything that went out (Node 35). This makes inventory *derivable and auditable* rather than assertable, which is what makes it trustworthy.
- **Identity.** A globally unique identity per (ingredient × location) stock position.
- **Owner.** The location.
- **Lifecycle.** Established → Active (fluctuating with movements) → Retired (ingredient discontinued at location).
- **Visibility.** Within the location; aggregate stock behavior informs fulfilment prioritization (Part 7).
- **Relationships.** OF ingredient; STORED_AT location (the canonical edge: Inventory STORED_AT Location); NET_OF stock movements; DEPLETED_BY sales (through recipes); REPLENISHED_BY purchase receipts; REDUCED_BY waste.
- **Authority.** No party *asserts* the on-hand number directly; it is the *computed net* of authorized movements. A manual count is itself a *movement* (an adjustment) recorded as truth, never a silent overwrite — so even a hand-count respects "stock is the net of its movements."
- **Versioning.** The full movement history *is* the versioning — the on-hand at any past instant is recoverable by summing movements up to that instant.
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Substantial (ingredients × locations); its *movement history* is oceanic and deepens continuously — a thick-node engine.
- **Examples.** 14 kg of chicken at the Maadi branch; a near-zero tomato position triggering reorder; a count adjustment recorded after a physical inventory.

### Node 35 — Stock Movement

- **Purpose.** A single change in the quantity of a stock item — a receipt, a sale-depletion, a waste, a transfer, a manual adjustment. Stock movements are the *atoms* from which inventory is computed; they are the truth, and the on-hand quantity is merely their running sum. This inversion — movements are primary, balance is derived — is the discipline that makes inventory honest.
- **Identity.** A globally unique identity per movement.
- **Owner.** The stock item (and thereby the location) it affects.
- **Lifecycle.** Recorded → Permanent. A movement, once true, is never edited; a correction is a *new*, opposite movement (never an alteration of the original — the append-only law).
- **Visibility.** Within the location.
- **Relationships.** AFFECTS stock item; CAUSED_BY a source (purchase receipt, sale, waste, transfer, count); DIRECTIONAL (in or out); TIMESTAMPED in event time.
- **Authority.** The authorizing process (a receipt, a sale, a manager's counted adjustment) authors it, bounded by role.
- **Versioning.** Movements are immutable; the sequence is the history.
- **Deletion Policy.** Never destroyed and never edited — the strictest append-only node, because it is the substrate of inventory truth.
- **Expected Growth.** Among the most oceanic nodes — every sale, receipt, waste, and count is a movement, forever.
- **Examples.** +20 kg chicken received; −0.2 kg chicken consumed by a shawarma sale; −5 kg spoiled (waste); a +1.5 kg adjustment from a physical count.

### Node 36 — Waste Event

- **Purpose.** The destruction of usable stock without sale — spoilage, spillage, error, theft-as-shrinkage, over-production. Waste is where margin quietly dies, and its record is what makes "which ingredients create margin loss" and "which suppliers create the most waste" answerable (Part 7). A waste event is a specific kind of outbound stock movement elevated to its own node because its *cause and pattern* carry outsized analytic value.
- **Identity.** A globally unique identity per waste event.
- **Owner.** The location; references the stock/ingredient destroyed.
- **Lifecycle.** Recorded → Permanent (append-only, like all movements).
- **Visibility.** Within the location; aggregate waste patterns feed benchmarks and supplier analysis.
- **Relationships.** DESTROYS stock (an outbound movement); OF ingredient; ATTRIBUTED to a cause (spoilage/error/over-prep); MAY_IMPLICATE supplier (short shelf life); AUTHORED_BY employee.
- **Authority.** The recording employee authors it, bounded by role; a manager may be authoritative over categorizing significant waste.
- **Versioning.** Immutable, append-only.
- **Deletion Policy.** Never destroyed — waste hidden is margin lied about; the graph refuses to let waste vanish.
- **Expected Growth.** Substantial and continuous; a key thickness signal (a node that records waste is a much thicker, more valuable node than one that hides it).
- **Examples.** 3 kg of unsold prepared rice discarded at close; a dropped tray; produce spoiled from a supplier's short-dated delivery.

---

## Family H — The Intelligence & Governance

*These four nodes are different in kind from the thirty-six above. The first thirty-six record what happened — they are truth (Part 1.4). The next two — Forecast and Benchmark — are **derivations**: they are computed *from* truth and are never themselves truth (Part 8). The last two — Audit Record and Report — are the graph reflecting on itself: the audit is truth about who did what to the graph; the report is a projection frozen for evidence. The catalogue includes them because they are real nodes with identity and history, but their authority is fundamentally constrained, and that constraint is stated in each.*

### Node 37 — Forecast

- **Purpose.** A prediction about the future — expected demand, expected staffing need, expected stock depletion. The forecast exists to *inform decisions before the fact* (how much to prep, whom to schedule, what to reorder). It is the canonical example of a node that **must never be mistaken for truth**: a forecast is a statement about a future that has not happened and may not, and RFC-001's invariant "a prediction is never written into the operational record as a fact" governs it absolutely.
- **Identity.** A globally unique identity per forecast instance (a forecast made at a time, for a horizon, is a distinct node from a later forecast for the same horizon — so the graph can later ask "how good were our forecasts?").
- **Owner.** Mezze as steward (derived from the restaurant's and the network's truth), surfaced to the restaurant.
- **Lifecycle.** Generated → Surfaced → (Superseded by a newer forecast) → Evaluated-against-outcome. A forecast's eventual comparison to what *actually* happened is itself valuable truth (it measures forecast quality) — and that comparison is truth, while the forecast never was.
- **Visibility.** Surfaced to the restaurant it concerns; built from network patterns without exposing peers' particulars.
- **Relationships.** PREDICTS demand/need (the canonical edge: Forecast PREDICTS Demand); DERIVED_FROM historical truth (orders, shifts, stock); INFORMS decisions (prep, staffing, reorder); EVALUATED_AGAINST later actuals.
- **Authority.** **None over truth.** A forecast may inform but never *assert* a fact into the operational record. It carries no truth-trust (Part 1.10); it is explicitly marked as prediction, always.
- **Versioning.** Each forecast is retained with its time and horizon, so the *track record* of forecasting accumulates — the graph learns how much to trust its own predictions by remembering them.
- **Deletion Policy.** Retired, never destroyed — retained forecasts, compared to outcomes, are how forecast quality is measured over years.
- **Expected Growth.** Substantial (regenerated continuously per location and horizon); disposable in *use* but retained in *history* for self-evaluation.
- **Examples.** "Expect 220 covers Friday"; "You will run out of chicken by Saturday"; "Schedule one more cook for the dinner rush" — each a prediction, none a fact until the future arrives and becomes truth of its own.

### Node 38 — Benchmark

- **Purpose.** A comparison of one restaurant against the aggregate of its peers — "you pay 12% more for tomatoes than similar restaurants," "your labor cost is high for your volume," "your dessert attach-rate is low." The benchmark is the single most visible product of the graph's *network* dimension (North Star): it is worthless with one restaurant and priceless with a hundred thousand, because it is precisely the thing no single restaurant can compute about itself. It is a derivation — never truth about the peer restaurants, always a *statement of relative position* computed under strict privacy.
- **Identity.** A globally unique identity per benchmark instance (a benchmark computed at a time, over a peer set, on a metric).
- **Owner.** Mezze as steward of the aggregate (Part 1.11 — authority over the aggregate belongs to the steward, never to any restaurant).
- **Lifecycle.** Computed → Surfaced → (Refreshed) → Superseded.
- **Visibility.** A restaurant sees *its own position* in a benchmark and the *aggregate* it is measured against — **never the underlying particulars of any peer** (the foundational privacy rule that makes benchmarking both trustworthy and legal — Part 9).
- **Relationships.** COMPARES restaurant to a peer aggregate (the canonical edge: Benchmark COMPARES Restaurant); DERIVED_FROM many restaurants' anonymized truth; DEFINES a peer set (by concept, size, geography); INFORMS decisions.
- **Authority.** The steward authors it under privacy rules. **No restaurant is authoritative over it, and it asserts nothing about any identifiable peer** — only about anonymized aggregates.
- **Versioning.** Each benchmark instance is retained, so a restaurant's *trajectory* against peers over years is itself visible (a powerful longitudinal product).
- **Deletion Policy.** Retired, never destroyed.
- **Expected Growth.** Grows with metrics × restaurants × time; its *value per instance* grows with graph density — the clearest embodiment of Metcalfe-for-restaurants (North Star flywheel).
- **Examples.** Ingredient-price benchmark; labor-efficiency benchmark; menu-mix benchmark; a financing-qualification benchmark (Part 7) that positions a restaurant against peers a lender has safely funded.

### Node 39 — Audit Record

- **Purpose.** Truth *about the graph itself* — who asserted what, when, under which authority. Every consequential change to the graph is accompanied by an audit record naming its author, its time, and its justification. The audit is how the graph stays *trustworthy about its own contents*: it is what lets anyone, years later, know that this void was authorized by this manager, this refund by that role, this price change by that owner. RFC-001's append-only audit invariants make this node the most rigidly immutable in the entire catalogue.
- **Identity.** A globally unique identity per audit record.
- **Owner.** The graph itself (the steward), on behalf of accountability; it references the node changed and the actor.
- **Lifecycle.** Recorded → Permanent. Never edited, never deleted, under any circumstance short of the person-erasure exception (which anonymizes the actor while preserving that *an* authorized actor acted).
- **Visibility.** Within the restaurant for its own actions; available to the steward for integrity; never exposed across restaurants.
- **Relationships.** ABOUT any consequential node change; ATTRIBUTES to an actor (employee/role/authority); TIMESTAMPED in event and wall-clock time; JUSTIFIES with a reason (comp reason, void reason, override reason).
- **Authority.** The audit record is authored by the act of change itself; no one may assert an audit record independent of the change it describes, and no one may alter one after the fact.
- **Versioning.** None — audit records are singular and immutable by definition. There is no "version 2" of what happened; there is only what happened.
- **Deletion Policy.** **Never** — the most absolute never in the catalogue. The audit trail's whole value is that it cannot be cleaned.
- **Expected Growth.** Oceanic — proportional to all consequential activity across the graph, forever.
- **Examples.** "Manager A voided line X at 21:04, reason: guest complaint"; "Owner B changed the price of item Y on date Z"; "Cashier C's drawer reconciled short by 12, recorded by Manager A."

### Node 40 — Report

- **Purpose.** A projection of the graph frozen at a moment and preserved as evidence — a daily sales report, a month-end statement, a tax filing, a franchise-royalty statement. A report differs from an ordinary projection (Part 6) in one way: an ordinary projection is *live and disposable*, recomputed from the graph on demand; a report is a projection *deliberately frozen and kept* because someone acted on it, filed it, or was paid against it, and the exact figures *as presented* must remain evidencable. The report is a projection that has been promoted to a keepsake.
- **Identity.** A globally unique identity per report instance.
- **Owner.** The restaurant (or the steward, for network reports) that generated it.
- **Lifecycle.** Generated → Frozen → Filed/Distributed → Permanent.
- **Visibility.** Within its owning restaurant; government-facing reports are shared with the relevant authority (Government projection — Part 6); network reports are anonymized.
- **Relationships.** PROJECTS a slice of the graph; FROZEN at a time; FILED_WITH an authority (some); EVIDENCES a figure someone relied on.
- **Authority.** The generator is authoritative that "this is what the graph showed at this moment"; the report never becomes a *source* of truth (it must always be re-derivable from the graph — Part 1.6), it merely *records that this was shown*.
- **Versioning.** A report is frozen; a *corrected* report is a new, later report referencing the original — the original is never altered (so a filed figure stays evidencable even after correction).
- **Deletion Policy.** Retired, never destroyed — filed reports are legal and contractual records.
- **Expected Growth.** Substantial and steady; grows with reporting cadence and franchise/royalty structures.
- **Examples.** A daily Z-report; a month-end P&L snapshot; a tax filing; a franchise royalty statement paid against.

---

*Forty nodes, eight families, one graph. Every one of them obeys the Standing Deletion Law (retired, never destroyed) and the Standing Versioning Law (change accumulates as history). Two of them — Forecast and Benchmark — are derivations that never become truth. One of them — Audit Record — is the most immutable of all. And every single node, transactional or organizational, person or product or money, is ultimately owned by, attributed to, and in service of the same small set of roots: the restaurant, the guest, the supplier. The next part describes the edges that bind them.*

---

# PART 3 — EDGE CATALOG

An edge is a relationship between two nodes that is itself real (Part 1.2). This part catalogues the principal edge types of the graph. It is not a list of every conceivable pairing — that would be infinite and useless — but of the *relationship types that carry meaning*, the verbs of the restaurant world. Each is described along six dimensions:

- **Direction** — which node is the subject and which the object; relationships are rarely symmetric, and reversing direction inverts meaning.
- **Cardinality** — how many of each side may participate: one-to-one, one-to-many, many-to-many.
- **Ownership** — whether the edge is an *ownership* edge (the subject is the root of responsibility for the object — Part 1.3) or a *reference* edge (the subject merely points at the object, which is owned elsewhere). This distinction governs everything downstream.
- **Historical behavior** — how the edge behaves in time (Part 1.7): whether it is permanent once true, bounded to an interval, or instantaneous; and whether it is retained forever (it always is).
- **Deletion behavior** — what happens to the edge when a node it joins is retired. The standing answer, like nodes, is *retained, never destroyed* — but the *interpretation* differs by edge type and is stated where it matters.
- **Authority** — who may assert the edge into the graph (Part 1.11).

A standing law governs every edge and is stated once:

> **Standing Edge Law.** No edge is ever destroyed. When a node is retired, the edges it participated in remain permanently in the graph as historical facts — because the relationship *was* true and history does not un-happen. A departed employee's WORKS_AT edges remain (they did work there); a closed location's OWNED_BY edge remains (it was owned). Edges gain an *end* in time; they never gain a deletion. This is what lets the graph answer questions about the past correctly forever.

The catalogue proceeds by relationship family, and it names the canonical edges from the brief explicitly, along with the other load-bearing relationships each family requires.

## 3.1 Ownership & Organizational Edges

These edges build the skeleton of responsibility — the chains down which authority and consistency flow (Part 1.3).

### Restaurant —OWNS→ Location
- **Direction.** Restaurant is subject; location is object. The restaurant owns the location, never the reverse.
- **Cardinality.** One-to-many. One restaurant owns many locations; a location belongs to exactly one restaurant (singular ownership — Part 1.3).
- **Ownership.** An **ownership** edge — the location's root of responsibility is its restaurant.
- **Historical behavior.** Bounded: true from the location's opening under this restaurant until a transfer or closure. On an ownership transfer (Part 5), the edge *ends* and a new OWNS edge begins from the acquiring restaurant — both are retained, so the location's full ownership lineage is permanent.
- **Deletion behavior.** Retained. A closed location keeps its OWNS edge (it *was* owned); the edge simply has an end.
- **Authority.** The restaurant asserts it at registration; ownership transfers are asserted under the authority of both parties and recorded as governed events.

### Restaurant —OWNS→ Brand · Brand —SERVED_AT→ Location
- **Direction / Cardinality.** Restaurant OWNS Brand (one-to-many; a brand has one owner). Brand SERVED_AT Location (many-to-many; a brand is served at many locations, a location may serve many brands — the cloud-kitchen case).
- **Ownership.** OWNS is ownership; SERVED_AT is **reference** (the location references the brand it serves; it does not own it — Part 1.3, ownership vs reference). This is the exact place the ownership/reference distinction earns its keep: a cloud kitchen *serves* five brands it may not *own*, and the graph keeps the two relationships distinct.
- **Historical behavior.** Bounded; a brand added to or dropped from a location is an interval with a start and (maybe) an end.
- **Deletion / Authority.** Retained; asserted by the owning restaurant (for OWNS) and the licensing arrangement (for SERVED_AT).

### Location —HOSTS→ {Shift, Station, Table, Cash Session}
- **Direction / Cardinality.** Location is subject; each is object. One-to-many in every case.
- **Ownership.** Ownership edges — each of these nodes' root of responsibility is its location.
- **Historical behavior.** Shifts and cash sessions are *bounded intervals* (they open and close); stations and tables are *long-lived* (configured, active, retired).
- **Deletion / Authority.** Retained; asserted by the location.

### Employee —WORKS_AT→ Location  *(canonical)*
- **Direction.** Employee is subject; location is object. The person works at the place.
- **Cardinality.** Many-to-many *over time* — an employee may work at several locations (transfers, multi-site staff), a location has many employees.
- **Ownership.** **Reference** — the employee is owned by the *restaurant* (the employing business), not by the location; WORKS_AT is an assignment, not ownership. This matters: an employee transferred between two locations of the same restaurant keeps one identity and one employer, changing only their WORKS_AT edges.
- **Historical behavior.** **Bounded interval** — the archetypal bounded edge. True from the day the employee starts at the location to the day they leave. The interval is the fact: "worked here from March to November" is precisely a WORKS_AT edge with a start and an end.
- **Deletion behavior.** Retained forever. A departed employee's WORKS_AT edges are the substance of every historical labor and payroll fact. The edge ends; it is never deleted (Standing Edge Law).
- **Authority.** The employing restaurant asserts it (hiring, assignment, transfer, departure).

### Employee —HOLDS→ Role · Role —GRANTS→ Permissions
- **Direction / Cardinality.** Employee HOLDS Role (many-to-many; an employee may hold several roles). Role GRANTS the permissions that are the basis of authority (Part 1.11).
- **Ownership.** Reference — the role is owned by the restaurant; the employee references it.
- **Historical behavior.** Bounded — a promotion ends one HOLDS interval and begins another; the history of *what role a person held when* is retained, so a past action can be judged against the authority the person actually had at the time (Part 1.7).
- **Deletion / Authority.** Retained; asserted by the restaurant.

### Employee —WORKS→ Shift · Shift —OPERATES→ Station  *(canonical: Shift OPERATES Station)*
- **Direction / Cardinality.** Employee WORKS Shift (many-to-many; a shift has many workers). Shift OPERATES Station (many-to-many within the shift).
- **Ownership.** Reference in both cases — the shift owns neither the employee nor the station; it *coordinates* them for an interval.
- **Historical behavior.** Bounded to the shift's interval; retained as the substance of labor analysis and of "which locations have unstable staffing" (Part 7).
- **Deletion / Authority.** Retained; asserted by the location's management.

## 3.2 Ordering Edges

These edges are the most numerous and the most time-sensitive in the graph — they are created constantly, often at the edge (offline), and they carry the core commercial truth.

### Customer —PLACED→ Order  *(canonical)*
- **Direction.** Customer is subject; order is object. The customer placed the order.
- **Cardinality.** One-to-many — a customer places many orders over time; an order is placed by exactly one customer (the responsible payer — Part 2, Node 11).
- **Ownership.** **Reference** — the order is its *own* aggregate root (Part 1.3); PLACED points from the customer to the order but does not make the customer the order's owner. This is subtle and important: the customer is *responsible for payment*, but the order's consistency is owned by the order itself.
- **Historical behavior.** **Permanent once true** — the archetypal permanent edge. An order was placed by a customer, and that never stops being true. Unlike WORKS_AT (bounded), PLACED has a birth and no end: the past does not release its grip on who placed an order.
- **Deletion behavior.** Retained forever — even if the customer exercises data erasure (Part 9), the skeletal fact that *an order was placed* survives; only the customer's private identity is anonymized, because the order *did happen* and the restaurant's truth must not be falsified.
- **Authority.** The restaurant (through its employees) asserts the order and its attribution; the customer is authoritative over their own identity.

### Order —CONTAINS→ Menu Item  *(canonical, realized through Order Line)*
- **Direction.** Order is subject; menu item is object — realized concretely through the Order Line node (Part 1.2, Part 2 Node 21).
- **Cardinality.** Many-to-many — an order contains many items; an item appears in countless orders.
- **Ownership.** The order **owns** its lines (ownership edge to Order Line); the line **references** the menu item (reference edge). So CONTAINS decomposes into an ownership edge (Order→Line) and a reference edge (Line→Item). This is the cleanest illustration in the whole catalogue of why a relationship-with-a-life (the line) becomes a node: the order owns *the line*, but not *the menu item*, which lives in the brand's menu.
- **Historical behavior.** Permanent — an order contained what it contained, forever, at the price captured on the line at the moment of sale (Part 2, Node 21 versioning).
- **Deletion behavior.** Retained. A voided line is a *recorded void*, its CONTAINS relationship retained with a void marker — the graph never pretends the line was never there.
- **Authority.** The restaurant's employees, bounded by role (voids and comps require authorization and are audited).

### Order —GENERATES→ Ticket · Ticket —ROUTED_TO→ Station
- **Direction / Cardinality.** Order GENERATES Ticket (one-to-many; one order may spawn several tickets). Ticket ROUTED_TO Station (many-to-many).
- **Ownership.** GENERATES is a *provenance* reference (the ticket is owned operationally by the location but traces to the order); ROUTED_TO is reference.
- **Historical behavior.** Permanent as provenance; the ticket's own life is measured in kitchen time (Part 1.9) and retained for prep-time analysis.
- **Deletion / Authority.** Retained; asserted by the kitchen.

### Order —AT→ Table · Order —WITHIN→ Shift · Order —ORIGINATED_AT→ Location
- **Direction / Cardinality.** Order is subject in each; one order references one table (optional), one shift, one location.
- **Ownership.** All **reference** edges — the order attributes itself to the table it was seated at, the shift it belongs to (business-day time — Part 1.9), and the location it originated at. None of these *own* the order.
- **Historical behavior.** Permanent — where and when an order happened is fixed truth, essential to every time- and place-based analysis.
- **Deletion / Authority.** Retained; asserted by the restaurant at the point of sale.

## 3.3 Money Edges

### Payment —SETTLES→ Order  *(canonical)*
- **Direction.** Payment is subject; order is object. The payment settles the order.
- **Cardinality.** Many-to-one *from payment's view within the aggregate*: an order may be settled by several payments (split over time), but **every payment belongs to exactly one order** (RFC-001 invariant). So: order-to-payment is one-to-many; payment-to-order is strictly one-to-one.
- **Ownership.** The payment **belongs to** the order's aggregate (Part 1.3) — this is close to an ownership edge, and the order is the consistency boundary within which payment and lines must agree (the total settled cannot exceed the total owed without a recorded overpayment).
- **Historical behavior.** **Instantaneous-then-permanent** — settlement happens at a moment (the instant the payment clears) and is then permanent truth. A later refund is a *separate* edge (REVERSES), never a mutation of SETTLES (Part 2, Node 29). "A paid order cannot become unpaid" is this edge's permanence made law.
- **Deletion behavior.** **Never removed** — SETTLES edges are the bedrock of the graph's financial truth and the input to underwriting (Part 7, Part 10). This is among the least deletable relationships in the graph.
- **Authority.** The settlement authority (processor for card, cash session for cash) is authoritative that the payment cleared; the restaurant is authoritative over which order it applies to.

### Payment —COMPRISES→ Tender · Tender —RECONCILES_TO→ Cash Session
- **Direction / Cardinality.** Payment COMPRISES Tender (one-to-many; a payment may be split across tenders). Cash tenders RECONCILE_TO a cash session (many-to-one).
- **Ownership.** COMPRISES is ownership (the payment owns its tenders — Part 2, Node 26); RECONCILES_TO is reference (the tender reconciles against the session's expected total).
- **Historical behavior.** Permanent; reconciliation discrepancies are recorded truths (Part 2, Node 9).
- **Deletion / Authority.** Retained; asserted by the settlement authority and the cash session.

### Refund —REVERSES→ Payment
- **Direction / Cardinality.** Refund is subject; payment is object. One-to-one or partial; a payment may be referenced by several partial refunds.
- **Ownership.** Reference — the refund is its own audited node (Part 2, Node 29) that *points at* the payment it reverses without altering it.
- **Historical behavior.** Permanent and *additive* — the refund is a new layer of truth; the original SETTLES edge is untouched. Both "was paid" and "was refunded" are permanently, independently true.
- **Deletion behavior.** Never removed — refunds are audit-critical.
- **Authority.** A role-authorized employee approves (audited — Part 2, Node 39); the settlement authority executes.

### Order —SUBJECT_TO→ {Discount, Tax}
- **Direction / Cardinality.** Order (or line) is subject; discount/tax is object. Many-to-many via applications.
- **Ownership.** Reference — the discount and tax are *defined* elsewhere (brand, jurisdiction) and *applied* to the order; the application is recorded on the order.
- **Historical behavior.** Permanent, at the definition version in force at the time (Part 2, Nodes 30, 31) — a past order's discount and tax are interpreted against the rules that were live *then*, never restated retroactively.
- **Deletion / Authority.** Retained; discounts asserted by role-authorized employees (comps audited), taxes governed by the jurisdiction.

## 3.4 Menu & Production Edges

### Recipe —USES→ Ingredient  *(canonical)*
- **Direction.** Recipe is subject; ingredient is object. The recipe uses the ingredient.
- **Cardinality.** Many-to-many — a recipe uses many ingredients; an ingredient is used by many recipes. The edge **carries a quantity** (how much of the ingredient the recipe uses) — a quantity that is a value object on the edge, not a node.
- **Ownership.** Reference — the recipe references ingredients it does not own; ingredients are owned by the restaurant's catalogue.
- **Historical behavior.** **Versioned and permanent** — this is the most analytically consequential edge in the catalogue. Each recipe *version* has its own USES edges with their quantities, so a sale two years ago is costed against the recipe *as it was then* (Part 2, Node 18). Collapsing this history silently falsifies every historical food-cost and margin number — the graph refuses to.
- **Deletion behavior.** Retained across all versions.
- **Authority.** The brand (canonical recipe) or location (approved variation).

### Menu Item —PRODUCED_BY→ Recipe · Menu Item —OFFERED_ON→ Menu
- **Direction / Cardinality.** Menu Item PRODUCED_BY Recipe (typically one active recipe per item, versioned). Menu Item OFFERED_ON Menu (many-to-many, each offering carrying a price).
- **Ownership.** Both reference — the item, recipe, and menu are all owned by the brand; these edges relate brand-owned definitions to each other.
- **Historical behavior.** Permanent and versioned — the *price at which an item was offered on a menu* is a dated fact (Part 2, Node 16), so historical revenue is interpreted against the price that was actually charged then.
- **Deletion / Authority.** Retained; asserted by the brand.

### Menu Item —ACCEPTS→ Modifier · Category —ORGANIZES→ Menu Item
- **Direction / Cardinality.** Menu Item ACCEPTS Modifier (many-to-many). Category ORGANIZES Menu Item (one-to-many typically).
- **Ownership.** Reference — all brand-owned definitions related to each other.
- **Historical behavior.** Permanent and versioned so past orders remain interpretable.
- **Deletion / Authority.** Retained; asserted by the brand.

## 3.5 Supply & Inventory Edges

### Supplier —SUPPLIES→ Ingredient  *(canonical)*
- **Direction.** Supplier is subject; ingredient is object. The supplier supplies the ingredient.
- **Cardinality.** Many-to-many — a supplier supplies many ingredients; an ingredient may be supplied by several suppliers (which is precisely what makes supplier comparison and substitution possible).
- **Ownership.** Reference — the supplier does not own the restaurant's ingredient node; it *is a source for* it. The restaurant owns its ingredient catalogue; the supplier is referenced as a provider.
- **Historical behavior.** Bounded and priced-over-time — the relationship is active while the restaurant buys from that supplier for that ingredient, and it carries a *price history* (what was actually paid, when — Part 2, Node 19). The price series on this edge is the raw material of both margin analysis and the "you overpay for X" benchmark (Part 7).
- **Deletion behavior.** Retained — a dropped supplier's price and reliability history is essential to procurement intelligence and to detecting "which suppliers create the most waste" (Part 7).
- **Authority.** The supplier is authoritative over its *quotes* (claims — Part 1.10); the restaurant is authoritative over what it *actually paid and received* (observations — which outrank quotes).

### Location —PLACES→ Purchase Order · Purchase Order —ORDERS→ Ingredient · Purchase Order —TO→ Supplier  *(canonical: Location PLACES Purchase Order)*
- **Direction / Cardinality.** Location PLACES Purchase Order (one-to-many). Purchase Order ORDERS Ingredient (many-to-many, with quantities and agreed prices). Purchase Order TO Supplier (many-to-one).
- **Ownership.** PLACES is ownership (the location owns its purchase orders); ORDERS and TO are references.
- **Historical behavior.** Permanent — what was ordered, from whom, at what agreed price, is fixed truth; partial receipts and reconciliation discrepancies are layered on (Part 2, Node 33).
- **Deletion / Authority.** Retained; asserted by the location, bounded by role.

### Inventory —STORED_AT→ Location  *(canonical)*
- **Direction.** Inventory (stock item) is subject; location is object. Stock is stored at the location.
- **Cardinality.** Many-to-one — many stock items (one per ingredient) are stored at a location; each stock position belongs to exactly one location.
- **Ownership.** **Ownership** — the stock position's root of responsibility is its location.
- **Historical behavior.** The stock position is the *net of its movements* (Part 2, Node 34), so this edge's "current quantity" is always a derived running sum, never an independently asserted number. Its history is the full movement series — permanent and oceanic.
- **Deletion behavior.** Retained.
- **Authority.** No party asserts the on-hand directly; it is computed from authorized stock movements (even a manual count is a *movement*, not an overwrite — the invariant "stock is the net of its movements").

### Stock Item —NET_OF→ Stock Movement · Waste —DESTROYS→ Stock
- **Direction / Cardinality.** Stock Item NET_OF Stock Movements (one-to-many; the balance is their sum). Waste DESTROYS Stock (an outbound movement).
- **Ownership.** NET_OF is a derivation relationship (the balance derives from the movements); DESTROYS is the causal relationship of a waste event to the movement it creates.
- **Historical behavior.** Movements are **immutable and append-only** (Part 2, Nodes 35, 36) — the strictest historical behavior in the catalogue. A correction is a new opposite movement, never an edit.
- **Deletion behavior.** Never removed and never edited.
- **Authority.** The authorizing process (receipt, sale, waste, count) authors the movement, bounded by role.

## 3.6 Intelligence & Governance Edges

*These edges connect the derivation and governance nodes (Part 2, Family H) to the truth they are computed from — and they carry a special constraint: **a derivation edge never confers truth on its subject.** A forecast that PREDICTS demand is not asserting that the demand is real; a benchmark that COMPARES a restaurant is not asserting a fact about any peer. The edge points *from* the derivation *to* the truth it draws on or the subject it describes, and it is one-directional in trust: truth flows into derivations, never out of them (Part 1.4, Part 8).*

### Forecast —PREDICTS→ Demand  *(canonical)*
- **Direction.** Forecast is subject; demand (a future quantity) is object. The forecast predicts the demand.
- **Cardinality.** Many-to-one over time — many forecasts (made at different times, for different horizons) predict the same future demand; each is retained so forecast quality can be measured against the eventual actual.
- **Ownership.** The forecast is owned by the steward (derived from the restaurant's and network's truth — Part 2, Node 37); PREDICTS is a *derivation* edge.
- **Historical behavior.** The forecast and its PREDICTS edge are retained *with their time and horizon*, so the graph accumulates a track record of its own predictions. **The edge never hardens into truth**: when the future arrives, the *actual* demand is a new truth node, and the forecast's edge is then EVALUATED_AGAINST it — the comparison is truth; the forecast never was.
- **Deletion behavior.** Retained (for self-evaluation).
- **Authority.** The steward authors it; **it asserts nothing into the operational record** (RFC-001: a prediction is never written as a fact).

### Benchmark —COMPARES→ Restaurant  *(canonical)*
- **Direction.** Benchmark is subject; restaurant is object. The benchmark compares the restaurant (to an anonymized peer aggregate).
- **Cardinality.** One benchmark instance compares one restaurant to a *peer set aggregate*; across the graph, every restaurant is compared by many benchmarks (metrics × time).
- **Ownership.** The benchmark is owned by the **steward** (authority over the aggregate belongs to the steward, never to any restaurant — Part 1.11); COMPARES is a derivation edge.
- **Historical behavior.** Retained per instance, so a restaurant's *trajectory against peers over years* is visible (Part 2, Node 38). Its value per instance grows with graph density — the Metcalfe flywheel (Part 10).
- **Deletion behavior.** Retained.
- **Authority.** The steward, under strict privacy: **the edge exposes the restaurant's own position and the anonymized aggregate, never any identifiable peer's particulars** (Part 9). This privacy constraint is what makes the COMPARES edge both trustworthy and lawful.

### Audit Record —ABOUT→ (any node change) · Audit Record —ATTRIBUTES→ Actor
- **Direction / Cardinality.** Audit Record ABOUT a consequential change (one-to-one with the change); ATTRIBUTES to an actor (employee/role/authority).
- **Ownership.** The audit record is owned by the graph itself (the steward) on behalf of accountability (Part 2, Node 39).
- **Historical behavior.** **Immutable and permanent** — no version, no edit, ever (the most absolute constraint in the catalogue).
- **Deletion behavior.** **Never** — subject only to the person-erasure exception, which anonymizes the actor while preserving that an authorized actor acted.
- **Authority.** Authored by the act of change itself; no one may assert or alter an audit edge independently of the change it describes.

---

*The edges are the sentences of the graph. Ownership edges build the skeleton; reference edges connect definitions to uses; the ordering, money, and supply edges carry the oceanic transactional truth; the derivation edges connect intelligence to the truth it draws on without ever letting interpretation masquerade as fact. Every edge is directional, every edge has a cardinality, every edge knows whether it owns or merely references, and no edge is ever destroyed. With nodes and edges defined, the next part shows how they come into being: every domain event is a change to the graph.*

---

# PART 4 — EVENT TO GRAPH

Nodes and edges are the *structure* of the graph. But the graph is not built by declaring structure; it is built by *things happening in the restaurant*. Every meaningful happening in the restaurant world is a **domain event** (RFC-001, Part 5), and:

> **Every domain event is a change to the graph. The graph is nothing more, and nothing less, than the accumulated effect of every event that ever occurred — applied in order, never undone.**

This is the deepest operational truth in the document. The graph is not a picture that someone maintains; it is a *consequence* — the sum of all events. State is not stored and edited; state is what you get when you apply every event in sequence (Part 1.7). An event, once it has occurred and been observed, changes the graph forever: it creates nodes, ends or begins edges, and layers new truth on top of old. It never reaches back and edits what earlier events established — corrections are themselves new events (Part 1.4, append-only).

Three laws govern how events touch the graph, stated once for all families:

> **Events create and extend; they never erase.** An event may create nodes, add edges, end the *validity interval* of an edge, or supersede a prior value going forward — but it never deletes a node, never removes an edge, and never rewrites a past fact. "Cancellation," "void," "refund," "closure" are all *new events layered on*, not erasures.

> **Every event carries its times.** Each event knows its event time (when it belongs to), its observation time (when it was noticed — Part 1.5), and its business day (Part 1.9). An event created at the edge (offline) carries its true event time even though it joins the graph later.

> **Every consequential event carries its author and authority.** Who caused it, under what role, with what justification (Part 1.11) — recorded as an audit record (Part 2, Node 39) inseparable from the event itself.

The rest of this part walks the event families. For each, it names the representative events and traces exactly what they do to the graph — which nodes are born, which edges are drawn, which truths are layered. This is the Rosetta Stone between RFC-001's event catalogue and the graph: it shows that *the ontology's events and the graph's mutations are the same thing seen from two sides.*

## 4.1 The Ordering Family

This is the highest-volume event family and the one most often created at the edge.

**OrderOpened.** A guest is seated (or a delivery order arrives) and an order begins.
- *Creates:* an **Order** node (identity born at the edge — Part 1.8, so it is real even offline).
- *Draws edges:* Order —ORIGINATED_AT→ Location; Order —WITHIN→ Shift (fixing its business day — Part 1.9); Customer —PLACED→ Order (if the payer is known; otherwise an anonymous customer); Order —EXPERIENCED_BY→ Guest (if known); Order —AT→ Table (for dine-in).
- *Layers:* nothing yet owed — the order is open and empty. Its whole future is a sequence of further events.
- *Author:* the employee who opened it (or the channel, for delivery), recorded.

**OrderLineAdded / OrderLineModified.** An item is rung onto the order.
- *Creates:* an **Order Line** node, owned by the order.
- *Draws edges:* Order —CONTAINS→ (Line —FOR→ Menu Item); Line —CARRIES→ Modifier(s); Line —ROUTES_TO→ Station (via the ticket).
- *Layers (critically):* the line **captures the price in force now** and the **recipe version in force now** (Part 2, Nodes 16, 18, 21) — so this line's commercial and cost truth is frozen against later menu changes. This is the single most important "layer" in the whole part, because it is what makes historical margin honest.
- *A modification* is a new event layering a change onto the line (new quantity, added modifier) — the prior state is retained in the line's history.

**CourseFired / TicketFired.** The kitchen is told to make something.
- *Creates:* a **Ticket** node (and, for paced service, groups lines into a **Course**).
- *Draws edges:* Order —GENERATES→ Ticket; Ticket —ROUTED_TO→ Station(s); Ticket —CONTAINS→ the items to make.
- *Layers:* the ticket's **kitchen-time clock starts** (Part 1.9) — its elapsed-time life begins, the substance of later prep-time analysis.

**ItemPrepared / TicketReady / OrderServed.** The food is made and delivered.
- *Layers:* state transitions on the ticket and lines, each with its elapsed kitchen time recorded (how long the guest waited). No new commercial truth; rich operational truth.

**OrderLineVoided / ItemComped.** An item is removed or given free.
- *Layers:* a **recorded void or comp** on the line (never a deletion — the line and its CONTAINS edge remain, marked). Requires role authorization; **creates an audit record** naming the authorizer and reason. This is a classic abuse vector, so the graph makes the void a *visible permanent truth*, not an erasure.

## 4.2 The Settlement Family

Where owed becomes paid — the highest-trust events (Part 1.10).

**PaymentInitiated / PaymentAuthorized / PaymentSettled.** The order is paid.
- *Creates:* a **Payment** node (edge-born, real even offline); one or more **Tender** nodes.
- *Draws edges:* Payment —SETTLES→ Order (the canonical settlement edge, instantaneous-then-permanent); Payment —COMPRISES→ Tender(s); cash Tender —RECONCILES_TO→ Cash Session.
- *Layers:* the order transitions toward Settled. Once Settled, the invariant locks: **a paid order cannot become unpaid** (RFC-001). The payment feeds directly into the cash-flow truth that underwriting draws on (Part 7, Part 10).
- *Author:* the settlement authority (processor/cash session) confirms clearing; the employee who took it is recorded.

**ReceiptIssued.** The guest is given proof.
- *Creates:* a **Receipt** node.
- *Draws edges:* Receipt —EVIDENCES→ Order and Payment; Receipt —ITEMIZES→ Lines; Receipt —STATES→ Taxes and Discounts. For fiscal jurisdictions, it *may satisfy a compliance obligation* (Government projection — Part 6), which is exactly the wedge that forces sales-truth into the graph (North Star).

**RefundRequested / RefundApproved / RefundExecuted.** Money goes back.
- *Creates:* a **Refund** node.
- *Draws edges:* Refund —REVERSES→ Payment (partially or wholly); Refund —AGAINST→ Order.
- *Layers:* net revenue is reduced *by a new layered truth* — the original SETTLES edge is untouched, so "was paid" and "was refunded" are both permanently true (Part 2, Node 29). Requires role authorization; **creates an audit record**. Anomalous refund frequency later feeds anomaly detection (Part 8).

**InvoiceIssued / InvoicePaid / InvoiceAged.** The account-customer path.
- *Creates:* an **Invoice** node.
- *Draws edges:* Invoice —ISSUED_TO→ Customer; Invoice —BILLS→ Order(s); later Payment —SETTLES→ (the invoice's orders). Aging is a first-class layered fact and a credit signal (Part 7).

**CashSessionOpened / CashSessionClosed / CashSessionReconciled.** Cash accountability.
- *Creates:* a **Cash Session** node (opened with a declared float).
- *Layers:* cash tenders accumulate against it; at close, a count is declared and **reconciled** against expected. A discrepancy is a *recorded truth* (Part 2, Node 9), never silently absorbed — with an audit record.

## 4.3 The Menu & Product Family

Lower-volume but high-consequence events, because they change how *future* orders will be interpreted — and, through versioning, must never change how *past* orders are interpreted.

**MenuItemCreated / PriceChanged / ItemDiscontinued.**
- *Creates / layers:* a **Menu Item** node (on creation); a **new dated price fact** on the item's OFFERED_ON edge (on price change — never an overwrite, so past orders keep their historical price — Part 2, Node 16); a **retirement** marker (on discontinuation — the item and all its history remain).
- *Draws edges:* Item —PRODUCED_BY→ Recipe; Item —OFFERED_ON→ Menu; Item —ACCEPTS→ Modifiers; Category —ORGANIZES→ Item.
- *Author:* the brand (canonical) or location (local), recorded — a price change is an audited fact (who changed the price, when).

**RecipeCreated / RecipeReformulated.**
- *Creates / layers:* a **Recipe** node; on reformulation, a **new recipe version** with its own USES edges and quantities (Part 3.4). The prior version is retained so historical sales cost correctly against the recipe *as it was then*. This is the versioning discipline that keeps every historical margin honest.

**ItemEightySixed / ItemAvailabilityRestored.** Temporary unavailability.
- *Layers:* an operational availability state on the item (distinct from discontinuation). The 86 is itself informative truth (it correlates with stock-outs and demand — Part 7).

## 4.4 The Staffing Family

**ShiftScheduled / ShiftOpened / ShiftClosed / ShiftReconciled.**
- *Creates:* a **Shift** node (a bounded interval fixing a business day — Part 1.9).
- *Draws edges:* Shift —BELONGS_TO→ Location; Employee —WORKS→ Shift; Shift —OPERATES→ Station(s).
- *Layers:* labor cost accrues over the interval; at close, sales and labor are attributed to the shift's business day; reconciliation settles it.

**EmployeeHired / EmployeeAssigned / EmployeePromoted / EmployeeDeparted.**
- *Creates:* an **Employee** node (on hire — the person's permanent identity, Part 2 Node 5).
- *Draws / ends edges:* Employee —WORKS_AT→ Location (a **bounded interval** that begins on assignment and *ends* — not deletes — on departure or transfer, Part 3.1); Employee —HOLDS→ Role (a bounded interval that ends and re-begins on promotion, so past actions are judged against the authority held *then*).
- *Layers:* status transitions retained; a departed employee is retired, their history permanent.

**ClockIn / ClockOut.** Attendance within a shift.
- *Layers:* dated attendance facts within the shift's history — the raw material of labor cost and of "which locations have unstable staffing" (Part 7).

## 4.5 The Supply & Inventory Family

**PurchaseOrderPlaced / GoodsReceived / PurchaseOrderReconciled.**
- *Creates:* a **Purchase Order** node.
- *Draws edges:* Location —PLACES→ Purchase Order; Purchase Order —TO→ Supplier; Purchase Order —ORDERS→ Ingredient(s) with quantities and agreed prices.
- *On receipt:* creates inbound **Stock Movement(s)** that increase the relevant **Stock Item** positions; records the *price actually paid* on the Supplier —SUPPLIES→ Ingredient price history (an observation that outranks the supplier's quote — Part 1.10). Reconciliation records any ordered-vs-received-vs-billed discrepancy as truth.

**StockConsumed (on sale).** The quiet, oceanic event.
- *Layers:* every settled sale, through the sold item's **recipe version at time of sale**, generates outbound **Stock Movements** depleting the consumed ingredients' Stock Items. This is how "stock is the exact net of its movements" (RFC-001 invariant) stays true automatically: sales *are* stock movements. No one asserts a new balance; the balance follows from the movement.

**StockCounted (physical count).**
- *Layers:* a manual count is recorded as an **adjustment Stock Movement** (never a silent overwrite of the balance — Part 2, Node 34). Even human counting respects "stock is the net of its movements": the count creates a movement equal to the difference, with an author and reason.

**WasteRecorded.**
- *Creates:* a **Waste Event** node and a corresponding outbound **Stock Movement**.
- *Draws edges:* Waste —DESTROYS→ Stock; Waste —OF→ Ingredient; Waste —ATTRIBUTED→ a cause; possibly Waste —IMPLICATES→ Supplier (short shelf life). Author recorded — waste hidden is margin lied about; the graph refuses to let it vanish (Part 2, Node 36).

**StockTransferred (between locations).**
- *Layers:* a paired outbound movement at the source and inbound movement at the destination — two movements, one transfer, both retained, keeping both locations' nets exact.

## 4.6 The Guest & Reservation Family

**GuestRecognized / GuestConsentGranted / GuestConsentWithdrawn.**
- *Creates / layers:* a **Guest** node transitions from anonymous to known; consent state is a dated, authoritative fact *owned by the guest* (Part 2, Node 10; Part 9). Consent withdrawal is honored as a governing truth over what may be derived about the guest.

**LoyaltyEnrolled / LoyaltyAccrued / LoyaltyRedeemed.**
- *Creates:* a **Loyalty Account** node.
- *Draws edges:* Loyalty —HELD_BY→ Guest; Loyalty —OFFERED_BY→ Restaurant/Brand; Loyalty —ACCRUES→ from orders; redemption creates a Discount application (Part 4.2). The *accrual history* is the substance of "which guests are becoming loyal" (Part 7).

**ReservationRequested / ReservationConfirmed / GuestSeated / NoShowRecorded.**
- *Creates:* a **Reservation** node (a promise about a future time — Part 2, Node 13).
- *Draws edges:* Reservation —MADE_BY→ Guest; Reservation —AT→ Location; on seating, Reservation —ASSIGNED_TO→ Table and becomes an Order (OrderOpened). A **NoShow** is a recorded truth with consequences (it informs reliability and demand forecasting) — never a silent nothing.

## 4.7 The Governance & Intelligence Family

*These events are different: the first two are the graph recording facts about itself; the last two are the graph producing derivations that never become truth (Part 1.4, Part 8).*

**AnyConsequentialChange → AuditRecorded.**
- *Creates:* an **Audit Record** node, inseparable from the change it describes (Part 2, Node 39).
- *Draws edges:* Audit —ABOUT→ the change; Audit —ATTRIBUTES→ the actor; timestamped in event and wall-clock time; justified with a reason. Immutable, never deleted — the most rigid event in the graph. Every void, comp, refund, price change, override, and reconciliation discrepancy triggers one.

**ReportGenerated.**
- *Creates:* a **Report** node — a projection *frozen* at a moment and kept as evidence (Part 2, Node 40). It must remain re-derivable from the graph (Part 1.6); it never becomes a source of truth, only a record that *this was shown and relied upon*.

**ForecastGenerated.**
- *Creates:* a **Forecast** node (Part 2, Node 37); Forecast —PREDICTS→ Demand.
- *Constraint:* **it writes nothing into the operational record as fact** (RFC-001 invariant). It draws on historical truth and network patterns; it informs decisions; it is retained with its time and horizon so its accuracy can later be measured against the actual — but it is never truth, and the graph enforces that boundary at the moment of creation.

**BenchmarkComputed.**
- *Creates:* a **Benchmark** node (Part 2, Node 38); Benchmark —COMPARES→ Restaurant.
- *Constraint:* computed from many restaurants' *anonymized* truth under strict privacy; it exposes the subject's own position and the aggregate, **never an identifiable peer's particulars** (Part 9). It asserts nothing about any peer as fact; it is a statement of relative position, retained per instance so trajectories are visible.

---

*Every family tells the same story: a thing happens in the restaurant; it is observed; and its observation creates nodes, draws edges, and layers truth — in order, forever, without erasing what came before. The ontology's events (RFC-001) and the graph's mutations (RFC-002) are one and the same, seen from two sides: the event is the happening; the graph change is its permanent trace. Nothing enters the graph except through an event, and no event ever leaves. This is why the graph is the complete, ordered, permanent record of the restaurant economy — and the next part shows how that record survives every upheaval the real world throws at it.*

---

# PART 5 — GRAPH EVOLUTION

The restaurant economy does not hold still. Restaurants open, close, merge, split, sell, rebrand, and franchise. People are recorded twice and turn out to be one. Two supplier records resolve to one supplier. A single-location shop becomes a forty-branch chain; a chain sells three branches to a competitor. The graph must absorb every one of these upheavals **without ever losing or falsifying a single past truth.** This is the hardest requirement in the whole document, because it is where the temptation to "just fix the data" is strongest — and where yielding to that temptation would destroy the one thing the graph is for.

The governing principle:

> **The graph evolves the way history evolves: only forward, only by addition. Every structural change to the world is a new event layered on top of an unbroken past. The graph never rewrites what was true; it records what changed, and keeps both.**

## 5.1 How nodes evolve

A node evolves by accumulating dated layers of change (Standing Versioning Law, Part 2). Its identity is fixed at birth and never changes (Part 1.8); everything else about it — its name, its price, its status, its relationships — is a series of facts each true of its own time. "The current state" of a node is the latest layer, computed by reading its history forward (Part 1.7).

This means a node is never "updated" in the sense of losing its former self. When a menu item's price changes, the old price does not vanish; it becomes *the price that was true until this date*, and the new price becomes *the price true from this date*. When an employee is promoted, the old role does not disappear; it becomes *the role held until this date*. The node is the whole rope of its history, not the frayed end you can currently see. This is what lets the graph answer, years later, "what did this dish cost the guest on that specific Tuesday" — a question that is unanswerable in any system that overwrites.

## 5.2 How edges evolve

An edge evolves by gaining a *validity interval* — a start, and sometimes an end (Part 3, Standing Edge Law). Permanent edges (Customer PLACED Order) begin and never end. Bounded edges (Employee WORKS_AT Location) begin and end, and the interval *is* the fact. When a bounded relationship changes — an employee transfers locations — the graph does not move the edge; it *ends* the old edge (WORKS_AT location A, until this date) and *begins* a new one (WORKS_AT location B, from this date). Both are retained. The employee's whole working lineage is the set of all their WORKS_AT intervals, in order.

An edge is never deleted, even when a node it joins is retired. A closed location's OWNS edge from its restaurant remains — it *was* owned; the edge simply has an end date matching the closure. This is why the graph can reconstruct not just what the world looks like now, but what it looked like at any past moment: it reads every edge's validity interval as of that moment.

## 5.3 How identities merge

Sometimes the world reveals that two nodes we believed distinct are in fact one — the same guest recorded under two phone numbers, two supplier records for one supplier, a duplicate employee from a re-hire that was not recognized. This is not an error to be silently cleaned; it is a **discovery to be recorded**.

A **merge** is a first-class, governed event (Part 1.8), and it obeys strict rules:

- **The merge is recorded, not hidden.** The graph does not quietly overwrite one node with the other. It records that, as of this moment, these two identities are understood to be the same, and it names who determined this and on what basis (an audit record — Part 2, Node 39).
- **Both histories are preserved and unified.** Everything each node was involved in — every order, every visit, every edge — is retained and now understood as belonging to the single merged identity. No history is lost in a merge; history is *joined*.
- **The merge is reversible.** Because the merge is a recorded event layered on top (not an erasure of the two originals), it can be *un-merged* if the determination turns out wrong. The graph never burns the bridge back. This reversibility is only possible because the merge added information rather than destroying it — the deepest reason the append-only law matters.
- **The fact of prior separateness survives.** The graph never loses the truth that these were once recorded as two. That itself is data (it reveals how duplicates arise and helps prevent them).

Identity merges are the single clearest demonstration of why the graph never deletes: a system that overwrites cannot un-merge, cannot audit the merge, and cannot learn from the duplication. A graph that layers can do all three.

## 5.4 How history survives

History survives because it is never a casualty of any evolution. Every mechanism above — node versioning, edge intervals, recorded merges — is *designed* to make change additive. The result is a standing guarantee:

> **Any past state of the graph is perfectly reconstructable. Pick any moment in the graph's life, and the graph can show you exactly what was true then — which restaurants existed, who worked where, what things cost, what was owed — because nothing that was true then has been removed; it has only been added to.**

This is not a feature; it is the substance of the asset (Part 10). History is accumulated time, and accumulated time is the one thing capital cannot buy (North Star). Every evolution mechanism exists to protect it.

## 5.5 How deleted restaurants remain historically valid

A restaurant closes. In a naive system, its data becomes an embarrassment — stale rows someone eventually purges. In the graph, a closed restaurant is a **retired node with a complete, permanently valid history** (Part 2, Node 1; Standing Deletion Law).

Everything it ever did remains true: every sale it made, every cost it paid, every employee it hired, every price it charged. Its retirement is a new truth (closed, as of this date), layered on top of a decade of operating truth that is *not* diminished by the closure. Years later, the graph can still answer "how did this restaurant perform in its third year," "what did closed restaurants in this segment have in common before they closed" — the second question being one of the most valuable the graph can answer (a leading indicator of failure that helps *living* restaurants — Part 7, Part 8). A closed restaurant is not dead weight; it is a permanently-valid data point, and often a more instructive one than a thriving peer, because *its ending is itself a lesson.*

This is why the graph gets *more* valuable as restaurants close, not less: every ending adds a completed longitudinal story that no competitor's snapshot of *currently-open* restaurants can match.

## 5.6 How mergers occur

Two restaurants become one — an acquisition, a consolidation. This is not the same as an identity merge (5.3, which corrects a duplicate); it is a *real-world combination of two genuinely-distinct businesses*, and the graph records it as exactly that.

- **Both restaurants keep their full, distinct histories.** The graph does not retroactively pretend they were always one. Restaurant A's decade and Restaurant B's decade remain separately true, each attributed to the business that lived it.
- **A combination event is recorded** as of the merger date: from this moment, these locations, staff, and operations fall under the combined entity. New activity attributes to the combined business; old activity stays attributed to whichever predecessor lived it.
- **The lineage is permanent.** The graph always knows that the combined business *descends from* A and B, and can show the combined trajectory (both histories unified going forward) or the separate ancestries (each predecessor's story) as the question requires.

This dual view — combined forward, distinct backward — is only possible because the graph layers rather than overwrites. It lets a lender underwrite the combined entity against the *unified* cash-flow history while an analyst studies each predecessor's *separate* pre-merger trajectory. Both are true; the graph holds both.

## 5.7 How franchises split

The inverse: one brand fragments across many independently-operated restaurants (franchising), or a company divests locations to new owners. The graph handles the split through the ownership/reference distinction it was built on (Part 1.3, Part 3.1).

- **The brand's identity persists** above the split (Part 2, Node 2). Franchisees *reference* (SERVED_AT) the brand; each franchisee *owns* its own operating truth. So the brand can span a hundred franchisee restaurants while each franchisee's sales, costs, and staff remain private to that franchisee (Part 9).
- **A divestiture ends one OWNS edge and begins another.** When a chain sells three locations, each location's OWNS edge from the seller *ends* as of the sale, and a new OWNS edge from the buyer *begins*. The location keeps its identity and its entire pre-sale history; that history stays attributed to the seller who lived it, while post-sale activity attributes to the buyer.
- **The franchise standards flow down as reference, the operating truth flows up as aggregate.** The franchisor sees brand-level aggregates (how the brand performs across franchisees) without seeing any single franchisee's private books beyond what the franchise agreement authorizes — the same steward-of-aggregate boundary that governs benchmarks (Part 1.11, Part 9).

## 5.8 How brands expand

A restaurant grows — one location to many, one brand to several, one city to a region. Expansion is the *happy* evolution, and the graph absorbs it as pure addition: new Location nodes, new Brand nodes, new SERVED_AT and OWNS edges, new oceanic transactional volume. Nothing about expansion requires rewriting the past; the small shop's early history remains the foundation of the chain's trajectory. The graph that watched a restaurant grow from one location to forty holds the *entire growth story* — and that longitudinal story is precisely what lets it underwrite the *next* restaurant's expansion against a hundred thousand peers who grew (or failed to grow) before it (Part 7, Part 10).

---

*Every upheaval the real world produces — merge, split, sale, closure, duplication, expansion — the graph absorbs the same way: forward, by addition, never by erasure. This is not a coincidence of design; it is the direct consequence of the first principles (truth is durable, history is append-only, identity is permanent, no node or edge is ever destroyed). The graph evolves exactly as reality evolves, and because it never throws away the past, it becomes the one place where the *entire* history of the regional restaurant economy is legible. The next part shows how that vast, permanent record is made useful without ever being mistaken for the record itself.*

---

# PART 6 — GRAPH PROJECTIONS

The graph holds everything, related to everything, forever. But no one consumes "everything." A line cook drowning in a Friday rush does not want the ontology; they want to know *what to cook next*. An owner does not want ten million events; they want to know *whether the business is healthy*. A lender wants years of cash flow; a supplier wants next week's demand; a regulator wants this quarter's tax. Each of these is a **projection**: the same underlying truth, filtered, arranged, and summarized into the shape one audience needs (Part 1.6).

The governing law, restated because it is the point of the entire part:

> **Every projection is disposable. The graph is permanent. Any projection can be discarded and rebuilt from the graph, because it holds no truth of its own — only a rearrangement of truth that lives in the graph. And no projection may ever become the sole home of a fact; the moment it does, it has stopped being a projection and become an unauthorized second source of truth — a corruption.**

This law is liberating and strict at once. Liberating: the company can build, kill, and reinvent views without fear, because none of them are load-bearing for truth — a broken dashboard, a redesigned report, a retired AI lens costs nothing, because the truth is safe in the graph and any view can be rebuilt from it. Strict: a view that starts *holding* truth the graph lacks has broken the law and endangered the asset.

What follows are the canonical projections. Each is a lens on the one graph; none is the graph.

## 6.1 The Operational View

**Audience:** the front line — servers, cashiers, hosts. **Question it answers:** *what is happening right now, and what do I do next?*

The operational view is the thinnest, fastest, most *present-tense* projection. It shows open orders, their states, table status, what is 86'd, what is waiting. It lives almost entirely in the now, caring little for history. It is the projection through which most *observation* enters the graph (Part 1.5) — the front line acts, and their actions become events. Its defining property is urgency: it must reflect the latest truth immediately, because the people using it are steering the restaurant in real time. It is utterly disposable — rebuilt continuously from the flow of events — and holds no truth the graph does not.

## 6.2 The Kitchen View

**Audience:** the line, the expo, the kitchen manager. **Question:** *what must be made, in what order, and are we falling behind?*

The kitchen view is the projection of tickets and courses arranged by *kitchen time* (Part 1.9) — elapsed durations, not clock positions. It shows fired tickets, their ages, which station is backed up, what is at risk of a long wait. It is where the graph's operational truth becomes a live production instrument. Like the operational view it is present-tense and disposable; unlike it, it is organized entirely around *elapsed time*, because the kitchen's reality is duration, not commerce.

## 6.3 The Owner View

**Audience:** the restaurant owner or operator. **Question:** *is my business healthy, and where is it leaking?*

The owner view widens and slows down. It projects sales trends, labor cost against sales, food cost, waste, top and bottom performers, comps and voids, cash discrepancies — the health of the business over days and weeks and months, always in *business-day time* (Part 1.9) so the numbers match how the restaurant actually operates. It is the projection where the graph's *depth* (North Star) pays off: an owner running their whole business on Mezze sees their true P&L in one lens, because the graph holds sales *and* costs *and* labor *and* supply. It is disposable and re-derivable; it never holds a number the graph cannot regenerate.

## 6.4 The Finance View

**Audience:** the bookkeeper, accountant, or finance function. **Question:** *what is recognized, owed, remitted, and reconciled?*

The finance view projects the graph into *accounting time* (Part 1.9) — recognizing revenue in periods, aging invoices, tracking tax owed and remitted, reconciling cash sessions, and freezing the figures that get filed (as Report nodes — Part 2, Node 40). It is the most rule-bound projection, because the world it serves is legally exact. Crucially, even here the law holds: the finance view *presents* truth in accounting shape, but the truth lives in the graph's payments, invoices, taxes, and movements; the view re-derives it. A filed report is *frozen and kept* as evidence, but it remains re-derivable from the graph — it records that a figure was shown, it is not the figure's only home.

## 6.5 The Analytics View

**Audience:** the operator or the steward, looking back to understand. **Question:** *what patterns, over time, explain performance?*

The analytics view is the retrospective lens — the projection that reads deep history to surface trends, mixes, correlations, and comparisons. It is where menu-mix analysis, day-part patterns, retention curves, and cohort behavior live. It draws on the graph's *depth over time*, and its value grows with the graph's history (Part 10). It is disposable and re-derivable — an analytics view can be reinvented monthly without touching a single truth. It presents *derivations* (Part 8), and it presents them *as* derivations, never letting a computed trend masquerade as a recorded fact.

## 6.6 The Forecast View

**Audience:** the operator planning ahead. **Question:** *what is likely to happen, so I can prepare?*

The forecast view projects the graph *forward* — expected demand, staffing needs, stock depletion (Part 2, Node 37). It is unique among projections in that it shows *predictions, not truth*, and it is scrupulously honest about the difference: everything in it is marked as forecast, carries no truth-trust (Part 1.10), and writes nothing back into the operational record as fact (RFC-001 invariant). It is the projection most easily abused — the temptation to treat a confident forecast as a fact is constant — and the law that protects against that abuse is stated in the view itself: *a prediction is never truth.* It is disposable in the extreme: forecasts are regenerated continuously, and each is retained only so its accuracy can later be measured against what actually happened.

## 6.7 The Supplier View

**Audience:** suppliers, and the operator managing procurement. **Question:** *what will be needed, and how is the supply relationship performing?*

The supplier view projects the procurement side of the graph — purchase orders, deliveries, price histories, reliability, and, at scale, *aggregated demand* across restaurants (the liquidity engine — North Star). To an individual operator it shows their own supplier performance and price trends. To the network it becomes the demand-aggregation lens that turns many restaurants' needs into buying power — always under the privacy rule that no restaurant's specific deal is exposed to another (Part 9). It is disposable; the truth (what was ordered, received, paid) lives in the graph's purchase orders and movements.

## 6.8 The Government View

**Audience:** tax and regulatory authorities. **Question:** *is this restaurant compliant, and what does it owe?*

The government view projects exactly — and *only* — what an authority is entitled to see: fiscal receipts, tax computed and remitted, the compliance artifacts a jurisdiction requires (Part 2, Nodes 27, 31). It is the narrowest-authority projection: it exposes what the law mandates and nothing more, never a restaurant's private operating detail beyond the regulatory requirement. It is also the projection behind the compliance *wedge* (North Star): because a jurisdiction requires the restaurant's sales-truth in a compliant form, the restaurant must put that truth into the graph — the fastest way the graph acquires dense, real nodes. The view is disposable; the truth lives in the graph, and the government view merely re-derives the mandated slice.

## 6.9 The AI View

**Audience:** every intelligent capability Mezze offers — recommendations, anomaly alerts, optimizations. **Question:** *what does the truth imply, and what should be done?*

The AI view is the projection that turns the graph into decisions (Part 8). It is emphatically *a lens, not the asset* (North Star): the intelligence is grounded in the graph's ground truth, and its outputs are *derivations that never become truth* (Part 1.4). The AI view may recommend, alert, rank, and predict — and every one of its outputs is marked as derived, carries only the trust of its inputs and method, and is forbidden from writing itself back into the record as fact. It is the most disposable projection of all: models change, methods improve, whole approaches are replaced — and the graph beneath is untouched, so every generation of intelligence is rebuilt on the same permanent truth. This is the deepest reason AI is *excluded* as an asset yet the graph is the answer: AI is a replaceable lens; the graph it looks through is not (North Star, Part 10).

---

*Nine projections, one graph. The line cook's urgent now and the lender's decade of cash flow are the same truth, shaped for different eyes. Every one of them is disposable — build them, kill them, reinvent them freely — because not one holds a truth the graph lacks. This is the discipline that keeps the graph the single source of truth: the views serve the graph and re-derive from it; they never rule it and never replace it. The permanence is in the graph; the usefulness is in the projections; and the law that separates them is what keeps the whole structure honest. The next part asks what questions we put to this structure — the canonical questions that make the graph worth having.*

---

# PART 7 — GRAPH QUERIES

A graph is worth exactly what can be asked of it. This part describes the **canonical questions** — the questions the Operating Graph exists to answer, stated in the language of the restaurant world and not of any technology (no mechanism, no query language — Part 0). These are not example reports; they are the *reasons the graph is built the way it is*. Every node, edge, and versioning discipline in the earlier parts exists so that these questions can be answered *truthfully and longitudinally*, and most of them are questions that **no single restaurant can answer about itself** — which is exactly where the graph's value lives.

A framing distinction runs through the whole part. Questions come in two kinds:

- **Introspective questions** — a restaurant asking about *itself*, answerable from its own private truth. Valuable, and the table stakes.
- **Network questions** — a restaurant (or the steward) asking a question that can *only* be answered by standing one restaurant against many. These are the questions the graph exists for, because they are un-askable at one restaurant and un-buyable by any competitor (Part 10). They are answered under strict privacy — the asker sees their own position and the anonymized aggregate, never a peer's particulars (Part 9).

The canonical questions follow, each traced to the graph structure that answers it.

## 7.1 Which recipes are least profitable?

*Introspective, deepened by the network.* For each menu item, the graph holds what it *earned* (the price captured on every order line at the moment of sale — Part 2, Node 21) and what it *cost* (the recipe version in force at that sale, its USES edges and ingredient quantities, priced at what was actually paid — Parts 2, 3.4). The gap is margin, and because both sides are versioned in time, the graph computes *true historical margin* — not today's price against today's cost, but each sale against the reality of its own day. Least-profitable items surface as those whose earned-minus-cost is thin or negative across real sales. The network deepens it: *is this item unprofitable everywhere, or only here?* — a question only the graph can answer, and one that tells the operator whether the problem is the dish or their execution of it.

## 7.2 Which suppliers create the most waste?

*Network-flavored.* The graph links suppliers to the ingredients they supply (Part 3.5), those ingredients to the waste events that destroy them (Part 2, Node 36), and waste events to their causes. When a supplier's deliveries correlate with short-shelf-life spoilage across purchase cycles — and, across the network, correlate with waste at *many* restaurants — the supplier is implicated not by one operator's grudge but by a pattern in the ground truth. This is a question a single restaurant guesses at and the graph *knows*, because it has watched the same supplier's goods across a hundred kitchens.

## 7.3 Which restaurants behave similarly?

*Pure network.* Un-askable at one restaurant by definition. The graph holds each restaurant's operating signature — menu mix, day-part pattern, labor structure, price positioning, growth trajectory — over years. Similarity is the recognition of restaurants whose signatures move alike. This is the foundation beneath benchmarking (Part 2, Node 38): to tell a restaurant "you overpay relative to your peers," the graph must first know *who its peers are* — restaurants of like concept, size, and geography that behave similarly. Similarity is computed over anonymized signatures; a restaurant learns its *cohort*, never the identities within it (Part 9).

## 7.4 Which promotions improved retention?

*Introspective, sharpened by the network.* The graph holds every discount and promotion application (Part 2, Node 30), the orders they touched, the guests who received them (Part 2, Node 10), and — crucially, over time — whether those guests *came back*. Retention is a longitudinal fact: it can only be seen by watching guests across months, which the graph does and a snapshot cannot. So the graph can distinguish a promotion that bought a one-time spike from one that built returning guests — and, across the network, tell which *kinds* of promotion build retention in which *kinds* of restaurant. This is the difference between discounting that grows a business and discounting that quietly bleeds it.

## 7.5 Which locations have unstable staffing?

*Introspective.* The graph holds every shift, every WORKS_AT interval, every clock-in and clock-out (Parts 2, 3.1, 4.4). Staffing instability — high turnover, chronic understaffing at peak, erratic scheduling — is a pattern across these bounded intervals over time. Because WORKS_AT edges *end* rather than delete (Part 3.1), the graph retains the full churn history even of departed staff, which is exactly what makes instability visible: a location that cannot keep people shows it in the accumulation of short, ended intervals. Unstable staffing is also a *leading indicator* the network can act on — it often precedes decline (Part 8).

## 7.6 Which ingredients create margin loss?

*Introspective, deepened by the network.* Margin loss hides in ingredients whose *cost rose* while the menu prices they feed *held* — a squeeze invisible unless both are tracked in time, which the graph does (ingredient price history on the SUPPLIES edge, Part 3.5; menu prices on the OFFERED_ON edge, Part 2 Node 16). The graph traces each ingredient forward through the recipes that use it to the items it feeds, and flags where rising cost is silently eating margin the operator has not repriced for. Across the network, it answers the sharper question: *is this ingredient's cost rising for everyone (a market move) or only for me (a bad supplier)?* — which tells the operator whether to reprice or to renegotiate.

## 7.7 Which restaurants qualify for financing?

*Pure network — the graph's most valuable question.* This is the question the entire asset thesis turns on (North Star, Part 10). A blind lender sees an applicant's stated numbers; the graph sees a restaurant's *actual* cash flow (from settled payments — the highest-trust truth, Part 1.10), its cost trajectory, its stability, and — decisively — how its pattern compares to the hundreds of similar restaurants the graph has *already watched succeed or fail* (5.5, 7.3). Qualification is not a credit score bought from a bureau; it is the recognition that this restaurant's ground-truth pattern resembles restaurants that repaid, and diverges from those that defaulted. No competitor can answer this without the graph's history, because the answer *is* the history. This is where the graph stops being analytics and becomes the credit model itself.

## 7.8 Which stores should receive inventory first?

*Network-flavored, operational.* When supply is constrained — a shortage, a delivery delay, a promotion drawing down stock faster than expected — the graph knows each location's current stock net (Part 2, Node 34), its forecasted depletion (Part 2, Node 37), and its demand pattern. Prioritization is the ranking of locations by urgency of need against likelihood of sale — send stock where it will run out soonest and sell fastest. For a multi-location operator this is introspective; for the network's demand-aggregation and supplier-clearing role (North Star liquidity), it becomes a question the graph answers across restaurants, allocating constrained supply to where it does the most good.

## 7.9 Which guests are becoming loyal?

*Introspective, longitudinal.* Loyalty is not a state; it is a *trajectory* — a guest whose visits are growing more frequent, whose spend is deepening, whose relationship is warming (Part 2, Nodes 10, 12). The graph sees this only because it watches guests over time and never collapses their accrual history to a current balance (Part 2, Node 12 versioning). So it can distinguish a guest who *is* loyal (a steady regular) from one who is *becoming* loyal (an accelerating newcomer worth investing in) from one who is *slipping away* (a former regular going quiet — the most actionable of the three). This is a question about *change over time*, and change over time is precisely what the graph, alone, retains.

## 7.10 The shape of every canonical question

Step back and the pattern is unmistakable. Every question above is a question about **relationships across time**, and most are questions about **one restaurant against many**. The introspective ones (least-profitable recipes, margin-losing ingredients, unstable staffing, becoming-loyal guests) require the graph's *depth over time* — they are unanswerable in any system that overwrites the past. The network ones (similar restaurants, financing qualification, waste-causing suppliers, promotion effectiveness at scale, inventory prioritization) require the graph's *breadth across restaurants* — they are unanswerable by any single restaurant and un-buyable by any competitor, because the answer *is* the accumulated ground truth of the whole network (Part 10).

This is why the graph is built as it is: versioned so time-questions are truthful, connected so relationship-questions are answerable, permanent so longitudinal-questions have a past to read, and network-wide so the questions that matter most can be asked at all. The canonical questions are not a feature list; they are the *proof that the structure earns its complexity*. And the next part shows how the answers are produced — with intelligence that emerges from the graph, and never replaces its truth.

---

# PART 8 — GRAPH INTELLIGENCE

The graph's most valuable outputs — the answers to Part 7's network questions — are not truths. They are *derivations*: conclusions drawn from truth (Part 1.4). This part describes how intelligence emerges from the graph, and it is built around one uncompromising boundary, because crossing it would destroy the graph's trustworthiness and therefore the asset:

> **Intelligence emerges from the graph but never becomes the graph. A derivation may inform any decision, but it is never written back into the record as a fact. Truth is what happened; intelligence is what it means; and the graph never lets meaning masquerade as happening.**

And a second law, equally load-bearing (North Star):

> **Intelligence never emerges through AI alone. It emerges from the graph — the accumulated ground truth of a hundred thousand restaurants over a decade — of which AI is merely the lens. A competitor's AI is grounded in nothing; Mezze's is grounded in the region's ground truth. The intelligence is in the graph; the model only reads it.**

This is why RFC-000 and the North Star exclude AI as an asset yet make the graph the answer: models are commodities sold to everyone; a model *grounded in this graph* is available to no one else. Intelligence is not the model — it is the model *plus the ground truth*, and only the ground truth is un-buyable.

The forms of intelligence follow. For each, the part states plainly whether it is **derived** (and therefore disposable, re-computable, never truth) and confirms that **none of them ever become truth.**

## 8.1 Patterns

**Derived.** A pattern is a regularity in the ground truth — this item sells at this day-part, this cost rises each season, this guest returns every fortnight. Patterns emerge by reading history, which the graph retains completely (Part 1.7). A pattern is a *description of what has repeatedly happened*, and it is never itself a happening: the graph records the sales; the pattern is our reading of them. Patterns are disposable — re-read the history with a better eye and you get better patterns, on the same untouched truth.

## 8.2 Communities

**Derived.** A community is a set of restaurants (or guests, or suppliers) that behave alike (Part 7.3) — the cohorts beneath benchmarking. Communities emerge from similarity across anonymized signatures; they are the graph recognizing its own structure. A community is never a truth about any member — it asserts nothing about an identifiable restaurant's private facts; it is a statement of resemblance, computed under privacy (Part 9). Communities are disposable and re-computable as the graph grows and signatures sharpen.

## 8.3 Benchmarks

**Derived.** A benchmark positions one restaurant against its community's aggregate (Part 2, Node 38; Part 7). It is the graph's most visible intelligence and the clearest embodiment of the network effect: worthless at one restaurant, priceless at a hundred thousand. A benchmark is emphatically *not truth about the peers* — it exposes the subject's own position and an anonymized aggregate, never a peer's particulars (Part 9). It is a derivation, retained per instance so trajectories are visible, and re-computable as the community changes. **It never becomes truth**: "you overpay for tomatoes" is a *comparison*, not a fact about any specific competitor's tomato bill.

## 8.4 Similarity

**Derived.** Similarity is the underlying measure beneath communities and benchmarks — how alike two restaurants, guests, or suppliers are, across their signatures over time. It is a computed relationship, not an observed one; nothing in the world *is* "73% similar" — similarity is our lens. It is disposable and improves as the graph deepens. It never becomes truth; it is the scaffolding on which trustworthy comparison is built.

## 8.5 Anomaly detection

**Derived.** An anomaly is a departure from a restaurant's own established pattern or its community's norm — a refund rate that spikes (Part 2, Node 29), a cash session chronically short (Part 2, Node 9), a void pattern that suggests abuse (Part 4.1), a cost that jumps against the market. Anomalies emerge by comparing current truth to historical and peer patterns. An anomaly is a *flag for attention*, never a verdict and never a truth: it says "look here," not "this is fraud." The graph surfaces the anomaly; a human, with authority (Part 1.11), investigates and — if warranted — records a *new truth* (a correction, an adjustment) as an event. The anomaly itself is disposable; the investigation's outcome, if any, is truth.

## 8.6 Forecasts

**Derived — and the sharpest example of never-becoming-truth.** A forecast predicts a future that has not happened (Part 2, Node 37; Part 6.6). It emerges from history and network patterns, and it carries *no truth-trust whatsoever* (Part 1.10). RFC-001's invariant governs it absolutely: *a prediction is never written into the operational record as a fact.* The graph enforces this at the moment of creation (Part 4.7): a forecast informs the prep list, the schedule, the reorder — and writes nothing back as truth. When the future arrives, the *actual* is a new truth; the forecast is then measured against it (Part 3.6), and the measurement is truth while the forecast never was. Forecasts are the most disposable intelligence of all — regenerated continuously, retained only to grade themselves.

## 8.7 Optimization

**Derived.** Optimization is intelligence that *recommends an action* — the best prep quantity, the best staffing level, the best reorder point, the best allocation of constrained stock (Part 7.8). It emerges from forecasts and patterns, and it is *advice*, never truth and never command: it recommends; a human with authority decides; and only the human's decision, enacted as an event, becomes truth. An optimization that is followed produces real events (a prep, a schedule, an order) that *are* truth — but the recommendation itself never was. Optimizations are disposable and improve as the graph and its forecasts improve.

## 8.8 Decision support

**Derived — the synthesis, and the point.** Decision support is where all the above converge into help for a human choosing what to do: the financing qualification (Part 7.7), the reprice recommendation (Part 7.6), the supplier-switch suggestion (Part 7.2), the guest-win-back nudge (Part 7.9). It is the graph's ultimate output — *the lens that turns ground truth into value the restaurant feels* (North Star). And it is, to the last, a derivation: it supports the decision; it never makes the decision a fact. The human decides; the decision becomes an event; the event becomes truth. Decision support is disposable, re-computable, and improves forever on the same permanent graph — which is exactly why the graph, not the intelligence, is the asset.

## 8.9 The boundary, stated once more

Every form of intelligence in this part is **derived**, and **not one of them ever becomes truth**. This is not a limitation to be engineered around; it is the discipline that makes the graph worth trusting — and therefore worth building intelligence on at all. A restaurant will let the graph underwrite its loan, benchmark its costs, and advise its decisions *only because it knows the graph never lies about what is fact and what is inference.* The moment a forecast is recorded as a sale, a benchmark as a peer's real number, or an anomaly as a verdict, the graph has lied, and trust — the thing that took a decade to build — is gone. The boundary between truth and derivation is the boundary between an asset that compounds and a liability that collapses. The graph keeps it absolutely.

---

# PART 9 — GRAPH GOVERNANCE

A graph this valuable, this permanent, and this private must be *governed* — not by a mechanism, but by principles about who may do what to it and how its integrity is protected over decades (Part 0: no implementation). Governance is what keeps the graph trustworthy across twenty years, a thousand engineers, and a hundred thousand restaurants who have entrusted it with their most sensitive truth.

## 9.1 Who owns nodes?

Every node has exactly one owning root of responsibility (Part 1.3), and ownership determines authority (Part 1.11). The organizational, operational, and transactional nodes are owned by the **restaurant** (through its locations, shifts, and employees) — the restaurant owns its own truth, sees it in full, and no other restaurant ever sees it (Part 2, Node 1). The person nodes — **guest, customer** — are owned, in the sense of self-determination, by the *people themselves*: they own their identity, their contact details, and their consent, and a restaurant holds only the *relationship*, never dominion over the person (Part 2, Nodes 10, 11; 9.6). The derivation and network nodes — **benchmark, forecast**, and the aggregates behind them — are owned by **Mezze as steward** (Part 1.11), because they belong to no single restaurant and could not exist for any one of them alone. This tripartite ownership — restaurants own their operations, people own themselves, the steward owns the aggregate — is the constitutional structure of the whole graph, and no part may reach across it.

## 9.2 Who owns edges?

An edge is owned by the node on its owning side (Part 3). Ownership edges are owned by the responsible root; reference edges are owned by the referring node. The consequence that matters for governance: **authority to assert an edge never crosses an ownership boundary.** A restaurant may draw edges within its own truth; it may *never* draw an edge into another restaurant's truth, and it may never assert a benchmark or forecast edge, because those belong to the steward. The steward, conversely, may compute aggregate edges but may *never* expose the private edges beneath them. The edge-ownership rule is the privacy boundary made structural.

## 9.3 Who approves schema changes?

The graph's shape — its nodes, edges, and invariants — is the ontology (RFC-001), and it changes only through the same governed process that produced RFC-001 and this document: a deliberate, reviewed amendment to the canonical model, never an ad-hoc addition by any single team or system. The steward's architecture function is the guardian of the shape. A new node type, a new edge type, a changed invariant — each is a constitutional amendment, weighed against the whole and ratified deliberately, because the shape is what a thousand engineers and a decade of history depend on. **Nothing quietly adds a node type in a corner of the graph;** the shape is shared and its changes are governed. This is the direct application of RFC-000's engineering laws to the graph itself.

## 9.4 How are breaking changes prevented?

By an absolute rule descending from the append-only nature of the graph (Part 1.7):

> **The graph's shape may grow but may never break. New node types, edge types, and derivations may be added; existing ones may be extended; but nothing that history depends on is ever removed or redefined in a way that falsifies the past.**

Because every past fact was recorded under the shape in force at its time, and because the graph must reconstruct any past state truthfully (Part 5.4), the shape can only ever be *added to*, never *subtracted from* or *retroactively altered*. A field's meaning cannot change beneath the history that used it; a node type cannot be deleted while past facts reference it. This is the same discipline as the append-only truth, applied to the shape: the graph evolves forward, never in a way that breaks what came before. It is why an implementation four rewrites from now must still honor this document — the shape is a contract with the entire past.

## 9.5 How is graph quality measured?

Graph quality is measured along the dimensions the North Star named — density, depth, exclusivity — plus the integrity dimensions this document adds:

- **Completeness of observation** (Part 1.5) — is the restaurant's real activity fully captured, or is truth being lost? A node that loses transactions is a corrupt node. *Losslessness is the first quality measure.*
- **Depth per node** (North Star) — does a node give only sales, or sales *and* costs *and* labor *and* supply? Thin nodes are low-quality; thick nodes are the asset. Depth is a quality measure, not just a growth measure.
- **Freshness and correctness** — does the graph reflect the latest truth, and does it reconcile (cash sessions balance, stock nets match counts, payments match orders)? Unreconciled truth is suspect truth.
- **Trust distribution** (Part 1.10) — what share of the graph's facts are high-trust direct observations versus soft assertions? A graph rich in directly-observed payment and sales truth is more valuable than one padded with unverified claims.

Quality is not a vanity metric; it is what determines whether the graph can underwrite a loan or benchmark a peer. A dense graph of thin, lossy, unreconciled nodes is worth far less than a smaller graph of thick, complete, reconciled ones — which is why the North Star kills "logo count" in favor of Graph Value.

## 9.6 How is trust measured, and how is privacy protected?

Trust is a property of every fact, derived from provenance (Part 1.10): direct observation outranks assertion, assertion outranks derivation, nothing outranks reality. Governance makes this operational by ensuring every fact carries its provenance, so the graph always knows how much weight a fact can bear — and never lets a low-trust fact silently overwrite a high-trust one (Part 1.10).

Privacy is the other face of trust, and it is the governance rule on which the entire asset depends:

> **A restaurant's private truth never leaves that restaurant. The steward may compute aggregates across many restaurants, but no restaurant ever sees another's particulars — only anonymized aggregates and its own position within them. A guest's private truth never leaves the restaurant that knows them without the guest's own consent. And a person's right to erasure is honored by removing their private attributes while preserving the anonymized skeletal fact that the events they were part of did occur — because the restaurant's truth must not be falsified by a person's departure.**

This privacy boundary is what makes benchmarking both *valuable* (everyone benefits from the pattern) and *trustworthy* (no one sees my books) — the exact balance on which the asset rests (Part 1.11, Part 10). A single breach of it — one restaurant seeing another's private numbers — would collapse the trust that took a decade to earn. Governance guards this boundary above all others.

## 9.7 How are orphan nodes prevented?

An orphan is a node with no owning root — a node accountable to no one, a fact belonging to nothing (Part 1.3). Orphans are prevented by the constitutional requirement that **every node is born with an owner**: no node comes into being except through an event (Part 4), and every event attributes what it creates to a responsible root. An order is born owning its lines and owned by a location and shift; a payment is born belonging to an order; a stock movement is born affecting a stock item at a location. There is no path by which a node enters the graph unowned, because there is no path by which a node enters except through an event that names its place. Ownership is not a cleanup step; it is a birth condition. A graph with no orphans is a graph where every fact is accountable — and accountability is what makes the whole structure auditable, governable, and trustworthy.

## 9.8 The self-governance of the graph

Finally, the graph governs *itself* through the audit record (Part 2, Node 39): every consequential change carries, inseparably, the truth of who made it, when, under what authority, and why. This is governance turned inward — the graph keeping an immutable, append-only record of every hand that ever touched it. It is why, years later, any change can be explained, any authority verified, any anomaly traced to its author. The audit trail's whole value is that it *cannot be cleaned* (Part 2, Node 39), and that immutability is the last line of governance: a graph that remembers everything done to it, forever, is a graph that cannot be quietly corrupted. Governance is not a committee; it is a property of the structure — ownership at birth, authority bounded by ownership, privacy that never leaks, a shape that grows but never breaks, and a memory of every change that can never be erased.

---

# PART 10 — THE GRAPH ASSET

Everything in the preceding nine parts exists to produce one thing: an asset. Not a product, not a technology, not a feature — an **asset**, in the strict sense of something that holds and compounds value over time and cannot be taken away. This final part explains why the Operating Graph becomes the company's largest asset, why it compounds, and why — uniquely among everything Mezze builds — it survives every force that destroys ordinary advantages. This is the descent of the North Star into the graph's own structure: the strategy named the asset; this document *is* the asset, described.

## 10.1 Why the graph becomes the company's largest asset

Mezze will build many valuable things — software, design, payments, compliance, intelligence, a marketplace. Every one of them is *replicable capital* (North Star): a competitor with enough money and time can build, buy, or copy each. The software can be rewritten. The design can be hired. The payments can be licensed. The compliance can be certified. The AI is a commodity sold to everyone. The integrations can be adapted. None of these is the asset, because each can be reproduced.

The Operating Graph cannot be reproduced, and the reason is contained entirely in its first principles. The graph is the **accumulated, ordered, permanent record** (Part 1.7) of how a hundred thousand restaurants actually ran, over a decade, captured losslessly (Part 1.5), held as ground truth (Part 1.4), and connected densely enough that the network questions (Part 7) can be answered. Its single irreducible input is **time × nodes** — elapsed years across a live network — and time is the one resource no amount of capital compresses (North Star). The graph is therefore the largest asset not because it is the most expensive thing to build, but because it is the *only* thing that cannot be rebuilt: it is made of history, and history is made only of time that has actually passed.

Everything else Mezze owns is a *means* to the graph (North Star): the software captures it, the design wins the adoption that thickens it, the payments provide its highest-fidelity truth, the compliance forces sales into it, the intelligence turns it into value the restaurant feels. Revenue is a *lagging output* of the graph's value, not the asset itself. The company is not the tools; it is the graph the tools produce.

## 10.2 Why it compounds

An ordinary moat sits still and erodes. The graph is a moat that *grows with every node and makes every existing node more valuable* — the only kind of asset that gets *harder* to catch as it scales (North Star flywheel). The mechanism is Metcalfe's law applied to restaurants:

Every new restaurant added to the graph makes the benchmarks sharper (a larger, finer peer set — Part 8.3), the underwriting safer (more repaid-and-defaulted patterns to compare against — Part 7.7), and the demand pool larger (more buying power to clear — North Star liquidity) — *for all the other restaurants already in the graph.* A competitor with a thousand nodes cannot produce the benchmark, the credit decision, or the supplier leverage that a hundred-thousand-node graph produces, because those outputs are functions of *density and history*, and density and history are exactly what the competitor lacks. **The gap widens with scale.** Each restaurant that joins does not merely add itself; it increases the value of every restaurant already present, which lowers churn, drives word-of-mouth, and eases the next sale — which adds more restaurants. The flywheel turns itself.

And it compounds on a second axis: **depth over time** (North Star). A node that has been in the graph for five years is worth far more than a new one, because it carries five years of longitudinal truth — five years of trajectory, seasonality, and outcome that a snapshot cannot match. Even a *closed* restaurant compounds the asset (Part 5.5): its ending is a completed story, often more instructive than a living peer, and it can never be un-lived. So the graph compounds twice — wider with every node, deeper with every day — and neither dimension can be fast-forwarded.

## 10.3 Why it survives technology changes

Technology is mortal by design (Part 0). In twenty years Mezze will have rewritten its systems several times, changed its languages, and replaced its entire infrastructure — and the graph will be unscathed, because *the graph is not any of those things.* The graph is the shape of reality (Part 1); the technologies are implementations that observe and serve it (Part 1.5, Part 1.6). When an implementation is replaced, the truth it held is re-expressed in the new one, because the truth was never *in* the technology — the technology was a lens on truth that exists in the world and is recorded in a shape (this document) that no rewrite touches.

This is precisely why RFC-002 forbids itself every technological word (Part 0). A document that named a storage engine would die with that engine. A document that names only nodes, edges, truth, and time is true in every decade, on every technology, forever. The graph survives technology changes because it was *defined* to be independent of them — the abstinence of this document is the survival mechanism.

## 10.4 Why it survives AI

AI is the force most likely to be mistaken for the asset, and the North Star is emphatic that it is not: AI is a commodity sold by the same vendors to Mezze and to every competitor equally. What survives — what no competitor can obtain — is **AI grounded in the graph** (Part 8). A model reading Mezze's graph sees the region's ground truth; the same model reading a competitor's thin data sees noise. When the next generation of AI arrives, and the one after that, each will be a *better lens on the same permanent graph* (Part 6.9) — and each will be better *for Mezze specifically* in proportion to the graph beneath it, which no rival can match. AI does not threaten the graph; it *increases the graph's value*, because every advance in intelligence makes the ground truth more valuable to whoever holds it — and only Mezze holds this one. The graph survives AI by being the thing AI needs and cannot supply itself: reality, recorded.

## 10.5 Why it survives acquisitions

A competitor cannot buy the graph, and this is worth stating precisely because it is the question a rival's strategist will ask first. You cannot buy someone else's decade of longitudinal, exclusive, node-level operating truth (North Star). It is not for sale; and even if the company were acquired, the graph would be *stale the moment it changed hands* if the network it observes were disrupted, because the graph's value is that it is *live* — continuously fed by a hundred thousand restaurants that trust it. Money buys capabilities; it cannot buy elapsed time across a live network, and it cannot buy the *trust* (Part 9.6) that took a decade to earn and that a single privacy breach would destroy. A competitor who acquired Mezze would acquire the graph's *past*; only by keeping the network's trust and continuing to feed it losslessly would they keep its *future* — which is to say, they would have to keep being Mezze. The asset is not portable in the way capital is; it is rooted in a living, trusting network, and that rooting is the moat.

## 10.6 Why it survives rewrites

This is the narrowest and most technical of the survival claims, and it is the reason this document exists at all. Software is rewritten; the graph is not, because the graph is *specified here, independent of software* (Part 0, Part 10.3). A rewrite re-implements the observation and the projections (Parts 1.5, 1.6) against the same unchanged shape. The truth — every node, every edge, every event, every past state (Part 5.4) — is carried forward intact, because it was never the property of the code being replaced. This is why the graph's shape may grow but may never break (Part 9.4): the shape is a contract with the entire past, and a rewrite must honor it exactly. A company whose asset lived *in its code* would lose the asset with every rewrite; Mezze's asset lives in a shape that outlives all its code, and so survives every rewrite by construction.

## 10.7 Why competitors cannot recreate it

Assemble the reasons and the conclusion is airtight. To recreate the graph, a competitor would need to acquire a hundred thousand restaurants, run them losslessly for a decade, capture not just their sales but their costs and labor and supply (depth), become the exclusive system of record for each so the truth is ground truth and not a fragment (exclusivity), earn the trust that lets restaurants share their most sensitive numbers, and do all of this *before Mezze did* — because the graph's value is its head start in elapsed time, and elapsed time cannot be compressed (North Star). The single input the graph requires is time × nodes, and a competitor can add capital, talent, and technology to their effort but cannot add *time already passed.* They can start today and, in a decade, have a decade-old graph — by which point Mezze's graph is twenty years old and twice as dense. The gap does not close; it widens (10.2). This is what it means for an asset to be un-recreatable: not that it is hard, but that the one ingredient it requires is the one ingredient no one can manufacture.

## 10.8 The graph in 2045

Picture the graph twenty years on. It holds the operating truth of the entire regional restaurant economy — every sale, cost, price, shift, supplier order, and outcome, across hundreds of thousands of restaurants, over two decades, including the complete, permanently-valid histories of every restaurant that opened, grew, merged, split, or closed in that time (Part 5). It is the place where the region's restaurant economy is *legible*: where a restaurant's true P&L is known better than its owner knows it, because it is measured against a hundred thousand peers (Part 7). Where the industry is *financeable*: where working capital is underwritten against cash flows only the graph can see, at losses no blind lender can match, because the graph *is* the credit model (Part 7.7). Where the industry is *transactable*: where demand aggregates into buying power and procurement clears through the graph because that is where the liquidity is (North Star).

By 2045 Mezze is no longer a POS company, no longer a payments company, no longer a software company at all in the way it began. It is the **ground-truth data layer and clearing house of the regional restaurant economy** (North Star) — the entity that knows, finances, and supplies an industry, and that cannot be dislodged because a challenger would have to reproduce two decades of live, exclusive, trusted ground truth across a network, and time is the one thing capital cannot buy. The technologies that carried the graph there will have been replaced several times over. The graph will not have been replaced once. It will only have grown wider, deeper, and more irreplaceable with every restaurant, every day, and every year that no competitor can ever go back and acquire.

And the description of that graph — what a node is, what an edge is, what truth is, why history is the moat — will still be this document, unchanged, because it was written about reality, and reality does not need a new version.

---

## Closing — The Graph Is the Company

RFC-000 gave Mezze its laws. RFC-001 gave Mezze its language. RFC-002 has given Mezze its shape — the one structure into which every API, every event, every model, every payment, every report, and every integration ultimately resolves.

> **Every entity is a node. Every relationship is an edge. Every event is a change to the graph. Every invariant is a law the graph obeys. Every projection is a disposable view of it. Every form of intelligence is a derivation from it that never becomes it. And the whole of it — accumulated, ordered, permanent, exclusive, trusted, and made only of elapsed time — is the one asset the company owns that no one can buy, copy, rewrite, or outlast.**
>
> **The restaurant is the truth. The graph is the record. Everything else is implementation.**

This is the canonical description of the Operating Graph. It is the heart of Mezze, and it is written to be true, word for word, for the next twenty years.

*— Chief Systems Architect. Descended from RFC-000 and RFC-001. Amended by nothing. The shape of the company.*
