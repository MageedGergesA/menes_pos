# Environment Sheet

> Operator: ____________________  Date: __________  Release tag: `mezze-pilot-rc1`  Branch: `main`  Device/Client: ____________________

> Rule: no item may be marked Pass without a real on-site observation. Leave blank until executed.

Confirm and record the exact on-site environment. The running code MUST be the tagged commit.

| Item | Value to record |
|------|-----------------|
| Release tag | mezze-pilot-rc1 |
| Commit hash (from `git rev-parse HEAD`) | __________________________ |
| Confirm HEAD == tag (`git describe --tags`) | ☐ yes |
| Odoo version | __________ |
| Python version | __________ |
| PostgreSQL version | __________ |
| OS / host | __________ |
| Database name | __________ |
| web.base.url (HTTPS, not localhost) | __________ |
| env_profile = production | ☐ yes |
| MEZZE_MASTER_KEY present in env (value NOT recorded) | ☐ yes |
| Workers / proxy configured | __________ |
| Branch company / currency / timezone | __________ |
| Validator run on this host: 0 FAIL | ☐ yes  (attach output) |
