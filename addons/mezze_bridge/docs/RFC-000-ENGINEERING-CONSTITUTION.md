# RFC-000 — The Mezze Engineering Constitution

**Status:** Ratified · Permanent · Supersedes no RFC and is superseded by none
**Scope:** Every system, service, terminal, and line of code at Mezze
**Audience:** Every engineer, present and future. Mandatory reading.
**Lifespan:** Written to be correct in 2045. It names no framework, library, language, database, cloud, or model, because those are mortal and these principles are not.

---

## How to read this document

This is not a style guide and not an architecture diagram. It is the **law** that every architecture RFC, every service, and every code review is judged against. When a technical decision is hard, this document decides it. When a new engineer asks "how do we build things here," this is the answer, and the honest expectation is that they know it by heart.

Every law in this document exists to serve one thing, and if you understand that one thing you can re-derive the rest: **Mezze's only irreplaceable asset is the Operating Graph — the exclusive, longitudinal, ground-truth record of how restaurants really run — and the trust that lets us hold it.** Engineering exists to *capture that truth losslessly, hold it immutably, serve it reliably, and never betray the trust that permits it.* A lost transaction is a hole in the asset. A silent data corruption is a lie in the ground truth. A breach is the end of the trust and therefore the asset. A system that cannot be observed cannot be trusted. Every engineering principle below is a defense of the graph or the trust, and if a principle here ever seems arbitrary, trace it to one of those two and it will make sense.

The Company Constitution named a permanent distinction that governs this entire RFC: **principles do not change; implementation details do.** This document contains only principles. The moment it names a specific technology, it has failed its purpose. Technologies are chosen in the architecture RFCs that descend from this one, on merit, and replaced without ceremony when better ones appear. Hold the tools loosely. Defend the principles to the death.

---

# PART 1 — Engineering Philosophy

How Mezze software is built. These are the load-bearing beliefs; everything else is their consequence.

**The software must continue operating without the Internet.** A restaurant serves customers whether or not the network is up, and our software must serve with it. The terminal is not a window onto a cloud; it is a complete system that happens to synchronize. This is not a feature we add for reliability; it is the physics of the business, and it is also graph integrity — the ground truth is captured at the source, losslessly, whether or not a round-trip to the cloud succeeds. A system that stops working when the network stops is a system that loses the restaurant's revenue and our truth in the same instant, and we do not build such systems.

**Every important action becomes an immutable event.** State is a projection of history, not the other way around. When something meaningful happens — a sale, a payment, a price change, a shift — we record it as a fact that occurred at a time, and we never erase or overwrite that fact. This is because the graph *is* history: its value is longitudinal, and a system that overwrites the past destroys the asset. Immutable events give us, as a free consequence, the audit trail, the replay, the offline reconciliation, the analytics, and the ability to reconstruct any past state. We do not choose event immutability for elegance; we choose it because the truth of what happened is the thing we sell.

**Trust is more valuable than speed.** When correctness and speed conflict on any path that touches money, data, or the customer's dependence on us, correctness wins, every time, without debate. We are permitted to be slower; we are not permitted to be wrong about someone's money or to lose someone's truth. A fast system that occasionally corrupts is worthless to us, because our asset is the *reliability* of the ground truth, and a single corruption teaches every customer that the record cannot be trusted. Speed is optimized within correctness, never at its expense.

**Data is never silently destroyed.** Nothing important is deleted; it is superseded, tombstoned, or archived, and the fact of its supersession is itself an event. A customer's data belongs to the customer, the ground truth belongs to the graph, and neither may vanish without a trace and a reason. Silent destruction of data is the single most dangerous class of bug we can ship, because it is invisible until the moment it is catastrophic, and because it is a lie in the ground truth that no downstream computation can detect.

**Failure is expected; recovery is automatic.** Networks partition, printers die, processors time out, disks fill, and processes crash — not as exceptions but as the normal weather of distributed systems at scale. We design for failure as the default case, not the edge case. Every operation that can fail has a defined outcome, a retry, and a recovery path, and "lost" is never a permissible outcome for anything that matters. A system whose recovery requires a human at 2 a.m. is a system that has failed to be engineered, because the human will not always be there and the restaurant serving dinner cannot wait.

**Users never lose work.** A cashier who took an order, a manager who made a change, a kitchen that fired a ticket — their work is captured the instant it happens and survives every failure between that instant and its permanent home. From the user's side, work is never lost, because to them the work *is* the business, and losing it is losing revenue and trust. This is the offline-first and never-lost principles felt from the user's chair, and it is the promise every system upholds.

**Prefer boring technology over fashionable technology.** We choose proven, well-understood, operationally-simple technologies over exciting ones, because our asset compounds over decades and the excitement of a technology is inversely correlated with its longevity and its operational calm. Fashion is a liability on a system that must run reliably for years on hardware in a restaurant and hold data that must survive for the life of the company. We adopt the new only when it makes a principle *cheaper to uphold*, never because it is new, and we treat résumé-driven and conference-driven technology choices as bugs. Boring is a competitive advantage when your edge is compounding, not novelty.

**Integrate before rebuilding.** When a capability exists in a mature system the world already trusts — accounting, a payment network, a tax authority's interface — we integrate it behind a clean boundary before we consider building our own, because building captures no ground truth we do not already get by integrating, and it consumes the engineering that should be deepening the graph. We build only what *captures new truth* or *deepens exclusivity*; everything else, we integrate. Our own origin taught this: we bootstrapped on a mature back-office and put it behind an interface, and that was correct — the mistake would have been to rebuild it instead of integrating it.

**The whole system is designed to be reproducible.** Any state we hold can be reconstructed from its events; any environment we run can be recreated from its definition; any deployment can be rolled forward or back to a known point. Reproducibility is what makes a distributed system debuggable, recoverable, and trustworthy over decades. A state that cannot be reproduced is a state we do not truly understand and cannot truly defend.

