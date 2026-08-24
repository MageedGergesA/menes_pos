"""Shared hardware render + transport helpers.

One place builds the receipt layout and one place does the raw TCP send, so a
receipt printed synchronously (controllers/hardware.py) and one delivered through
the outbox print consumer are byte-identical, and the socket path (timeout, close)
is identical too. Rendering happens from the AUTHORITATIVE order at send time, so
no document content is stored in the event payload.
"""

import base64
import json
import socket

import requests

from odoo import fields

from ..domain import epos, scale
from ..domain.escpos import Ticket, INIT, DRAWER


def _money(v):
    return '%.2f' % (v or 0.0)


def _tax_breakdown(order):
    """{tax name: amount} for the order, per RATE rather than one blended figure.

    The paper receipt printed a single ``Tax`` line while the screen receipt showed
    the per-rate split. A guest reclaiming VAT, and an inspector reading the paper,
    both need the rates named.
    """
    out = {}
    for line in order.lines:
        taxes = line.tax_ids
        if not taxes:
            continue
        share = line.price_subtotal_incl - line.price_subtotal
        if not share:
            continue
        # Split a multi-tax line across its taxes by their relative rate rather than
        # attributing the whole amount to the first one.
        total_rate = sum(abs(t.amount) for t in taxes) or 1.0
        for t in taxes:
            out[t.name] = out.get(t.name, 0.0) + share * (abs(t.amount) / total_rate)
    return out


