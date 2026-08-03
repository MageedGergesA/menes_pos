# Cash-Machine Integration Audit (S2C-7 / L7)

Source-based audit of the **local Odoo 19 tree** (`/home/mageed/odoo_work_19/odoo`,
`enterprise2/`). No assumptions — every claim below cites the actual addon code.

> **Headline finding.** In this Odoo 19 source there is exactly **ONE** native
> automated cash-machine integration: **`pos_glory_cash`** (Glory). There is **no
> `pos_cashdro` and no `pos_cashmatic` addon** anywhere in `odoo/addons` or
> `enterprise2/` — those names appear only in Mezze's own prior sell-ready docs,
> never in Odoo. We therefore build Mezze's cash-machine orchestration against the
> one integration that exists (Glory) and classify Cashdro/Cashmatic truthfully as
> **not present in this Odoo version**. We do not fake support for a module that
> does not ship here.

## Per-machine classification

| Attribute | **Glory** | **Cashdro** | **Cashmatic** |
|---|---|---|---|
| ADDON | `pos_glory_cash` | — | — |
| INSTALLED? | installable (Community, LGPL-3, Odoo S.A.) | **NOT PRESENT** | **NOT PRESENT** |
| AVAILABLE? | yes (depends `point_of_sale`) | no addon in this tree | no addon in this tree |
| NATIVE INTEGRATION ID | `pos.payment.method.payment_method_type = 'glory_cash'` | n/a | n/a |
| BROWSER-DIRECT? | **YES** — browser opens a WebSocket straight to the machine | n/a | n/a |
| SERVER-MEDIATED? | **NO** — Odoo server never touches the device transaction | n/a | n/a |
| LOCAL NETWORK REQUIRED? | **YES** — `glory_websocket_address` = machine LAN IP | n/a | n/a |
| LNA? | Yes — browser reaches a private LAN IP (Chromium Local Network Access applies) | n/a | n/a |
| HTTPS? | `ws://IP:3000` on http, `wss://IP:3001` on https (`glory.js:29-31`) | n/a | n/a |
| REFUND SUPPORT? | Cash **dispense / withdrawal** via negative-amount payment, **manager-only** (`glory.js:359`). No distinct "refund a sale" API beyond dispensing cash. | n/a | n/a |
| CASH COUNT SUPPORT? | **YES** — `InventoryRequest`/`InventoryResponse` returns per-denomination inventory + status (`constants.js:33-36,154-163`) | n/a | n/a |
| FILL/EMPTY VIA ODOO? | **NO** — replenish/collect are machine-side (`WAITING_REPLENISHMENT`, `CollectRequest`); Odoo does not manage inventory | n/a | n/a |
| STANDALONE CASHIER REUSE PATH? | **PENDING** — see below | n/a | n/a |
| PHYSICAL CERTIFIED? | **NO** — no hardware available; software only | n/a | n/a |

### Glory — how the native integration actually works

- **`models/pos_payment_method.py`** adds `payment_method_type = 'glory_cash'` and three
  fields: `glory_websocket_address` (IP), `glory_username`, `glory_password`.
  `_load_pos_data_fields` **ships all three (including the password) into the POS
  bootstrap** — because the integration is browser-direct, the browser needs them to
  authenticate to the machine.
- **`static/src/app/services/pos_store.js`** patches `PosStore.processServerData` to
  attach `pm.payment_terminal = new GloryService(this, pm)` — i.e. Glory reuses the
  **native POS `PaymentInterface`/`payment_terminal` slot**, the same one card
  terminals use.
- **`static/src/glory.js`** (`GloryService extends PaymentInterface`, 641 lines) is the
  protocol client. It opens a `SocketIoService` WebSocket to the machine
  (`ws://IP:3000` / `wss://IP:3001`), logs in, and drives a Glory XML protocol
  (`ChangeRequest` to start a payment, `ChangeCancelRequest` to cancel,
  `InventoryRequest` for cash count, `StatusRequest`, `CollectRequest`, `ResetRequest`,
  occupy/release for cross-POS exclusion). On `ChangeResponse` SUCCESS it reads
  `Cash type="1"` (deposited) and `type="2"` (change returned) and calls
  `paymentLine.setAmount(cashGiven)` + `setReceiptInfo(...)`.
- **Network/security**: `neutralize.sql` scrubs the IP on a DB copy but **not** the
  stored username/password.

