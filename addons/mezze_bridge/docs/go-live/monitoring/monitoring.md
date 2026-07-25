# Monitoring & Alerts (P1 §18)

Each alert: **severity · threshold · owner · destination · runbook · ack**.

| Signal | Sev | Threshold | Owner | Runbook |
|---|---|---|---|---|
| Odoo process down | Critical | any worker exit | Ops | restart workers; failure-recovery |
| PostgreSQL unreachable | Critical | connect fail | Ops | DB reconnect; offline POS |
| HTTP 5xx rate | High | >2% / 5 min | Eng | inspect logs by correlation id |
| Payment failures | High | >3 / 10 min | Branch admin | payment-terminal runbook |
| Duplicate-payment prevented (idempotent hit) | Info | any | Eng (trend) | expected; watch for spikes |
| Refund failures | High | any | Branch admin | refund runbook |
| Outbox backlog | High | >200 pending or age >10 min | Ops | outbox replay |
| Dead-letter events | High | >0 | Eng | stuck-outbox runbook |
| KDS backlog | Medium | >50 active tickets or SLA breach | Kitchen lead | expedite/86 |
| Printer failures | Medium | any hardware job dead-lettered | Branch admin | printer runbook |
| Aggregator signature failures | High | >5 / 5 min | Eng | secret rotation |
| Status-webhook failures | Medium | dead-lettered | Eng | outbox runbook |
| Disk space | High | <15% free | Ops | expand / rotate logs |
| DB size growth | Medium | anomalous | Ops | archive audit |
| Backup success | Critical | missing daily backup | Ops | backup-restore |
| Cron failures | Medium | any mezze cron error | Eng | inspect ir_cron |
| Active session anomaly | Medium | session open >18h | Branch admin | session runbook |

Implementation note: HTTP/DB/process health via the reverse proxy + a process supervisor;
business signals (outbox backlog, dead letters, payment failures) are queryable from the
existing audit log + outbox tables (see support visibility). Avoid alerts with no runbook.
