# Lane board query complexity — measured before and after (DT-PERF6.1)

Every number here comes from a real HTTP request against a real Odoo, measured
back-to-back on one quiet host: the **before** server runs `d8eca31` and the
**after** server runs this branch, both against the **same database**, reseeded
between sizes. Nothing is modelled or extrapolated.

## Method

- `POST /mezze/api/v1/drivethru/board`, per-terminal bearer token, `workers=0`.
- Total queries per request read from Odoo's own access-log line (the integer
  after the response size).
- KDS-specific statements counted with the SQL collector
  (`--log-handler=odoo.sql_db:DEBUG`), over a **single** request window, after a
  warm-up request — so no result is carried over from a previous request.
- Latency: 5 warm-up requests discarded, then 25–30 measured; median and p95.

## Queries

| active cars | KDS statements before | KDS statements after | total queries before | total queries after |
|---|---|---|---|---|
| 1   | 2   | **1** | 18  | **17** |
| 6   | 16  | **1** | 32  | **17** |
| 36  | 96  | **1** | 112 | **17** |
| 100 | 266 | **1** | 282 | **17** |

The before-shape at 36 cars breaks down as **60 searches + 36 reads**: 36 payload
lookups, 24 more from the legacy `preparing → ready` mirror (one per car still
preparing), plus a read of every matched ticket's state. Optimising only the
payload would have left the mirror's 24 behind, which is why both consumers of
readiness in a board request share one map.

After the change the single statement is:

```sql
SELECT "mezze_kds_ticket"."pos_order_id" FROM "mezze_kds_ticket"
 WHERE ("mezze_kds_ticket"."pos_order_id" IN (…36 ids…)
   AND "mezze_kds_ticket"."state" NOT IN ('ready','served'))
 GROUP BY …                                        -- 0.531 ms
```

**Total** queries are flat at 17 from 1 car to 100 — not merely bounded for
readiness, but bounded for the whole request. DT-CORE6's additions
(`vehicle_stage`, `lane_sequence`, `service_sequence`) are plain field reads and
contribute none of them, which this re-measurement confirms rather than assumes.

## Latency (ms)

| active cars | before median | before p95 | after median | after p95 |
|---|---|---|---|---|
| 1   | 30.7  | 27.8–52.2 | 26.8 | 23.7–56.6 |
| 6   | 30.0  | 34.7      | 24.3 | 29.9      |
| 36  | 61.2  | 68.6      | 25.5 | 28.5      |
| 100 | 129.9 | 156.5     | 32.1 | 34.8      |

At 1 and 6 cars the two are within run-to-run noise (three repetitions each; the
p95 column shows the spread), which is the expected result — there was never much
to save at that size. The point of the change is the shape: before, latency roughly
quadrupled from 6 to 100 cars; after, it moves by about 8 ms across the same range.

Latency is evidence and is deliberately **not** asserted in the automated suite —
host load varies and a millisecond threshold would be a flaky test. The
deterministic regression gate is the query count, pinned in
`tests/test_drivethru_readiness_batch.py`.

## Still open, and not addressed here

`/drivethru/board` is declared read-only but the legacy mirror writes, so a request
that flips a car `preparing → ready` is replayed by Odoo on a read-write cursor —
the whole board is computed **twice** for that request. It is pre-existing, it is
not what this phase set out to fix, and the right fix is bound up with retiring the
overloaded `state` field rather than with flipping a route flag. Recorded so it is
visible; the doubling now costs 17 queries instead of 112.
