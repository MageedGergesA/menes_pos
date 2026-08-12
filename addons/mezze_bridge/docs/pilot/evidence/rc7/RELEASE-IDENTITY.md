# RC7 — Release identity

Every value below was read from the **running process**, not from a config file or a
source tree, and then cross-checked against the git worktree and the database.

| Source | Value |
|---|---|
| Git tag | `mezze-v1.0-rc7` |
| Annotated tag object | `6e0e884d557fe2a9972eca3495c400cfafb3774d` |
| Peeled commit | `de27828ada4d22f4bedf7ccf4cfd72ec0123a6b3` |
| `product_version` (runtime) | `1.0.0-rc.7` |
| `module_version` (runtime + DB) | `19.0.2.7.0` |
| `odoo_version` | `19.0` |
| `git_commit` (runtime) | `de27828ada4d22f4bedf7ccf4cfd72ec0123a6b3` |
| `release_channel` | `rc` |
| `edition` | Mezze Cloud |

## Independent proofs

1. **Running process** — `mezze.productization.release_identity()` called through an
   authenticated session on the canonical endpoint `:8090`, and separately on the
   shadow endpoint `:8092`. Both returned the values above.
2. **Process code path** — the master process cmdline points at
   `conf/odoo-mezze-rc7-pilot.conf`, whose `addons_path` ends at
   `/home/mageed/odoo_work_19/mezze-rc7-pilot/addons`.
3. **Worktree** — that path is a detached worktree: `HEAD = de27828…`,
   `git describe --tags --exact-match = mezze-v1.0-rc7`, `git status --porcelain` empty,
   `git diff` and `git diff --cached` both exit 0.
4. **Database** — `ir_module_module.latest_version` for `mezze_bridge` = `19.0.2.7.0`.

Re-proved unchanged after a shadow restart, after the canonical cutover, and again
after a canonical restart.

## Superseded runtime

The endpoint previously served **RC6**, confirmed live immediately before it was
stopped: `product_version 1.0.0-rc.6`, `git_commit e85be35c31a3ae285464…` (full:
`e85be35c31a3ae285494f68ecc67aaed493fd687`), DB `mezze_pilot_rc6`. RC6 was not
assumed from a previous report — it was queried from the running process.
