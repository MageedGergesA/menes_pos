# RC6 PILOT — PROVIDER / INTEGRATION MATRIX

**Re-checked on 2026-08-12 against the RC6 pilot database** — not copied from RC5.

| Integration | State | Classification | Can reach a real third party? |
|---|---|---|---|
| Outgoing email (`ir.mail_server`) | **0 configured** | NOT CONFIGURED | **No** — mail cannot leave |
| Queued mail | **0 outgoing** | — | no backlog |
| Payment provider `demo` | `test` | SANDBOX | No |
| All other payment providers | **20 disabled** | DISABLED | **No** |
| Payment terminal | none; no hardware | NOT CONFIGURED | No |
| SMS / WhatsApp | no parameters | NOT CONFIGURED | No |
| Delivery aggregators | no parameters | NOT CONFIGURED | No |
| Webhooks | none | NOT CONFIGURED | No |

**Real charge capability: NOT READY.** No live provider, no terminal, no credentials.
Gates 10–12 cannot run until a provider environment is chosen explicitly and its terminal
is on the LAN. No charge, refund or reversal was attempted, and none should be without
explicit operator authorisation.

**Net risk during this redeployment: zero real customer communications and zero real
charges were possible.** Nothing had to be switched off to make that true.

## Two decisions the operator still owns

1. **`env_profile = development`, `neutralized = false`.** Harmless today because nothing
   outbound is configured, but it is the wrong posture the moment a real provider or mail
   server is added for the pilot. Decide deliberately: keep it un-neutralized because the
   pilot must exercise a real provider, or neutralize and accept those gates cannot run.

2. **Transport is plain HTTP, LAN-only** (`0.0.0.0:8090`, no TLS, not proxied). For a
   LAN pilot that is usually acceptable, **but it is a live blocker for the QR gate**:
   browsers restrict `getUserMedia` (camera) to secure contexts, so a customer phone
   pointed at `http://192.168.8.181:8090` will generally be unable to open the camera to
   scan. If the intended workflow is "customer scans a table QR with their own phone
   camera app", the camera is the phone's native app and the page only has to *load*, which
   plain HTTP does. If any in-page scanning is expected, HTTPS is required first.

   **Recorded as: BLOCKING FOR PHONE/QR PHYSICAL GATE (transport), not an RC6 software
   defect.** Internet exposure cannot be determined from inside the host and remains
   **UNKNOWN**; confirm LAN-only or place it behind HTTPS before device testing. No public
   exposure was configured by this task.
