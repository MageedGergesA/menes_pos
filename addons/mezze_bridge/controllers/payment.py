"""S2 Slice 2B — cashier payment experience CONTRACT endpoints.

Read-mostly JSON contracts the cashier UI + receipt consume: valid device list,
payment breakdown (masked ref, NO secrets), reconciliation summary/settlement/finalize,
external-refund confirmation, and a manager payment report. All authenticated, branch-scoped,
and free of PAN/CVV/PIN/track/provider-secret data. Reuses the Slice-2A backend engine.
"""
from odoo import http
from odoo.exceptions import UserError

from .main import MezzeBridgeController, API_PREFIX


def _mask_ref(ref):
    """Safe reference for cashier screen/receipt: last 4-6 chars, dots for the rest."""
    ref = (ref or '').strip()
    if not ref:
        return ''
    if len(ref) <= 4:
        return ref
    keep = ref[-4:] if len(ref) < 10 else ref[-6:]
    return '••••' + keep


class MezzePaymentController(MezzeBridgeController):

    # ------------------------------------------------------------------ devices
    @http.route(f'{API_PREFIX}/payment/devices', type='json2', auth='none',
                methods=['POST'], csrf=False)   # read-only
    def payment_devices(self, config_id=None, payment_method_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        dom = [('active', '=', True)]
        if config_id:
            dom += ['|', ('config_id', '=', int(config_id)), ('config_id', '=', False)]
        devices = env['mezze.payment.device'].sudo().search(dom)
        if payment_method_id:
            pmid = int(payment_method_id)
            devices = devices.filtered(lambda d: not d.payment_method_ids or pmid in d.payment_method_ids.ids)
        return {'ok': True, 'devices': [{
            'id': d.id, 'name': d.name, 'code': d.code, 'mode': d.mode,
            'acquirer': d.acquirer_label or '', 'certification_status': d.certification_status,
        } for d in devices]}

    # -------------------------------------------------------------- breakdown
    @http.route(f'{API_PREFIX}/payment/breakdown', type='json2', auth='none',
                methods=['POST'], csrf=False)   # read-only, receipt/UI
    def payment_breakdown(self, uuid=None, order_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        order = (env['pos.order'].sudo().search([('uuid', '=', uuid)], limit=1)
                 if uuid else env['pos.order'].sudo().browse(int(order_id)))
        if not order.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        lines = []
        for p in order.payment_ids:
            pm = p.payment_method_id
            entry = {
                'method': pm.name,                       # configured name, not the engine mode
                'device': p.mezze_device_id.name or '',
                'amount': round(p.amount, 2),
                'ref_masked': _mask_ref(p.payment_ref_no),
                'confirmation_source': p.mezze_confirmation_source,
            }
            if p.mezze_external_refund_status and p.mezze_external_refund_status != 'not_required':
                entry['external_refund_status'] = p.mezze_external_refund_status
            lines.append(entry)
        paid = round(sum(order.payment_ids.mapped('amount')), 2)
        return {'ok': True, 'payments': lines, 'pos_reference': order.pos_reference,
                'state': order.state,
                'total': round(order.amount_total, 2), 'paid': paid,
                'change': round(max(0.0, paid - order.amount_total), 2)}

    # --------------------------------------------------------- reconciliation
    @http.route(f'{API_PREFIX}/reconciliation/summary', type='json2', auth='none',
                methods=['POST'], csrf=False)   # read-only
    def reconciliation_summary(self, session_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        session = env['pos.session'].sudo().browse(int(session_id))
        if not session.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        recon = env['mezze.payment.reconciliation'].sudo().build_for_session(session)
        return {'ok': True, 'reconciliation_id': recon.id, 'state': recon.state,
                'overall_status': recon.overall_status, 'total_difference': round(recon.total_difference, 2),
                'lines': [{
                    'line_id': l.id, 'method': l.payment_method_id.name, 'device': l.device_id.name or '',
                    'expected': round(l.expected_amount, 2), 'settlement': round(l.settlement_amount, 2),
                    'difference': round(l.difference, 2), 'status': l.status,
                    'ref': _mask_ref(l.settlement_reference),
                } for l in recon.line_ids]}

    @http.route(f'{API_PREFIX}/reconciliation/settlement', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def reconciliation_settlement(self, line_id=None, amount=None, reference=None,
                                  source='manual_terminal_settlement', note=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        line = env['mezze.payment.reconciliation.line'].sudo().browse(int(line_id))
        if not line.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        line.reconciliation_id.record_settlement(
            line, float(amount or 0.0), reference=reference, source=source, note=note,
            operator=env.uid)
        return {'ok': True, 'line_id': line.id, 'difference': round(line.difference, 2),
                'status': line.status}

    @http.route(f'{API_PREFIX}/reconciliation/finalize', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def reconciliation_finalize(self, reconciliation_id=None, approved_by=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        recon = env['mezze.payment.reconciliation'].sudo().browse(int(reconciliation_id))
        if not recon.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        try:
            recon.finalize(approved_by=int(approved_by) if approved_by else None)
        except UserError as e:
            return self._json({'ok': False, 'error': 'needs_manager_approval', 'message': str(e)}, status=409)
        return {'ok': True, 'reconciliation_id': recon.id, 'state': recon.state}

    # ----------------------------------------------------- external refund
    @http.route(f'{API_PREFIX}/payment/external_refund/confirm', type='json2', auth='none',
                methods=['POST'], csrf=False, readonly=False)
    def external_refund_confirm(self, payment_id=None, reference=None, note=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        p = env['pos.payment'].sudo().browse(int(payment_id))
        if not p.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        p.mezze_confirm_external_refund(reference=reference, note=note, actor='user:%s' % env.uid)
        return {'ok': True, 'payment_id': p.id, 'external_refund_status': p.mezze_external_refund_status}

    # --------------------------------------------------------- manager report
    @http.route(f'{API_PREFIX}/payment/report', type='json2', auth='none',
                methods=['POST'], csrf=False)   # read-only
    def payment_report(self, session_id=None, **kw):
        auth = self._authorize()
        if auth:
            return auth
        env = self._api_env()
        session = env['pos.session'].sudo().browse(int(session_id))
        if not session.exists():
            return self._json({'ok': False, 'error': 'not_found'}, status=404)
        payments = env['pos.payment'].sudo().search([('session_id', '=', session.id)])
        by_method, by_device = {}, {}
        refunds = 0.0
        for p in payments:
            by_method[p.payment_method_id.name] = round(by_method.get(p.payment_method_id.name, 0.0) + p.amount, 2)
            dn = p.mezze_device_id.name or '—'
            by_device[dn] = round(by_device.get(dn, 0.0) + p.amount, 2)
            if p.amount < 0:
                refunds += p.amount
        return {'ok': True, 'by_method': by_method, 'by_device': by_device,
                'refunds': round(refunds, 2), 'payment_count': len(payments)}
