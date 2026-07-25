# Training Index (P1 §25)
Role-scoped quick guides for the pilot, cross-referenced to runbooks/:
- **Host/Server** — arrival, seat, table transfer, safe merge (merge-with-payments is blocked), course hold/fire.
- **Cashier** — tender (cash/card/mixed/partial/change), lost-response retry (same uuid), refund via engine, session close.
- **Kitchen** — KDS prep states, 86 an item (propagates to all channels).
- **Manager** — approvals, refunds (≤ sold, enforced), reports, pause a channel, read the outbox/dead-letter view.
- **All** — internet/printer outage behavior (queue + reconnect), escalation triggers (duplicate payment, lost order, permanent outbox stall).
