# GIT / RELEASE TRUTH (forensic — from git, not reports)

Audit date: 2026-08-05. Repo: `/home/mageed/odoo_work_19/mezze`. Branch: `main`.

## HEAD / remote
- **HEAD = main = origin/main = `5ec05b15871c4d9e3a71d5626de1d275410f4f6c`**
- Working tree: **CLEAN** (before this audit's uncommitted audit docs)
- Divergence origin/main…main: **0 0** (in sync)
- Remote branches: `main` (5ec05b1), `baseline` (fe60960), `review/full` (514368)

## Module / product version
- `addons/mezze_bridge/__manifest__.py` → **`version: "19.0.2.0.0"`**
- Product/release identity (runtime `/admin/version` etc.): see PROJECT-STATE (audit lane) — reconcile against this.

## Tag table (local vs remote — verified independently)
ls-remote peeled (`^{}`) commit shas were compared to local `rev-parse <tag>^{}`. **All identical; no tag moved.**

| Tag | Type | Commit (local == remote) | Ancestor of HEAD? | Commits behind HEAD |
|---|---|---|---|---|
| sprint-1-design-foundation | annotated | 258b255 | yes | 89 |
| v2.0.0-rc1 | annotated | 1f80710 | yes | 61 |
| mezze-pilot-rc1 | annotated | 634d17e | yes | 40 |
| mezze-pilot-rc2 | annotated | 13276b9 | yes | 39 |
| mezze-pilot-rc3 | annotated | 8ad8ed9 | yes | 37 |
| mezze-v1.0-rc1 | annotated | ad32f3e | yes | 17 |
| mezze-v1.0-rc2 | annotated | 7fee641 | yes | 14 |
| **mezze-v1.0-rc3** | annotated | **fb59c79** | yes | **12** |

(ls-remote shows the tag-OBJECT sha for annotated tags — that is NOT the commit; the peeled `^{}` line is the commit. Local tag-objects also match remote tag-objects. No discrepancy.)

## Current release identity
- **CURRENT HEAD:** `5ec05b1` (design: reservations + governance statuses)
- **LATEST PUBLISHED COMMIT:** `5ec05b1` (== origin/main)
- **LATEST CERTIFIED PRODUCT RC:** **`mezze-v1.0-rc3` → fb59c79** (design-P2 restoration per its result doc)
- **LATEST PILOT RC:** `mezze-pilot-rc3` → 8ad8ed9
- **HEAD is NOT the certified release.** HEAD is **12 commits ahead of mezze-v1.0-rc3**.

## The 12 commits since the certified RC (fb59c79..HEAD) — ALL design/status/docs
| Commit | Message | Area | Prod change | Tests | Certified by later RC? |
|---|---|---|---|---|---|
| 553b21b | docs: DESIGN-P3 grounding | DOCS | no (docs) | — | no |
| cd49743 | canonical button system (P3A partial) | DESIGN/BUTTON | CSS/JS | — | no |
| e341988 | advance button migration (P3A.1) | BUTTON | CSS/JS | — | no |
| e8be9f1 | migrate kiosk actions to canonical buttons | BUTTON | static | — | no |
| 5d96530 | migrate shop and QR actions to buttons | BUTTON | static | — | no |
| 1b64d05 | complete canonical button system | BUTTON | CSS | — | no |
| b442cea | add canonical status and badge system | STATUS | CSS | — | no |
| c229c54 | migrate pos-prototype + admin status | STATUS | static/js | — | no |
| e8dd328/e8d8328 | migrate pos KDS state badge | STATUS | static | — | no |
| 1f31672 | migrate floor and delivery to canonical statuses | STATUS | static | +1 test | no |
| a853d5a | close floor and delivery status gaps | STATUS/TEST | static/js | +1 test | no |
| 5ec05b1 | migrate reservations and governance statuses | STATUS/TEST | static/js | +1 test | no |

**Conclusion:** every commit since the last certified RC is **design (P3A Buttons + P3B Status) + docs + 3 structural tests** — NO core-functional, payment, offline, or model/business-logic change since `mezze-v1.0-rc3`. So the certified FUNCTIONAL product == `mezze-v1.0-rc3`; HEAD adds only uncertified design migration on top.

## Audit integrity
Production code NOT modified in this audit. No commit, no tag, no push. rc1/rc2/rc3 unmoved.
