# Mezze Universal Payments — Capability Audit (S2 §1)

Grounded in the actual installed Odoo 19 modules + Mezze code at `9f20f5b`. Classification:
**ODOO CORE** (reuse as-is) · **MEZZE ALREADY** (built) · **MEZZE EXTENSION** (genuine S2 delta) ·
**PROVIDER-SPECIFIC** · **PHYSICAL CERT ONLY** (S1.2/commercial) · **DEFERRED**.

## What already exists (do NOT rebuild)
### Odoo 19 core (installed / available)
- `pos.payment.method` carries the pluggable payment infrastructure:
  - `is_cash_count` → **L1 cash**; `type` (cash / bank / **pay_later = Customer Account** → **L6**)
  - `split_transactions` → split/mixed foundation
  - `use_payment_terminal` (pluggable selection) → **L3 integrated terminals**
  - `payment_method_type` "Integration" (none/terminal/qr_code/online…) + `qr_code_method`/`default_qr` → **L4 bank QR**
  - `journal_id` → accounting
- `pos.payment`, `pos.order` → canonical money rows/lifecycle.
- `payment` + `account_payment` (installed); `payment_paymob` (**installed**) → **L5 online**, Paymob native.
- `pos_online_payment`, `pos_online_payment_self_order`, `l10n_test_pos_qr_payment` (core) → online/QR POS layer.
- `payment_demo` (available, uninstalled) → deterministic online test provider (§27).
- ~19 provider modules present (adyen, stripe, mollie, razorpay, worldline, paypal, mercado_pago, dpo,
  flutterwave, xendit, nuvei, iyzico, buckaroo, asiapay, authorize, redsys, aps, custom, demo) → **L3/L5 SUPPORTED VIA ODOO**.
- Cash machines (Cashdro/Cashmatic/Glory) → **L7 SUPPORTED VIA ODOO** (adapters ship in POS/IoT ecosystem; not installed here).

### Mezze already built
- Cash, partial, mixed/split tender, payment idempotency, payment concurrency (SELECT-FOR-UPDATE),
  refund ceilings, linked refunds, concurrent-refund locks, lifecycle FSM, transactional outbox, auth,
  financial reconciliation tooling — all covered by the existing suite (`test_money_invariants`,
  `test_refund_ceiling`, `test_runtime_refund`, `double_pay_race`, etc.).
- `mezze.payment.provider` (code + tender + branch + credential_param) and `mezze.payment.transaction`
  (linked to Odoo `payment.transaction`, order linkage, amount/currency/kind/state/provider_reference) →
  online-provider scaffolding partly present.

## Per-level classification
| Level | Feature | Classification | Notes |
|---|---|---|---|
| L1 | Cash (exact/change/partial/mixed/rounding) | **MEZZE ALREADY** | verify change≠tendered invariant test exists/added |
| L1 | Generic manual tender (card/wallet/InstaPay/transfer/cheque) | **MEZZE EXTENSION** (thin) | branch-configurable `pos.payment.method` + Mezze mode/policy metadata |
| L2 | External terminal, manually confirmed + reference/approval | **MEZZE EXTENSION** | reference-policy fields + duplicate-reference detection + device link |
| — | Payment device registry (`mezze.payment.device`) | **MEZZE EXTENSION** | no exact Odoo equivalent; lightweight operational model |
| L3 | Odoo integrated terminals (Stripe/Adyen/…) | **ODOO CORE** (reuse `use_payment_terminal`) | Mezze: state normalization + reconciliation/report join; **not** Mezze-hardware-certified |
| L3 | Force-done recovery | **ODOO CORE + MEZZE policy** | wrap with manager-perm + reason + audit + reconciliation flag |
| L4 | Bank-app / payment QR | **ODOO CORE** (`qr_code_method`) | Mezze: keep Table-QR vs Payment-QR strictly separate; static/dynamic/confirmed classification |
| L5 | Online provider framework | **ODOO CORE** (`payment.provider`/`payment.transaction`) + **MEZZE ALREADY** (scaffold) | server-authoritative amount, idempotent notification→one pos.payment |
| L5 | Paymob | **PROVIDER-SPECIFIC (native, installed)** | software path READY; real external Test = **NOT EXECUTED** until creds |
| L6 | Customer account / credit | **ODOO CORE** (`type=pay_later` + receivable) | Mezze: optional credit-limit policy (warn/approve/block) if narrow + tested |
| L7 | Cash machines | **ODOO CORE / PHYSICAL CERT ONLY** | SUPPORTED VIA ODOO; physical device = NOT TESTED |
| all | Refund common engine | **MEZZE ALREADY** | every path routes through existing refund invariants; add manual-external status |
| all | Session reconciliation (settlement input + differences) | **MEZZE EXTENSION** | new reconciliation record; never edit historical pos.payment |
| all | Payment config validator checks | **MEZZE EXTENSION** | extend go-live validator |

## Genuine S2 build delta (what actually needs writing)
1. **Payment-method Mezze metadata** on `pos.payment.method`: `mezze_mode` (CASH/MANUAL/EXTERNAL_TERMINAL/
   ODOO_TERMINAL/BANK_QR/ONLINE_PROVIDER/CUSTOMER_ACCOUNT/CASH_MACHINE) + policy fields
   (`reference_policy`, `require_customer`, `allow_partial/mixed/refund`, `manager_approval_required`,
   `reconciliation_required`). Extend, don't replace Odoo semantics.
2. **`mezze.payment.device`** registry (name/code/branch/register/mode/acquirer/active/methods/recon policy).
3. **Manual reference capture + duplicate detection** (configurable scope: device+ref / method+ref / branch+ref; warn + manager override + audit).
4. **Reconciliation model** (`mezze.payment.reconciliation`): per-method expected vs settlement, statuses
   (MATCHED/OVER/SHORT/MISSING_SETTLEMENT/UNRECONCILED), provenance; separate from pos.payment.
5. **Terminal state normalization + force-done policy wrapper** (reuse Odoo; add manager/reason/audit).
6. **Online idempotency join**: ensure one `payment.transaction` DONE → one Mezze pos.payment (reuse
   `mezze.payment.transaction`); server-authoritative amount recompute + availability recheck before intent.
7. **Payment config validator** checks + **payment health** into the connectivity/status surface.
8. **Cashier/device/customer UX** (minimal, existing shell/tokens; EN/AR) + **receipt breakdown**.
9. **Tests** (L1/L2 manual, L3 mocked terminal states, L4 QR config, L5 demo-provider online +
   idempotency/concurrency/out-of-order, L6 credit, refunds, reconciliation, multi-worker).
10. **Docs** (README + per-level + CERTIFICATION-MATRIX + country-provider-matrix).

## Do-not
No seven engines — all converge on `pos.payment`/`pos.order` + the existing money/refund invariants.
No card vault, no PAN/CVV/PIN/track fields. No proprietary terminal drivers. No provider credentials in
frontend/logs/git. "SUPPORTED VIA ODOO" ≠ "MEZZE CERTIFIED".
