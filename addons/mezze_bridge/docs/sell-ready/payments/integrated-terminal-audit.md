# S2C-3 — Integrated Payment Terminal Audit (Odoo 19 source)

> Audit performed against the **installed local Odoo 19 source** at
> `/home/mageed/odoo_work_19/odoo` before any code was written (S2C-3 §2).
> Nothing here is inferred from provider marketing or documentation — every claim
> cites a file in this tree.

## 1. Native terminal architecture (as it actually is)

Odoo POS terminals are **client-side** `PaymentInterface` subclasses registered into
the **native POS store**:

- Base class: `point_of_sale/static/src/app/utils/payment/payment_interface.js`
  — `constructor(pos, payment_method_id)`; the whole contract (`sendPaymentRequest(uuid)`,
  `sendPaymentCancel(order, uuid)`, `sendPaymentReversal`, `close`) operates on the
  **native POS order's selected payment *line*** identified by `uuid`.
- Registration: `register_payment_method('<id>', Class)` into
  `@point_of_sale/app/services/pos_store` — keyed by the `use_payment_terminal`
  selection value.
- Server model field: `pos.payment.method.use_payment_terminal`
  (`point_of_sale/models/pos_payment_method.py:51`), selection built by
  `_get_payment_terminal_selection()` (only shows installed interfaces).
- Result storage (server, SAFE metadata only): `pos.payment`
  (`point_of_sale/models/pos_payment.py`) — `transaction_id`, `payment_ref_no`,
  `payment_method_authcode`, `card_type`, `cardholder_name`, `payment_status`.
  **No PAN / CVV / PIN / track / EMV** anywhere.
- Force Done: native, **unrestricted** — `payment_screen.js:367 sendForceDone(line)`,
  surfaced as a plain button in `payment_lines.xml` on `waiting` / `force_done`
  states. Any cashier can click it.

### Trust model (how success becomes authoritative)

Worked example — Stripe (`pos_stripe/static/src/app/payment_stripe.js`):
client fetches a **server-minted** connection token (`stripe_connection_token`),
creates a **server-mediated** PaymentIntent (`stripe_payment_intent`), the reader
SDK collects+processes against Stripe, then the **server captures**
(`stripe_capture_payment`). Success is the provider SDK's `paymentIntent` result,
mediated by server RPCs on `pos.payment.method`. The `pos.payment` row is written
later when the whole order syncs. **The financial truth is the provider's,
established through the server — never a bare browser boolean.**

Adyen / Mercado Pago / Viva.com / QFPay additionally ship **server controllers**
(`controllers/main.py`) with webhook/notification/poll routes — i.e. explicitly
**Odoo-server-mediated** verification.

## 2. Providers found in THIS installed source

| Provider | Module | Installed? | `use_payment_terminal` id | Server-mediated | Client `this.pos.*` coupling | IoT |
|---|---|---|---|---|---|---|
| Adyen | `pos_adyen` | available (not installed) | `adyen` | **Yes** (controllers/main.py webhook) | 6 accesses | No IoT (terminal API) |
| Stripe | `pos_stripe` | available (not installed) | `stripe` | Yes (intent+capture RPC) | 4 accesses | No IoT |
| Razorpay | `pos_razorpay` | available (not installed) | `razorpay` | RPC-mediated | 5 accesses | No IoT |
| Mercado Pago | `pos_mercado_pago` | available (not installed) | `mercado_pago` | **Yes** (controllers/main.py) | 2 accesses | No IoT |
| Viva.com | `pos_viva_com` | available (not installed) | `viva_com` | **Yes** (controllers/main.py) | 4 accesses | No IoT |
| QFPay | `pos_qfpay` | available (not installed) | `qfpay` | **Yes** (controllers/main.py) | 2 accesses | No IoT |
| Pine Labs | `pos_pine_labs` | available (not installed) | `pine_labs` | RPC-mediated | 7 accesses | No IoT |

Restaurant / self-order shims also present: `pos_restaurant_adyen`,
`pos_restaurant_stripe`, `pos_self_order_{adyen,stripe,razorpay,qfpay,pine_labs}`.

**NOT present in this source** (spec listed them, but local source is authoritative):
Ingenico, SIX, Worldline, Mollie, DPO Pay, Tyro → classify **NOT PRESENT**.