### Glory — normalized machine states available at source
From `constants.js` `GLORY_STATUS` / `GLORY_STATUS_STRING`: `IDLE`, `STARTING_PAYMENT`,
`WAITING_PAYMENT` ("Waiting for insertion of cash"), `COUNTING`, `CALCULATING_CHANGE`,
`DISPENSING`, `WAITING_CANCEL`, `CANCELLING`, `COLLECTING`, `ERROR`,
`WAITING_ERROR_RECOVERY`, plus results `SUCCESS`, `CANCEL`, `CHANGE_SHORTAGE`,
`OCCUPIED_BY_OTHER`, `EXCLUSIVE_ERROR`, `DUPLICATE_TRANSACTION`, `AUTO_RECOVERY_FAILURE`.
Mezze's normalized layer maps onto: `READY → SENDING → WAITING_CASH → COUNTING →
RETURNING_CHANGE → APPROVED` plus `CANCELLED / ERROR / UNKNOWN`. We only use states the
source actually exposes; denomination-level state is available but **only surfaced to
authorized roles as a cash-count read**, never fabricated per-note UI.

## Standalone Owl reuse — like L3, this is the crux

Classification of the native Glory code for reuse from the **standalone Mezze Owl
cashier** (`/mezze/pos`), which does **not** run the native `PosStore`:

| Piece | Class | Notes |
|---|---|---|
| `utils/socket_io.js`, `utils/glory_xml.js`, `utils/constants.js` | **REUSABLE THROUGH NARROW ADAPTER** | pure protocol utilities; no PosStore dependency |
| `glory.js` (`GloryService`) | **TIGHTLY COUPLED TO NATIVE POS** | needs `this.pos` (PosStore), `order.payment_ids`, `paymentLine.payment_status/setAmount/setReceiptInfo/transaction_id`, `pos.getCashier()._role`, `pos.printReceipt`, `env.utils`, native dialog service |
| `pos_store.js` patch, `payment_lines.xml`, `cancel_dialog` | **TIGHTLY COUPLED TO NATIVE POS** | patches `PosStore`, native payment-screen templates |

**Conclusion — same honest position as S2C-3 integrated terminals:** the *protocol* is
reusable but the *orchestration* (`GloryService`) is welded to the native POS runtime.
Wiring the real Glory device to the standalone cashier means building a **narrow
PosStore-shaped facade** so `GloryService` can drive the Mezze order/payment model over
the machine WebSocket — that adapter is **not built in this slice**. We do **not** copy
the native POS internals into Mezze, and we do **not** reimplement the Glory XML/socket
protocol.

```
Glory cash machine:
  SUPPORTED BY ODOO:            YES (pos_glory_cash, browser-direct WebSocket)
  MEZZE STANDALONE ADAPTER:     PENDING (narrow PosStore facade over glory.js — not built here)
  MEZZE PHYSICAL:               NOT TESTED (no hardware)

Cashdro / Cashmatic:
  SUPPORTED BY THIS ODOO 19:    NO (no pos_cashdro / pos_cashmatic addon present)
```

## What S2C-7 therefore builds

Because no native cash-machine adapter can be safely reused from the standalone cashier
yet, S2C-7 delivers the **Mezze cash-machine ORCHESTRATION software** — the
server-authoritative payment spine, one-payment idempotency, concurrency lock,
authoritative-amount ceiling, forged-success rejection, cancel/connection-failure/
uncertain semantics, change reporting (inserted ≠ payment), refund-through-ceiling, and
cash-count read — proven with a **TEST-ONLY simulator** (never in production config).
This reuses the exact `mezze.terminal.transaction` financial spine already certified for
L3 integrated terminals; it is the same "device confirms → server settles exactly one
pos.payment" contract, with cash-machine-flavoured states and change semantics.

- **No device protocol is written by Mezze.** No Glory XML, no socket_io, no note/coin
  acceptor, no recycler, no firmware.
- Real Glory device path over the standalone cashier: **adapter PENDING** (refused
  server-side — a real cash-machine method cannot mint a payment from a browser claim).
- Machine credentials (`glory_username`/`glory_password`) are **never** loaded into the
  Mezze bootstrap, DOM, debug handle, logs, receipt, or support bundle.

## Network / deployment truth (Edge)
Cash machines are **local-branch LAN hardware**. The native integration is
**browser-direct over the LAN** — a browser on the restaurant LAN talks to the machine's
private IP; a remote cloud server cannot reach that private IP. This aligns with Mezze
Edge: `cashier browser → LAN → cash machine`. A WAN/Internet outage does **not** imply
the cash machine is offline — device/LAN health is tracked separately from Internet
status. We never equate "Internet online" with "cash machine online".
