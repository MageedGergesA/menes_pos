# Performance (P1 §15)
- **Concurrency correctness under load:** live 2-worker runs sustain concurrent seat/fire/pay/merge/aggregator
  traffic with zero double-effects (idempotent by order uuid / business id). This is the pilot-relevant risk (correctness under contention), and it holds.
- **API guardrails:** per-endpoint rate limits (e.g. shop_status 40/60s fail-open; aggregator burst limiting) prevent a single client from starving others.
- **Not measured here:** formal p95 latency / sustained-throughput benchmark under a synthetic peak-hour load
  generator. A single-branch pilot's real peak (a few concurrent terminals) is well within the proven concurrency envelope.
**Classification:** Pilot supported. A formal load-test report is a pre-public-launch (not pre-pilot) task.
