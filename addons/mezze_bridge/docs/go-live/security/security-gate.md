# Security Launch Gate (P1 §6)

| Check | Result | Evidence |
|---|---|---|
| Shared-admin fallback disabled in production | PASS (prod) | `_resolve_principal`: shared token disabled in production profile; only a scoped emergency activation admits it. Validator: `shared_admin_disabled` FAIL if prod+not-disabled. |
| Development tokens removed | PASS (prod procedure) | dev shared token is a documented dev-only fallback; production sets `shared_token_disabled=1`. |
| Secrets outside source | PASS | `MEZZE_MASTER_KEY` from env; aggregator/webhook secrets envelope-encrypted (AES-GCM), never in ORM reads. |
| Public routes rate-limited | PASS | `/shop/status` rate-limited (40/60s/ip); checkout + aggregator + QR gated; atomic across workers. |
| QR cannot substitute another table | PASS | table derived from the signed QR identity, not a client id. |
| Status tokens cannot enumerate orders | PASS | opaque 128-bit token, **hash-stored**, expiry+revocation; sequential id → 404 (tests). |
| Aggregator callbacks require valid signatures | PASS | HMAC-SHA256; bad signature → 401 (test). |
| Webhook replay / nonce across workers | PASS | proven in the multi-worker replay increment (P6.5). |
| Branch/company scope authoritative | PASS | resolved from the principal, never client-trusted. |
| Customer totals never trusted | PASS | server prices (`_build_lines`, `_promo_for_cart`). |
| Terminals cannot open Admin Console | PASS | ADMIN_SETTINGS cap; terminals denied (tests). |
| Auditors read-only | PASS | ADMIN_CAPS auditor = read/export only (tests). |
| Manager perms require human principals | PASS | cashier roles (admin/manager/supervisor); no machine-only admin. |
| Logs exclude card data/credentials/tokens/PII | PASS | audit classifier emits set/unset for secret-shaped keys; only the token HASH is stored. |

## Status-token lifecycle (implemented)
- **Generation:** 128-bit (`os.urandom(16).hex()`), minted once per order (idempotent).
- **Storage:** SHA-256 **hash** only — the raw token is never stored server-side (returned once to the customer).
- **Entropy:** 128 bits.
- **Expiry:** `mezze_bridge.status_token_ttl_hours` (default 24h); expired tokens do not resolve.
- **Revocation:** `mezze_revoke_status_token()` — immediate, unresolvable thereafter.
- **After cancellation/refund/completion:** status still resolves (shows the final public state) until expiry/revocation.
- **Retention:** token hash retained with the order; revoke on privacy request.
- **Rate limits:** 40 lookups / 60s / client (fail-open, low-risk read).
- Tests: `TestStatusTokenLifecycle` (hash-not-raw, expiry, revocation) + O1 status tests.
