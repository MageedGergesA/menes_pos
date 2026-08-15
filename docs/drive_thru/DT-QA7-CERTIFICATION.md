# DT-QA7 — drive-thru QA and evidence closure

Closes the three things standing between the drive-thru and a clean certification:
the timer test, the RateLimit test, and visual evidence that predated the fixes it
was supposed to certify.

No product behaviour changed in this phase. Both test failures turned out to be in
the tests, and both diagnoses are recorded with the measurements that produced them
rather than with the hypothesis that preceded them — in each case the first
hypothesis was wrong.

## 1. The timer test

**Failing assertion:** `test_03_the_timer_is_prominent_and_ticks` held a `.qtime`
node and asserted its text changed within 1.6 s.

**Suspected cause:** headless timer throttling. **Wrong.** Measured in the headless
test browser on `/mezze/drivethru`:

```
visibility=visible  hidden=false
setInterval(1000) delivered [1000,1000,1000,1000,1000,1000,1000,1000]
requestAnimationFrame        480 frames in 8s
```

No throttling anywhere.

**Actual cause:** the board's own 2 s poll replaces `#lanes` wholesale, so the node
the test was holding is **detached mid-wait** and stops updating while the board
carries on:

```
captured node                08:01 08:01 08:02 08:02 08:02 08:02 08:02 08:02
re-queried                   08:01 08:01 08:03 08:03 08:05 08:05 08:05 08:07
document.contains(captured)  true  true  false false false false false false
```

Whether the poll landed inside the 1.6 s window was a coin toss — which is why it
passed for weeks and then failed every run under load. Waiting longer would have
bought a luckier coin, not a certified product.

**What replaced it.** The three concerns the old test conflated are now certified
separately:

