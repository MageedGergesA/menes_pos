# -*- coding: utf-8 -*-
"""Glory cash machines — the protocol, server-side, with no I/O.

**A correction first, because it shaped this file.** The parity report said for a
long time that Glory was "welded to the native browser store, so Mezze cannot reuse
it", and that the IoT hardware proxy "does not exist in Community". Both claims were
checked and only half of the first one holds: ``pos_glory_cash`` is right there in
the Community tree under LGPL-3, and so are ``iot_base`` and ``iot_drivers``. The
DRIVER is browser-side JavaScript, so its code genuinely cannot be reused by a
product that drives hardware from the server — but the PROTOCOL it speaks is fully
readable, which is a completely different situation from "cannot".

So this is that protocol, implemented where Mezze puts hardware: on the server.
Doing it server-side is not merely a port. A cash machine is the one device in a
shop that physically holds money, and the till that happens to have a browser tab
open is the worst possible authority over it — a refreshed page or a closed laptop
should not be able to lose track of cash mid-transaction. Here the session, the
sequence number and the outcome live in the database with everything else.

The exchange, from ``pos_glory_cash``:

  * a socket.io-framed WebSocket carries a small handshake — login, credential
    check, function settings, open session — which yields a session id;
  * everything after that is XML in and XML out: ``StatusRequest``,
    ``InventoryRequest``, ``ChangeRequest`` (take a payment), ``ChangeCancelRequest``,
    ``CollectRequest``, ``ResetRequest``, ``OccupyRequest``, ``ReleaseRequest``;
  * every response carries a numeric ``result`` attribute, and the numbers matter
    far more than a success flag would: ``CHANGE_SHORTAGE`` means the machine took
    the money and could not give the right change back, which is a different
    conversation with a customer than a machine that simply refused.

Amounts are integer minor units on the wire, as they should be.
"""
import re
from xml.etree import ElementTree

#: Result codes, verbatim from pos_glory_cash/static/src/utils/constants.js.
RESULT = {
    0: 'SUCCESS', 1: 'CANCEL', 2: 'RESET', 3: 'OCCUPIED_BY_OTHER',
    4: 'OCCUPATION_NOT_AVAILABLE', 5: 'NOT_OCCUPIED', 6: 'DESIGNATION_SHORTAGE',
    9: 'CANCEL_CHANGE_SHORTAGE', 10: 'CHANGE_SHORTAGE', 11: 'EXCLUSIVE_ERROR',
    12: 'CHANGE_INCONSISTENCY', 13: 'AUTO_RECOVERY_FAILURE', 21: 'INVALID_SESSION',
    22: 'SESSION_TIMEOUT', 40: 'INVALID_CASSETTE_NUMBER', 41: 'IMPROPER_CASSETTE',
    43: 'EXCHANGE_RATE_ERROR', 44: 'COUNTED_CATEGORY_2_3',
    96: 'DUPLICATE_TRANSACTION', 98: 'PARAMETER_ERROR', 99: 'PROGRAM_ERROR',
    100: 'DEVICE_ERROR',
}

REQUESTS = {
    'status': ('StatusRequest', 'StatusResponse'),
    'inventory': ('InventoryRequest', 'InventoryResponse'),
    'pay': ('ChangeRequest', 'ChangeResponse'),
    'cancel': ('ChangeCancelRequest', 'ChangeCancelResponse'),
    'collect': ('CollectRequest', 'CollectResponse'),
    'reset': ('ResetRequest', 'ResetResponse'),
    'occupy': ('OccupyRequest', 'OccupyResponse'),
    'release': ('ReleaseRequest', 'ReleaseResponse'),
}

#: The machine finished and the money is settled.
SETTLED = frozenset({'SUCCESS'})
#: Nothing was taken; the bill stays payable and the cashier simply tries again.
HARMLESS = frozenset({'CANCEL', 'RESET', 'NOT_OCCUPIED', 'OCCUPATION_NOT_AVAILABLE',
                      'OCCUPIED_BY_OTHER', 'DUPLICATE_TRANSACTION'})
#: The machine HELD money it could not resolve. Never auto-retried: a second
#: attempt against a drawer that already swallowed a note takes it twice.
UNCERTAIN = frozenset({'CHANGE_SHORTAGE', 'CANCEL_CHANGE_SHORTAGE',
                       'CHANGE_INCONSISTENCY', 'AUTO_RECOVERY_FAILURE',
                       'DEVICE_ERROR', 'EXCLUSIVE_ERROR'})


class GloryError(Exception):
    """A machine that did not complete, with its own word for why."""

    def __init__(self, code, name='', uncertain=False):
        self.code = code
        self.name = name or RESULT.get(code, 'UNKNOWN')
        self.uncertain = uncertain
        super().__init__('%s (%s)' % (self.name, code))


def header(seq, session_id, client_id='MezzePos'):
    """The three elements every XML request opens with."""
    return ('<Id>%s</Id><SeqNo>%011d</SeqNo><SessionID>%s</SessionID>'
            % (client_id, int(seq), session_id or ''))