def receipt_ticket(order, width=48, gift=False, tax_qr=None,
                   encoding='cp437', codepage_id=None, bill=False):
    """Build the customer receipt for a pos.order. Pure record traversal.

    ``gift`` prints the items without any prices — Odoo's ``basic_receipt``. A gift
    receipt that still shows what everything cost is not a gift receipt.

    ``bill`` prints what is OWED, before any of it has been paid — the slip a guest
    asks for at the end of a meal. It carries the items and the total but no tender
    lines and no tax QR, and it says on its face that it is not a receipt. A
    pro-forma that looks like a receipt is one a guest can walk out holding, and one
    an inspector can find in a drawer.

    ``tax_qr`` is an authority payload (ZATCA TLV, an ETA document URL) printed as a
    real QR. Mezze had no barcode command at all, so a signed tax QR could not reach
    paper — which blocks the two regimes this product is sold into.
    """
    # WHICH LANGUAGE the paper is in.
    #
    # Every label below used to be an English literal, so an Arabic branch printed an
    # Arabic product name under an English "Subtotal" — the screens are bilingual and
    # only the paper was not. The customer's own language wins when we know it; the
    # company's is the fallback, because that is the language the shop trades in.
    #
    # `env` is a local on purpose: it is what resolves the language for `_()` below.
    lang = (order.partner_id.lang or order.company_id.partner_id.lang
            or order.env.context.get('lang'))
    env = order.env(context=dict(order.env.context, lang=lang)) if lang else order.env
    order = order.with_env(env)
    # `env._` rather than the module-level alias: the alias resolves its language by
    # inspecting the calling frame, and in a plain function like this one it found no
    # language and printed English labels regardless of the customer. Proven by
    # test_10, which failed against the alias.
    _ = env._
    tk = Ticket(width, encoding, codepage_id)
    config = order.config_id
    company = config.company_id
    tk.line(company.name or config.name, 'c', bold=True, big=True)
    tk.line(config.name, 'c')
    # Identity an inspector expects, and a guest needs to find the shop again.
    for part in (company.street, company.city, company.phone):
        if part:
            tk.line(part, 'c')
    if company.vat:
        tk.line('%s %s' % (_vat_label(company), company.vat), 'c')
    # An operator-authored header (config.receipt_header) was simply never read.
    if config.receipt_header:
        tk.feed()
        for row in str(config.receipt_header).splitlines():
            tk.line(row.strip(), 'c')
    tk.feed()
    if bill:
        # Named for what it is, at the top, where a guest looks first.
        tk.line(_('BILL'), 'c', bold=True)
    tk.lr(_('Bill') if bill else _('Receipt'), order.pos_reference or str(order.id))
    tk.lr(_('Date'), fields.Datetime.to_string(order.date_order or fields.Datetime.now()))
    cashier = _cashier_name(order)
    if cashier:
        tk.lr(_('Served by'), cashier)
    if getattr(order, 'tracking_number', None):
        tk.lr(_('Order'), str(order.tracking_number))
    if order.partner_id:
        tk.lr('Customer', order.partner_id.name)
    tk.rule()
    for l in order.lines:
        name = (l.full_product_name or l.product_id.display_name or '')
        if gift:
            tk.line('%g x %s' % (l.qty, name[:tk.width - 2]))
        else:
            tk.lr('%g x %s' % (l.qty, name[:tk.width - 12]),
                  _money(l.price_subtotal_incl))
        note = getattr(l, 'customer_note', '') or ''
        if note:
            tk.line('    %s' % note[:tk.width - 6])
    tk.rule()
    if gift:
        # No prices, no totals, no tender — that is the entire point.
        tk.line(_('Gift receipt'), 'c')
    else:
        tk.lr(_('Subtotal'), _money(order.amount_total - order.amount_tax))
        for name, amount in sorted(_tax_breakdown(order).items()):
            tk.lr(name, _money(amount))
        if not _tax_breakdown(order) and order.amount_tax:
            tk.lr(_('Tax'), _money(order.amount_tax))
        tk.lr(_('TOTAL'), _money(order.amount_total), bold=True)
        tk.rule()
        if bill:
            # Anything already settled is shown, because a guest who paid a deposit
            # or split part of the bill needs to see it — but what is LEFT is the
            # figure they are being asked for.
            paid = sum(p.amount for p in order.payment_ids)
            if paid:
                for p in order.payment_ids:
                    tk.lr(p.payment_method_id.name, _money(p.amount))
                tk.lr(_('Due'), _money(order.amount_total - paid), bold=True)
            tk.feed()
            tk.line(_('This is not a receipt'), 'c')
        else:
            for p in order.payment_ids:
                tk.lr(p.payment_method_id.name, _money(p.amount))
            if order.amount_return:
                tk.lr(_('Change'), _money(order.amount_return))
    # Gift cards sold on this order. A card whose code never reaches paper is a card
    # the customer cannot use — they paid for it and walk out with nothing to present.
    # Read from the cards themselves, not from a response payload, so a reprint of an
    # older receipt carries the same codes as the original.
    if not gift:
        for card in _issued_giftcards(order):
            tk.feed()
            tk.line(_('GIFT CARD'), 'c', bold=True)
            tk.line(card.code, 'c', bold=True, big=True)
            tk.lr(_('Value'), _money(card.points))
            if card.expiration_date:
                tk.lr(_('Valid until'), str(card.expiration_date))
    inv = order.account_move
    if inv and 'l10n_eg_uuid' in inv._fields and inv.l10n_eg_uuid:
        tk.feed()
        tk.line(_('ETA e-invoice'), 'c')
        tk.line(inv.l10n_eg_uuid, 'c')
    if tax_qr and not bill:
        # Never on a bill: the QR is what makes a document a tax invoice, and a
        # pro-forma is not one.
        tk.feed()
        tk.qr(tax_qr, _('Scan to verify this invoice'))
    if config.receipt_footer:
        tk.feed()
        for row in str(config.receipt_footer).splitlines():
            tk.line(row.strip(), 'c')
    else:
        tk.feed()
        tk.line(_('Thank you!'), 'c')
    return tk


def _issued_giftcards(order):
    """The gift cards minted by this order, from the audit trail that recorded them.

    ``loyalty.card`` has no link back to the pos.order that sold it, so the audit row
    written in the same transaction as the card is what ties the two together.
    """
    env = order.env
    rows = env['mezze.audit.log'].sudo().search([
        ('event', '=', 'giftcard.issue'),
        ('res_model', '=', 'pos.order'),
        ('res_id', '=', order.id),
    ])
    codes = []
    for row in rows:
        try:
            code = (json.loads(row.detail or '{}') or {}).get('code')
        except (TypeError, ValueError):
            code = None
        if code and code not in codes:
            codes.append(code)
    if not codes:
        return env['loyalty.card']
    return env['loyalty.card'].sudo().search([('code', 'in', codes)])


