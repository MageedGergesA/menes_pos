# Mezze POS — Update / Patch Process

## Principles

- **Backup first, always.** No update runs without a fresh, verified backup.
- **Migrations ride Odoo.** Schema/data changes use Odoo's normal upgrade scripts
  (module `-u`), never manual SQL against a live DB.
- **Validator-gated.** An update is not "done" until the go-live validator is green
  for the site's profile and a smoke test passes.
- **Rollback ready.** Every step is reversible from the pre-update backup.

## Edge (operator-run)

`deploy/edge/upgrade.sh` performs, in order:

1. **Backup** — `backup.sh` (pg_dump -Fc + filestore + config + SHA256SUMS + marker).
2. **Fetch** — `git fetch` / checkout the target tag/commit on the module tree.
3. **Update** — `odoo-bin -u mezze_bridge --stop-after-init` (runs migrations).
4. **Restart** — the systemd service.
5. **Validate** — `validate.sh` (edge profile) → must not FAIL.
6. **Smoke** — a scripted end-to-end order.
7. **Rollback** — on any failure, `restore.sh --backup <pre-update>` returns the
   site to the exact prior state.

## Cloud (Mezze-managed)

Mezze rolls updates on the `stable` / `rc` channel: staged on a neutralized copy,
validated, then applied with a managed backup + rollback. Customers are notified of
the target version; `/admin/version` reflects the new build afterward.

## Compatibility policy

- **Certified:** Odoo 19.0 Community. Migrations are written and tested for 19.0.
- **NOT claimed:** Odoo 20. Do not update the underlying Odoo to 20 in production
  until a dedicated `mezze_bridge` certification pass for 20 exists. The product
  version bumps MAJOR when such a migration lands (see `VERSIONING.md`).

## Verifying an update

After any update: `GET/POST /admin/version` shows the new `module_version` /
`git_commit`; `/admin/golive` is green for the site's profile; the operator runs
the UAT smoke subset (`docs/customer/UAT.md`).
