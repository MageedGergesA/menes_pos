# S6 — Final Physical Pilot & Commercial Launch Certification

**This is a physical pilot, not a software task.** It certifies that a real
restaurant can buy Mezze POS today and operate it safely on real hardware, real
network conditions, and real staff. Software development is **FROZEN**.

## Status

```
S6 SOFTWARE PREFLIGHT:   PASS
S6 PHYSICAL PILOT:       NOT EXECUTED
CLOUD:                   NOT CERTIFIED
EDGE:                    NOT CERTIFIED
FINAL mezze-v1.0:        NOT CREATED
```

## Start here

- **[FIELD-RUNBOOK.md](FIELD-RUNBOOK.md)** — the full sequential pilot script (phases 0–36).
- **[PILOT-DAY-CHECKLIST.md](PILOT-DAY-CHECKLIST.md)** — one-page day-of cheat sheet.
- **[HARDWARE-PURCHASE-CHECKLIST.md](HARDWARE-PURCHASE-CHECKLIST.md)** — what to buy.
- **[software-preflight.md](software-preflight.md)** — the software gates already run (real).
- **[hardware-inventory.md](hardware-inventory.md)** — fill before the pilot.
- **[commercial-matrix.md](commercial-matrix.md)** — per-feature certification status.
- **[cloud-dod.md](cloud-dod.md)** · **[edge-dod.md](edge-dod.md)** — exit criteria.
- **[final/profile-signoffs.md](final/profile-signoffs.md)** · **[signoff.md](signoff.md)** — verdicts + named signoff.
- **[defects/DEFECT-TEMPLATE.md](defects/DEFECT-TEMPLATE.md)** — defect log + RC patch rule.

## Certified release under test (do NOT deploy arbitrary `main`)

```
S6_CERT_TAG    = mezze-v1.0-rc1
S6_CERT_COMMIT = ad32f3ea533912e01cacaa92e3427f808ff1a92e
```

Verified frozen (PART 1): working tree clean, divergence `0 0`,
`HEAD == mezze-v1.0-rc1^{} == ad32f3e`. Every S6 environment deploys **this exact
tag**. Runtime identity is `/mezze/api/v1/admin/version.git_commit == ad32f3e…`.

## The S6 rule

S6 is **not** a feature/architecture/redesign/hardening phase. It answers one
question: *can a real restaurant operate this safely?* If a real defect appears:
`reproduce → narrow patch → full regression → clean retest of the affected gate →
new immutable mezze-v1.0-rc2`. **Never move or recreate `mezze-v1.0-rc1`.** If no
defect appears, no code changes.

## What has been verified in software (dev host) vs what requires the physical pilot

**Software-executable — completed on a dev host (see `software-preflight.md`):**
- PART 1 release freeze — **PASS**
- PART 50 support-bundle secret scan (5 planted secrets, leakage=0) — **PASS**
- PART 46 DB integrity queries (overpaid/orphan/outbox) — **PASS**
- PART 53 security-smoke, software portion (route coverage, demo off) — **PASS**
- PART 6 validator wiring — runs correctly; **FAILs on a factory-empty DB by
  design** (nothing configured). A real pilot onboards to green for its profile.

**NOT executable by a coding agent — REQUIRES the physical pilot team
(status = PENDING PHYSICAL EXECUTION, which is neither PASS nor FAIL):**
real hosted Cloud deployment; two clean Ubuntu 24.04 Edge hosts; Epson TM-m30
printing real paper; cash drawer; physical tablets/phones; UPS; physically pulling
WAN/power; a 4–8h staffed shift; financial reconciliation of real takings;
hardware/terminal/cash-machine/kiosk physical certification.

**No fabricated evidence.** A gate is CERTIFIED only with real artifacts
(commands, logs, photos, model/firmware, operator, timestamp, expected vs actual).

## Evidence layout

Each subdirectory holds one gate's evidence. Use `results-template.md` per gate.
Fill `hardware-inventory.md`, then the per-gate sheets, then `commercial-matrix.md`,
then `cloud-dod.md` / `edge-dod.md`, and finally `signoff.md`.

## Final tag policy (PART 66)

Do **not** create `mezze-v1.0` until the required Cloud Base **and** Edge Base
profiles physically PASS (if both editions launch together). RCs stay immutable:
`rc1 → (defects) rc2 → … → all base profiles PASS → mezze-v1.0`.
