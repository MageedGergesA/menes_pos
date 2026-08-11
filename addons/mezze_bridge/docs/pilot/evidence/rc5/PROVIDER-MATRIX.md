# RC5 PILOT — PROVIDER / INTEGRATION MATRIX

Every outbound integration was classified before the runtime was started, so that
preparation could not send a real customer communication or move real money.

**Nothing was disabled that a physical gate needs** — the entries below are the state as
inherited from the source database, not suppressions applied by this task.

| Integration | State in pilot DB | Classification | Can it reach a real third party? |
|---|---|---|---|
| Outgoing email (`ir.mail_server`) | **0 servers configured** | NOT CONFIGURED | **No** — mail cannot leave |
| Queued mail (`mail_mail` outgoing) | **0 pending** | — | No backlog to flush |
| Payment provider `demo` | state `test` | SANDBOX | No — demo provider |
| All other payment providers (11) | state `disabled` | DISABLED | **No** |
| Payment terminal | none configured; no hardware | NOT CONFIGURED | No |
| SMS | no parameters present | NOT CONFIGURED | No |
| WhatsApp | no parameters present | NOT CONFIGURED | No |
| Delivery / aggregators (UrbanPiper, Talabat…) | no parameters present | NOT CONFIGURED | No |
| Webhooks | none configured | NOT CONFIGURED | No |
| Mezze API shared token | `mezze_bridge.api_token` **SET** (redacted) | internal | Local only |
| Scheduled jobs | **20 active / 21 total** | ENABLED | Local only — no outbound provider exists for them to call |

## Net risk during preparation

**Zero real customer communications and zero real charges are possible in the current
configuration** — there is no mail server, no live payment provider and no messaging
integration. Nothing had to be switched off to make that true.

## Two states the operator should decide on before the shift

1. **`env_profile = development`** and **`neutralized = false`**.
   The database is *not* neutralized. That is currently harmless (nothing outbound is
   configured) but it is the wrong posture the moment a real payment provider or mail
   server is added for the pilot. Decide deliberately: either keep it un-neutralized
   because the pilot must exercise a real provider, or neutralize and accept that those
   gates cannot run.

2. **Payment terminal: NOT READY.** No provider account, no terminal hardware, no
   credentials. Gates 10, 11 and 12 cannot run until a provider environment
   (sandbox *or* live, chosen explicitly) is configured and its terminal is on the LAN.
   External payment certification remains **PENDING** independently of this pilot.

## Reminder

No real charge, refund or reversal was attempted during preparation, and none should be
until the operator explicitly authorises pilot execution with a named provider
environment.