Classification per S2C-3 §2:

- **INSTALLED:** none (no `pos_*` terminal addon is installed in the Mezze DB;
  `mezze_bridge` depends only on `point_of_sale, pos_restaurant, payment_paymob`).
- **AVAILABLE BUT NOT INSTALLED:** Adyen, Stripe, Razorpay, Mercado Pago, Viva.com,
  QFPay, Pine Labs.
- **NOT PRESENT:** Ingenico, SIX, Worldline, Mollie, DPO Pay, Tyro.

Architecture class per provider: all seven are **CLIENT-DIRECT + ODOO-SERVER-MEDIATED**
(SDK/terminal on the client, trust anchored by server RPC and/or webhook), **NO IOT**
for the reader itself. Definitive IoT vs no-IoT per physical device family remains
**UNKNOWN UNTIL DEVICE TEST** and is out of scope here (§61, §78).

## 3. Can native adapters be reused directly? (S2C-3 §4)

**No — category C (tightly coupled).** Every adapter:

1. is constructed with the **native POS store** (`new X(pos, payment_method_id)`);
2. reads/writes the **native POS order's selected payment line**
   (`this.pos.getOrder().getSelectedPaymentline()`, `line.setPaymentStatus(...)`,
   `line.transaction_id`, `line.amount`);
3. registers itself into `pos_store` via `register_payment_method`;
4. issues RPC through `this.pos.data.call(...)`.

The Mezze production cashier is a **standalone Owl app** (`/mezze/pos`) with **no**
native POS store, order model, or paymentline objects. Importing an adapter would
drag in the entire native POS runtime. There is **no safe direct-reuse path** for
the standalone cashier in v1. (Options A "import directly" and B "reusable service
API" are both false against the source; only C is true.)

## 4. Reuse strategy chosen (S2C-3 §5, §42)

- Mezze implements **ZERO provider protocol.** No Stripe/Adyen/Ingenico/Worldline/
  auth/polling/callback logic is copied into `mezze_bridge`.
- Mezze builds **ONE** client orchestration layer (`terminal_service.js`) with
  normalized states + a single-in-flight guard, delegating the actual transaction
  to an **adapter** resolved from a registry keyed by the native
  `use_payment_terminal` identifier — **reusing Odoo's registry keys, not its
  coupled classes.**
- The only concrete adapter shipped is a **test-only simulator** (never selectable
  in production). Real providers are registered as **PENDING** adapters that
  refuse to start and report status — no fake success.
- The **authoritative outcome is decided server-side** (`mezze.terminal.transaction`).
  A browser `{"approved": true}` can NEVER mint a payment (§12, §68): for the
  simulator the server computes the outcome from the request's stored scenario; for
  a real provider the completion is simply not accepted (PENDING) → no payment.

Therefore, per §5, every real provider is classified:

```
SUPPORTED BY ODOO
MEZZE STANDALONE CASHIER INTEGRATION: PENDING
```

and the Mezze orchestration layer + simulator are what S2C-3 certifies (software).

## 5. Native behaviours preserved / improved

| Native behaviour | Mezze treatment |
|---|---|
| Client-side status machine (waiting/waitingCard/waitingCapture/done/retry) | Mapped to normalized states READY/SENDING/WAITING_CUSTOMER/PROCESSING/APPROVED/DECLINED/CANCELLED/ERROR/TIMEOUT/UNKNOWN |
| Connection failure auto-cancels the transaction | Preserved conceptually: server marks txn `error`; UI shows actionable error; never auto-paid |
| Unrestricted Force Done | **Hardened:** manager-PIN gated, reason required, eligible-state required, provenance `manual_force_done`, reconciliation-flagged, immutable audit (cashier can never self-force) |
| Safe result metadata (transaction_id, payment_ref_no, authcode, card_type) | Reused verbatim on `pos.payment`; no new PAN/secret fields |

## 6. IoT (S2C-3 §61)

None of the seven local providers require Odoo IoT for the reader (they are
terminal-API / SDK based). Whether a *specific physical device family* needs IoT is
**UNKNOWN UNTIL DEVICE TEST** and is explicitly out of scope for the software slice.
