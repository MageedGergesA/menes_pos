# Tax integration — ETA e-receipt (B2C)

Screen **22 Tax compliance**. The UI was already right, so this round did not redesign it: it
specifies **every backend condition** the connector can be in, makes all nine reachable in the
prototype, and writes down what each one costs and who clears it.

The competitive audit's point stands and is worth restating plainly: **what is missing is real
certification, not UI.** Nothing below substitutes for ETA preproduction sign-off on a real
taxpayer profile. This document is the state machine that certification will be run against.

---

## The modelling decision: two axes, never one

Nine conditions, but they are not nine points on one line. Each carries two independent facts:

- **`fault`** — whose problem it is: `document` (ours), `transport` (the connection), or none
- **`auto`** — whether time alone fixes it

Collapsing these is the classic failure. A branch that treats "invalid item code" the same as
"service unavailable" retries a permanently-invalid payload four hundred times overnight, burns its
rate budget, and still has unproved money at close. So the screen says, per receipt, **whose problem
it is** and **whether anyone has to do anything.**

| Condition | Fault | Retries itself | Terminal | What it means |
|---|---|---|---|---|
| **Accepted** | — | — | yes | UUID returned. Proved, QR resolves, out of the window. |
| **Submitted** | — | yes | no | Signed and sent, awaiting an answer. In flight, *not* proved. |
| **Resubmitting** | — | yes | no | Corrected payload in flight after a rejection. Same receipt number, new document. |
| **Queued** | — | yes | no | Signed, held locally, goes on the next pass. Window running. |
| **Retry** | transport | yes | no | A previous attempt failed on transport. Exponential backoff. |
| **Offline** | transport | yes | no | No route out of the branch. Signed and safe on the terminal. |
| **Service unavailable** | transport | yes | no | ETA 5xx or timeout. Their side. Payload valid, will be accepted unchanged. |
| **Rejected** | document | **no** | no | ETA read it and refused. Will never be accepted as sent. |
| **Invalid item code** | document | **no** | no | An item has no EGS/GS1 code on the taxpayer profile. |

**Invalid item code is broken out of Rejected on purpose.** It is the single most common B2C
rejection, and its fix is not on the receipt — it is on the product, once, and it clears every
future sale of that item. Treating it as a generic rejection sends staff to the wrong screen.

## Transport conditions are branch-wide, not per receipt

A link that is down is down for every queued receipt. So `taxSt(receipt)` resolves the row's
displayed condition against a single branch-level link state (`up` / `eta` / `offline`), rather than
letting each row carry a stale local reason:

- link `offline` → every open receipt reads **Offline**
- link `eta` → every open receipt reads **Service unavailable**
- link `up` → receipts that were offline/unavailable fall back to **Retry** and resume backoff

The header panel states the link condition and what it costs, and it is switchable in the prototype
so all three are demonstrable. Under ETA-down the panel says the quiet part: *the backoff is doing
the work, and a manual send does nothing.*

## Retry policy

- Exponential backoff with jitter; the row shows **attempt n/6** and **next attempt in m min**.
- **6 attempts, then it stops** and waits for a person. Stated on the detail pane in those terms:
  so a broken payload cannot hammer the gateway all night.
- Only `transport` faults and in-flight states retry. A `document` fault reads
  **waiting on a person** in the row itself — there is no silent retry that looks like progress.
- Retry never re-signs. The signature is over the document; a retry is the same signed document
  going out again.

## Submission is not acceptance

`Submitted` and `Resubmitting` are distinct from `Accepted` because the difference is legal.
A receipt that sent is not a receipt that is proved. The toast on a manual send says it:
*Accepted means a UUID comes back, not that it sent.*

`Resubmitting` reuses the **same receipt number** with a corrected document. This is the one place
a mistake is expensive: a second submission under a **new** number is a duplicate filing, not a
retry. The action copy states this at the point of the click.

## The window and the exposure

24 hours (`TAX_WINDOW = 1440`) from charge to acceptance. Every open receipt shows time remaining,
in minutes under three hours because two receipts an hour apart must not read alike. The KPI strip
totals **unproved money**, split by who can clear it:

- Accepted
- In flight (submitted + resubmitting)
- Held, not sent (queued — signed on the terminal, never submitted)
- Waiting on the link (transport faults only — nobody needs to act)
- Waiting on a person (document faults)
- Unproved LE

The five buckets are disjoint and sum to the ledger. `Queued` is its own bucket precisely because
it is neither in flight nor blocked on the connection: nothing is wrong, it simply has not gone yet.
Its detail card reads **Nobody yet** rather than *In flight*, and the legend says **the next pass**
clears it — not ETA, which has never seen it.

Shift close is blocked while unproved receipts remain, and the session checklist reads the same
`sessTaxPending()` — one definition, two screens.

## Signing device

Three conditions, unchanged from the existing design and orthogonal to the nine above: drive
present, drive removed, IoT proxy unreachable. A missing drive means receipts still issue and queue
**unsigned** — the window runs on every one of them. This is why the device state sits next to the
ledger rather than in a settings page.

## Error codes seeded

| Code | Meaning | Fault |
|---|---|---|
| 4103 | Item code not registered on the taxpayer profile | document → **Invalid item code** |
| 4021 | Buyer type invalid for a consumer receipt | document |
| 4001 | Signature invalid or certificate expired | document (device) |
| 4055 | Total does not equal the sum of the lines | document (bug — escalate, do not retry) |
| 5001 | ETA service temporarily unavailable | transport |

---

## For Claude Code

**Persistence:** the receipt queue is local-first on the terminal and survives restart, power loss
and app upgrade. A signed, unsubmitted receipt is the branch's legal exposure — it must never live
only in memory. Same buffer discipline as the device sync queue in `docs/DEVICE_PLATFORM.md`.

**Idempotency:** submission carries the receipt's own UUID as the idempotency key. ETA must be able
to receive the same submission twice without creating two records.

**Classification at the edge:** map the provider's response to exactly one of the nine conditions at
the boundary, before anything is stored. Never persist a raw provider error as a state — persist the
condition plus the raw error for the log line.

**Never auto-retry a document fault.** The rule is one line of code and it is the difference between
a queue that drains and a queue that thrashes.

**Certification path** (the actual gap):
1. EGS/GS1 codes on all 148 menu items — the prototype shows 142, and names the 6 missing
2. Signing certificate issued against the real taxpayer profile
3. ETA preproduction submission of each of the nine conditions, evidenced
4. Production credential per branch, never shared
5. Retention: signed payloads and UUIDs kept for the statutory period, exportable

**Odoo mapping:** native Odoo covers e-invoicing (B2B), not B2C e-receipts, so the POS owns the
receipt payload, the signing device and the submission window. Receipts post against the same
`pos.order` and the same journal; the connector is a custom localisation module with credentials in
`ir.config_parameter`.

## Bilingual

Every condition name, consequence line, fault attribution and action goes through `tr()`; attempts,
codes, minutes and money through `N()`. Error codes and HTTP statuses stay Latin — they are
identifiers an operator reads out to support.
