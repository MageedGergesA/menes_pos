# Omnichannel Acceptance (P1 §16)
Channels proven by the suite + live multi-worker (O1):
- **QR table ordering** — signed, channel can be paused; checkout rejects 86'd items (`_assert_available`).
- **Pickup** — pay at counter; secure public status token (hash-stored, 24h expiry, revocable).
- **Delivery** — order/zone/fee/ETA + accepted/preparing/ready; **pay-on-delivery**; driver dispatch is manual (runbook).
- **Aggregator (prepaid)** — HMAC-signed callbacks, 401 on bad signature, rate-limited, **idempotent** (duplicate callback → one order); each active channel must carry an encrypted secret (validator check).
- **Customer status** — `/shop/status` rate-limited (40/60s, fail-open), generic 404 on miss, token len<24 rejected pre-hash.
**Disabled:** online card checkout (no live PSP redirect proven), drive-thru (not operationally accepted).
