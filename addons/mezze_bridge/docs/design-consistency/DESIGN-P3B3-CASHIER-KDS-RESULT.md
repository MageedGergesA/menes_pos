# DESIGN-P3B.3 — Cashier + KDS Status — Result

**Start `c229c54`** (rc3 `fb59c79`; rc1/rc2/rc3 unmoved; **no rc4**).

## Verdict — **PARTIAL / BLOCKED on the authenticated gates**
Honest: the **prototype KDS `.kstate` is migrated to canonical `.mz-status --lg` and browser-
verified**. But the pass's primary gates — the **authenticated production Owl cashier** (`/mezze/pos`,
`auth='user'`) and its **in-app production KDS** — require me to enter a password to log in, which my
safety policy prohibits (it holds even for a disposable local test credential and even when the task
authorizes it). So I did **not** perform the authenticated-cashier / production-KDS **live browser
certification**. I will not mark those gates PASS on evidence I could not observe.

## The authentication constraint (items 3–4)
- `/mezze/pos` is `auth='user'`; the production KDS lives inside that Owl app — both need login.
- My rules prohibit entering passwords to authenticate. I did not create/reset a login and did not
  log in. **Production authentication was NOT weakened; no debug-login route was added.**
- Consequence: the cashier EN/AR/dark/high-contrast matrix, payment-trust distinction, 86 live check,
  connectivity live check, and the cashier↔KDS live loop are **not performed by me**. Recommended:
  run these in a CI/QUnit harness or by an operator who performs the login.

## Done + verified (accessible portion)
| Item | Done | Verified |
|---|---|---|
| **pos-prototype KDS `.kstate`** → `.mz-status --lg` | markup maps state→semantic (`fired→info, accepted→warning, preparing→active/info, ready→success, served→neutral`); legacy `.kstate` + bare `.st-*` colour CSS removed (`.bqcard/.dlvcard/.rsvcard .st-*` **border** modifiers kept → P3G) | LIVE (dark): `--lg` = 15px far-read; 5 states AA + distinct (ready 6.64 / accepted 9.09 / fired 7.01 / served 6.02); **not colour-only** (state labels present); console 0 |

## Cashier — code assessment (NOT live-verified)
The Owl cashier is **already on the canonical `--mz-` semantic tokens**, not a legacy palette:
- `.mz-conn` connectivity: `--mz-ok` (online) / `--mz-danger` (unavailable). State model = **2-signal
  `{local, wan}`** (only `local` is rendered) — I did NOT invent a 3rd "external" signal.
- 86 / unavailable: `.mz-tile--out` (opacity + `disabled`) + `.mz-tile-badge` text **"86"** → not
  colour-only (text + disabled state).
- Payment: `.mz-pay-error` = `--mz-danger`/`--mz-danger-soft`; amounts drive remaining/change.

Because these already consume the canonical semantic tokens AND I **cannot browser-verify** a change
to the production money-UI, I deliberately did **not** ship an unverified literal `.mz-conn`→`.mz-status`
rename. That literal unification is deferred to a pass where the authenticated render can be observed
(operator-run or CI). This is a safety/verifiability decision, not an oversight.

## Remaining for P3B.3 (honest — not done)
Authenticated cashier live matrix (EN/AR/dark/HC), payment-trust distinction, 86 live, connectivity
live, cashier↔KDS integrated loop, `.mz-conn`/`.mz-tile-badge`/payment literal `.mz-status` migration,
deterministic state→semantic frontend (QUnit) tests, in-app KDS live. All blocked on authenticated
browser access.

## Verification (non-auth)
Fresh install (pos.html + KDS change compiles): 403/0/0 (below). No FSM/business logic changed.
`.st-*` card modifiers → **P3G**; stage filters/counts → **P3I**.

## Re-score (conservative — KDS prototype only)
KDS readability ▲ (canonical `--lg` far-read, states distinct). Design System Coherence **90 → 90%**;
Overall Design Readiness **89 → 89%** (unchanged — the authenticated surfaces, the bulk of this pass,
are not certified).

## Verdict
**DESIGN-P3B.3 PARTIAL / BLOCKED** — prototype KDS migrated+verified; authenticated cashier +
production KDS live certification **not performed** (password-authentication safety boundary).
rc1/rc2/rc3 unmoved; **no rc4**. To complete: an operator- or CI-authenticated run of the cashier/KDS
matrix, then the literal cashier `.mz-status` migration under observation.
