# Mezze Drive-Thru — master state

The canonical answer to *what is actually done*, kept in the repository rather than
in a chat transcript. Every claim here is traceable to a commit, a test, or a
committed evidence file; anything that could not be verified says so.

| | |
|---|---|
| Previous audit HEAD | `54db5599987642c16cb0f76ec7ea9cf167eee05a` |
| **Updated audit HEAD** | **`fef5b01f5981daad248dff0e1ab6be07191d8db4`** |
| Branch | `feature/drive-thru-enterprise-ux` — not pushed, not merged |
| RC7 | `de27828ada4d22f4bedf7ccf4cfd72ec0123a6b3` — UNCHANGED, ancestor of HEAD |
| RC8 | not created |

Superseded audits are not rewritten. The `54db559` audit remains true of `54db559`;
this document is true of `fef5b01`, and the delta is the terminal-state work.

## What changed since the previous audit

Three commits, one defect:

```
fef5b01  docs: terminal-state safety under a real four-worker HTTP race
4c4e4d0  test: prevent drive-thru vehicle resurrection
e1d2345  fix: make drive-thru terminal vehicle stages immutable
```

The `54db559` audit found — by source tracing only — that `cancelled` and `departed`
were not terminal at the authoritative transition layer: `/drivethru/stage` checked
only that the record existed, and `_set_stage` had no guard, so `cancel → window →
collected` walked a void visit back to the window and handed food out against it.

That is now closed at three doors, and the defect was **demonstrated by execution**
rather than left as a source reading — the negative control removed the guards and
`cancel → window` returned HTTP **200**.

| | |
|---|---|
| Terminal stages | **CLOSED** — `departed`, `cancelled` reach nothing |
| Cancelled/departed resurrection | **CLOSED** — 409 `invalid_transition` for every action, `pay` included |
| Authenticated HTTP proof | **PASS** — live server, every refusal observed over real HTTP |
| 4-worker cancel/forward race | **PASS** — 12 cars, 24 simultaneous requests, 4 worker PIDs, 0 cars left at a window |
| Negative control | **PASS** — 12 of 18 tests fail without the guards; restored byte-identically |

## Architecture as it stands

**Authority.** `vehicle_stage` is the physical truth. The legacy `state` field is a
compatibility projection and remains overloaded with kitchen values
(`preparing`/`ready`) — documented debt, not fixed here.

| Truth | Authority |
|---|---|
| Kitchen readiness | `mezze.kds.ticket` via `mezze.kitchen.readiness.mixin` |
| Payment | `pos.order` via `_paid()` |
| Physical position | `vehicle_stage` |
| Lane arrival order | `lane_sequence` (immutable, stamped at create) |
| Merged service order | `service_sequence` (idempotent, claimed at call-forward) |
| Channel | `pos.order.mezze_channel == 'drivethru'` |

**Movement contract** (`LEGAL_TRANSITIONS`): every active stage may reach every other
active stage — deliberately open, because branches really do wave a car from the lane
to pickup or send it back to pay; what protects the customer there is conditional
(paid AND kitchen-ready AND the topology's handoff window), not positional. The
terminal region is closed, and that is where the contract has teeth.

## Test state at this HEAD

| | |
|---|---|
| Full module regression | **748 / 2 / 0** (workers=0, fresh `--without-demo=all` DB) |
| Drive-thru terminal | **18 / 18** |
| All drive-thru suites | **91 tests, 1 failure** (the timer test below) |
| New failures from the terminal work | **0** |

The two failures are pre-existing and reproduce identically at `d8eca31` and
`54db559`:

1. `TestRateLimit.test_atomic_under_real_concurrency` — `17 != 25`. RateLimit code
   and test are byte-identical to RC7 (`git log mezze-v1.0-rc7..HEAD --` on both
   files is empty).
2. `TestDriveThruUx.test_03_the_timer_is_prominent_and_ticks` — asserts a visible
   change inside ~1.6 s.

Both are dispositioned in `DT-QA7-CERTIFICATION.md`. **The suite is not green**, and
is not described as green anywhere in this repository.

## Drive-thru surface

| Area | Status |
|---|---|
| Order Taker, Payment, Pickup, KDS identity | COMPLETE WITH KNOWN DEBT |
| Vehicle journey, both topologies, both sequences, dual lane | COMPLETE |
| Handoff safety (paid × kitchen × position) | COMPLETE |
| Terminal lifecycle | **COMPLETE** (this phase) |
| Board performance / N+1 | COMPLETE — 96 → 1 KDS statements, 112 → 17 total at 36 cars |
| 4-worker HTTP concurrency | COMPLETE — sequence and terminal races both proven |
| Arabic / RTL on the lane board | COMPLETE — key parity, EN + AR render tests |
| OCB (customer confirmation board) | **NOT STARTED** — no route, no template, no model |
| Touch-first vehicle capture | **NOT STARTED** — one free-text input; lane hardcoded to 2 |
| Pull-forward / holding UX | PARTIAL — stage and action exist, no UI |
| UX scores | **NOT RE-VERIFIED** — the 88/91/93/91 figures quoted in chat exist in no file or commit message in this repository |

## Known debt, recorded and unfixed

1. `state` still overloaded; the board query and the client's `activeCars()` filter on
   it rather than on `vehicle_stage`.
2. `/drivethru/board` is declared read-only but the legacy mirror writes, so a
   mirroring request is replayed on a read-write cursor and computes the board twice
   — now 17 queries instead of 112.
3. Payment may show a car that is not at the window as CURRENT. It is labelled in
   both languages, but the Complete-payment CTA is not gated and the server's `pay`
   action has no position gate. Deliberate (money early is fine, handoff is the
   irreversible step) but worth a decision.
4. `/drivethru/stage` enforces no window-occupancy limit; twenty cars can occupy
   `payment_window` at once.
5. The concurrency harnesses live in `tests/concurrency/`, which this repo keeps out
   of version control; the evidence they produce is committed under `docs/drive_thru/`.
