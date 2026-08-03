# S6 — Per-Profile Commercial Signoff (PART 52)

Each profile is certified **independently**. Mark exactly one verdict per profile
with evidence. Starting state for every profile is **AWAITING EXECUTION** (physical
pilot not started). Do not pre-mark any verdict.

Verdicts: **GO** / **CONDITIONAL GO** (named blockers) / **NO-GO** / **NOT INCLUDED**.

---

## Cloud Base
- Exit criteria: `cloud-dod.md` (rows 1–27)
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **AWAITING EXECUTION** — 0/27 physical gates run
- Blockers / conditions: ____________________

## Edge Base
- Exit criteria: `edge-dod.md` (Cloud rows + E1–E16)
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **AWAITING EXECUTION** — 0/16 Edge physical gates run
- Blockers / conditions: ____________________

## Optional — Kiosk
- Gate: PART 22 (physical kiosk). Software CERTIFIED (S4).
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **NOT INCLUDED** unless a physical kiosk is sold + tested
- Note: absence must NOT block non-kiosk sales.

## Optional — Paymob (online)
- Gate: PART 32 (sandbox + live). Software CERTIFIED (S2C-5), redirect-only.
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **EXTERNAL CERT PENDING** — no credentials executed
- Note: refund/tokenization/capture NOT claimed.

## Optional — Integrated terminal
- Gate: PART 33. Only the exact provider/device tested becomes certified.
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **NOT INCLUDED** unless a specific device is sold + tested
- Device/provider: ____________________

## Optional — Cash machine (Glory / Cashdro / Cashmatic)
- Gate: PART 34. Each device independently; simulator ≠ certification.
- Verdict: ☐ GO ☐ CONDITIONAL GO ☐ NO-GO ☐ NOT INCLUDED
- Current: **NOT INCLUDED** unless a specific device is sold + tested
- Device: ____________________

---

## Roll-up to final signoff
Transfer the verdicts above into `signoff.md` and collect the four named signoffs
(Technical, Operations, Finance/Reconciliation, Restaurant Manager). Create
`mezze-v1.0` only when the required base profiles are **GO** (PART 66).
