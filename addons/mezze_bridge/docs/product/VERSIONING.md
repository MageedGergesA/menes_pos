# Mezze POS — Versioning & Releases

## Version identity

Every running deployment answers "what build is this?" from
`GET/POST /mezze/api/v1/admin/version` (admin-gated) →
`mezze.productization.release_identity()`:

| Field | Example | Source |
|---|---|---|
| `product_version` | `1.0.0-rc.6` | `MEZZE_PRODUCT_VERSION` constant — the ONE source; must be advanced with each RC (see below) |
| `edition` | `Mezze Edge` / `Mezze Cloud` | deployment mode |
| `deployment_mode` | `edge` / `cloud` | `mezze.edge.connectivity.deployment_mode()` |
| `module_version` | `19.0.2.0.0` | `ir_module_module.latest_version` |
| `odoo_version` | `19.0` | `odoo.release.version` |
| `git_commit` | `<sha>` | deploy-stamped `mezze_bridge.build_commit`, else `git rev-parse` |
| `release_channel` | `stable` / `rc` / `dev` | `mezze_bridge.release_channel` |
| `build` | `n/a` or CI id | `mezze_bridge.build_id` |

The Edge host script `deploy/edge/release-identity.sh` reports the same identity
from outside the app (git/psql), for support without a running server.

## Version policy — MAJOR.MINOR.PATCH

The **product** version (`MEZZE_PRODUCT_VERSION`) is semantic:

- **MAJOR** — breaking change to the API contract, data model migration that is
  not backward-compatible, or an edition/deployment change requiring operator action.
- **MINOR** — new backward-compatible capability (a new payment mode, a new channel).
- **PATCH** — bug fix or hardening with no contract change.
- Pre-release suffix (`-rc.N`, `-dev`) marks a candidate before GA.

The **module** manifest version stays on Odoo's `19.0.x.y.z` convention so Odoo's
own upgrade machinery orders migrations correctly. The two move together: a product
MINOR bumps the module's `x`; a product PATCH bumps `y`/`z`.

## Release channels

| Channel | Audience | Meaning |
|---|---|---|
| `stable` | Customer GA | fully certified; the default for production |
| `rc` | Pilot / early adopter | feature-complete, certification in progress |
| `dev` | Engineering | unstable; never on a customer site |

Set per-deployment via `ir.config_parameter mezze_bridge.release_channel`.

## Odoo compatibility

- **Certified:** Odoo 19.0 Community.
- **NOT claimed:** Odoo 20 (unreleased/uncertified). Do not run `mezze_bridge` on
  Odoo 20 in production until a dedicated certification pass exists.

## Upgrades / migrations

Schema/data migrations ride Odoo's **normal upgrade scripts** (module `-u`), never
manual SQL. The Edge upgrade path (`deploy/edge/upgrade.sh`) is: mandatory backup →
`git fetch`/checkout → module `-u` (runs migrations) → restart → validator → smoke →
rollback on failure. See `docs/product/UPDATE-PROCESS.md`.

## RC identity guard

`product_version` is a hand-maintained constant, and in RC5 it was left at
`1.0.0-rc.1` while the build shipped as release candidate 5 — the running product
misreported which candidate it was (RC5 DEFECT-02). Everything else in the identity
payload is derived, so only this one string could drift.

`TestReleaseIdentity.test_24_product_version_matches_the_git_tag` closes that: whenever
`HEAD` sits **exactly** on a `mezze-v<major>.<minor>-rc<N>` tag, the constant must read
`<major>.<minor>.0-rc.<N>`, or the suite fails. On ordinary development commits there is
no tag to compare against and the test skips, so it never blocks normal work — it only
bites at the moment a candidate is frozen, which is exactly when it matters.

**When cutting a new RC:** advance `MEZZE_PRODUCT_VERSION` in the same commit that will
be tagged. The module version (`__manifest__.py`) is a separate identity and is only
bumped when the addon's own schema/behaviour requires it — an RC tag alone is not a
reason to bump it.