def build(kind, seq, session_id, amount_minor=None, verify=None,
          client_id='MezzePos'):
    """One XML request, framed the way the device expects it.

    The trailing NUL is part of the wire format, not an accident — the reference
    implementation appends it and a device that never sees it waits for the rest of
    a message that has already been sent.
    """
    if kind not in REQUESTS:
        raise GloryError(98, 'PARAMETER_ERROR')
    root = REQUESTS[kind][0]
    body = header(seq, session_id, client_id)
    if kind == 'pay':
        if amount_minor is None or int(amount_minor) <= 0:
            raise GloryError(98, 'PARAMETER_ERROR')
        body += '<Amount>%d</Amount><Option type="1"/>' % int(amount_minor)
    if kind == 'collect' and verify is not None:
        body += '<Option type="%d"/>' % int(verify)
    return ('<%s>%s</%s>' % (root, body, root)) + '\x00'


def _strip(raw):
    if isinstance(raw, (bytes, bytearray)):
        raw = bytes(raw).decode('utf-8', 'replace')
    # The device pads with NULs and the odd control byte; the reference client
    # strips them before parsing and so must this.
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw or '').strip()


def parse(raw):
    """Read a response into ``(name, root)`` or raise :class:`GloryError`.

    A response that cannot be parsed at all is a failure, not a success. A device
    behind a captive portal or a proxy answers with something — and reading "no
    result attribute" as "fine" is how a shop finds out at closing time.
    """
    text = _strip(raw)
    if not text:
        raise GloryError(100, 'DEVICE_ERROR', uncertain=True)
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        raise GloryError(99, 'PROGRAM_ERROR', uncertain=True)
    attr = root.get('result')
    if attr is None:
        raise GloryError(99, 'PROGRAM_ERROR', uncertain=True)
    try:
        code = int(attr)
    except (TypeError, ValueError):
        raise GloryError(99, 'PROGRAM_ERROR', uncertain=True)
    name = RESULT.get(code)
    if name is None:
        # A code from firmware nobody here has seen. Uncertain by default: an
        # unfamiliar answer about a machine holding cash must not be read as "no
        # money moved".
        raise GloryError(code, 'UNKNOWN', uncertain=True)
    if name in SETTLED:
        return name, root
    raise GloryError(code, name, uncertain=name in UNCERTAIN)


# ---------------------------------------------------------------------------
# socket.io framing
# ---------------------------------------------------------------------------
# Glory speaks XML, but the XML rides inside a socket.io v4 envelope, which is
# itself a thin text protocol over a WebSocket. The reference client
# (pos_glory_cash/static/src/utils/socket_io.js) uses two digits: an engine.io
# PACKET type, then for a MESSAGE a socket.io MESSAGE type, then JSON.
#
#   "0" open        "2" ping        "4" message
#   message "0" connect   "2" event   "3" ack
#
# So an outbound event is the two characters "42" followed by a JSON array. This
# is reimplemented rather than imported because the reference lives in browser
# JavaScript, and it is small enough that the alternative — shelling out to a
# Node process from a POS server — would be the larger risk.

PACKET_OPEN, PACKET_PING, PACKET_PONG, PACKET_MESSAGE = '0', '2', '3', '4'
MSG_CONNECT, MSG_EVENT, MSG_ACK = '0', '2', '3'


def encode_event(payload):
    """One outbound socket.io event frame."""
    import json as _json
    body = payload if isinstance(payload, list) else [payload]
    return PACKET_MESSAGE + MSG_EVENT + _json.dumps(body)


def decode_frame(frame):
    """(kind, payload) for one inbound frame.

    ``kind`` is one of ``open``, ``ping``, ``pong``, ``connect``, ``event``,
    ``ack`` or ``other`` — the caller decides what to do, because a device that
    answers PING while a payment is in flight is normal and one that answers
    ``other`` is not.
    """
    import json as _json
    if not frame:
        return 'other', None
    text = frame.decode('utf-8', 'replace') if isinstance(frame, (bytes, bytearray)) else str(frame)
    head, rest = text[:1], text[1:]
    if head == PACKET_OPEN:
        try:
            return 'open', _json.loads(rest or '{}')
        except ValueError:
            return 'open', {}
    if head == PACKET_PING:
        return 'ping', None
    if head == PACKET_PONG:
        return 'pong', None
    if head != PACKET_MESSAGE:
        return 'other', text
    sub, body = rest[:1], rest[1:]
    kind = {MSG_CONNECT: 'connect', MSG_EVENT: 'event', MSG_ACK: 'ack'}.get(sub, 'other')
    if kind in ('event', 'ack'):
        try:
            return kind, _json.loads(body or '[]')
        except ValueError:
            return kind, None
    return kind, body or None


def amount_in(root):
    """What the machine says it has taken, in minor units."""
    if root is None:
        return 0
    node = root.find('.//Amount')
    if node is None or not (node.text or '').strip():
        return 0
    try:
        return int((node.text or '0').strip())
    except (TypeError, ValueError):
        return 0