def _vat_label(company):
    """What the tax number is CALLED where this shop trades.

    'VAT' is wrong in Egypt and in Saudi Arabia, and a receipt that mislabels the
    registration number is a receipt an inspector queries.
    """
    code = (company.country_id.code or '').upper()
    return {'SA': 'VAT No.', 'EG': 'Tax Reg.', 'AE': 'TRN'}.get(code, 'VAT')


def _cashier_name(order):
    """Who served this. Prefers the Mezze cashier over the API service user."""
    c = getattr(order, 'mezze_cashier_id', None)
    if c:
        return c.name
    return order.employee_id.name if getattr(order, 'employee_id', None) else (
        order.user_id.name or '')


def raw_send(host, port, data, timeout=4):
    """Raw ESC/POS over TCP (JetDirect 9100). Bounded connect+send timeout.
    Raises OSError on an unreachable/timed-out device (classified by the caller)."""
    sock = socket.create_connection((host, int(port or 9100)), timeout=timeout)
    try:
        sock.settimeout(timeout)
        sock.sendall(data)
    finally:
        sock.close()
    return len(data)


def epos_send(printer, data, timeout=4):
    """Deliver an ESC/POS stream to an Epson ePOS printer over HTTP.

    The bytes are the ones the caller rendered — the envelope carries them in
    ``<command>``, so an ePOS printer and a 9100 printer produce the same paper
    from the same order.

    ``requests`` failures are ``OSError`` subclasses, so an unreachable ePOS
    printer classifies exactly like an unreachable socket one and every existing
    handler keeps working. What is NOT an OSError is a printer that answered: ePOS
    returns HTTP 200 for "out of paper", so the body is the verdict.
    """
    url = epos.service_url(printer.host, printer.port,
                           device_id=printer.epos_device_id,
                           https=bool(printer.epos_https),
                           timeout_ms=printer.epos_timeout_ms or 10000)
    body = epos.build_envelope(data)
    resp = requests.post(
        url, data=body, timeout=timeout, allow_redirects=False,
        headers={'Content-Type': 'text/xml; charset=utf-8',
                 'If-Modified-Since': 'Thu, 01 Jan 1970 00:00:00 GMT',
                 'SOAPAction': '""'})
    if resp.status_code != 200:
        # A redirect or an auth challenge is the device (or something in front of
        # it) declining the job, not printing it.
        raise epos.EposError('http_%d' % resp.status_code,
                             (resp.text or '')[:120],
                             permanent=400 <= resp.status_code < 500)
    epos.parse_response(resp.content)
    return len(data)


def _iot_url(base, path):
    """Compose a Hardware Proxy endpoint from its PARTS.

    Same rule as the ePOS endpoint: a stored free-form URL is a request the server
    makes on behalf of whoever last edited the field, and "IoT box address" is not
    reviewed like an outbound webhook. Only the host and scheme come from
    configuration; the path is ours.
    """
    base = (base or '').strip().rstrip('/')
    if not base:
        raise ValueError('missing_iot_url')
    if not base.startswith(('http://', 'https://')):
        base = 'http://' + base
    if '?' in base or '#' in base:
        raise ValueError('bad_iot_url')
    return base + path


def iot_print(printer, data, timeout=4):
    """Print through Odoo's own Hardware Proxy (the LGPL ``iot_drivers`` module).

    The box takes the SAME ESC/POS bytes Mezze would have pushed down a socket,
    base64 in a JSON-RPC envelope, and hands them to whatever printer is plugged
    into it. That is the point of supporting it: a USB or serial printer has no
    address of its own, and the box is how it gets one — one renderer, a third
    transport.
    """
    url = _iot_url(printer.iot_url, '/hw_proxy/default_printer_action')
    resp = requests.post(
        url, json={'jsonrpc': '2.0', 'method': 'call',
                   'params': {'data': {'action': 'print_receipt',
                                       'document': base64.b64encode(bytes(data)).decode()}}},
        timeout=timeout, allow_redirects=False,
        headers={'Content-Type': 'application/json'})
    if resp.status_code != 200:
        raise epos.EposError('http_%d' % resp.status_code, (resp.text or '')[:120],
                             permanent=400 <= resp.status_code < 500)
    try:
        payload = resp.json()
    except ValueError:
        raise epos.EposError('unparseable_response', (resp.text or '')[:120])
    # The proxy answers ``result: false`` when no printer is attached — a 200 that
    # means nothing was printed, exactly the trap ePOS has.
    if payload.get('error') or payload.get('result') is False:
        raise epos.EposError('iot_no_printer',
                             str(payload.get('error') or '')[:120])
    return len(data)