---

# PART 2 — Domain-Driven Design: Bounded Contexts

Mezze is not one system; it is a set of **bounded contexts**, each of which owns a coherent piece of the restaurant's reality, speaks its own precise language, and holds authority over its own truth. Contexts communicate through explicit contracts and events, never by reaching into each other's data. This is not an implementation choice; it is how a system stays comprehensible and independently evolvable for twenty years, and how the graph stays coherent — each fact has exactly one owner responsible for its truth.

The permanent law of contexts: **each context is the single source of truth for the facts it owns; no other context may hold or mutate those facts, only subscribe to the events the owner publishes.** A fact with two owners is a fact with no truth. Ownership boundaries are drawn along the natural seams of the restaurant's reality:

- **Restaurant Operations** — owns the order and the service: the lifecycle of an order from open to settle, across dine-in, takeaway, and delivery; the floor, the tables, the coursing. It is the heartbeat of the graph — the highest-frequency truth — and the origin of most events. It owns *what was sold, to whom, when, at what price, and how the service unfolded.*

- **Kitchen** — owns fulfillment and the kitchen constraint: tickets, routing, capacity, timing, station load, and the bump. It owns *what was made, where, when, and how the constraint behaved.* It is downstream of Operations (an order becomes tickets) and its truth feeds capacity intelligence.

- **Payments** — owns the money movement: tenders, authorization, capture, settlement, reversal, reconciliation. It owns *how money moved and whether it reconciled.* It is the highest-fidelity truth of cash flow — the input to credit — and it holds itself to the strictest correctness bar in the company, because it moves other people's money.

- **Inventory** — owns stock and cost reality: what is on hand, what depletes with each sale, waste, par levels, transfers, and the true cost of goods. It owns *what things cost and where they go.* It is one of the thickest data surfaces — the difference between a sales-node and a whole-business-node — and its truth feeds food-cost intelligence.

- **Guests** — owns the customer relationship: identity, history, loyalty, consent, and preferences. It owns *who the guests are and what they are owed*, and it is the context most bound by privacy law, because it holds the most personal truth. Its handling of consent and erasure is a matter of trust, not convenience.

- **Reservations** — owns the seat over time: bookings, waitlist, deposits, and the optimization of seat-hours. It owns *who is coming and when, and how the seats were filled.*

- **Identity** — owns *who may act and as whom*: humans (staff, managers, owners), devices (terminals), and systems (services, partners). It is the authority for authentication and the source of the actor on every event. Every other context trusts Identity and no other for *who did this.* It holds the least data and the most power, and it is guarded accordingly.

- **Reporting** — owns the *read* of the truth for humans: aggregations, dashboards, exports, and the operational views. It is a *projection* context — it owns no source-of-truth facts, only derived views built from other contexts' events — and its independence lets the read side scale and evolve without endangering the write side.

- **Intelligence** — owns *understanding*: benchmarking, forecasting, prediction, anomaly detection, and the models that turn the graph into insight. Like Reporting, it owns no source truth; it consumes the events of every context and produces *derived* knowledge and predictions, which are always reproducible and never confused with the ground truth they are derived from (Part 4).

- **Finance** — owns the *financial infrastructure*: the ledger boundary to the outside accounting world, working-capital, payroll, and the reconciliation of money at the business level. It integrates the mature back-office (accounting) behind a boundary rather than reimplementing it, and it owns *the financial position and the credit relationship.*

- **Supplier Network** — owns the *supply side of the market*: suppliers, catalogs, purchase orders, deliveries, and the aggregation of demand. It owns *what was ordered from whom, at what price, and whether it arrived*, and it is the seed of the two-sided liquidity that the graph becomes.

- **Marketplace** — owns the *clearing of the two-sided economy*: the matching and transacting between restaurants and the other side (suppliers, lenders, guests, developers). It owns *what cleared through the graph*, and it is the context where liquidity becomes measurable and the graph becomes a market.

Contexts are drawn so that a change in one rarely forces a change in another, so that each can be understood, tested, secured, and scaled on its own terms, and so that the whole remains legible to an engineer who holds one context in their head. **A context that grows entangled with another has drifted from this constitution and is refactored back to a clean boundary; entanglement is technical debt against comprehensibility, which is debt against the twenty-year lifespan.**

---

# PART 3 — Event Philosophy

Events are the spine of Mezze. Everything important that happens is recorded as an event, and the events are the truth from which all state is derived. This is because the graph *is* the accumulated events of a hundred thousand restaurants over years, and the discipline of the event model is the discipline that keeps that asset whole.

**Everything important is an event.** If a fact matters to the business — a sale, a payment, a price change, a stock movement, a login, a config change — it is recorded as an event: an immutable statement that *this happened, at this time, caused by this actor, in this context.* State (the current order total, the current stock level) is a *projection* of events, recomputed from them, never the primary record. The primary record is always the history.

**Immutability.** An event, once written, is never modified or deleted. A correction is a new event that supersedes the old; the old remains, because the fact that we once believed it is itself part of the truth and part of the audit. Immutability is what makes the record trustworthy to a bank, a regulator, and a court, and what makes replay and time-travel possible. A mutable event log is not an event log; it is a database that has lost its history and, with it, the asset.

**Ordering.** Events within a stream have a definite, total order, and that order is preserved through capture, transport, storage, and replay. Order is the difference between a coherent history and a pile of facts, and many truths (the sequence of price changes, the order of tenders on a bill) are meaningful only in their order. Where events across streams must be related, we relate them explicitly by causal keys, never by wall-clock timing, because clocks lie and causality does not.