| | |
|---|---|
| `03_the_timer_is_prominent` | type scale vs vehicle name and branding |
| `03a` | the arithmetic, controlled clock, no sleeping: MM:SS across the hour boundary, server timestamps parsed as **UTC** (parsing them as local would shift every timer by the branch's offset), elapsed at T0 and T0+61 s, a clock behind the server never reading negative, warn/late band boundaries |
| `03b` | a tick moves the visible digits by exactly the elapsed 61 s |
| `03c` | the tick is **scheduled** — the debug handle reports the live interval id |
| `03d` | a real browser really delivers, counted rather than hoped for |

**Product code changed: NO** in behaviour. Two testability seams were added, both
inert in production: the clock is read through a variable that is `Date.now` on
every product path, and the anonymous interval callback now has a name. The debug
handle follows the Register and Kitchen convention exactly — developer mode only,
explicit `delete` otherwise, no secret reachable through it.

**Negative controls.** Breaking `elapsed()` fails 03a, 03b, 03d and 04.
Un-scheduling the tick fails 03c — *after* it was strengthened. The first version of
03c searched the source for `setInterval(tickTimers, 1000)`, and the sabotage
commented that line out and the whole suite still passed, because `assertIn` matched
the text inside the comment. A test with no teeth, found by running the control
rather than by trusting it.

## 2. RateLimit

**Failing assertion:** `test_atomic_under_real_concurrency`, `17 != 25` — and it was
never the atomicity invariant. That assertion is the line above, and it passed every
single time.

The test opens **25 real independent connections at once**. `db_maxconn` is
deployment configuration and is **16** on this machine, so the surplus threads raised
`PoolError`, which the worker did not catch, and died without recording anything.

**Measured**, 10 runs each, same machine and same SQL:

```
db_maxconn=64   recorded 25/25 every run                        PASS 10/10
db_maxconn=16   recorded 16,21,22,22,23,24,24,24,24,25
                every lost thread: "PoolError: The Connection Pool Is Full"
                                                                PASS  1/10
```

and in **all 20 runs, at both pool sizes, exactly `limit` threads were within the
limit**. The limiter was correct the whole time.

**Classification: ENVIRONMENT / HARNESS.** Product behaviour unchanged; the rate
limiter is byte-identical to RC7 (`git log mezze-v1.0-rc7..HEAD --` on
`models/rate_limit.py` and the test is empty for the model).

**Fix:** the worker now waits for a connection and retries, which is what a real
request does. The race is untouched — still 25 independent connections contending
for one row, still asserting exactly `limit` allowed.

**After the fix:**

| | |
|---|---|
| workers=0 | **10 / 10 pass** |
| workers=4 | **10 / 10 pass** (one void run — a pre-existing DB meant 0 post-tests — was replaced by a fresh iteration, not counted as a pass) |

**Negative control — and an honest limit on the assertion's reach.** Three sabotages
were tried:

1. `DO UPDATE SET count = (SELECT count …) + 1` — **still passed**. The subquery reads
   the pre-update row under the same row lock; the statement is still atomic.
2. A genuine two-statement read-then-write TOCTOU with a 10 ms gap — **still passed**.
   Odoo cursors run at REPEATABLE READ, so the losers raise `SerializationFailure` and
   the worker retries; the count still ends correct.
3. A per-thread key, so the counter stops being shared across connections —
   **FAILED, `AssertionError: 25 != 10`**.

So the assertion does have teeth against the invariant it exists to protect (no
double-allowance across independent connections), but it **cannot** distinguish an
atomic upsert from a retried read-then-write. That is a real limitation of its
discriminating power and is recorded rather than glossed.

## 3. Accessibility sweep

Measured on the live surfaces at a real 1440×740 viewport (iframe, verified
`innerWidth === 1440`), KDS at top level.

| | Order Taker | Payment | Pickup | KDS |
|---|---|---|---|---|
| visible controls | 47 | 21 | 21 | 80 |
| controls < 44px | **0** | **0** | **0** | **0** |
| positive `tabindex` | **0** | **0** | **0** | **0** |
| unnamed buttons | **0** | **0** | **0** | **0** |
| keyboard-reachable | 47/47 | 21/21 | 21/21 | — |
| ARIA name/state/role attrs | 25 | 26 | 28 | 47 |
| live regions | 0 | 0 | 1 | 0 |
| horizontal page overflow | none | none | none | none |

Preference media queries come from `design/components.css`, which the board links:
`forced-colors` ✓ · `prefers-contrast` ✓ · `prefers-reduced-motion` ✓ ·
`:focus-visible` ✓ (22 rules) · `prefers-color-scheme` ✓. RTL is handled with logical
properties (`padding-inline`, `inline-start/end`) rather than `[dir=rtl]` overrides,
and was verified visually in Arabic on the order taker, payment and pickup.

## 4. Visual evidence

Regenerated at this HEAD. Every earlier screenshot predated the row-button fix
(`54db559`) and the terminal FSM (`e1d2345`), so none of them showed a board whose
buttons worked.

Viewport labels are literal. `1440x740` and `1024x760` were rendered in a fixed-size
iframe with `innerWidth` asserted; `wide` means the browser's own ~2494px viewport.
The screenshot tool cannot capture a region taller than ~784px, which is why the
fixed viewports are 740/760 tall rather than 900.

| File | Shows |
|---|---|
| `qa7-order-wide-en-15car.jpg` | 15 cars, both lanes, READY and PREPARING |
| `qa7-order-wide-en-callforward-worked.jpg` | Call forward clicked → CAR-000 AT WINDOW |
| `qa7-order-wide-ar-rtl.jpg` | Arabic, full RTL mirror |
| `qa7-order-1440x900-en.jpg` | true 1440 viewport |
| `qa7-order-1024x760-en.png` | true 1024 viewport, no page overflow |
| `qa7-payment-1440x740-at-window.png` | current car at the window, tenders, CTA |
| `qa7-payment-1440x740-not-called-forward.png` | the not-called-forward warning |
| `qa7-payment-1440x740-ar-rtl.png` | Arabic payment, warning in Arabic |
| `qa7-pickup-1440x740-ar-ready-paid.png` | READY + PAID, handoff enabled (Arabic) |
| `qa7-pickup-1440x740-ar-kitchen-blocker.png` | PREPARING + PAID, CTA disabled |
| `qa7-pickup-1440x740-en-payment-blocker.png` | READY + UNPAID, CTA disabled |
| `qa7-pickup-1440x740-en-handoff-succeeded.png` | handoff done, car gone, next car up |
| `qa7-fsm-invalid-transition-toast-en.png` | a stale board acting on a car another till cancelled: **"This car has already left the lane"** |
| `qa7-kds-wide-mixed-channels-drivethru-identity.jpg` | 32 tickets; Counter tickets carry no vehicle, the two real drive-thru orders carry **L1 BLUE PICKUP** / **L2 SILVER HATCH** |

**Not regenerated, and why:** Arabic KDS. The KDS takes its language from the Odoo
user, not a URL parameter, and Arabic is not installed in the evidence database.
The existing `kds-arabic-1440.png` from DT-UX5 stands, and Arabic KDS remains covered
by the automated localization tests. Recorded as a gap rather than substituted.

Also worth recording: the KDS would not mount in this database until its cached
asset bundles were deleted and regenerated. That is an evidence-database artefact —
the same code mounts fine elsewhere and the KDS browser tests pass in the suite —
but it cost real time and is noted for whoever meets it next.
