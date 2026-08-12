# RC6 PILOT — RELEASE IDENTITY

Verified twice: on the shadow runtime before cutover, and **again on the canonical
endpoint after cutover**. Shadow validation alone was not treated as sufficient.

## What the running application reports

```json
{"product": "Mezze POS", "product_version": "1.0.0-rc.6",
 "edition": "Mezze Cloud", "deployment_mode": "cloud",
 "module": "mezze_bridge", "module_version": "19.0.2.7.0",
 "odoo_version": "19.0", "odoo_series": "19.0",
 "git_commit": "e85be35c31a3ae285494f68ecc67aaed493fd687",
 "release_channel": "rc", "build": "n/a",
 "neutralized": false, "env_profile": "development"}
```

## Independent corroboration

| Source | Value |
|---|---|
| Loaded module `__file__` | `/home/mageed/odoo_work_19/mezze-rc6-pilot/addons/mezze_bridge/__init__.py` |
| `git rev-parse HEAD` on the loaded tree | `e85be35c31a3ae285494f68ecc67aaed493fd687` |
| `git describe --tags --exact-match` | **`mezze-v1.0-rc6`** |
| `ir.module.module.latest_version` | `19.0.2.7.0` |
| Process cmdline | `odoo-bin -c …/mezze-rc6-pilot-runtime/conf/odoo-mezze-rc6-pilot.conf` |
| Config `addons_path` | `…/mezze-rc6-pilot/addons` (NOT the dev checkout, NOT RC5) |

All sources agree.

## Why `git_commit` is trustworthy here

`mezze_bridge.build_commit` is **UNSET** in the pilot database, so `release_identity()`
does not echo a configured string — it falls through to running `git rev-parse HEAD`
against the module tree it was actually imported from. The reported SHA is therefore
derived from the deployed code, not declared.

## DEFECT-02 acceptance

| | RC5 | RC6 |
|---|---|---|
| `product_version` | `1.0.0-rc.1` (**wrong** — build was rc5) | **`1.0.0-rc.6`** |
| `git_commit` | correct | correct |
| `module_version` | correct | correct |

**DEFECT-02 DEPLOYED: PASS** — accepted from the *running runtime*, not from source.

Identity was re-confirmed unchanged after the post-cutover restart.

## Versions are separate identities

`product_version` (`1.0.0-rc.6`) tracks the release candidate. `module_version`
(`19.0.2.7.0`) is the Odoo addon version and was deliberately **not** bumped: the RC6 fix
required no schema change, and an RC tag is not an addon-version event.
