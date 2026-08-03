"""S5 — first-run onboarding / setup-progress tracker.

A real, resumable, idempotent onboarding flow that REUSES existing Odoo models
(res.company / pos.config / account.journal / product / restaurant.table /
mezze.cashier / payment methods / delivery zones) — it introduces NO duplicate
``mezze.restaurant`` shadow model. Each step's completion is DERIVED from the
live go-live validator, never a stored boolean: a step is done only when its
underlying capability check actually passes. Re-running the wizard is safe —
progress is read from live config, and the only stored state is per-step
"acknowledged" markers (idempotent JSON in ir.config_parameter), used for
informational steps that have no validator check (e.g. KDS layout, devices).
"""
import json

from odoo import api, models

_ACK_PARAM = 'mezze_bridge.onboarding_ack'

# Ordered setup steps. ``checks`` are validator check names that PROVE the step;
# a step with no checks is informational (completion via explicit ack). ``optional``
# steps never block go-live. Each step maps to a REAL Odoo configuration surface.
STEPS = [
    {'id': 'restaurant', 'title': 'Restaurant & company', 'checks': ['company_currency', 'company_timezone'],
     'config': 'res.company', 'help': 'Company name, currency and timezone (Settings › Companies).'},
    {'id': 'branch', 'title': 'Branch / POS point', 'checks': ['pos_config_present'],
     'config': 'pos.config', 'help': 'At least one POS configuration (a branch till).'},
    {'id': 'tax', 'title': 'Taxes & journals', 'checks': ['journals'],
     'config': 'account.journal', 'help': 'Cash/bank journals and default taxes for the fiscal country.'},
    {'id': 'pos', 'title': 'Payment methods', 'checks': ['payment_methods', 'payment_modes', 'cash_journal'],
     'config': 'pos.payment.method', 'help': 'Payment methods on the POS config, each classified + journaled.'},
    {'id': 'menu', 'title': 'Menu / products', 'checks': ['selforder_catalog'],
     'config': 'product.product', 'help': 'POS-available products with categories.'},
    {'id': 'tables', 'title': 'Tables (dine-in)', 'checks': ['selforder_table_qr'], 'optional': True,
     'config': 'restaurant.table', 'help': 'Floor plan tables; QR tokens mint on first table link.'},
    {'id': 'kds', 'title': 'Kitchen display', 'checks': [], 'optional': True,
     'config': 'mezze.kds.ticket', 'help': 'Route order lines to prep stations (informational — no config gate).'},
    {'id': 'staff', 'title': 'Staff & PINs', 'checks': [], 'ack_check': 'cashiers',
     'config': 'mezze.cashier', 'help': 'Cashier/manager PINs (a manager PIN is needed for approvals).'},
    {'id': 'payments', 'title': 'Payment devices', 'checks': ['payment_devices'], 'optional': True,
     'config': 'mezze.payment.device', 'help': 'Terminals/QR/cash machines for methods that require a device.'},
    {'id': 'delivery', 'title': 'Pickup & delivery', 'checks': ['delivery_zone_configured'], 'optional': True,
     'config': 'mezze.delivery.zone', 'help': 'Delivery zones, fees and COD (optional).'},
    {'id': 'selforder', 'title': 'Self-order channels', 'checks': ['selforder_arabic_lang'], 'optional': True,
     'config': 'ir.config_parameter', 'help': 'QR / pickup / kiosk channels and Arabic language.'},
    {'id': 'devices', 'title': 'Printers & drawer', 'checks': [], 'optional': True,
     'config': 'mezze.hw.job', 'help': 'Receipt printers and cash drawer (physical — verified on-site).'},
    {'id': 'review', 'title': 'Review & go-live', 'checks': [], 'terminal': True,
     'config': None, 'help': 'Run the Go-Live readiness check for your chosen profile.'},
]


class MezzeOnboarding(models.AbstractModel):
    _name = 'mezze.onboarding'
    _description = 'Mezze first-run onboarding / setup progress'

    @api.model
    def _acks(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(_ACK_PARAM) or '{}'
        try:
            d = json.loads(raw)
            return d if isinstance(d, dict) else {}
        except Exception:  # noqa: BLE001
            return {}

    @api.model
    def _ack_state(self, step):
        """Best-effort completion for informational steps that have no validator
        check — DERIVED from live data where possible, else the stored ack."""
        if step.get('ack_check') == 'cashiers':
            n = self.env['mezze.cashier'].sudo().search_count([])
            mgr = self.env['mezze.cashier'].sudo().search_count([('role', '=', 'manager')])
            if n and mgr:
                return 'done', '%d staff PIN(s), manager present' % n
            if n:
                return 'attention', '%d staff PIN(s) but no manager PIN' % n
            return 'pending', 'no staff PINs yet'
        # generic informational step: done if explicitly acknowledged
        return ('done', 'acknowledged') if self._acks().get(step['id']) else ('pending', 'not started')

    @api.model
    def status(self, profile='full'):
        """Return the resumable onboarding state for a profile. Completion is
        DERIVED from the live validator — never a stored flag. Idempotent to call."""
        report = self.env['mezze.golive.validator'].run(profile=profile)
        by_name = {c['name']: c for c in report['checks']}
        steps = []
        for st in STEPS:
            checks = st.get('checks') or []
            if st.get('terminal'):
                # the review step reflects the overall validator verdict
                state = {'PASS': 'done', 'WARNING': 'attention', 'FAIL': 'blocked'}.get(
                    report['overall'], 'pending')
                detail = 'go-live overall=%s (%d fail, %d warn)' % (
                    report['overall'], report['fails'], report['warnings'])
            elif not checks:
                state, detail = self._ack_state(st)
            else:
                statuses = [by_name.get(n, {}).get('status', 'N/A') for n in checks]
                if 'FAIL' in statuses:
                    state = 'blocked'
                elif all(s == 'N/A' for s in statuses):
                    state = 'pending'
                elif 'WARNING' in statuses:
                    state = 'attention'
                else:
                    state = 'done'
                detail = '; '.join('%s=%s' % (n, by_name.get(n, {}).get('status', 'N/A')) for n in checks)
            steps.append({
                'id': st['id'], 'title': st['title'], 'help': st['help'],
                'optional': bool(st.get('optional')), 'state': state, 'detail': detail,
                'config_model': st.get('config'),
            })
        required_done = all(s['state'] in ('done', 'attention') for s in steps
                            if not s['optional'] and s['id'] != 'review')
        return {
            'ok': True, 'profile': profile, 'profile_label': report.get('profile_label'),
            'steps': steps,
            'overall': report['overall'],
            # onboarding is complete ONLY when the validator does not FAIL for the
            # chosen profile AND every required step is satisfied — not a boolean.
            'complete': report['overall'] != 'FAIL' and required_done,
            'fails': report['fails'], 'warnings': report['warnings'],
        }

    @api.model
    def acknowledge(self, step_id, done=True):
        """Idempotently record an ack for an informational step. Reruns never create
        duplicates — this only flips a JSON key. Validator-gated steps ignore acks."""
        valid = {s['id'] for s in STEPS if not (s.get('checks') or s.get('terminal'))}
        if step_id not in valid:
            return {'ok': False, 'error': 'not_an_informational_step'}
        acks = self._acks()
        if done:
            acks[step_id] = True
        else:
            acks.pop(step_id, None)
        self.env['ir.config_parameter'].sudo().set_param(_ACK_PARAM, json.dumps(acks))
        return {'ok': True, 'step': step_id, 'done': bool(done)}
