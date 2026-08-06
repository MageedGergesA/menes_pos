# ORIGINAL RESTAURANT UX PRINCIPLES (Restaurant UX Patterns + Cashier/Kitchen/Payment specs)

Positioning (stated repeatedly): "**Faster, simpler and safer than Foodics, Toast, Lightspeed, Square and Dynamics 365**." Every pattern benchmarked before shipping.

## Seven workflow laws
1. One canonical path per task. 2. Exactly one obvious next step ("the primary action is always the loudest thing present"). 3. Every mistake has a single faster-than-restart way back ("Recovery is designed, not improvised"). 4. No hidden state / silent failure. 5. No dead ends ("a failed payment, lost printer or dropped connection never destroys an order"). 6. Measured in clicks/dialogs, tuned for the busiest hour. 7. Every workflow closes on an unmistakable confirmation. **Budget: 600 orders/hour; happy paths carry ZERO dialogs — confirmations reserved for payment + destructive actions only.**

## Cashier speed
- Product grid virtualized to 10k SKUs (≤200 live DOM cards, 60fps, add ≤16ms, zero layout shift).
- **Pinned/recent favorites** — "cashiers hit the same 5–8 categories all shift" → cut eye+hand travel.
- Multi-key search (EN+AR substring, SKU, barcode, alias, fuzzy) — "at rush, search beats browsing" ("/" focuses, Enter adds top result).
- **Predictive defaults** (last order type, usual tender, popular items) pre-fill the common case to one tap.
- Safe keyboard shortcuts mirror every touch action for expert cashiers (⌘↵ charge, ⌘Z undo, F2 clear).

## Payment hierarchy
- Totals panel = **read-only mirror of the Order Engine** ("the workspace renders, never computes").
- Nine tenders: cash · card · wallet · gift card · voucher · store credit · bank transfer · house account · custom. Only config-enabled render; **suggested tender pre-highlighted**.
- Cash: denomination + smart-rounded suggestions (next 5/10/50); change ≤16ms; drawer-open audited; overpayment never blocks.
- Card: explicit state machine (select→authorizing→approved|declined|timeout|cancelled) with retry-without-re-entry and **idempotency key (a retry never double-charges)**.

## Kitchen distance readability
- Cooks read from 1–2m with busy hands → large type, high contrast, **pre-attentive aging color + timer + position (not color alone)**.
- Ticket state machine fired→cooking→ready→served (+recalled/rejected/void) drives color *and* position; count-up timer ok→warn→late maps to semantic tones + subtle late-pulse.
- Priority tickets get a brand-accent border + top position; **allergen always a danger Badge, never color-only**.
- Bump ≤1 action, bump-bar key mapped; recall reversible within a window; 86 propagates live to the POS grid; scales to 1000 tickets (≤120 live cards, new ticket ≤1s in correct priority slot).

## Floor / reservation / scanning
24px zone separation "so tables and reservations never visually merge"; 16–20px between tickets across the pass; table identity on tickets (Table 12 · N items).

## Order types / courses / late / cancellation / addition / 86
Dine-in / Takeaway / Delivery / Drive-thru segmented at top. Fire-by-course honored (course-group headers brighten once on fire). Late = ambient slow border-pulse (SLA breach). Void/refund = destructive safeguards + "Voided by manager". Kitchen 86 → cashier notified instantly on the exact line, one-tap substitute/remove; guest total + KDS update together.

## Manager override
Refund/void escalate to shift-supervisor; "Approval declined → refund halts in a reversible *pending* state; nothing issued until authorized." Default-deny RBAC (→ABAC) with temporary elevation → Odoo res.groups + record rules.

## One-hand / busy-shift / offline
44px targets, ≥8px separation, destructive extra-separated, primary within thumb arc. **Every rushed action reversible for a few seconds via an undo toast ("speed without fear").** Optimistic UI + safe rollback, input preserved across a sync. Offline-first — calm offline badge, ordering continues from local cache, outbox auto-syncs on reconnect via **per-key merge** ("only true clashes surface a quick review").

## Remediation-priority read
The highest-leverage restaurant-UX principles NOT yet visible in production: **favorites/predictive defaults**, **undo-toast "speed without fear"**, **keyboard parity**, and the **five un-built staff workspaces** (Floor/Table-Map, Reservations, CRM, Reporting as production screens). The two shipped workspaces (Cashier, KDS) already honor the core payment-mirror/idempotency and kitchen-aging/allergen/86 laws.
