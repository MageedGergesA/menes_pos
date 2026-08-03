# Mezze POS — Backup & Restore

How your data is protected differs by edition. In both, a backup means the **whole**
system: database + filestore + configuration.

## What is backed up

- **Database** (orders, menu, customers, accounting, settings).
- **Filestore** (product images, attachments, receipts/reports).
- **Configuration** (the deployment's settings needed to bring it back up).

## Mezze Cloud — managed by Mezze

- Mezze runs scheduled backups (database + filestore) with an offsite copy.
- You do not operate anything. To **request a restore** or a copy for staging,
  contact Mezze support with the date/time you need.
- To **verify**, ask support for the latest backup timestamp; we can confirm the last
  successful backup and its offsite status.

## Mezze Edge — local + offsite, on your box

Edge keeps you running even if the internet is down, so backups live on the branch
box with an optional offsite copy.

- **Backup:** `deploy/edge/backup.sh` runs on a schedule — dumps the database, copies
  the filestore, and captures config; optional offsite rsync sends a copy off the box.
- **Restore:** `deploy/edge/restore.sh` restores database + filestore + config. A
  restore of **RTO ≈ 14 seconds** has been recorded in testing — fast enough to
  recover a branch mid-service.
- **Upgrades are backup-gated:** `deploy/edge/upgrade.sh` takes a mandatory backup
  before it touches anything, so an update can always be rolled back.

## How to verify a backup (Edge)

1. Confirm the backup job is scheduled and its last-run marker is recent (the go-live
   Edge validator reports backup recency as a host fact to check).
2. Periodically do a **test restore** onto a staging box and confirm it comes up.
   A backup you have never restored is a hope, not a backup.

## How to request or escalate

- **Cloud:** contact Mezze support for restores, copies, or verification.
- **Edge:** your operator/implementation partner runs `backup.sh` / `restore.sh`; pull
  a support bundle (`/admin/support_bundle`) if you need Mezze to help diagnose.