def send_to_printer(printer, data, timeout=4):
    """The one way a printer is spoken to.

    Both the synchronous endpoints and the outbox consumer route through here, so
    a branch that switches a printer to ePOS switches BOTH paths at once. A second
    dispatch written next to one of the two call sites is how a queued receipt ends
    up going somewhere a live one does not.
    """
    transport = getattr(printer, 'transport', 'raw')
    if transport == 'epos':
        return epos_send(printer, data, timeout=timeout)
    if transport == 'iot':
        return iot_print(printer, data, timeout=timeout)
    return raw_send(printer.host, printer.port, data, timeout=timeout)


def read_scale(scale_rec, timeout=3):
    """Ask a scale what is on it, and believe only a settled answer.

    One socket, one enquiry, one reply — deliberately not a stream. A cashier taps
    once and gets the weight that was on the pan at that instant; a background poll
    would put a number on the bill that nobody chose.

    Transport failures stay ``OSError``, so an unplugged scale classifies exactly
    like an unreachable printer. A scale that ANSWERS but says the pan is still
    moving raises :class:`domain.scale.ScaleError`, because that is not a broken
    device — it is a reading that must not be charged for.
    """
    proto = scale_rec.protocol or scale.TOLEDO
    if proto == 'iot':
        # The box owns the serial cable; it answers {'weight': <kg>}. Same three
        # refusals as a direct scale — the unit is compared, never converted.
        url = _iot_url(scale_rec.iot_url, '/hw_proxy/scale_read')
        resp = requests.post(url, json={'jsonrpc': '2.0', 'method': 'call',
                                        'params': {}},
                             timeout=timeout, allow_redirects=False)
        if resp.status_code != 200:
            raise scale.ScaleError('unreadable', 'http_%d' % resp.status_code)
        try:
            weight = (resp.json() or {}).get('result', {})
        except ValueError:
            raise scale.ScaleError('unreadable', 'bad_json')
        if isinstance(weight, dict):
            weight = weight.get('weight')
        if weight is None:
            raise scale.ScaleError('no_reply')
        return scale.parse(scale.LINE, 'ST,GS,%s%s' % (
            weight, (scale_rec.uom_name or '').strip()),
            want_unit=(scale_rec.uom_name or '').strip())
    sock = socket.create_connection(
        (scale_rec.host, int(scale_rec.port or 4001)), timeout=timeout)
    try:
        sock.settimeout(timeout)
        enquiry = scale.ENQUIRE.get(proto)
        if enquiry:
            sock.sendall(enquiry)
        raw = sock.recv(256)
    finally:
        sock.close()
    return scale.parse(proto, raw, want_unit=(scale_rec.uom_name or '').strip())


def kitchen_ticket(order, station=None, width=48, encoding='cp437',
                   codepage_id=None, station_of=None):
    """The ticket a cook works from.

    Lives here, next to the receipt renderer, for the reason the receipt does: the
    synchronous ``/print/kitchen`` and the queued auto-print must produce the SAME
    paper. Two renderers drift, and the way you find out is a cook working from a
    ticket that is missing the line the guest phoned about.

    ``station_of`` is passed in rather than imported, because the routing rule lives
    on the controller and this module deliberately knows nothing about it.
    """
    tk = Ticket(width, encoding, codepage_id)
    tk.line((station or 'KITCHEN').upper(), 'c', bold=True, big=True)
    tk.lr('Order', order.tracking_number or order.pos_reference or str(order.id))
    table = order.table_id.table_number if order.table_id else None
    tk.lr('Table', table or 'Takeaway')
    tk.lr('Time', fields.Datetime.to_string(fields.Datetime.now())[11:16])
    tk.rule()
    lines = order.lines
    if station and station_of:
        lines = lines.filtered(lambda l: station_of(l.product_id) == station)
    for l in lines:
        name = (l.full_product_name or l.product_id.display_name or '')
        tk.line('%g x %s' % (l.qty, name), bold=True)
        # The cashier's TYPED instruction. ``full_product_name`` carries the
        # configured choices in parentheses and this does not: "allergy - no nuts"
        # reached the kitchen display and never the paper, so a branch that prints
        # instead of screens was blind on the line that matters most.
        note = (getattr(l, 'customer_note', '') or '').strip()
        if note:
            tk.line('   ! %s' % note)
        seat = int(getattr(l, 'mezze_seat', 0) or 0)
        if seat:
            tk.line('   seat %d' % seat)
    return tk


