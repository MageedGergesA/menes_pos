# -*- coding: utf-8 -*-
"""Driving a Glory cash machine from the server.

``domain/glory`` is the protocol with no I/O; this is the socket that carries it,
and the wiring into ``mezze.terminal.transaction`` — the same server-authoritative
spine that already refuses to let a browser assert that money moved.

The transport is injectable (``_open_socket``) so the whole exchange can be driven
in tests without a machine, exactly as the Stripe and ePOS adapters are. What no
mock can establish is whether a real Glory unit accepts these bytes; that is stated
on the parity row rather than implied by a green suite.

The sequence, from ``pos_glory_cash``: connect, wait for the engine.io OPEN frame,
then four socket.io events — login, credential check, function settings, open
session — which yield a session id. Every XML request after that carries that id
and a monotonic sequence number.

**Why the session id lives in the database.** A cash machine physically holds money.
If the session is state in a browser tab, a refreshed page during a payment leaves a
machine holding a note that nothing in the system knows about. Here the id, the
sequence and the outcome are rows, so a crashed till is a recoverable situation
rather than a discrepancy somebody finds at close.
"""
import logging

from odoo import fields, models

from ..domain import glory

_logger = logging.getLogger(__name__)

#: How long to wait for any single frame. A cashier is standing at the machine.
_FRAME_TIMEOUT = 8
#: A payment waits on the customer feeding notes in, so it gets its own budget.
_PAY_TIMEOUT = 180


class GloryTransport:
    """One connection's worth of conversation. Not an Odoo model — a helper the
    transaction owns for the length of a request."""

    def __init__(self, url, user, password, client_id='MezzePos', socket=None):
        self.url = url
        self.user = user
        self.password = password
        self.client_id = client_id
        self._sock = socket
        self.session_id = None

    # -- socket ---------------------------------------------------------
    def _open_socket(self):
        if self._sock is not None:
            return self._sock
        import websocket   # provided by websocket-client
        self._sock = websocket.create_connection(self.url, timeout=_FRAME_TIMEOUT)
        return self._sock

    def _send(self, payload):
        self._open_socket().send(glory.encode_event(payload))

    def _recv(self, want=('event',), timeout=_FRAME_TIMEOUT):
        """Read frames until one of ``want`` arrives.

        PING is answered rather than treated as noise: a device kept waiting for a
        PONG closes the connection, and it does that most readily during the long
        wait while a customer is feeding notes in — i.e. exactly when losing the
        connection is most expensive.
        """
        sock = self._open_socket()
        sock.settimeout(timeout)
        while True:
            kind, payload = glory.decode_frame(sock.recv())
            if kind == 'ping':
                sock.send(glory.PACKET_PONG)
                continue
            if kind in want:
                return kind, payload
            if kind == 'other':
                raise glory.GloryError(100, 'DEVICE_ERROR', uncertain=True)

    def close(self):
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:  # noqa: BLE001 — closing must never mask an outcome
            pass

    # -- handshake ------------------------------------------------------
    def connect(self):
        """Log in and open a session. Returns the session id."""
        self._recv(want=('open',))
        for request, response in (
            ('login request', 'login response'),
            ('check credential', 'credential ok'),
            ('getFunctionSetting', 'sendFunctionSetting'),
        ):
            self._send([request, {'user': self.user, 'password': self.password}])
            self._recv(want=('event',))
        self._send(['openSession', {'user': self.user}])
        _kind, payload = self._recv(want=('event',))
        self.session_id = self._session_from(payload)
        if not self.session_id:
            raise glory.GloryError(21, 'INVALID_SESSION')
        return self.session_id

    @staticmethod
    def _session_from(payload):
        if isinstance(payload, list) and len(payload) > 1:
            body = payload[1]
            if isinstance(body, dict):
                return body.get('sessionId') or body.get('SessionID') or body.get('sid')
            if isinstance(body, str):
                return body
        return None

    # -- requests -------------------------------------------------------
    def request(self, kind, seq, amount_minor=None, verify=None, timeout=None):
        """One XML request/response. Raises GloryError on anything but SUCCESS."""
        xml = glory.build(kind, seq, self.session_id,
                          amount_minor=amount_minor, verify=verify,
                          client_id=self.client_id)
        self._send([glory.REQUESTS[kind][0], xml])
        _k, payload = self._recv(
            want=('event',), timeout=timeout or _FRAME_TIMEOUT)
        raw = payload[1] if isinstance(payload, list) and len(payload) > 1 else payload
        return glory.parse(raw)


class MezzeTerminalTransactionGlory(models.Model):
    _inherit = 'mezze.terminal.transaction'

    def _glory_device(self):
        self.ensure_one()
        return self.mezze_device_id

    def mezze_glory_pay(self, transport=None):
        """Take a cash payment on the machine, server-side.

        Outcomes are the machine's, never the till's:

        * SUCCESS settles exactly one ``pos.payment`` through the same converging
          path every other tender uses;
        * a harmless refusal (cancelled, reset, occupied by another till) leaves the
          bill payable and nothing is written;
        * an UNCERTAIN result — ``CHANGE_SHORTAGE`` and its relatives — means the
          machine is holding money it could not resolve. That is never auto-retried
          and never settled: a second attempt against a drawer that already swallowed
          a note takes it twice. It goes to the manager override with its own
          provenance, which is what that override exists for.
        """
        self.ensure_one()
        if self.state == 'approved':
            return self
        device = self._glory_device()
        url = (getattr(device, 'glory_url', '') or '').strip()
        if not url:
            self.write({'state': 'error', 'error_code': 'glory_unconfigured'})
            return self
        prec = self.currency_id.decimal_places or 2
        amount_minor = int(round(self.amount * (10 ** prec)))
        link = transport or GloryTransport(
            url, device.glory_user or '', device._glory_password() or '',
            client_id='MezzePos')
        try:
            link.connect()
            self.write({'state': 'waiting_customer'})
            _name, root = link.request('pay', 1, amount_minor=amount_minor,
                                       timeout=_PAY_TIMEOUT)
            taken = glory.amount_in(root)
            self.write({'provider_reference': 'GLORY-%s' % (link.session_id or ''),
                        'inserted_amount': round(taken / float(10 ** prec), prec)})
            self._settle_payment(provenance='cash_machine')
            self.write({'state': 'approved', 'uncertain': False, 'error_code': ''})
        except glory.GloryError as exc:
            _logger.warning("Mezze glory %s: %s", self.request_id, exc)
            if exc.uncertain:
                self.write({'state': 'unknown', 'uncertain': True,
                            'error_code': exc.name})
            else:
                self.write({'state': 'cancelled', 'uncertain': False,
                            'error_code': exc.name})
        except OSError as exc:
            # We never reached it, or lost it mid-way. Not a decline, and not a
            # settlement: a machine that was mid-transaction may be holding cash.
            _logger.warning("Mezze glory %s transport: %s", self.request_id, exc)
            self.write({'state': 'unknown', 'uncertain': True,
                        'error_code': 'transport'})
        finally:
            link.close()
        return self