**Idempotency.** Every event carries a stable, globally-unique identity, and processing the same event twice produces exactly the same result as processing it once. This is the property that makes offline sync, retries, and recovery *safe*: a batch replayed after a crash, a message delivered twice by an at-least-once transport, an event resent because an ack was lost — none of these corrupt the truth, because the second processing is recognized and has no additional effect. Idempotency is the foundation on which exactly-once is built.

**Exactly-once.** Every event that matters is applied to the truth exactly one time — no more (idempotency guards duplicates) and no less (durability and retry guard losses). "Applied zero times" is a lost fact, a hole in the graph; "applied twice" is a double-count, a lie in the graph; both are forbidden, and the machinery that guarantees exactly-once (durable capture, idempotent apply, acknowledged delivery, a reconcile ledger for the poison cases) is core infrastructure, not an optimization.

**Replay.** Because events are immutable and ordered, the truth can be reconstructed by replaying them, and any projection — any current-state view, any report, any model input — can be rebuilt from scratch by replaying the events that produced it. Replay is how we recover from a corrupted projection, how we build a new view of old data, and how we prove that state is reproducible. A system whose state cannot be rebuilt from its events has a primary record that is not its events, and has therefore abandoned this constitution.

**Audit.** The event log *is* the audit trail. Every money-affecting and privileged action is, by construction, an immutable event attributed to an actor at a time, and the trail cannot be altered after the fact because events cannot be altered. Audit is not a separate system we bolt on; it is a free consequence of building on immutable events, and it is the foundation of the trust and the regulatory authority that let us hold the graph.

**Versioning and event evolution.** Events are contracts that must survive twenty years, during which the systems that produce and consume them will change many times. So every event is versioned, and the rules of evolution are strict: we may *add* optional information to an event over time, but we may never *change the meaning* of what was already recorded, and a consumer must tolerate versions it does not fully understand rather than break. Old events, written years ago, must remain readable and meaningful forever, because they are the graph's history, and a schema change that renders old events unreadable is a schema change that destroys part of the asset. Event evolution is forward-only and backward-compatible, always.

**Time-travel.** Because the truth is the replayable history, we can reconstruct the state of any restaurant, or the whole graph, *as it was at any past moment* — what the stock was, what was owed, what the price had been. Time-travel is the analytical superpower the event model grants: it lets us ask not only "what is true now" but "what was true then" and "what changed between," which is the foundation of every longitudinal insight the graph produces. A system that can only tell you the present has thrown away the past, and the past is what we sell.

The reason for all of it, stated once: **the event model is not a technical preference; it is the shape of the asset.** The graph is longitudinal, immutable, ordered ground truth, and the event model is that description made into an engineering discipline. Every event correctly captured is a fact added to the asset; every event lost, duplicated, mutated, or rendered unreadable is a defect in the asset. We build on events because we are building the graph.

---

# PART 4 — Data Philosophy

Not all data is equal, and the most dangerous engineering mistakes come from treating sacred data like disposable data or disposable data like sacred data. Mezze distinguishes six kinds, by their *source of truth* and their *lifecycle*, and treats each according to its nature.

