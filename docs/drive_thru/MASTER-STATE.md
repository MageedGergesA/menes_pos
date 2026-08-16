# Mezze Drive-Thru — master state

The canonical answer to *what is actually done*, kept in the repository rather than
in a chat transcript. Every claim here is traceable to a commit, a test, or a
committed evidence file; anything that could not be verified says so.

| | |
|---|---|
| Previous audit HEAD | `54db5599987642c16cb0f76ec7ea9cf167eee05a` |
| **Current HEAD** | **`72206323c6c10e905d732d796748b0a73fdd0f10`** — convergence commit closure |
| Working tree | **CLEAN** — nothing in flight |
| Branch | `feature/drive-thru-enterprise-ux` — not pushed, not merged |
| RC7 | `de27828ada4d22f4bedf7ccf4cfd72ec0123a6b3` — UNCHANGED, ancestor of HEAD |
| RC8 | not created |
| Full regression at this HEAD | **866 / 0 / 0** (fresh `--without-demo=all` DB, workers=0) |

Superseded audits are not rewritten. The `54db559` audit remains true of `54db559`;
the terminal-state sections below are true of `fef5b01`; the convergence section
immediately following is true of the current HEAD.

## Cashier ↔ Drive-Thru convergence (current HEAD)

The Order Taker is the Mezze Register in drive-thru mode, from the same stylesheets
and the same rules — not a second implementation of them.

| Layer | One definition | Consumed by |
|---|---|---|
| Product browser | `static/design/product-browser.css` | Register bundle + `drivethru.html` |
| Category navigation | `static/design/category-nav.css` | both |
| Order panel | `static/design/order-panel.css` | both |
| Product configuration — rules | `static/design/product-config.js` | both |
| Product configuration — panel | `static/design/product-config.css` | both |
| Pre-fire cart pricing | `mezze.cart.pricing` (server) | operator panel **and** the customer board |

| Area | Status | Evidence |
|---|---|---|
| CONV-1 product browser | COMPLETE | one `.mz-tile` definition in the repo |
| CONV-2a category foundation | COMPLETE | Register measured pixel-identical at 1920/1440/1280/1024 |
| CONV-2b order/ops role split | COMPLETE | `?mode=order` is a four-pane workspace; `?mode=ops` is the original board with every row action |
| CONV-3 product configuration | **COMPLETE** | shared rules + shared panel + Register capability + write path; 21 tests (`mezze_conv3`), behavioural on both surfaces |
| Station navigation | COMPLETE | crumb trail, real links, in-place switching; 7 tests (`mezze_dt_stations`) |
| Cart line identity | COMPLETE | both surfaces key a line by product **and** configuration (`MezzeProductConfig.lineKey`); the product-id-only merge is gone |
| Money authority | COMPLETE | no browser-side arithmetic on either surface; the server re-derives every figure |
| Modifiers — combos | **NOT STARTED** | `_product_combos()` publishes them; nothing selects them |
| Touch-first vehicle capture | **NOT STARTED** | unchanged by this work |

Convergence-scope readiness: **9.5 / 10**. The half point is the drive-thru order
panel at 1024 — 321px where the Register is 341px, because the lane's `_appearance`
does not pass `ws_panel_width`.

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

## Test state at the terminal-state HEAD (`fef5b01`)

| | |
|---|---|
| Full module regression | **784 / 0 / 0** (workers=0, fresh `--without-demo=all` DB) |
| Drive-thru terminal | **18 / 18** |
| Drive-thru UX (incl. the rebuilt timer tests) | **28 / 28** |
| RateLimit, 10 iterations each | **10/10 at workers=0, 10/10 at workers=4** |
| New failures from the terminal work | **0** |

The suite is green. It reached green in DT-QA7 by fixing two *tests* — neither
failure was ever a product defect, and both diagnoses are recorded with the
measurements that produced them in `DT-QA7-CERTIFICATION.md`:

1. `TestDriveThruUx.test_03` held a DOM node across the board's 2s re-render, so the
   node was detached mid-wait. The headless browser was never throttled — measured
   `setInterval` delivering at exactly 1000ms. Replaced by five tests that certify
   the elapsed-time arithmetic against a controlled clock, the tick, and the wiring.
2. `TestRateLimit.test_atomic_under_real_concurrency` asked for 25 simultaneous
   connections from a pool of 16, and the surplus threads died on `PoolError`
   without recording a result. The atomicity invariant passed in all 20 measurement
   runs at both pool sizes. The worker now waits for a connection.

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
| OCB (customer confirmation board) | **BUILT** (DT-UX6) — customer route, display model, live projection, two-lane isolation, Arabic; see `OCB-ARCHITECTURE.md` / `OCB-SECURITY.md` / `OCB-EVIDENCE.md` |
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
6. **Drive-thru order panel is 321px at 1024**, where the Register is 341px: the
   lane's `_appearance` does not pass `ws_panel_width`. Convergence debt.
7. **The Register's `/` search shortcut has no lane equivalent.** Training-parity debt.
8. ~~`design/product-config.js` carried a raw NUL as the `lineKey` delimiter, which
   made git treat it as binary.~~ **CLOSED** — the delimiter is now written as the
   `\u0000` escape: same runtime key, and the file diffs and merges as text again.
9. ~~`conv2b-order-1920-en.jpg` and `conv2b-order-15cars.jpg` are byte-identical.~~
   **CLOSED** — the 1920 capture is genuine (its scaled geometry resolves to the
   measured 1920 layout: queue 200 / categories 201 / catalogue 1178 / panel 341,
   six columns, fifteen cars in the rail) and is the file the evidence table cites.
   `conv2b-order-15cars.jpg` was an unreferenced second copy of the same bytes and
   was removed. `conv2b-ops-15cars.jpg` is a different image and stays.
10. The crumb-trail comment in `drivethru.html` still calls the crumbs "buttons";
    they became real links before landing. Comment-only inaccuracy.
