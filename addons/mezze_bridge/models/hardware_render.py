"""Shared hardware render + transport helpers.

One place builds the receipt layout and one place does the raw TCP send, so a
receipt printed synchronously (controllers/hardware.py) and one delivered through
the outbox print consumer are byte-identical, and the socket path (timeout, close)
is identical too. Rendering happens from the AUTHORITATIVE order at send time, so
no document content is stored in the event payload.
"""

import socket

from odoo import fields

from ..domain.escpos import Ticket, INIT, DRAWER


def _money(v):
    return '%.2f' % (v or 0.0)


def receipt_ticket(order, width=48):
    """Build the customer receipt for a pos.order. Pure record traversal."""
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
        tk.lr('%g x %s' % (l.qty, name[:tk.width - 12]), _money(l.price_subtotal_incl))
    tk.rule()
    tk.lr('Subtotal', _money(order.amount_total - order.amount_tax))
    tk.lr('Tax', _money(order.amount_tax))
    tk.lr('TOTAL', _money(order.amount_total), bold=True)
    tk.rule()
    for p in order.payment_ids:
        tk.lr(p.payment_method_id.name, _money(p.amount))
    inv = order.account_move
    if inv and 'l10n_eg_uuid' in inv._fields and inv.l10n_eg_uuid:
        tk.feed()
        tk.line('ETA e-invoice', 'c')
        tk.line(inv.l10n_eg_uuid, 'c')
    tk.feed()
    tk.line('Thank you!', 'c')
    return tk


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


def drawer_bytes():
    return INIT + DRAWER
