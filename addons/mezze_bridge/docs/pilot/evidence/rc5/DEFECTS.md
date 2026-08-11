# RC5 PILOT PREPARATION — DEFECT RECORD

Build under test: `mezze-v1.0-rc5` / `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6`.

**The RC5 worktree was not edited. No fix was applied. RC6 was not created.**
These are recorded for operator decision.

> **Status update — appended, nothing above rewritten.** Both defects were **FOUND IN
> RC5** and are **FIXED IN RC6** (`mezze-v1.0-rc6` →
> `e85be35c31a3ae285494f68ecc67aaed493fd687`). RC5 did **not** pass them; this report
> correctly discovered them and stands exactly as written. Closure evidence —
> reproduction before/after, multiworker, restart, legacy-row upgrade, negative control —
> is in `../rc6/DEFECT-CLOSURE.md`.

---

## DEFECT-01 — Two Register sessions on one POS config evict each other (MEDIUM)

**Affects:** gate 6 (staff tablet), and any scenario with more than one Register open on
the same POS config — including a simple browser reload while another device is serving.

### What happens

Opening `/mezze/pos` mints a **fresh** bearer token and writes it onto a terminal record
whose identifier is derived **only from the POS config** — `cashier-web-<config_id>`
(`controllers/cashier.py::_mint_terminal_token`). There is one such record per config, so
a second Register open overwrites the first one's token. The first session keeps a token
the server no longer recognises and every subsequent API call returns **401**.

In the UI this surfaces as a workspace that rendered correctly and then failed to load its
data — e.g. **"Couldn't load reservations."** with a Retry button. The Retry does not help,
because the token is gone, and nothing tells the user that another device took over.

### Reproduction (measured on the pilot deployment)

```
token A minted (open Register)          -> /reservations/list  200
token B minted (open Register again)    -> A != B
token A                                 -> /reservations/list  401
token B                                 -> /reservations/list  200
```

Server log for the failing session:

```
"POST /mezze/api/v1/reservations/list HTTP/1.1" 401
"POST /mezze/api/v1/edge/status HTTP/1.1"       401
```

### Why it was not caught earlier

The gate defaults to `mezze_bridge.api_security = 'enforce'`, but the test fixtures set it
to `'observe'`, which audits instead of blocking. The 590-test suite therefore does not
exercise the enforcing path with two concurrent Register principals on one config.

### Severity assessment

Not a data-loss or money defect, and **not a deployment blocker** — a single-device
Register works correctly. It is a multi-device availability defect, and a physical pilot
is precisely a multi-device scenario, so it is likely to be hit and easy to misdiagnose as
"the tablet dropped the network".

### Not fixed here

The obvious direction (a per-session/per-device terminal identity instead of one per POS
config, or refusing to silently rotate a live token) is a **product change**. RC5 is
immutable; this belongs in an RC6 built from RC5 lineage, on operator authorisation.

### Workaround for a pilot run today

Use **one Register per POS config**, or create an additional POS config per device, and
avoid reloading the Register on one device while another is serving.

---

## DEFECT-02 — Product version self-reports `1.0.0-rc.1` while running RC5 (LOW, cosmetic)

`release_identity()` returns `"product_version": "1.0.0-rc.1"` on a build tagged
`mezze-v1.0-rc5`. The value is the module constant `MEZZE_PRODUCT_VERSION = '1.0.0-rc.1'`
(`models/productization.py:17`), which was not advanced as the release candidates
progressed.

Everything else in the identity payload is correct and *derived*: `git_commit` is obtained
by running `git rev-parse HEAD` against the loaded module tree and reported
`4b0feb1e4794134d57466bc17e6dc2ea5f4080b6` exactly, and `module_version` is `19.0.2.7.0`
from `ir.module.module`.

**Impact:** none functional. It matters only because this exercise is *about* release
identity: an operator reading the admin identity panel during a pilot would see "rc.1" and
could attach physical evidence to the wrong candidate. Mitigated by always recording the
tag and peeled commit, which this evidence package does.

**Not fixed here** — RC5 is immutable.

---

## Not defects (recorded so they are not re-investigated)

| Observation | Actual cause |
|---|---|
| Cashier DOM probe reported "not booted" | rAF freeze in a background tab; a screenshot flushed rendering and the app was fully present with real data |
| `POST /mezze/api/v1/kds/board` → 404 | wrong endpoint name in my probe; the real route is `kds/state`, which returns 200 |
| `_sql_constraints` WARNING at registry load | Odoo 19 deprecation notice emitted by base/third-party models, present equally on the development instance |
