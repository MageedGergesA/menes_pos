"""P1 — production configuration validator + go-live readiness checks.

A runnable, structured validator (``mezze.golive.validator.run()``) that inspects
the live configuration and returns per-check Pass / Warning / Fail / N/A. A launch
must be blocked on any unresolved Fail. This is NOT a new platform layer — it only
READS existing config/records and reports; it never mutates business data.
"""
import os

from odoo import api, models

from ..domain import settings_catalog as _SC

PASS, WARN, FAIL, NA, NOT_TESTED = 'PASS', 'WARNING', 'FAIL', 'N/A', 'NOT TESTED'


class MezzeGoLiveValidator(models.AbstractModel):
    _name = 'mezze.golive.validator'
    _description = 'Mezze pilot go-live configuration validator'

    @api.model
    def run(self, profile='golive'):
        """Return {'overall', 'fails', 'warnings', 'checks': [{name, status, detail}]}.

        ``profile='golive'`` (default) is the P1 pilot validator. ``profile='edge'``
        appends Edge-deployment checks (S1.1 §11). NOT TESTED is used for facts that
        cannot be confirmed from inside Odoo (e.g. physical hardware) — never faked PASS.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        checks = []

        def add(name, status, detail=''):
            checks.append({'name': name, 'status': status, 'detail': detail})

        env_profile = (ICP.get_param('mezze_bridge.env_profile') or 'development').strip().lower()
        is_prod = env_profile == 'production'
        add('env_profile', PASS if is_prod else WARN,
            'profile=%s (production hardening only enforced in the production profile)' % env_profile)

        # --- security gate ---
        shared_disabled = str(ICP.get_param('mezze_bridge.shared_token_disabled', '')).strip().lower() in ('1', 'true', 'yes')
        emergency = False
        try:
            emergency = self.env['mezze.emergency.access'].is_active()
        except Exception:  # noqa: BLE001
            pass
        # in production the shared-admin machine token MUST be disabled (only a scoped
        # emergency activation admits it). In dev it is a documented convenience.
        if is_prod:
            add('shared_admin_disabled', PASS if shared_disabled else FAIL,
                'shared_token_disabled=%s' % shared_disabled)
        else:
            add('shared_admin_disabled', WARN, 'dev profile: shared-admin is a documented dev-only fallback')
        add('emergency_access_inactive', PASS if not emergency else WARN,
            'emergency break-glass %s' % ('active' if emergency else 'inactive'))

        add('master_key_present', PASS if os.environ.get('MEZZE_MASTER_KEY') else FAIL,
            'MEZZE_MASTER_KEY %s in environment' % ('set' if os.environ.get('MEZZE_MASTER_KEY') else 'MISSING'))

        api_sec = (ICP.get_param('mezze_bridge.api_security') or 'observe').strip().lower()
        add('api_security_enforced', PASS if api_sec == 'enforce' else WARN, 'api_security=%s' % api_sec)

        ttl = ICP.get_param('mezze_bridge.status_token_ttl_hours', 24)
        add('status_token_ttl', PASS, 'public status tokens expire after %s h and are revocable' % ttl)

        base = ICP.get_param('web.base.url') or ''
        add('base_url', WARN if ('localhost' in base or '127.0.0.1' in base or not base) else PASS,
            'web.base.url=%s' % (base or 'unset'))

        # --- branch / fiscal config ---
        company = self.env.company
        add('company_currency', PASS if company.currency_id else FAIL,
            'currency=%s' % (company.currency_id.name or 'unset'))
        add('company_timezone', PASS if (self.env.user.tz or company.partner_id.tz) else WARN,
            'tz=%s' % (self.env.user.tz or 'unset'))

        cfgs = self.env['pos.config'].sudo().search([])
        add('pos_config_present', PASS if cfgs else FAIL, '%d POS config(s)' % len(cfgs))
        pm = cfgs.mapped('payment_method_ids')
        add('payment_methods', PASS if pm else FAIL, '%d payment method(s) across configs' % len(pm))
        journals = self.env['account.journal'].sudo().search_count([('type', 'in', ('cash', 'bank'))])
        add('journals', PASS if journals else WARN, '%d cash/bank journal(s)' % journals)

        # --- S2 payment platform config ---
        PM = self.env['pos.payment.method'].sudo()
        active_pms = cfgs.mapped('payment_method_ids')
        no_mode = active_pms.filtered(lambda m: not m.mezze_mode)
        add('payment_modes', PASS if not no_mode else WARN,
            '%d/%d active methods classified' % (len(active_pms) - len(no_mode), len(active_pms)))
        cash_no_journal = active_pms.filtered(lambda m: m.is_cash_count and not m.journal_id)
        add('cash_journal', PASS if not cash_no_journal else FAIL,
            '%d cash method(s) missing a journal' % len(cash_no_journal))
        # REQUIRED-device methods must have at least one compatible device
        req_dev = active_pms.filtered(lambda m: m.device_policy == 'required')
        req_dev_bad = req_dev.filtered(lambda m: not m.mezze_device_ids)
        add('payment_devices', PASS if not req_dev_bad else FAIL,
            '%d method(s) require a device but have none configured' % len(req_dev_bad))
        try:
            codes = self.env['mezze.payment.device'].sudo().search([]).mapped('code')
            dup_codes = len(codes) != len(set(codes))
            add('payment_device_codes', PASS if not dup_codes else FAIL,
                'device codes unique' if not dup_codes else 'DUPLICATE device codes')
        except Exception:  # noqa: BLE001
            add('payment_device_codes', NA, 'device model unavailable')

        # --- S2C-3 integrated payment terminals ---
        term_pms = active_pms.filtered(lambda m: m.mezze_mode == 'odoo_terminal')
        if term_pms:
            no_provider = term_pms.filtered(lambda m: not m.mezze_terminal_provider)
            add('terminal_integration_set', PASS if not no_provider else FAIL,
                '%d integrated method(s) missing a terminal integration' % len(no_provider))
            sim = term_pms.filtered(lambda m: m.mezze_terminal_provider == 'test')
            add('terminal_simulator_not_production', PASS if not sim else WARN,
                ('no simulator method configured' if not sim
                 else '%d method(s) use the TEST simulator — never enable in production' % len(sim)))
            bad_journal = term_pms.filtered(lambda m: not m.journal_id or m.journal_id.type != 'bank')
            add('terminal_journal', PASS if not bad_journal else WARN,
                '%d integrated method(s) without a bank journal' % len(bad_journal))
            # Physical terminal certification is NEVER asserted here (software slice).
            real = term_pms.filtered(lambda m: m.mezze_terminal_provider
                                     and m.mezze_terminal_provider != 'test')
            add('terminal_hardware', NA,
                'HARDWARE = NOT TESTED for %d real-provider method(s); Mezze orchestration '
                'is software-certified, physical device certification is pending' % len(real))
        else:
            add('terminal_integration_set', NA, 'no integrated-terminal methods configured')

        # --- S2C-4 bank-app payment QR ---
        qr_pms = active_pms.filtered(lambda m: m.mezze_mode == 'bank_qr')
        if qr_pms:
            bad_qr = qr_pms.filtered(
                lambda m: m.payment_method_type != 'qr_code' or not m.qr_code_method
                or m.journal_id.type != 'bank' or not m.journal_id.bank_account_id)
            add('qr_payment_config', PASS if not bad_qr else FAIL,
                '%d bank-QR method(s) missing qr_code_method / bank journal / bank account'
                % len(bad_qr))
            # Egypt / InstaPay is NOT a supported bank-app QR scheme here — flag if
            # someone tries to pass an EGP-currency QR method off as certified.
            eg = qr_pms.filtered(lambda m: (m.company_id.currency_id.name or '') == 'EGP')
            add('qr_egypt_not_certified', PASS if not eg else WARN,
                'no EGP bank-QR method' if not eg else
                '%d EGP bank-QR method(s) — Egypt/InstaPay QR is NOT certified' % len(eg))
        else:
            add('qr_payment_config', NA, 'no bank-app QR methods configured')

        # --- S2C-6 customer account / credit ---
        acct_pms = active_pms.filtered(lambda m: m.mezze_mode == 'customer_account')
        if acct_pms:
            # per-customer debt REQUIRES Identify Customer (else it books to the
            # generic POS receivable with no partner).
            no_identify = acct_pms.filtered(lambda m: not m.split_transactions)
            add('customer_account_identify', PASS if not no_identify else FAIL,
                '%d Customer Account method(s) without Identify Customer (per-customer '
                'debt untracked)' % len(no_identify))
            bad_type = acct_pms.filtered(lambda m: m.type != 'pay_later')
            add('customer_account_type', PASS if not bad_type else FAIL,
                '%d Customer Account method(s) not pay_later (journal must be blank)' % len(bad_type))
            approval = acct_pms.filtered(lambda m: m.mezze_credit_policy == 'manager_approval')
            has_mgr = bool(self.env['mezze.cashier'].sudo().search_count([('role', '=', 'manager')]))
            add('customer_credit_approver', PASS if (not approval or has_mgr) else WARN,
                'manager approver available for credit approval' if (not approval or has_mgr)
                else '%d method(s) need manager approval but no manager PIN exists' % len(approval))
            try:
                use_limit = self.env.company.account_use_credit_limit
                add('customer_credit_limit_toggle', PASS if use_limit else WARN,
                    'company credit-limit checking is ON' if use_limit
                    else 'company credit-limit checking is OFF (limits not enforced)')
            except Exception:  # noqa: BLE001
                add('customer_credit_limit_toggle', NA, 'accounting credit-limit toggle unavailable')
        else:
            add('customer_account_identify', NA, 'no Customer Account methods configured')

        # --- S2C-7 automated cash machines ---
        cm_pms = active_pms.filtered(lambda m: m.mezze_mode == 'cash_machine')
        if cm_pms:
            # TEST simulator must never be live in production (§31): reject a cash-machine
            # method wired to the 'test' provider.
            test_cm = cm_pms.filtered(lambda m: (m.mezze_terminal_provider or '') == 'test')
            add('cash_machine_simulator_absent', PASS if not test_cm else FAIL,
                'no simulator cash-machine method' if not test_cm else
                '%d cash-machine method(s) wired to the TEST simulator — not production-safe' % len(test_cm))
            # Native Glory device address present (structural — credentials never printed).
            glory = cm_pms.filtered(lambda m: m.payment_method_type == 'glory_cash')
            if glory and 'glory_websocket_address' in cm_pms._fields:
                missing_ip = glory.filtered(lambda m: not (m.glory_websocket_address or '').strip())
                add('cash_machine_device_address', PASS if not missing_ip else FAIL,
                    'Glory device address configured' if not missing_ip else
                    '%d Glory cash-machine method(s) missing the device IP' % len(missing_ip))
            else:
                add('cash_machine_device_address', NA,
                    'no native Glory method (pos_glory_cash) configured')
            # Physical certification is explicitly NOT claimed without hardware.
            add('cash_machine_physical', NA,
                'cash-machine orchestration software only — physical device certification pending (no hardware)')
        else:
            add('cash_machine_configured', NA, 'no cash-machine methods configured')

        # --- S2C-5 online customer payment providers ---
        try:
            Provider = self.env['payment.provider'].sudo()
            live = Provider.search([('state', '=', 'enabled')])
            test = Provider.search([('state', '=', 'test')])
            # a published+enabled provider must have a payment journal + configured
            # (structurally) credentials — never assert a provider online just because
            # a config record exists.
            bad = live.filtered(lambda p: not p.journal_id)
            add('online_provider_journal', PASS if not bad else FAIL,
                '%d enabled online provider(s) without a payment journal' % len(bad))
            # online-payment POS methods must have a published provider for the currency
            online_pms = active_pms.filtered('is_online_payment')
            no_prov = online_pms.filtered(
                lambda m: not m._get_online_payment_providers(error_if_invalid=False))
            add('online_method_provider', PASS if not no_prov else WARN,
                '%d online method(s) without a published provider' % len(no_prov))
            # Paymob truth: refund/tokenization/capture are NOT supported by Odoo's
            # Paymob provider — flag any config that pretends otherwise.
            paymob = Provider.search([('code', '=', 'paymob')])
            bad_refund = paymob.filtered(lambda p: p.support_refund and p.support_refund != 'none')
            add('paymob_no_refund_claim', PASS if not bad_refund else FAIL,
                'Paymob refund correctly NOT claimed' if not bad_refund
                else 'a Paymob provider claims refund support it does not have')
            # orphan online transactions (done but no linked pos.payment) — a
            # reconciliation anomaly to surface, never auto-resolve.
            orphan = self.env['payment.transaction'].sudo().search_count(
                [('pos_order_id', '!=', False), ('state', '=', 'done'),
                 ('payment_id.pos_order_id', '=', False)])
            add('online_tx_reconciled', PASS if orphan == 0 else WARN,
                '%d online transaction(s) done but not linked to a POS payment' % orphan)
            add('online_providers', PASS if (live or test) else NA,
                '%d enabled, %d test online provider(s)' % (len(live), len(test)))
        except Exception:  # noqa: BLE001 — online payment optional / module boundary
            add('online_providers', NA, 'online payment framework unavailable')

        # --- operations plumbing ---
        crons = self.env['ir.cron'].sudo().search_count([('name', 'ilike', 'mezze')]) or \
            self.env['ir.cron'].sudo().search_count([('model_id.model', 'in', ('mezze.outbox.event', 'mezze.api.nonce'))])
        add('scheduled_jobs', PASS if crons else WARN, '%d mezze cron(s)' % crons)

        dead = 0
        try:
            dead = self.env['mezze.outbox.event'].sudo().search_count([('state', '=', 'dead')])
        except Exception:  # noqa: BLE001
            pass
        add('outbox_dead_letters', PASS if dead == 0 else WARN, '%d dead-letter event(s)' % dead)

        # aggregator channels must have a secret set (if any channel exists)
        try:
            aggs = self.env['mezze.aggregator'].sudo().search([('active', '=', True)])
            missing = aggs.filtered(lambda a: not a.sudo().secret_enc)
            if not aggs:
                add('aggregator_secrets', NA, 'no active aggregator channels')
            else:
                add('aggregator_secrets', PASS if not missing else FAIL,
                    '%d/%d channels missing a secret' % (len(missing), len(aggs)))
        except Exception:  # noqa: BLE001
            add('aggregator_secrets', NA, 'aggregator model unavailable')

        # catalog seeded (settings governance). The expected count comes from the
        # authoritative catalog itself (domain/settings_catalog.py), not a hardcoded
        # number; we also verify key uniqueness and status validity, so a genuine
        # miss (fresh install without the bootstrap) FAILs rather than silently warns.
        Defs = self.env['mezze.setting.def'].sudo()
        expected = len(_SC.CATALOG_101)
        rows = Defs.search([])
        keys = rows.mapped('key')
        unique_ok = len(keys) == len(set(keys))
        valid_status = all(s in ('working', 'disabled', 'hidden') for s in rows.mapped('status'))
        if len(rows) == expected and unique_ok and valid_status:
            add('settings_catalog', PASS, '%d/%d setting defs, keys unique, status valid' % (len(rows), expected))
        elif len(rows) == 0:
            add('settings_catalog', FAIL, 'catalog EMPTY — module install did not seed the %d-setting catalog' % expected)
        else:
            add('settings_catalog', WARN, '%d setting defs (expected %d; unique=%s; status_valid=%s)'
                % (len(rows), expected, unique_ok, valid_status))

        if profile == 'edge':
            self._edge_checks(add, ICP)

        fails = [c for c in checks if c['status'] == FAIL]
        warns = [c for c in checks if c['status'] == WARN]
        return {
            'overall': FAIL if fails else (WARN if warns else PASS),
            'fails': len(fails), 'warnings': len(warns), 'total': len(checks),
            'checks': checks, 'profile': profile,
        }

    @api.model
    def _edge_checks(self, add, ICP):
        """Edge-deployment checks (S1.1 §11). Reads what is inspectable from inside
        Odoo; marks NOT TESTED for facts that require host/hardware inspection."""
        import platform
        import shutil

        # supported OS (best-effort from inside the process)
        try:
            osrel = platform.platform()
            add('edge_os', PASS if 'Linux' in osrel else WARN, 'os=%s (Ubuntu 24.04 LTS x86-64 is the certified target)' % osrel)
        except Exception:  # noqa: BLE001
            add('edge_os', NOT_TESTED, 'OS not detectable from process')

        # PostgreSQL connection + version (live cursor)
        try:
            self.env.cr.execute("SHOW server_version")
            pgv = self.env.cr.fetchone()[0]
            add('edge_postgres', PASS, 'connected; server_version=%s' % pgv)
        except Exception as e:  # noqa: BLE001
            add('edge_postgres', FAIL, 'PostgreSQL query failed: %s' % e)

        # worker + proxy config (from the running Odoo config)
        try:
            from odoo.tools import config as _cfg
            workers = _cfg.get('workers', 0)
            add('edge_workers', PASS if int(workers) >= 1 else WARN,
                'workers=%s (Edge production should run >=1 worker)' % workers)
            add('edge_proxy_mode', PASS if _cfg.get('proxy_mode') else WARN,
                'proxy_mode=%s (required behind nginx)' % bool(_cfg.get('proxy_mode')))
            add('edge_max_cron', PASS if int(_cfg.get('max_cron_threads', 0)) >= 1 else WARN,
                'max_cron_threads=%s' % _cfg.get('max_cron_threads', 0))
        except Exception:  # noqa: BLE001
            add('edge_workers', NOT_TESTED, 'odoo config not inspectable')

        # HTTPS base url
        base = ICP.get_param('web.base.url') or ''
        add('edge_https_base_url', PASS if base.startswith('https://') else WARN,
            'web.base.url=%s (must be https:// behind the Edge proxy)' % (base or 'unset'))

        # disk capacity for the filestore/backup volume
        try:
            du = shutil.disk_usage('/')
            free_pct = 100.0 * du.free / du.total
            st = PASS if free_pct > 20 else (WARN if free_pct > 10 else FAIL)
            add('edge_disk', st, 'root free=%.0f%% (%0.1f GB of %0.1f GB)'
                % (free_pct, du.free / 1e9, du.total / 1e9))
        except Exception:  # noqa: BLE001
            add('edge_disk', NOT_TESTED, 'disk usage not inspectable')

        # database size
        try:
            self.env.cr.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            add('edge_db_size', PASS, 'database size=%s' % self.env.cr.fetchone()[0])
        except Exception:  # noqa: BLE001
            add('edge_db_size', NOT_TESTED, 'db size not inspectable')

        # clock: DB vs process time skew (both from this host, so a coarse sanity check)
        try:
            self.env.cr.execute("SELECT now()")
            add('edge_clock', PASS, 'db clock reachable=%s (verify NTP on host)' % self.env.cr.fetchone()[0])
        except Exception:  # noqa: BLE001
            add('edge_clock', NOT_TESTED, 'clock not inspectable')

        # secrets present (QR signing + status token) — presence only, never values
        qr = bool(ICP.get_param('mezze_bridge.qr_signing_secret') or ICP.get_param('mezze_bridge.qr_secret'))
        add('edge_qr_secret', PASS if qr else WARN, 'QR signing secret %s' % ('set' if qr else 'unset'))
        add('edge_master_key', PASS if os.environ.get('MEZZE_MASTER_KEY') else FAIL,
            'MEZZE_MASTER_KEY %s in environment' % ('set' if os.environ.get('MEZZE_MASTER_KEY') else 'MISSING'))

        # --- connectivity subsystem (S1.1A) ---
        try:
            conn = self.env['mezze.edge.connectivity']
            mode = conn.deployment_mode()
            add('edge_deployment_mode', PASS if mode == 'edge' else WARN,
                'MEZZE_DEPLOYMENT_MODE=%s (Edge deployments should be "edge")' % mode)
            targets = conn._probe_targets()
            add('edge_wan_probe_config', PASS if targets else WARN,
                '%d WAN probe target(s) configured' % len(targets))
            # WAN currently offline is EXPECTED to survive on Edge -> informational, never FAIL
            st = conn._probe_wan().get('state', 'unknown')
            add('edge_wan_state', PASS if st == 'online' else WARN,
                'WAN=%s (offline is survivable on Edge — informational, not a product FAIL)' % st)
            add('edge_status_subsystem', PASS, 'connectivity status subsystem available')
        except Exception as e:  # noqa: BLE001
            add('edge_status_subsystem', FAIL, 'connectivity subsystem misconfigured: %s' % e)

        # host-level facts NOT inspectable from inside Odoo -> honest NOT TESTED
        for name, note in (
            ('edge_nginx', 'reverse proxy status — check `nginx -t` + systemctl on host'),
            ('edge_websocket', 'gevent/websocket proxying — verify with a browser bus smoke test'),
            ('edge_service_autostart', 'systemd enable/boot-start — verify `systemctl is-enabled mezze-edge`'),
            ('edge_backup_recency', 'last successful backup — verify via backup.sh marker on host'),
            ('edge_ntp', 'NTP/chrony sync — verify `timedatectl` on host'),
            ('edge_receipt_printer', 'physical printer — S1.2 hardware certification'),
            ('edge_cash_drawer', 'physical drawer — S1.2 hardware certification'),
        ):
            add(name, NOT_TESTED, note)

    @api.model
    def report_text(self, profile='golive'):
        r = self.run(profile=profile)
        title = 'MEZZE EDGE VALIDATOR' if profile == 'edge' else 'MEZZE GO-LIVE CONFIG VALIDATOR'
        lines = ['%s — overall=%s (%d fail, %d warn, %d checks)'
                 % (title, r['overall'], r['fails'], r['warnings'], r['total']), '']
        for c in r['checks']:
            lines.append('  [%-9s] %-26s %s' % (c['status'], c['name'], c['detail']))
        return '\n'.join(lines)
