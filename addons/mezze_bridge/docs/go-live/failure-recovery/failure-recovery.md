# Failure Recovery (P1 §16–17)
Proven by the concurrency suite + outbox model:
- **Lost payment response** — re-submit same order uuid → engine returns the existing payment; never a second (double_pay_race).
- **Worker/process kill mid-flight** — queued work re-delivers once on recovery (idempotent consumers; mw_replay).
- **Stuck / poison outbox event** — dead-letter state, attempt count, last error, correlation id; **replay never duplicates** the effect; validator flags dead letters.
- **Aggregator duplicate callback** — one order (idempotent).
- **Illegal concurrent transition** — 409, no silent overwrite.
Evidence: tests/concurrency/{double_pay_race,outbox_race,mw_replay,p52_race}_evidence.txt.