**Operational Data — the ground truth. Sacred.** The immutable events and the source-of-truth facts each context owns: the sales, payments, stock movements, shifts, orders. This is the graph. It is captured losslessly, held immutably, replicated durably, and never silently destroyed. Its lifecycle is *forever* — operational data is retained for the life of the relationship and the demands of law and the value of history, and it is deleted only under explicit legal obligation (a customer's right to erasure) and even then by a recorded, auditable act, never a silent one. This is the data every other principle exists to protect.

**Analytical Data — the reshaped truth. Reproducible.** Operational events reshaped for fast reading and aggregation: the warehouse, the columnar stores, the read models. It is *derived* — its source of truth is always the operational events, and it can always be rebuilt by replay — so it is treated as a durable but reconstructible projection, not a primary record. Its lifecycle is *as long as it is useful*, and it can be dropped and rebuilt without loss, because the truth is not here; the truth is in the events it was built from. We never confuse the analytical copy for the source, and we never mutate it as if it were authoritative.

**Knowledge — the understood truth. Derived and versioned.** Benchmarks, learned patterns, the aggregate understanding the graph produces: "restaurants of this type in this city pay this for this." Knowledge is derived from operational data across many nodes, and it is *versioned* — because it changes as the population changes and as we learn — and it is *reproducible* from the operational data and the method that produced it. Its lifecycle follows the method: when we improve how we compute a benchmark, we recompute it, and we keep the provenance so any piece of knowledge can be traced to the truth and the method that produced it.

**Predictions — the anticipated truth. Derived, dated, and never confused with fact.** Forecasts of demand, cash, stock-outs, labor needs: statements about a future that has not happened. A prediction is *derived* from knowledge and operational data, it is *stamped with the moment and the model that produced it*, and it is **never** written into the operational record as if it were a fact, because it is not one. The most important law of predictions is that they are *proposals, not truth* (Part 8): a prediction may inform a human or drive an action *with approval*, but it never silently mutates the ground truth, because a predicted stock level written as an actual stock level is a lie injected into the graph. Predictions have a short, well-defined lifecycle — they are superseded as reality unfolds, and their accuracy against what actually happened is measured (this is the Restaurant Intelligence Score), because a prediction that is never checked against reality is a guess that never learns.

**Derived Data — the computed truth. Always reproducible, never authoritative.** Any value computed from other data — totals, rollups, materialized views, caches of expensive computations. Derived data is a convenience and an optimization, never a source of truth, and it must always be reconstructible from the data it derives from. The law of derived data is that *it may be wrong without the truth being wrong* — if a cache is stale or a rollup is corrupt, we rebuild it from the source and lose nothing, because the source is elsewhere. We never let a derived value drift into being treated as authoritative, because that is how a computation bug becomes a permanent lie.

**Temporary Data — the ephemeral. Disposable by design.** Session state, in-flight computation, transient UI state, short-lived caches. Temporary data exists to make the moment work and is expected to vanish; nothing important ever lives *only* in temporary data, because temporary data is, by definition, allowed to disappear. The law of temporary data is that *its loss is never a loss of truth or work* — if it can vanish and something important is gone, it was miscategorized and belonged in operational data. The offline-first and never-lose-work principles are, in part, the discipline of never letting the important live in the ephemeral.

The lifecycle law that governs all six: **know which kind every piece of data is, protect the sacred (operational) absolutely, treat everything derived as reconstructible and never authoritative, and never let the important live only in the ephemeral.** The gravest data bugs are category errors — treating a derived value as truth, or letting real work live only in a cache — and this taxonomy exists to prevent them.

---

# PART 5 — API Philosophy

APIs are the contracts through which contexts, customers, and partners depend on us, and a contract that breaks is a trust broken. Because trust is the precondition of the asset, our API discipline is, at root, a discipline of never betraying a dependent.

**Internal communication (context to context).** Contexts communicate through explicit, typed contracts and through the events they publish — never by reaching into each other's storage. Internal contracts are strict and evolve under the same compatibility rules as external ones, because an internal break is an outage, and an outage is a trust event. The internal API surface is designed for clarity and independence: a context can be understood, tested, and changed without reading another context's internals, which is what keeps the system comprehensible for twenty years.

**External APIs (customers and their tools).** Our external API is a public promise. Customers and their integrations build on it, and their businesses come to depend on it, and so we treat it with the gravity of a dependency other people's livelihoods rest on. It is documented as the source of truth, it is versioned, and it is stable within a version — a customer who built against it last year must still work this year.

**Partner APIs (banks, suppliers, aggregators, developers).** The interfaces through which the two-sided network connects and the graph is fed and cleared. These carry the additional weight that a partner failure can sever node acquisition (a bank) or liquidity (a supplier), and so they are held to the reliability and compatibility bar of critical infrastructure. Partner APIs are designed to *feed the graph* — to capture and clear truth through us — never in a way that lets a partner accumulate the ground truth instead of us.

**Versioning.** Every API is versioned, always, from the first release, because an unversioned API is an API that cannot evolve without breaking someone. A version is a stable contract; changes that would break a consumer go into a new version, and old versions remain supported for a long, published window. There is no such thing as an unversioned public interface at Mezze.

**Compatibility.** Within a version, we only make backward-compatible changes: we add, we never remove or change the meaning of what exists, and consumers are built to tolerate additions they do not understand. This is the same forward-only, backward-compatible rule as event evolution (Part 3), applied to APIs, and for the same reason: things depend on us, and a dependency that suddenly means something different is a dependency betrayed.

**Authentication and authorization.** Every API call is authenticated — we always know *who* is calling — and authorized — we always check *whether they may*. There is no anonymous access to anything that touches the truth, and the identity and permission of a caller are established by the Identity context and no other. (Part 7 governs how.) An API that trusts its caller without verifying identity is a breach waiting to be discovered, and we have learned, from our own founding, that a broad surface on weak authentication is a debt against trust that must be repaid before scale.

**Deprecation.** Nothing is removed abruptly. Deprecation is a *process*: announce, provide the replacement, support both for a long published period, measure who still depends on the old, help them migrate, and only then retire — and even then, gracefully. A deprecation that surprises a customer is a break, and a break is a trust event.

**Never breaking customers.** This is the law that subsumes the rest: *we do not break the people who depend on us.* Not with a version change they did not opt into, not with a removed field, not with a changed meaning, not with a surprise deprecation. If a change would break a customer, it is not shipped in a way that reaches them without their choice. The cost of maintaining compatibility is real and we pay it gladly, because the alternative — a customer's integration breaking during their Friday-night rush because we changed something — is a betrayal of the trust that is our asset's precondition. **We would rather carry a compatibility burden for years than break one customer once.**

---

# PART 6 — Offline Philosophy

Offline is not a degraded mode; it is a first-class mode, because the restaurant's reality does not pause when the network does, and our software must not either. Everything the restaurant needs to serve must function with no connectivity, and the truth captured offline must reconcile losslessly when connectivity returns.

**The node owns its truth.** The terminal is the authoritative source of the facts that originate at the terminal — the orders it took, the payments it captured, the tickets it fired — from the instant they happen until they are durably reconciled to the cloud. Ownership is local-first: the truth is born at the node and the node holds it safely, so that no cloud outage, network partition, or slow round-trip can lose it. The cloud is authoritative for *cross-node* truth (the shared catalog, the aggregate graph); the node is authoritative for *its own* events until they are acknowledged.

**Everything the restaurant needs, works offline.** Taking an order, sending it to the kitchen, taking a cash payment, printing a receipt, opening and closing — the operations that constitute service — all function with no network, from cached master data and local capture. Operations that genuinely require the network (an online card authorization, a real-time cross-branch view) degrade explicitly and safely — the user is told what is available and what is queued — but the core act of serving a customer never depends on connectivity. What works offline is a deliberate, documented set, chosen so that a restaurant can run a full service in a blackout and lose nothing.

**Synchronization is durable, ordered, and idempotent.** Offline-captured events are held in a durable, ordered, local queue that survives crashes and power loss (it is not memory; it is persistent), and when connectivity returns they are drained to the cloud in order, exactly once, via the idempotent event machinery of Part 3. Synchronization is not "upload when online"; it is a rigorous, ordered, acknowledged replay of the node's truth into the graph, with a cursor that never loses its place and a guarantee that a partial sync, interrupted and resumed, corrupts nothing.

**Conflict resolution is by design, not by accident.** Where offline events from different sources can conflict, we design the events so that they *commute* wherever possible — they carry deltas, not absolute states, so that "sold two" and "sold three" merge to "sold five" regardless of order, rather than one overwriting the other. Where events genuinely cannot commute (two people editing the same reservation), we define an explicit, deterministic resolution rule and record the conflict as a business event a human can inspect, rather than silently picking a winner. The law is that *conflicts are resolved by a rule decided in advance and recorded, never by whichever write happened to arrive last*, because last-write-wins on important data is a silent, invisible loss of truth.

**Recovery is automatic and lossless.** A terminal that crashes, loses power, or goes offline for a day recovers on its own: its durable queue survives, its unsynced events are still there, and on reconnection it drains them and rejoins the graph with nothing lost and nothing double-counted. Recovery requires no human intervention in the normal case, because the human is busy serving dinner, and a recovery that needs an engineer is a recovery that has failed the restaurant.

**Failure modes are enumerated and each has a defined outcome.** We do not hope offline works; we enumerate how it fails — network gone, cloud gone, disk full, queue corrupt, clock skewed, partial sync, poison event — and we define, for each, exactly what happens, so that no failure is a surprise and none is silent. A poison event that cannot sync is dead-lettered and surfaced, and the cursor advances past it, so one bad event never blocks a terminal's whole queue. An enumerated failure with a defined outcome is engineered; an unenumerated failure is a latent incident, and in a system that holds money and truth, latent incidents are the ones that end companies.

The reason offline is sacred, stated once: **the ground truth is born at the moment of service, in the restaurant, often without a reliable network, and if we cannot capture and hold it there, losslessly, we do not have the asset.** Offline-first is not a robustness nicety; it is the guarantee that the graph is complete and true, and it is the promise to the restaurant that our software will never be the reason they cannot serve.

---

# PART 7 — Security Philosophy

Mezze holds the most sensitive dataset in its industry — the true operating and financial reality of a hundred thousand businesses — and it holds it only because those businesses, their banks, and their regulators *trust* us to. Security is therefore not a feature or a cost; it is the guardianship of the precondition of the entire asset. A breach is the one category of failure from which there may be no recovery, because it does not degrade the trust — it ends it.

**Zero-trust posture.** We assume every network is hostile, every boundary is attackable, and every request is unauthenticated until proven otherwise. Nothing is trusted because of where it comes from; everything is verified. This is the default stance of every system, internal and external, and it is the opposite of the mistake our own founding made — a broad surface trusting a shared credential — which we correct permanently by never trusting position over proof.

**Identity is the root of everything.** Every action, human or machine, is attributable to an authenticated identity: a person, a device, or a system, established by the Identity context and carried on every event. There is no anonymous action against the truth. Humans authenticate strongly; devices carry their own cryptographic identity; systems and partners authenticate with credentials scoped to exactly what they may do. The chain of *who did this* is unbroken from the click to the immutable event, because attribution is the foundation of both authorization and audit.

**Authorization is least-privilege, always.** Every actor may do exactly what their role requires and nothing more, checked at every boundary, defaulting to denial. Privilege is granted narrowly, elevated only temporarily and only with a recorded reason, and never accumulated. A system that grants broad access "for convenience" has traded the asset's safety for a small ease, and we do not make that trade. Elevation of privilege is itself an audited event, so that even legitimate power leaves a trail.

**Secrets are managed, never embedded.** Credentials, keys, and tokens live in a managed secret store, are never written in code or configuration or logs, are scoped as narrowly as possible, and *rotate* on a schedule and on any suspicion of compromise. A secret that never rotates is a secret that will eventually leak and stay leaked; rotation limits the blast radius of the inevitable. The founding lesson — credentials that were too broad and too static — is answered permanently by this discipline.

**Encryption everywhere it matters.** The truth is encrypted in transit and at rest, always, with keys managed and rotated by the secret discipline above. Encryption is not selective; the ground truth is uniformly sensitive, and uniform protection removes the class of bug where the one unencrypted path is the one that leaks.

**Audit is immutable and complete.** Every security-relevant and money-relevant action is recorded in the append-only, tamper-evident trail (Part 3), attributed and timestamped, and it cannot be altered after the fact. The audit trail is both a security control (we can see what happened) and a trust artifact (we can *prove* what happened to a bank, a regulator, or a court). A security system without an immutable audit is a system that cannot prove its own integrity, which is worthless when the whole point is to be trusted.

**Supply chain is guarded.** The code, dependencies, and infrastructure we build on are themselves an attack surface, and we treat them as one: we know what we depend on, we verify what we run, and we assume that a component we did not write may be compromised. The integrity of the graph depends on the integrity of everything that touches it, including the tools that build and run it.

**The one law of security, stated so it is never forgotten:** *we hold other people's businesses in our hands, and we act like it — we assume hostility, we prove identity, we grant the least, we rotate the secrets, we encrypt the truth, we audit immutably, and we treat a breach as the only true emergency, because trust is the precondition of the asset and a breach is its end.*

---

# PART 8 — AI Philosophy

AI is powerful at Mezze precisely because we own the ground truth it must reason over, and dangerous precisely because it can seem to *know* things it only *guesses*. The philosophy that keeps AI valuable and safe is a strict separation between *truth*, which the graph owns, and *proposals*, which AI makes.

**The Operating Graph is truth. AI is not.** The single source of truth is the immutable event history and the source-of-truth facts each context owns. AI does not hold truth; it consumes it. Whatever an AI concludes is a *derived* artifact (Part 4), stamped with the model and moment that produced it, and never elevated to the status of the ground truth it was derived from.

**AI never owns truth.** No fact enters the graph because an AI asserted it. Facts enter the graph because they *happened* and were captured as events by the context that owns them. An AI's output is never a source of truth for anything, ever, because an AI's output is a computation over the past, not a record of a real event, and the moment we let a computation masquerade as a fact, we have injected a lie into the asset.

**AI never modifies truth.** No AI silently mutates an operational fact — not a stock level, not a price, not a balance. The ground truth is immutable and owned by its context, and an AI has no authority to alter it. An AI may *propose* a change (reorder this stock, adjust this price), and that proposal becomes a real event only when a human decides, or when a human has *pre-authorized* an automated action within explicit guardrails — but in every case the resulting event is a genuine, attributed action, never a silent AI overwrite.

**AI proposes; humans decide.** The permanent shape of AI at Mezze is advisory-then-agentic-under-authority: AI forecasts, recommends, and — where a human has granted it bounded authority — acts, but the human is always the source of the decision, either in the moment (approving) or in advance (setting the guardrails and delegating). AI runs the restaurant the way a trusted lieutenant runs it: with real authority, within limits set by the owner, accountable through an audit trail, and never beyond the mandate given. The human manages the exceptions, and the exceptions are always surfaced, never hidden.

**AI consumes truth; the graph is its ground.** Every AI at Mezze is grounded in the graph — it reasons over our proprietary, high-fidelity, real-time ground truth, which is exactly what makes it right often enough to trust. We do not ship AI that reasons over nothing (that is the vanity AI the anti-roadmap forbids); we ship AI grounded in the graph, and its quality is measured by the accuracy of its predictions against what actually happened (the Restaurant Intelligence Score). An AI's value is a function of the truth beneath it, which is why owning the truth makes us the landlord of AI in our industry and never its tenant.

**Every AI action is attributable and auditable.** When an AI acts — even under delegated authority — the action is a real, attributed event in the immutable trail, recorded as *taken by the AI under the authority granted by this human within these bounds*, so that the chain of accountability is unbroken. An AI action that cannot be audited is an AI action we do not permit, because unaccountable automation is untrustworthy automation, and trust is the precondition of everything.

The reason for the strict separation, stated once: **the graph is the asset, and its value is that it is *true*; an AI that could quietly write to it or claim its authority would be an engine for corrupting the one thing we sell. So AI is walled outside the truth: it reads the truth, it proposes over the truth, humans and bounded authority turn proposals into real events, and the truth remains what actually happened. This wall is permanent.**

---

# PART 9 — Testing Philosophy

We build a system that holds money and truth for a hundred thousand businesses over decades, and a system like that is defined not by whether it works in the demo but by whether it *fails safely* under every condition it will actually meet. Testing is how we know. Our founding shipped money-handling code with no automated tests, and that debt had to be repaid before we could be trusted at scale; the permanent answer is that **untested code that touches money, truth, or trust does not ship** — not as a guideline, as a gate.

The testing discipline is a pyramid, widest at the base, and its shape is deliberate: many fast tests of small units, fewer tests of integration, fewer still of the whole, plus specialized tests for the failure modes that a naive suite would miss.

**Domain tests (the base, the most numerous).** The business rules of each bounded context, tested in isolation, fast, and exhaustively: the order math, the tax determination, the discount ordering, the split logic, the reconciliation, the stock deltas. These are the tests that guarantee the *truth is computed correctly*, and because a wrong total is a wrong fact in the graph and a betrayal of the customer, domain logic that touches money is tested to the highest coverage in the company. If the domain is wrong, everything above it is confidently wrong.

**Integration tests.** That contexts, when composed, uphold their contracts and their events flow correctly: an order becomes tickets and a payment and a stock movement, coherently. Integration tests catch the errors that live in the seams between correct units, which is where distributed systems actually break.

**Contract tests.** That every API and every event contract is honored by both its producer and its consumers, so that the compatibility promises of Part 5 are *verified*, not hoped. A contract test is what lets us evolve a system without breaking the customers and contexts that depend on it — it fails loudly the moment a change would break a dependent, before that change reaches anyone.

**Migration tests.** That every schema and data migration is correct *and reversible*: it transforms the data as intended, it can be rolled back, and old events remain readable after it. Because the graph's history must survive forever (Part 3), a migration that corrupts or orphans old data is a migration that destroys part of the asset, and migration tests are the guard against it. Every migration is tested forward and backward before it touches production truth.

**Property-based tests.** For the invariants that must hold across *all* inputs, not just the examples we thought of: idempotency (applying an event twice equals applying it once), commutativity (deltas merge order-independently), conservation (money in equals money out), reproducibility (state rebuilt from events equals state as it was). Property tests explore the input space we would never enumerate by hand, and they are how we gain confidence in the exactly-once and conflict-resolution guarantees that offline correctness rests on.

**Offline-simulation tests.** That the offline philosophy (Part 6) actually holds: we simulate network loss, partition, crash, power failure, partial sync, poison events, and clock skew, and we assert that nothing is lost, nothing is double-counted, conflicts resolve by the defined rule, and recovery is automatic. Offline correctness cannot be verified by hoping the network stays up; it is verified only by taking the network away in a test and watching the system keep its promises.

**Chaos tests.** That the system survives the failures it will meet in production — killed processes, slow dependencies, exhausted resources, lost messages — because "failure is expected; recovery is automatic" (Part 1) is a claim that must be *proven* by inducing failure and observing recovery, not asserted in a design doc. Chaos is how we find the recovery paths that do not actually work before a customer finds them at 8 p.m.

**Performance tests.** That the system meets its budgets under realistic and peak load, because a system that is correct but too slow to take an order during a rush has failed the restaurant as surely as one that is wrong. Performance is tested against the load the graph will actually generate, on the hardware it will actually run on.

**Security tests.** That the security philosophy (Part 7) holds under attack: authentication cannot be bypassed, authorization cannot be escalated, secrets are not exposed, tenants cannot cross, and the audit cannot be forged. Because a breach is the one unrecoverable failure, security is tested adversarially and independently, and it is verified by trying to break in, not by assuming we cannot be broken into.

**Required coverage, as a matter of law:** paths that touch money, the ground truth, tenant isolation, or authentication are held to the strictest standard — they are not shipped without domain, integration, contract, property, and failure tests proving they are correct and safe, because a defect in these paths is a defect in the asset or the trust. Paths that touch only derived, temporary, or presentation data are tested proportionate to their risk. The principle is not "test everything equally"; it is *"test in proportion to what a failure costs the asset and the trust,"* and for money and truth, the cost is the company, so the coverage is maximal.

---

# PART 10 — Operational Philosophy

A system we cannot see is a system we cannot trust, and a system our customers cannot rely on is a system that forfeits the trust that is our asset's precondition. Operations — the discipline of running the system reliably and knowing its state at all times — is therefore not back-office plumbing; it is graph integrity and trust, made continuous.

**Observability is a default, not an addition.** Every system emits the truth about itself — its metrics, its traces, its logs, its health — from the first line, because you cannot operate, debug, or be trusted to run what you cannot see. Observability is designed in, not bolted on, and a system that cannot tell us what it is doing is a system that will fail our customers silently, which is the worst way to fail. The founding state — a system with no observability — is corrected permanently by making self-reporting a property of every service.

**Monitoring answers "is it healthy?" continuously.** We monitor the health of every critical path — can a restaurant take an order, take a payment, print a ticket, sync its truth — with checks that run continuously and synthetically, per store where it matters, so that we know a store is in trouble *before the store's customers do*. A monitoring gap on a critical path is a blind spot on the trust, and blind spots are where outages become reputation events.

**Tracing follows a request across contexts.** Because the system is composed of bounded contexts, a single business action (an order, a payment) crosses several, and when it fails we must be able to follow it end-to-end to find where. Distributed tracing is how a failure in a system of many parts is diagnosed in minutes instead of days, and speed of diagnosis is speed of recovery, which is the customer's trust preserved.

**Logging records what happened, structured and searchable.** Logs are structured, attributed, and correlated to traces, so that when we need to understand an incident we can reconstruct it precisely. Logs never contain secrets or unnecessary personal data (Part 7), and they are retained proportionate to their operational and compliance value.

**Metrics measure what matters, including the graph.** We measure system health (latency, errors, saturation) and we measure the *asset* (the Part-3 north-star metrics: density, depth, exclusivity, prediction accuracy, liquidity, trust), because the engineering exists to grow the graph and we must see whether it is. A metric that no one watches is a metric that should not exist; a graph metric that no one measures is an asset growing or shrinking in the dark.

**Incident response is defined, practiced, and blameless.** Failures will happen; what distinguishes a resilient company is not their absence but the discipline of the response. We define who responds, how they are alerted, how they communicate, and how they recover, and we practice it, and we conduct blameless reviews afterward that fix the *system* rather than the person, because a culture that blames people hides the incidents that the next fix depends on seeing. Every incident that touches the truth or the trust is treated with the gravity that the asset demands.

**Backups and recovery are automatic, and recovery is proven.** The ground truth is backed up durably and continuously, and — this is the part naive companies skip — the recovery is *tested*, regularly, by actually restoring, because a backup that has never been restored is a hope, not a backup. Recovery objectives (how much data we could lose, how fast we can recover) are defined, measured, and met, because the ground truth is the asset and losing it is losing the company.

**Disaster is tested, not just planned.** We do not merely write a disaster-recovery plan; we *exercise* it — we practice losing a region, a data store, a critical dependency — because a plan that has never been run is a document, and a document does not recover a business at 3 a.m. Disaster testing is the operational equivalent of chaos testing: we induce the catastrophe in a controlled way to prove we survive it, before the uncontrolled version arrives.

The reason operations is sacred, stated once: **our asset is the *reliable, trustworthy availability* of the ground truth, and operations is the continuous discipline of keeping it reliable, trustworthy, and available. A system that is correct in a test but opaque, unmonitored, and unrecoverable in production has not protected the asset; it has merely postponed the moment of its loss.**

---

# PART 11 — Evolution

This constitution is permanent, but the systems built under it are not; they will be replaced many times over twenty years, and the discipline of *how* they change is what lets the company evolve without losing itself or its asset. Evolution is governed, not chaotic, and it obeys a few permanent rules.

**Principles are fixed; implementations are replaceable.** The laws in this document do not change. The technologies that satisfy them change constantly, and are replaced without ceremony when a better one makes a principle cheaper to uphold. An engineer proposing a new technology answers one question — *does it uphold the principles better?* — and never the question *is it exciting?* The distinction between a principle and an implementation is itself the most important thing an engineer must learn to see, because confusing them is how a company either ossifies (treating a tool as sacred) or drifts (treating a principle as optional).

**Architecture changes through RFCs.** A significant change to the architecture is proposed as an RFC that descends from this one, argues its case against these principles, is reviewed openly, and is ratified before it is built. RFCs are how the company reasons about change deliberately and leaves a record of *why*, so that a future engineer can understand not just what the system is but why it became so. This RFC-000 is the root; every architecture RFC is judged against it, and an RFC that violates a principle here is rejected regardless of its other merits.

**RFCs evolve by supersession, never by silent edit.** When a decision changes, a new RFC supersedes the old, and the old remains in the record marked as superseded, because the history of our decisions is itself valuable — it is the audit trail of the architecture, and it teaches future engineers the reasoning that led here. We never silently rewrite the record of what we once decided, for the same reason we never silently mutate the ground truth: the history is part of the truth.

**Deprecated systems die on a schedule, gracefully.** A system being replaced is not switched off; it is *deprecated* through the same disciplined process as an API (Part 5) — announce, provide the replacement, migrate the dependents, measure who remains, help them move, and only then retire. A system dies when nothing depends on it, not when we are tired of it, because a dependent left stranded is a trust broken.

**Migrations are reversible, tested, and lossless.** Every migration — of schema, of data, of infrastructure — is reversible (we can roll back if it goes wrong), tested (forward and backward, Part 9), and lossless (no truth is destroyed, and old events remain readable). We migrate the graph the way a surgeon operates on a beating heart: carefully, reversibly, and never in a way that could lose the patient. A migration that cannot be rolled back is a bet we do not make with the asset.

**Technical debt is tracked, and the debt against the asset is paid first.** We distinguish debt that merely slows us from debt that endangers the asset or the trust — an untested money path, a security gap, a place where truth could be lost, a tenant-isolation weakness — and we pay the second kind first, always, because it is not really debt; it is a latent loss of the asset waiting to be realized. Our founding carried exactly this kind of debt (no tests on money, a weak auth surface, no observability), and the lesson is permanent: *asset-endangering debt is paid before features, because a feature on top of a hole in the asset is a taller structure over the same hole.*

**We strangle and replace; we rarely rewrite wholesale.** When a system must be replaced, we replace it incrementally, behind stable interfaces, moving piece by piece while the old and new run side by side, rather than betting the company on a big-bang rewrite. This is how our own front-end monolith and our own ERP coupling are meant to be replaced — strangled behind interfaces, not thrown away in one dangerous leap — because a wholesale rewrite of a system that holds the asset is a wholesale risk to the asset, and we do not take wholesale risks with the one thing we cannot replace.

The reason evolution is disciplined, stated once: **the company must be able to change everything about how it works while never losing the asset it works to build. Governed evolution — fixed principles, RFC'd changes, graceful deprecation, reversible migrations, asset-debt paid first, strangle-don't-rewrite — is how a system stays alive and improving for twenty years without a single moment where a change to the machinery becomes a loss of the truth.**

---

# PART 12 — The Fifty Engineering Laws

These are mandatory. Every engineer knows them. Every review checks them. Every system upholds them. They are the compression of this entire RFC into fifty sentences an engineer can hold in memory, and when a decision is unclear, they decide it.

### Truth & Events
1. Every mutation of importance produces an event.
2. Every event is immutable — corrected by a new event, never edited.
3. Every event is attributed to an authenticated actor and a time.
4. State is a projection of events, never the primary record.
5. Every event carries a stable, globally-unique identity.
6. Every event is processed exactly once — never zero times, never twice.
7. Every event stream has a definite, preserved order.
8. Events relate by causal keys, never by wall-clock timing.
9. Every event is versioned; its meaning, once recorded, never changes.
10. Old events remain readable and meaningful forever.

### Data
11. Operational ground truth is sacred and never silently destroyed.
12. Every derived, analytical, or cached value is reproducible from its source.
13. No derived value is ever treated as authoritative.
14. The important never lives only in temporary or in-memory data.
15. Every piece of data has exactly one owning context.
16. Data is deleted only by an explicit, audited, lawful act — never silently.

### Reproducibility & State
17. Every state is reproducible by replaying its events.
18. Every environment is recreatable from its definition.
19. Any past state of the truth can be reconstructed for any moment.

### APIs & Compatibility
20. Every API is versioned from its first release.
21. Within a version, only backward-compatible changes are made.
22. Consumers tolerate additions they do not understand.
23. Nothing public is removed without a full deprecation process.
24. We never break a customer with a change they did not choose.
25. No API call is anonymous to anything that touches the truth.

### Offline
26. Everything the restaurant needs to serve works with no network.
27. The node owns its truth until the cloud acknowledges it.
28. Offline capture is durable, ordered, and survives crash and power loss.
29. Synchronization loses nothing and double-counts nothing.
30. Conflicts resolve by a rule decided in advance and recorded — never last-write-wins.
31. Recovery from failure is automatic and requires no human in the normal case.
32. Every failure mode is enumerated and has a defined, non-silent outcome.

### Security & Trust
33. Every request proves its identity; position is never trusted over proof.
34. Every actor has least privilege, checked at every boundary, denied by default.
35. Every secret is stored in a managed store, never embedded, and rotates.
36. The truth is encrypted in transit and at rest.
37. Every privileged and money-affecting action is in the immutable audit trail.
38. A breach is the one unrecoverable failure; we engineer as if it is fatal.
39. Every engineer protects the trust before they protect the schedule.

### AI
40. The Operating Graph is truth; AI is never truth.
41. AI never owns or silently modifies a fact.
42. AI proposes; a human decides or has bounded, audited, pre-authorized authority.
43. Every AI action is attributed and auditable like any other action.

### Testing
44. Code that touches money, truth, tenancy, or identity does not ship untested.
45. Every migration is reversible and tested forward and backward.
46. Offline, chaos, and security guarantees are proven by inducing failure, not assumed.

### Operations & Evolution
47. Every system is observable by default; a blind path is a forbidden path.
48. Every backup's recovery is proven by actually restoring it.
49. Principles are fixed and defended; technologies are held loosely and replaced on merit.
50. Asset-endangering debt — untested money paths, security gaps, possible truth loss — is paid before any feature.

---

## Closing

These parts and these fifty laws are the engineering constitution of Mezze. They name no technology, because technologies die and these must not. They exist to serve one thing across every decade and every rewrite: **capture the ground truth losslessly, hold it immutably, serve it reliably, and never betray the trust that lets us hold it.** An engineer who builds by these laws is building the Operating Graph, whether they are writing the terminal, the sync engine, the payment workflow, or the model that reasons over it all.

When a technical decision is hard, this document decides it. When it does not obviously decide it, the engineer traces the decision to the invariant — *does this protect and grow the graph, and does it protect the trust?* — and the answer is there.

*Build Mezze from these RFCs. This is their root.*

*Capture the truth. Hold it immutably. Serve it reliably. Protect the trust. Everything else is implementation.*
