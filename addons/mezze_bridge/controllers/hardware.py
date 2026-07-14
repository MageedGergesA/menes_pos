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
import logging
import socket

from odoo import fields, http
from odoo.http import request

from .main import MezzeBridgeController

_logger = logging.getLogger(__name__)

HW_PREFIX = '/mezze/hardware'

# ESC/POS command bytes
_INIT = b'\x1b\x40'
_AL = {'l': b'\x1b\x61\x00', 'c': b'\x1b\x61\x01', 'r': b'\x1b\x61\x02'}
_BOLD_ON, _BOLD_OFF = b'\x1b\x45\x01', b'\x1b\x45\x00'
_BIG_ON, _BIG_OFF = b'\x1d\x21\x11', b'\x1d\x21\x00'
_CUT = b'\x1d\x56\x00'
_DRAWER = b'\x1b\x70\x00\x19\xfa'  # kick pin 0


class Ticket:
    """A tiny receipt builder → renders to both ESC/POS bytes and plain-text
    preview from the same row list."""

    def __init__(self, width=48):
        self.width = max(24, int(width or 48))
        self.rows = []  # ('text', align, text, bold, big) | ('rule',) | ('feed', n)

    def line(self, text='', align='l', bold=False, big=False):
        self.rows.append(('text', align, str(text), bold, big))
        return self

    def lr(self, left, right, bold=False):
        w = self.width
        left, right = str(left), str(right)
        gap = w - len(left) - len(right)
        if gap < 1:
            left = left[:max(0, w - len(right) - 1)]
            gap = w - len(left) - len(right)
        return self.line(left + ' ' * max(1, gap) + right, bold=bold)

    def rule(self):
        self.rows.append(('rule',))
        return self

    def feed(self, n=1):
        self.rows.append(('feed', n))
        return self

    def _enc(self, s):
        return s.encode('cp437', 'replace')

    def to_text(self):
        out = []
        for r in self.rows:
            if r[0] == 'rule':
                out.append('-' * self.width)
            elif r[0] == 'feed':
                out.extend([''] * r[1])
            else:
                _, align, text, _b, _g = r
                if align == 'c':
                    out.append(text.center(self.width))
                elif align == 'r':
                    out.append(text.rjust(self.width))
                else:
                    out.append(text)
        return '\n'.join(out)

    def to_escpos(self, drawer=False):
        buf = bytearray(_INIT)
        for r in self.rows:
            if r[0] == 'rule':
                buf += _AL['l'] + self._enc('-' * self.width) + b'\n'
            elif r[0] == 'feed':
                buf += b'\n' * r[1]
            else:
                _, align, text, bold, big = r
                buf += _AL.get(align, _AL['l'])
                if big:
                    buf += _BIG_ON
                if bold:
                    buf += _BOLD_ON
                buf += self._enc(text) + b'\n'
                if bold:
                    buf += _BOLD_OFF
                if big:
                    buf += _BIG_OFF
        buf += b'\n\n\n' + _CUT
        if drawer:
            buf += _DRAWER
        return bytes(buf)


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
        sock = socket.create_connection((printer.host, printer.port or 9100), timeout=timeout)
        try:
            sock.sendall(data)
        finally:
            sock.close()
        return len(data)

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
        except OSError as exc:
            _logger.warning("Mezze printer %s unreachable: %s", printer.name, exc)
            return {'ok': False, 'error': 'printer_unreachable', 'message': str(exc),
                    'printer': printer.name, 'preview': tk.to_text()}

    # -- receipt ---------------------------------------------------------------
    def _receipt_ticket(self, env, order, width):
        tk = Ticket(width)
        config = order.config_id
        tk.line(config.company_id.name or config.name, 'c', bold=True, big=True)
        tk.line(config.name, 'c')
        tk.feed()
        tk.lr('Receipt', order.pos_reference or str(order.id))
        tk.lr('Date', fields.Datetime.to_string(order.date_order or fields.Datetime.now()))
        if order.partner_id:
            tk.lr('Customer', order.partner_id.name)
        tk.rule()
        for l in order.lines:
            name = (l.full_product_name or l.product_id.display_name or '')
            tk.lr('%g x %s' % (l.qty, name[:tk.width - 12]), self._money(l.price_subtotal_incl))
        tk.rule()
        tk.lr('Subtotal', self._money(order.amount_total - order.amount_tax))
        tk.lr('Tax', self._money(order.amount_tax))
        tk.lr('TOTAL', self._money(order.amount_total), bold=True)
        tk.rule()
        for p in order.payment_ids:
            tk.lr(p.payment_method_id.name, self._money(p.amount))
        # ETA e-invoice reference, when the order was invoiced + cleared
        inv = order.account_move
        if inv and 'l10n_eg_uuid' in inv._fields and inv.l10n_eg_uuid:
            tk.feed()
            tk.line('ETA e-invoice', 'c')
            tk.line(inv.l10n_eg_uuid, 'c')
        tk.feed()
        tk.line('Thank you!', 'c')
        return tk

    @http.route(f'{HW_PREFIX}/print/receipt', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_receipt(self, order_id=None, uuid=None, printer_id=None, preview=False, **kw):
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._bridge._api_env()
        order = self._order(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        printer = self._pick_printer(env, order.config_id, 'receipt', printer_id)
        tk = self._receipt_ticket(env, order, printer.width if printer else 48)
        drawer = bool(printer and printer.open_drawer
                      and any(p.payment_method_id.is_cash_count for p in order.payment_ids))
        return self._emit(printer, tk, preview, drawer=drawer)

    # -- kitchen ---------------------------------------------------------------
    def _kitchen_ticket(self, env, order, station, width):
        tk = Ticket(width)
        tk.line((station or 'KITCHEN').upper(), 'c', bold=True, big=True)
        tk.lr('Order', order.tracking_number or order.pos_reference or str(order.id))
        table = order.table_id.table_number if order.table_id else None
        tk.lr('Table', table or 'Takeaway')
        tk.lr('Time', fields.Datetime.to_string(fields.Datetime.now())[11:16])
        tk.rule()
        lines = order.lines
        if station:
            lines = lines.filtered(lambda l: self._bridge._station_of(l.product_id) == station)
        for l in lines:
            name = (l.full_product_name or l.product_id.display_name or '')
            tk.line('%g x %s' % (l.qty, name), bold=True)
        return tk

    @http.route(f'{HW_PREFIX}/print/kitchen', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def print_kitchen(self, order_id=None, uuid=None, station=None, printer_id=None, preview=False, **kw):
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._bridge._api_env()
        order = self._order(env, order_id, uuid)
        if not order:
            return self._json({'ok': False, 'error': 'unknown_order'}, status=404)
        printer = self._pick_printer(env, order.config_id, 'kitchen', printer_id, station=station)
        tk = self._kitchen_ticket(env, order, station, printer.width if printer else 48)
        return self._emit(printer, tk, preview)

    # -- cash drawer -----------------------------------------------------------
    @http.route(f'{HW_PREFIX}/drawer/open', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def drawer_open(self, config_id=None, printer_id=None, **kw):
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._bridge._api_env()
        config = self._bridge._resolve_config(env, config_id)
        printer = self._pick_printer(env, config, 'receipt', printer_id)
        if not printer or not printer.host:
            return self._json({'ok': False, 'error': 'no_drawer_printer'}, status=400)
        try:
            n = self._send(printer, _INIT + _DRAWER)
            return {'ok': True, 'sent': True, 'bytes': n, 'printer': printer.name}
        except OSError as exc:
            return {'ok': False, 'error': 'printer_unreachable', 'message': str(exc)}

    # -- printer roster + test print ------------------------------------------
    @http.route(f'{HW_PREFIX}/printers', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def printers(self, config_id=None, **kw):
        auth = self._bridge._authenticate()
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

    @http.route(f'{HW_PREFIX}/test', type='json2', auth='none',
                methods=['POST'], csrf=False, cors='*')
    def test_print(self, printer_id=None, preview=False, **kw):
        auth = self._bridge._authenticate()
        if auth:
            return auth
        env = self._bridge._api_env()
        printer = env['mezze.printer'].browse(int(printer_id)) if printer_id else env['mezze.printer']
        if printer_id and not printer.exists():
            return self._json({'ok': False, 'error': 'unknown_printer'}, status=404)
        tk = Ticket(printer.width if printer else 48)
        tk.line('MEZZE', 'c', bold=True, big=True)
        tk.line('printer test', 'c')
        tk.feed()
        tk.lr('Printer', printer.name if printer else '(preview)')
        tk.lr('Status', 'OK')
        tk.feed()
        tk.line('If you can read this, the', 'c')
        tk.line('printer is wired correctly.', 'c')
        return self._emit(printer, tk, preview)
