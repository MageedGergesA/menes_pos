# Hardware Acceptance (P1 §12) — **On-site verification required**
The build/CI host has **no physical hardware** (no receipt printer, kitchen printer, cash drawer, or payment terminal).
- **What IS proven in code:** hardware jobs are queued through the outbox (`hw_job` / `outbox_event`) and
  dispatch idempotently on reconnect; printer/KDS-unavailable is handled by the outbox queue (runbook).
- **What MUST be verified on-site before first service:** actual receipt print, kitchen ticket print,
  cash-drawer kick, and (if used) payment-terminal tender on the pilot hardware, per runbooks/.
**Classification:** Pilot supported with on-site verification. Not a code blocker; a mandatory pre-service gate.
