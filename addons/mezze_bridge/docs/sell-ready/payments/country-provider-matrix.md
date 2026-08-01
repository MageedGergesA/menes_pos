# Mezze Payments — Country / Provider Matrix (S2 §57)

Scalable record, not marketing. Only what the installed Odoo build + Mezze actually support.

| Provider | Type | Channel | Odoo module | Installed | Software | Production |
|---|---|---|---|---|---|---|
| Paymob | Online (card/wallet) | QR/pickup/delivery/web | payment_paymob | YES | READY | External Test PENDING |
| Demo | Online (test) | any | payment_demo | available (uninstalled) | for CI acceptance | N/A |
| Stripe/Adyen/Mollie/Razorpay/Worldline/PayPal/MercadoPago/DPO/Flutterwave/Xendit/Nuvei/Iyzico/Buckaroo/AsiaPay/Authorize/Redsys/APS | Online + (some) POS terminal | per provider | payment_* | present, uninstalled | SUPPORTED VIA ODOO | NOT TESTED |

Countries: per each provider's own documented coverage (do not restate/claim here). Paymob = first MENA
target (Egypt). No unsupported-country claims.
