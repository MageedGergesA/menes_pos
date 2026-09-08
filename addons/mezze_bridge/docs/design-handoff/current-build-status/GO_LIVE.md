# Mezze — Online (cloud SaaS) Go-Live Checklist

Turns the missing ~28% (see readiness map) into an ordered, actionable path.
Ordered by **unblocking power** — do P0 before anything else; P1 is required for a
real merchant; P2 integrations can phase in after first customer; P3 is
business/legal, run in parallel.

Owner: **Dev** = code, **Founder** = accounts/paperwork, **External** = a 3rd
party (bank/ETA/aggregator) gates the timeline.

---

## P0 — Launch blockers (nothing ships without these)

### 0.1 Production deployment — get off `localhost` · Dev
- [ ] Provision a VPS (the Teklines Contabo box already exists) — Ubuntu, Postgres 15+, Python 3.12 venv, Odoo 19 CE.
- [ ] Reverse proxy (nginx) + **HTTPS** (certbot/Let's Encrypt). The whole token/cookie story assumes HTTPS in prod — `secure` cookie only sets under TLS.
- [ ] Real Postgres (not the dev DB): tuned `postgresql.conf`, dedicated role, `pg_hba` locked down.
- [ ] Odoo as a **systemd service** (workers ≥ 2, `proxy_mode = True`, `list_db = False`, strong `admin_passwd`).
- [ ] Domain + DNS (mezzehq.com / mezzepos.com — noted as free in the strategy).
- **Unblocks:** everything else (can't test payments/ETA/webhooks without a public HTTPS origin).

### 0.2 Payments — prove real money · Founder + External + Dev
- [ ] **Founder:** open a real **Paymob** merchant account (Egypt) → KYC → get live `api_key / public_key / secret_key / hmac_key`.
- [ ] Configure the native `payment.provider` (code=`paymob`) in prod with live keys; set `account_country_id = Egypt`.
- [ ] **Run one real card transaction end-to-end** (intent → hosted checkout → webhook `/payment/paymob/webhook` HMAC → capture → order finalized). This has NEVER happened — highest risk item.
- [ ] Verify the **charge-before-finalize** + `/w1/payment/void` compensating-reversal path with a real capture (force a finalize failure, confirm the reversal fires).
- [ ] Decide **refund policy**: Paymob has no Odoo auto-refund (`support_refund='none'`) → confirm the manual-reversal queue + staff process.
- [ ] **Fawry / wallets:** enable via Paymob (or a 3rd-party acquirer); repeat the real-transaction test.
- **Unblocks:** the entire card revenue path (the product's #1 promise: "no lock-in, your own processor").

### 0.3 ETA compliance — decide the regime · Founder + External + Dev
- [ ] **Founder:** confirm with an accountant/ETA which regime applies: **e-invoice (B2B)** vs **e-receipt (B2C POS)**. This is a business/legal decision, not a code one.
- [ ] **B2B path (built):** register the company on the ETA portal, get the **USB signing token** + certificate, install `l10n_eg_edi_eta`, configure the journal/EIN, run one real cleared invoice.
- [ ] **B2C e-receipt path (GAP):** not native — either (a) integrate an ETA e-receipt provider/SDK, or (b) scope + build the POS e-receipt submission. **Estimate this before promising B2C compliance.**
- [ ] Until cleared, the receipt honestly shows "no e-invoice (B2C)" — keep that honest, don't fake a "cleared" badge.
- **Unblocks:** legally selling to Egyptian businesses that need tax invoices.

---

## P1 — Required for a real paying merchant

### 1.1 Auth hardening · Dev
- [ ] Move off the single **shared token** to **per-terminal tokens** (`mezze.terminal.token` already exists) or full **session-auth** on the API. Shared-token + `cors='*'` is fine for a demo, risky for prod multi-tenant.
- [ ] Tighten CORS: replace `cors='*'` on money endpoints with an allow-list of the deployed origin(s).
- [ ] Rotate the strong token out of any dev URLs/history; confirm the launcher-cookie path is the only entry.
- [ ] Rate-limit auth + webhook endpoints (fail2ban / nginx `limit_req`).

### 1.2 Real merchant data · Founder + Dev
- [ ] Real **chart of accounts** (l10n_eg) + real **tax config** (replace the demo 12%/14% seed with the merchant's actual VAT/service).
- [ ] Real product catalog, prices, categories, modifiers, **barcodes**.
- [ ] Real branches (`pos.config`), floors, tables, payment methods, opening floats.
- [ ] Real staff users + cashier PINs (retire the demo MR/AH/NF/KS · 1234).
- [ ] BoM/recipes for the food-cost moat (only a few demo products have them today).

### 1.3 Backups, monitoring, runbook · Dev
- [ ] Automated Postgres + filestore **backups** (daily, offsite, tested restore).
- [ ] Uptime + error monitoring (Sentry/healthcheck on `/mezze/api/v1/health`).
- [ ] Log rotation; a basic **runbook** (restart, restore, rotate token, close stuck session).
- [ ] Load-test a realistic shift (concurrent fires to one table, KDS, checkout) — the concurrency code is built but unproven at scale.

---

## P2 — Integrations (phase in after first merchant is live)

### 2.1 Delivery aggregators · Founder + External + Dev
- [ ] **Founder:** apply for **Talabat / Jahez** partner/API access (each is a business onboarding).
- [ ] **Dev:** write the per-aggregator **payload adapter** (their real webhook shape → our normalised contract) + wire their **HMAC secret**.
- [ ] Build the **status-push-OUT** leg (`_notify`) against their real accept/ready/dispatch API.
- [ ] Reconcile **commission** into the GL (currently informational only).

### 2.2 Hardware · Founder + Dev
- [ ] Test against a **real network thermal printer** (ESC/POS :9100) — bytes verified via mock, never a physical device.
- [ ] Wire the cash drawer to the receipt printer; confirm the kick.
- [ ] **Arabic receipt** (printer Arabic codepage + RTL reshaping) — currently Latin-only.

### 2.3 Receipt delivery · Dev
- [ ] Email invoice + **WhatsApp** receipt are **demo placeholders** (toast only). Wire real email (Odoo mail) + WhatsApp (Meta Cloud API) if promised.

---

## P3 — Business / legal (run in parallel, non-code) · Founder

- [ ] Merchant onboarding flow + contract; pricing tiers live.
- [ ] Company commercial registration / tax posture (for billing merchants).
- [ ] **Terms of Service / Privacy / data-handling** (POS handles customer PII + payments).
- [ ] Support channel + SLA.
- [ ] Odoo Apps Store listing compliance (if the free module ships there).

---

## Critical path (shortest route to first live merchant)

```
0.1 Deploy (HTTPS) ──► 0.2 Paymob live + 1 real txn ──► 1.2 Real merchant data ──► 1.1 Auth harden ──► 1.3 Backups ──► GO
                   └──► 0.3 ETA decision (parallel; gates B2B invoicing only)
```

Aggregators (2.1), hardware (2.2), and WhatsApp/email (2.3) are **fast-follow** — a
café can run a full paid shift without them. The two things that genuinely block
revenue are **0.1 deployment** and **0.2 a proven real card transaction**.

## The one-line honest summary
The software is ~90% built; go-live is gated by **deployment + real payment/ETA
credentials** — external steps no amount of extra code replaces. Estimated
engineering to close P0+P1 (assuming creds arrive): **~2–3 focused weeks**;
calendar time depends on Paymob KYC + ETA token turnaround.
