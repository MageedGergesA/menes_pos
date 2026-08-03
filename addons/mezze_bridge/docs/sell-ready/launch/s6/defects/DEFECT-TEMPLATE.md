# S6 Defect — <ID>

Copy per defect: `defects/DEF-<NNN>.md`. Redact customer PII.

| Field | Value |
|---|---|
| **ID** | DEF-___ |
| **Severity** | CRITICAL / MAJOR / MINOR |
| **Date / time (tz)** | |
| **RC under test** | mezze-v1.0-rc1 / ad32f3ea533912e01cacaa92e3427f808ff1a92e |
| **Environment** | Cloud / Edge Host A / Edge Host B |
| **Device** | (model + firmware) |
| **Operator (name + role)** | |
| **Preconditions** | |
| **Steps to reproduce** | 1. … 2. … 3. … |
| **Expected** | |
| **Actual** | |
| **Evidence** | (paths: photo/log/screenshot) |
| **Financial impact** | none / amount + explanation |
| **Customer impact** | |
| **Reproducible?** | yes / no / intermittent |
| **Workaround?** | none / describe |
| **Owner** | |
| **Disposition** | fix-now / defer / not-a-defect / scope-out-of-profile |
| **Fix commit** | (SHA on a NEW rc, never a moved tag) |
| **Retest result** | PASS / FAIL / pending |

## Severity policy
- **CRITICAL** — money incorrect, duplicate charge, lost paid order, data
  corruption, security breach, unrecoverable operation → **STOP PILOT**.
- **MAJOR** — core workflow blocked, real hardware unusable, repeated staff blocker,
  Arabic/tablet unusable, reconciliation mismatch → **FIX BEFORE SELLING** the
  affected profile.
- **MINOR** — cosmetic / non-blocking → defer.

## RC patch rule
Never move `mezze-v1.0-rc1`. A code fix follows: reproduce → narrow fix → tests →
full regression → retest the affected physical gate → new annotated
`mezze-v1.0-rc2` (then rc3, … as needed). Every RC is immutable.
