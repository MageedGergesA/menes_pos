# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""POS hardware endpoints — network ESC/POS printing + cash drawer.

The server renders an ESC/POS byte stream and sends it over raw TCP (port 9100)
to a network thermal printer; the cash drawer is kicked through the printer's
drawer pin. Every print endpoint supports ``preview=True`` (and falls back to a
preview when no printer is configured / reachable) so the flow is demoable and
testable without physical hardware. Barcode scanners are keyboard-HID and live
entirely in the front-end.

Known limitation: receipts render in the printer's Latin codepage (cp437). A
fully Arabic receipt needs a printer with an Arabic codepage + RTL reshaping —
tracked for a later pass; the English receipt is correct today.
"""
import json
import logging

from odoo import fields, http
from odoo.http import request

from .main import MezzeBridgeController
from ..domain.escpos import Ticket, INIT, DRAWER
from ..models import hardware_render
from ..domain import epos
from ..domain import scale as scale_domain

_logger = logging.getLogger(__name__)

HW_PREFIX = '/mezze/hardware'

#: What the self-test prints so the code page is actually exercised.
#:
#: Keyed by code page rather than by language: the question the operator is
#: asking is "does THIS printer have THIS page in ROM", and the honest way to
#: answer it is to send a byte of that page and look at the paper. The words are
#: picked to need joining -- detached letters then read as a fault instead of a
#: font choice -- and the priced line is there because mixed-direction columns
#: are where receipt alignment usually breaks first.
#:
#: A Latin page needs no sample: the rest of the ticket already is one.
SAMPLES = {
    'cp1256': ('قهوة عربية', 'Arabic'),
    'cp864': ('قهوة عربية', 'Arabic'),
}

# back-compat aliases (used below for the drawer kick)
_INIT, _DRAWER = INIT, DRAWER


class MezzeHardwareController(http.Controller):

    _bridge = MezzeBridgeController()

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _money(self, v):
        return '%.2f' % (v or 0.0)

    # -- resolve + send --------------------------------------------------------
    def _order(self, env, order_id, uuid):
        if order_id:
            o = env['pos.order'].browse(int(order_id))
            return o if o.exists() else env['pos.order']
        if uuid:
            return env['pos.order'].search([('uuid', '=', uuid)], limit=1)
        return env['pos.order']

    def _pick_printer(self, env, config, printer_type, printer_id=None, station=None):
        P = env['mezze.printer']
        if printer_id:
            p = P.browse(int(printer_id))
            return p if p.exists() else P
        dom = [('config_id', '=', config.id), ('printer_type', '=', printer_type), ('active', '=', True)]
        printers = P.search(dom)
        if station:
            match = printers.filtered(lambda x: (x.station or '').lower() == station.lower())
            if match:
                return match[:1]
        return printers.filtered(lambda x: not x.station)[:1] or printers[:1]

    def _send(self, printer, data, timeout=4):
        return hardware_render.send_to_printer(printer, data, timeout=timeout)

    def _emit(self, printer, tk, preview, drawer=False):
        """Shared send-or-preview. Returns a JSON-able dict. Falls back to a
        preview (never 500s) when there's no printer or it's unreachable."""
        width = printer.width if printer else 48
        tk.width = max(24, width or 48)
        data = tk.to_escpos(drawer=drawer)
        if preview or not printer or not printer.host:
            return {'ok': True, 'sent': False,
                    'reason': 'preview' if preview else 'no_printer',
                    'bytes': len(data), 'preview': tk.to_text(),
                    'printer': printer.name if printer else None}
        try:
            n = self._send(printer, data)
            return {'ok': True, 'sent': True, 'bytes': n, 'printer': printer.name}
        except epos.EposError as exc:
            # The printer ANSWERED and said no. "Unreachable" would send a cashier
            # to check the network cable when the drawer of paper is what is empty,
            # so the printer's own code travels back to the till.
            _logger.warning("Mezze printer %s refused the job: %s", printer.name, exc)
            return {'ok': False, 'error': 'printer_error', 'code': exc.code,
                    'message': str(exc), 'printer': printer.name,
                    'preview': tk.to_text()}
        except OSError as exc:
            _logger.warning("Mezze printer %s unreachable: %s", printer.name, exc)
            return {'ok': False, 'error': 'printer_unreachable', 'message': str(exc),
                    'printer': printer.name, 'preview': tk.to_text()}

    # -- receipt ---------------------------------------------------------------
    def _receipt_ticket(self, env, order, width, printer=None):
        # shared layout (also used by the outbox print consumer, so a queued
        # receipt is byte-identical to a synchronous one)
        return hardware_render.receipt_ticket(
            order, width,
            encoding=(printer.codepage if printer else 'cp437'),
            codepage_id=((printer.codepage_id or None) if printer else None))

    @http.route(f'{HW_PREFIX}/print/receipt', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_receipt(self, order_id=None, uuid=None, printer_id=None, preview=False, **kw):
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        order = self._order(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        # object authorization: the principal must own the authoritative order's
        # company/branch (a valid order id from another branch is denied).
        denied = self._bridge._security_gate(env, 'print/receipt', target=order)
        if denied:
            return denied
        printer = self._pick_printer(env, order.config_id, 'receipt', printer_id)
        tk = self._receipt_ticket(env, order, printer.width if printer else 48, printer)
        drawer = bool(printer and printer.open_drawer
                      and any(p.payment_method_id.is_cash_count for p in order.payment_ids))
        return self._emit(printer, tk, preview, drawer=drawer)

    # -- bill (pro-forma, before payment) --------------------------------------
    @http.route(f'{HW_PREFIX}/print/bill', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_bill(self, order_id=None, uuid=None, printer_id=None, preview=False, **kw):
        """Print what the table OWES, before any of it is paid.

        The slip a guest asks for at the end of a meal, and the one a waiter needs in
        order to be asked for payment at all. Mezze could print a receipt for a settled
        order and nothing at all for an open one, so on a restaurant floor there was no
        way to close a table.

        Deliberately NOT a receipt: no tax QR, and it says so on its face. A pro-forma
        that looks like a receipt is one a guest can walk out holding and one an
        inspector can find in a drawer.
        """
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        order = self._order(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._bridge._security_gate(env, 'print/bill', target=order)
        if denied:
            return denied
        printer = self._pick_printer(env, order.config_id, 'receipt', printer_id)
        tk = hardware_render.receipt_ticket(
            order, printer.width if printer else 48, bill=True,
            encoding=(printer.codepage if printer else 'cp437'),
            codepage_id=((printer.codepage_id or None) if printer else None))
        # No drawer: nothing has been paid yet, so there is nothing to put in it.
        return self._emit(printer, tk, preview)

    # -- shift report (Z) ------------------------------------------------------
    @http.route(f'{HW_PREFIX}/print/z_report', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_z_report(self, session_id=None, printer_id=None, preview=False, **kw):
        """Print the shift's Z report.

        The figures come from the SAME endpoint the screen reads, so the paper and
        the screen cannot disagree — a shift report that is computed twice is a shift
        report that eventually reports two different days.
        """
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        session = env['pos.session'].browse(int(session_id or 0))
        if not session.exists():
            return self._json({'ok': False, 'error': 'unknown_session'}, status=404)
        denied = self._bridge._security_gate(env, 'print/z_report', target=session)
        if denied:
            return denied
        data = self._bridge.session_z_report(session.id)
        if not (isinstance(data, dict) and data.get('ok')):
            return self._json({'ok': False, 'error': 'z_report_failed'}, status=400)
        printer = self._pick_printer(env, session.config_id, 'receipt', printer_id)
        tk = hardware_render.z_report_ticket(
            data, printer.width if printer else 48,
            encoding=(printer.codepage if printer else 'cp437'),
            codepage_id=((printer.codepage_id or None) if printer else None))
        return self._emit(printer, tk, preview)

    # -- kitchen ---------------------------------------------------------------
    def _kitchen_ticket(self, env, order, station, width, printer=None):
        """Delegates to the shared renderer so a live ticket and a queued one are
        the same paper (see hardware_render.kitchen_ticket)."""
        return hardware_render.kitchen_ticket(
            order, station, width,
            encoding=(printer.codepage if printer else 'cp437'),
            codepage_id=((printer.codepage_id or None) if printer else None),
            station_of=lambda product: self._bridge._station_of(product))

    @http.route(f'{HW_PREFIX}/print/kitchen', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_kitchen(self, order_id=None, uuid=None, station=None, printer_id=None, preview=False, **kw):
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        order = self._order(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        denied = self._bridge._security_gate(env, 'print/kitchen', target=order)
        if denied:
            return denied
        printer = self._pick_printer(env, order.config_id, 'kitchen', printer_id, station=station)
        tk = self._kitchen_ticket(env, order, station, printer.width if printer else 48, printer)
        return self._emit(printer, tk, preview)

    # -- cash drawer -----------------------------------------------------------
    @http.route(f'{HW_PREFIX}/drawer/open', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=False)
    def drawer_open(self, config_id=None, printer_id=None, **kw):
        """Open the till without a sale.

        ``readonly=False`` is load-bearing. Odoo 19 runs an ``auth='none'`` route in a
        READ-ONLY transaction unless told otherwise, and this route now writes the
        audit row below — the INSERT was failing with "cannot execute INSERT in a
        read-only transaction", which ``_audit`` swallows by design so it can never
        roll back a sale. The drawer therefore opened and nothing recorded it, which
        is the one outcome this audit exists to prevent.
        """
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        config = self._bridge._resolve_config(env, config_id)
        printer = self._pick_printer(env, config, 'receipt', printer_id)
        if not printer or not printer.host:
            return self._json({'ok': False, 'error': 'no_drawer_printer'}, status=400)
        # object authorization: the printer's authoritative branch must be the
        # principal's (a printer id from another branch is denied).
        denied = self._bridge._security_gate(env, 'drawer/open', target=printer)
        if denied:
            return denied
        try:
            n = self._send(printer, _INIT + _DRAWER)
        except OSError as exc:
            return {'ok': False, 'error': 'printer_unreachable', 'message': str(exc)}
        # A NO-SALE drawer open is exactly the event a trail exists for: the till
        # opened and no money changed hands, which is both an ordinary thing a
        # cashier does (making change, correcting a miscount) and the shape of the
        # commonest till theft. Recording who and when costs nothing and is the only
        # way an unexplained variance at close can be traced to anything.
        self._bridge._audit(
            env, 'drawer.opened', severity='warning',
            **self._bridge._actor(env, kw),
            detail=json.dumps({'printer': printer.name, 'config_id': config.id,
                               'reason': (kw.get('reason') or '').strip() or None},
                              default=str))
        return {'ok': True, 'sent': True, 'bytes': n, 'printer': printer.name}

    # -- printer roster + test print ------------------------------------------
    @http.route(f'{HW_PREFIX}/printers', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def printers(self, config_id=None, **kw):
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        dom = [('config_id', '=', int(config_id))] if config_id else []
        out = [{'id': p.id, 'name': p.name, 'type': p.printer_type,
                'station': p.station or None, 'host': p.host or None,
                'port': p.port, 'width': p.width, 'open_drawer': p.open_drawer,
                'configured': bool(p.host)}
               for p in env['mezze.printer'].search(dom)]
        return {'ok': True, 'printers': out}

    # ------------------------------------------------------------------
    # Scale — what is actually on the pan
    # ------------------------------------------------------------------
    def _pick_scale(self, env, config, scale_id=None):
        S = env['mezze.scale']
        if scale_id:
            found = S.browse(int(scale_id))
            return found if found.exists() else S
        return S.search([('config_id', '=', config.id), ('active', '=', True)],
                        limit=1)

    @http.route(f'{HW_PREFIX}/scales', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def scales(self, config_id=None, **kw):
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        dom = [('config_id', '=', int(config_id))] if config_id else []
        return {'ok': True, 'scales': [
            {'id': s.id, 'name': s.name, 'protocol': s.protocol,
             'uom_name': s.uom_name or '', 'configured': bool(s.host)}
            for s in env['mezze.scale'].search(dom)]}

    @http.route(f'{HW_PREFIX}/scale/read', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*', readonly=True)
    def scale_read(self, config_id=None, scale_id=None, uom=None, **kw):
        """The weight on the pan, right now.

        ``uom`` is the unit the PRODUCT is priced in. It is compared against what
        the scale is set to and never converted: a scale left in pounds against a
        product priced per kilogram is a 2.2x error on the bill, and it is an error
        that always favours one side. Refusing sends a cashier to weigh it by hand;
        guessing puts a wrong number on a receipt nobody can check afterwards.

        An unstable reading gets its own answer rather than an error, because it is
        not a fault: the pan settles in a second and the cashier taps again.
        """
        auth = self._bridge._authorize(endpoint='scale/read')
        if auth:
            return auth
        env = self._bridge._api_env()
        config = self._bridge._resolve_config(env, config_id)
        found = self._pick_scale(env, config, scale_id)
        if not found:
            return self._json({'ok': False, 'error': 'no_scale'}, status=404)
        denied = self._bridge._security_gate(env, 'scale/read', target=found)
        if denied:
            return denied
        if not found.host:
            return self._json({'ok': False, 'error': 'scale_unconfigured',
                               'scale': found.name}, status=400)
        want = (uom or '').strip()
        if want and (found.uom_name or '').strip().lower() != want.lower():
            # Caught before the socket is opened: nothing about the reading can
            # rescue a scale that is set to the wrong unit for this product.
            return self._json({'ok': False, 'error': 'unit_mismatch',
                               'scale_uom': found.uom_name or '', 'product_uom': want,
                               'scale': found.name}, status=409)
        try:
            reading = hardware_render.read_scale(found)
        except scale_domain.ScaleError as exc:
            return self._json({'ok': False, 'error': exc.code, 'detail': exc.detail,
                               'scale': found.name}, status=409)
        except OSError as exc:
            _logger.warning("Mezze scale %s unreachable: %s", found.name, exc)
            return self._json({'ok': False, 'error': 'scale_unreachable',
                               'message': str(exc), 'scale': found.name}, status=503)
        return {'ok': True, 'scale': found.name, **reading}

    @http.route(f'{HW_PREFIX}/test', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def test_print(self, printer_id=None, preview=False, **kw):
        auth = self._bridge._authorize()
        if auth:
            return auth
        env = self._bridge._api_env()
        printer = env['mezze.printer'].browse(int(printer_id)) if printer_id else env['mezze.printer']
        if printer_id and not printer.exists():
            return self._json({'ok': False, 'error': 'unknown_printer'}, status=404)
        # The printer's OWN settings, not the defaults. This built its ticket with
        # a bare Ticket(width) and therefore always encoded CP437, while every
        # other path here -- receipt, bill, kitchen, Z -- carried the configured
        # code page. On a printer set to Arabic the self-test came out as '?' and
        # read as a broken printer, which is the worst way for a diagnostic to
        # fail: it accuses working hardware.
        encoding = printer.codepage if printer else 'cp437'
        tk = Ticket(printer.width if printer else 48, encoding,
                    (printer.codepage_id or None) if printer else None)
        tk.line('MEZZE', 'c', bold=True, big=True)
        tk.line('printer test', 'c')
        tk.feed()
        tk.lr('Printer', printer.name if printer else '(preview)')
        tk.lr('Width', '%d chars' % tk.width)
        # Both halves of the answer the operator is actually hunting for. Vendors
        # disagree about the ESC t n numbers -- Arabic especially -- so the number
        # that was really sent belongs on the paper, next to the result it
        # produced. Reading it off the printout beats deducing it from a table.
        tk.lr('Code page', '%s (ESC t %s)' % (tk.encoding, tk.codepage_id))
        tk.feed()
        tk.line('If you can read this, the', 'c')
        tk.line('printer is wired correctly.', 'c')

        sample = SAMPLES.get(tk.encoding)
        if sample:
            # A test print that never emits a byte of the script the code page
            # exists for is exactly the test that passes on a printer which cannot
            # print it. The sample words are chosen to need joining, so detached
            # letters are visible as a fault rather than looking like a font.
            text, label = sample
            tk.feed()
            tk.rule()
            tk.line('%s sample' % label, 'c')
            tk.line(text, 'c')
            tk.line('%s  x2  12.50' % text)
            tk.rule()
            tk.line('Letters joined, right to left,', 'c')
            tk.line('and the price column aligned?', 'c')
        return self._emit(printer, tk, preview)