def drawer_bytes():
    return INIT + DRAWER


def z_report_ticket(data, width=48, encoding='cp437', codepage_id=None):
    """Print the shift's Z report.

    Takes the payload the ``/sessions/<id>/z_report`` endpoint returns — which is
    Odoo's own ``get_sale_details`` — rather than a recordset, so the paper and the
    screen are rendered from ONE set of figures. A Z report whose paper is computed
    separately from its screen is a Z report that can disagree with itself.

    Gross and refunds are printed on their own lines. Netting them into a single
    "sales" figure would let a day of heavy returns read as a quiet day, which is
    precisely what the shift report exists to prevent.
    """
    cur = data.get('currency') or ''

    def m(v):
        return ('%s %s' % (cur, _money(v))).strip()

    tk = Ticket(width, encoding, codepage_id)
    tk.line(data.get('company') or '', align='c', bold=True)
    tk.line((data.get('branch') or {}).get('name') or '', align='c')
    tk.line('Z REPORT', align='c', bold=True, big=True)
    tk.line(data.get('session') or '', align='c')
    tk.rule()
    if data.get('opened_at'):
        tk.lr('Opened', data['opened_at'])
    if data.get('closed_at'):
        tk.lr('Closed', data['closed_at'])
    tk.lr('Orders', str(data.get('orders') or 0))
    tk.rule()

    tk.line('SALES', bold=True)
    tk.lr('Gross', m(data.get('gross')))
    if data.get('refunds'):
        tk.lr('Refunds (%s)' % (data.get('refund_orders') or 0), '-' + m(data.get('refunds')))
    tk.lr('Net', m(data.get('net')), bold=True)
    if data.get('discount_amount'):
        tk.lr('Discounts (%s)' % (data.get('discount_orders') or 0),
              '-' + m(data.get('discount_amount')))

    taxes = data.get('taxes') or []
    if taxes:
        tk.rule()
        tk.line('TAX', bold=True)
        for t in taxes:
            tk.lr(t.get('name') or 'Tax', m(t.get('amount')))
    refund_taxes = data.get('refund_taxes') or []
    if refund_taxes:
        for t in refund_taxes:
            tk.lr('%s (refunded)' % (t.get('name') or 'Tax'), '-' + m(t.get('amount')))

    payments = data.get('payments') or []
    if payments:
        tk.rule()
        tk.line('BY TENDER', bold=True)
        for p in payments:
            if p.get('is_cash_count'):
                continue
            tk.lr(p.get('name') or '', m(p.get('total')))

    # The drawer, last and on its own, because it is the part someone has to act on.
    cash = [p for p in payments if p.get('is_cash_count')]
    for c in cash:
        tk.rule()
        tk.line('CASH DRAWER', bold=True)
        for mv in (c.get('cash_moves') or []):
            tk.lr(mv.get('name') or '', m(mv.get('amount')))
        tk.lr('Expected', m(c.get('expected')))
        tk.lr('Counted', m(c.get('counted')))
        diff = c.get('difference') or 0.0
        tk.lr('Over / short', m(diff), bold=True)
    if data.get('change_given'):
        tk.lr('Change given', m(data.get('change_given')))

    if data.get('closing_note'):
        tk.rule()
        tk.line('Note', bold=True)
        tk.line(data['closing_note'])
    tk.feed(3)
    return tk
