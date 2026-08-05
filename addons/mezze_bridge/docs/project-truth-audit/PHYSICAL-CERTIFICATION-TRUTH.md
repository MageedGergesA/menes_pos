# PHYSICAL / EXTERNAL CERTIFICATION TRUTH

Audit 2026-08-05. Values are strictly PASS / FAIL / NOT EXECUTED. **No "logic proven ⇒ physical pass."**
Source: `deploy/edge/**`, `docs/sell-ready/edge/certification-report.md` (the module's OWN report), golive.py.

The Edge certification-report header states verbatim: *"VERDICT: NOT SELL-READY — engineering-preparation
pass only … performed on the developer laptop … no such hardware attached. Every physical/on-hardware gate
below is NOT EXECUTED."* No `mezze-edge-rc1` tag exists.

| Evidence item | Status |
|---|---|
| Real tablet | NOT EXECUTED |
| Real 1024×768 (RTL) | NOT EXECUTED |
| Receipt printer (ESC/POS) | NOT EXECUTED |
| Arabic receipt | NOT EXECUTED |
| Cash drawer | NOT EXECUTED |
| Physical KDS device | NOT EXECUTED |
| Customer-phone QR (on-device) | NOT EXECUTED |
| WAN disconnect 5 min | NOT EXECUTED |
| WAN disconnect 30 min | NOT EXECUTED |
| WAN disconnect 2 h | NOT EXECUTED |
| Power recovery / reboot autostart | NOT EXECUTED |
| UPS | NOT EXECUTED |
| Clean Ubuntu Host A | NOT EXECUTED (install proven **dry-run only**) |
| Clean Ubuntu Host B | NOT EXECUTED |
| nginx live | NOT EXECUTED (template + structure self-test only) |
| HTTPS live | NOT EXECUTED (local-CA cert script self-tested only) |
| WebSocket/bus live on Edge | NOT EXECUTED |
| Paymob real sandbox/live transaction | NOT EXECUTED (Demo provider only) |
| Integrated payment terminal (real) | NOT EXECUTED (simulator only) |
| Cash machine (real) | NOT EXECUTED (simulator only) |
| Representative staff UAT | NOT EXECUTED |
| 2–4 hour shift simulation | NOT EXECUTED |
| Session-close reconciliation (on hardware/live) | NOT EXECUTED |
| Backup/restore ON Edge host | NOT EXECUTED (scripts self-tested only) |

**Edge physical certification = 0% executed.** Deploy artifacts (installer/systemd/nginx/TLS/backup/restore/
validator/support-bundle/selftest) are WRITTEN, parameterized, and pass their own 21-check self-test
(syntax/render/cert-chain/redaction/dry-run) — but that validates the scripts, not a running host.

**On-site / O1 operational acceptance** (docs/go-live/on-site-acceptance/) = scaffolds/checklists, NOT
EXECUTED. **S6 physical pilot** = scaffold only (empty evidence dirs / .gitkeep).

Ubuntu certified target in current code = **24.04** (common.sh hard gate, golive.py, installer). One stale
artifact (`edge-validator-output.txt`) still says 22.04 — evidence drift.
