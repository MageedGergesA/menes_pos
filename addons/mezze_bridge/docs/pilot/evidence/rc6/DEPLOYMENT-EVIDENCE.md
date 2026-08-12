# RC6 PILOT REDEPLOYMENT — DEPLOYMENT EVIDENCE

Cutover of the physical-pilot environment from RC5 to RC6. **Preparation only — no
physical gate was executed, and none moved from PENDING.**

| | |
|---|---|
| Previous target | `mezze-v1.0-rc5` → `4b0feb1e4794134d57466bc17e6dc2ea5f4080b6` |
| **New target** | **`mezze-v1.0-rc6`** → **`e85be35c31a3ae285494f68ecc67aaed493fd687`** |
| Tag object | `86418a505fb808dc65f47113713be3ae59a01a7d` |
| Product version | `1.0.0-rc.1` (RC5, wrong) → **`1.0.0-rc.6`** |
| Module version | `19.0.2.7.0` — unchanged; the fix needed no schema change |
| Date | 2026-08-12 |

Local and remote tags were re-verified before anything was touched, and RC5/RC4 confirmed
unmoved on both.

---

## 1. Code checkout

Detached worktree created **from the tag**, never from a branch head:

```
/home/mageed/odoo_work_19/mezze-rc6-pilot
  HEAD                 e85be35c31a3ae285494f68ecc67aaed493fd687
  git describe         mezze-v1.0-rc6   (exact)
  git status           clean (0 entries)
  git diff / --cached  0 / 0
  register_instance.py present, product_version 1.0.0-rc.6
```

The RC5 worktree was **not** modified or reused. The development checkout was never
switched.

## 2. RC5 pre-cutover freeze

A **new** backup was taken of the exact pilot state immediately before cutover — separate
from the original mezze_dev backup, and kept as the rollback artifact.

| | |
|---|---|
| Source | `mezze_pilot_rc5` |
| Path | `mezze-rc5-pilot-backups/mezze_pilot_rc5_PRE-RC6-CUTOVER_20260812-102327.zip` |
| Size | 6,395,068 bytes (6.2 MB) |
| SHA-256 | `e04c53d50b5dc398e73ce6ad09b423196a49e9e4d13a95541c404a2186749e0f` |
| Taken | 2026-08-12 10:23:29 |
| Contents | `dump.sql` + `manifest.json` + **446 filestore entries** (`--no-filestore` NOT used) |

**Restore proof: PASS.** Restored into a throwaway database and compared against source —
module `19.0.2.7.0`, 1 POS config, 12 tables, 17 product templates, 526 attachments,
2 terminals, all identical; 446 filestore files; **0 of 525 stored attachments missing on
disk**. Verification copy destroyed; **backup retained**.

## 3. RC6 pilot database

| | |
|---|---|
| Source | `mezze_pilot_rc5` (preserved, **not** upgraded in place) |
| Target | **`mezze_pilot_rc6`** (name was free; nothing overwritten) |
| Method | restored **from the pre-cutover backup**, so provenance is the artifact itself |
| Filestore | `filestore/mezze_pilot_rc6` — 18 MB, **446 files** |

## 4. Legacy terminal state — the DEFECT-01 migration risk

RC6 changed terminal identity semantics **without** a schema migration, so the real
question was whether existing rows survive. The pilot database carries genuine legacy rows,
not synthetic ones:

| Identifier | Before upgrade | After upgrade |
|---|---|---|
| `cashier-web-1` (legacy config-keyed, `role=terminal`) | active, fingerprinted, no plaintext token | **unchanged** |
| `kitchen-display-1` (`role=kitchen`) | active, fingerprinted | **unchanged** |

No secret was printed at any point — only presence flags and key ids.

## 5. Upgrade

```
-c <rc6 conf> -d mezze_pilot_rc6 -u mezze_bridge --stop-after-init
UPGRADE_EXIT = 0
```

| Error class | Count |
|---|---|
| ERROR / CRITICAL | **0** |
| Tracebacks | **0** |
| XML / view parse | **0** |
| Asset | **0** |
| i18n | **0** |
| Registry | **0** |

`-u` was run explicitly even though the module version is unchanged, because RC6 carries
code and session-security corrections.

### Data integrity — 18 counters, before vs after

**Zero deltas. Not one counter moved.**

```
companies 1 · users_active 6 · pos_config 1 · product_templates 17 · products_pos 15
pos_category 4 · floors 1 · tables 12 · payment_methods 2 · taxes 4 · pricelists 0
partners 10 · attachments 526 · attach_stored 525 · terminals 2 · mezze_tables 44
mezze_xmlids 1164 · module_version 19.0.2.7.0
```

Filestore after upgrade: 446 files, **0 of 525 stored attachments missing on disk**.

**Unexpected data loss: 0.**

## 6. Shadow validation before cutover

