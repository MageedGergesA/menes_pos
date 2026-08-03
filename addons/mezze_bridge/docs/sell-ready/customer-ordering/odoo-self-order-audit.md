# Odoo 19 Native Self-Order Audit (S4 §3)

Source: `/home/mageed/odoo_work_19/odoo/addons/pos_self_order` (Community). Verdict per capability:
REUSE DIRECTLY / REUSE BACKEND / REUSE DESIGN-SEMANTICS / COEXIST / MEZZE ALREADY BETTER / NOT SUITABLE.

## Findings

| Native capability | Verdict | Evidence |
|---|---|---|
| `pos_self_order` OWL customer app (mobile/kiosk) | **COEXIST / NOT SUITABLE as the production frontend** | Mezze already ships a certified, bilingual, payment-integrated static storefront + table-QR ordering; adopting the native OWL self-order app would mean running two competing customer products |
| `self_ordering_mode` (nothing/consultation/mobile/kiosk) + `self_ordering_service_mode` (counter/table) + `self_ordering_pay_after` (each/meal) | **REUSE DESIGN-SEMANTICS** | `models/pos_config.py:35,42,82` — Mezze mirrors the *concepts* (kiosk mode, eat-in/takeaway, pay policy), not the fields |
| Order-taking route `/pos-self-order/process-order/<device_type>`; `source` = kiosk/mobile; takeaway = `preset.service_at != 'table'` | **REUSE SEMANTICS** | `controllers/orders.py:11,28,38,264` — Mezze keeps its own `_do_fire` engine + `mezze_channel` |
| **Native KIOSK payment — HARD LIMITATION** | **REUSE KNOWLEDGE (constraint)** | `models/pos_payment_method.py`: kiosk `_load_pos_self_data_domain` = `[('use_payment_terminal','in',['adyen','stripe'])]`; `_payment_request_from_kiosk` base is `pass`. **The native Odoo 19 kiosk can ONLY take Adyen/Stripe integrated card terminals — no cash, no arbitrary online provider, no pay-later.** |
| Kiosk payment route `/kiosk/payment/<config>/<device_type>` | reference only | `controllers/orders.py:191` |
| Session requirement: self-order needs an active session | **REUSE SEMANTICS** | `orders.py:254` (`has_active_session`) |
| Preparation display / KDS for self-orders (Enterprise) | **COEXIST** | Mezze has its own `mezze.kds.ticket` |
| `pos_online_payment` for self-order online pay | **REUSE BACKEND** | Mezze already reuses `/pos/pay` + `_process_pos_online_payment` (S2C-5) |
| Multi-language menu / translations | **MEZZE ALREADY BETTER** | Mezze storefront ships a full EN/AR dictionary + RTL + dark |
| Presets eat-in/takeaway + fiscal position | **REUSE SEMANTICS** | `models/pos_preset.py` `service_at`; Mezze applies its own pricelist/tax via `_build_lines` |

## Decisions
- **Native `pos_self_order` = NOT the production frontend** (COEXIST/off). Mezze's storefront + table-QR + new kiosk mode is the ONE customer-ordering product. Running the native OWL self-order app alongside would confuse administrators — documented as OFF/optional.
- **Native kiosk payment is Adyen/Stripe-terminal-ONLY.** Mezze does NOT inherit broader kiosk payment automatically. **Mezze kiosk v1 payment = pay-at-counter (PAYMENT_DUE, unpaid, never faked)**, using Mezze's own certified pickup pay-at-counter pattern. Integrated-terminal at a kiosk = software path (S2C-3 simulator) / **physical PENDING**. Cash at kiosk = **NEVER faked** (pay-at-counter only, unless a certified physical cash machine is present).
- **Reuse the SEMANTICS** (kiosk mode, eat-in/takeaway service mode, pay-after policy, session-required gate) on Mezze's own engine — not the native models/frontend.