RC6 was brought up on **shadow ports 8092/8093** while RC5 kept serving 8090/8091, so
rollback stayed available throughout validation. Ports were verified free first; the
pre-existing instances on 8071/8077 and the others were never touched.

| Check | Result |
|---|---|
| Shadow start | **PASS** — HTTP 200, gevent listening, 4 workers (10 processes) |
| DB isolation | **PASS** — `dbfilter` pinned, `list_db=False`, **0** other DB names at the selector |
| Crash loop | none — 0 tracebacks |
| Runtime identity | **PASS** (see `RELEASE-IDENTITY.md`) |
| DEFECT-01 gates | **PASS** (see `DEFECT-01-DEPLOYMENT-VERIFICATION.md`) |
| Restart recovery | **PASS** |
| Smoke | **PASS** |

## 7. Deployment smoke

On the real restored pilot data:

| Surface | Result | Evidence |
|---|---|---|
| Cashier | **PASS** | **BROWSER** — rendered with real data (Arabic Coffee, Fattoush, Hummus Beiruti, Mixed Grill, Shish Tawook…), 4 nav destinations, 12 tiles |
| Floor | **PASS** | **BROWSER** — Main Hall, 12 tables, 5/12 occupied, 13 covers, live order totals |
| KDS | **PASS** | **BROWSER** — "Kitchen · Mezze Dev", 0 LIVE, "Kitchen server online", canonical empty state |
| Orders | **PASS** | API — `orders/list` 200 |
| Reservations | **PASS** | API — `reservations/list` 200 |
| Waitlist | **PASS** | API — `waitlist/list` 200 |
| Shop / QR / Kiosk | **PASS** | HTTP 200 (plus courses, drive-thru, feedback, CFD, onboarding — 8/8) |

Floor and KDS were confirmed **visually this time**, unlike the RC5 report where only API
evidence existed — that distinction is preserved rather than blurred.

One RC5→RC6 behavioural difference is visible in the UI: the Cashier header now reads
**"Local server online"** (green) where RC5 showed *"Local server unavailable"*. That was
the same DEFECT-01 401 storm — `/edge/status` was being rejected — so it is a symptom
disappearing, not a new feature.

### Bounded EN/AR check

RC6 changes **zero** static/UI files versus RC5 (`git diff mezze-v1.0-rc5 mezze-v1.0-rc6 --
addons/mezze_bridge/static/` is empty), so the C1–C5.1 UI certification carries over
unchanged. A bounded confirmation was still run on the storefront:

| | `lang` | `dir` | computed direction | Arabic face | body.rtl | overflow |
|---|---|---|---|---|---|---|
| EN | `en` | `ltr` | ltr | no | no | 0 |
| AR | `ar` | `rtl` | **rtl** | **yes** | yes | 0 |

Arabic copy rendered: `اطلب أونلاين` · `طازج، يُحضّر عند الطلب — استلام أو توصيل.` ·
`استلام وتوصيل`, 12 product tiles in both languages.

*Method note:* a first AR reading wrongly showed English. The cause was my URL omitting the
`store=` token, so the page exits before `applyI18n()` runs and the authored English stays
on screen. Recorded so the same false negative is not re-investigated.

## 8. Canonical cutover

RC5's health, PIDs and identity were recorded, then **only** the RC5 pilot process was
stopped and 8090/8091 confirmed free before RC6 bound them.

| | |
|---|---|
| RC5 stopped | YES (master pid 964553; no RC5 process remains) |
| Canonical HTTP / gevent | **8090 / 8091** |
| Canonical DB | `mezze_pilot_rc6` |
| Workers | 4 |
| Config | `mezze-rc6-pilot-runtime/conf/odoo-mezze-rc6-pilot.conf` — a **new** file; the RC5 config was never edited in place |
| Unrelated instances | untouched (`mezze_dev`, `bft_ui`, `atmta_*`, `mho_*` all still running) |

Post-cutover identity, the full A/B proof and a restart were **all re-run on 8090** —
shadow validation alone was not treated as sufficient.

## 9. No cross-contamination

```
RC5 worktree   4b0feb1e…  clean   (unchanged)
RC6 worktree   e85be35c…  clean   tag mezze-v1.0-rc6
dev checkout   6f38a37f…  clean   branch design/v1-uiux-completion
RC5 database   module 19.0.2.7.0, 2 terminals — preserved, NOT upgraded in place
RC6 database   upgraded state
```

## 10. Housekeeping note worth recording

Validation left **23 per-instance terminal rows** in the RC6 database (one per browsing
context my probes created). They were removed so the pilot starts from the 2 genuine
legacy rows, and a fresh client was re-verified working afterwards.

The underlying characteristic is real and the operator should know it: **every new
browsing context creates a persistent `mezze.terminal` row**. Over a long pilot with many
device reconnects that table will grow. It is not a defect — rows are inert, least-
privilege and revocable — but it is a housekeeping item, and there is no automatic
pruning.
