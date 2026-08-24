# -*- coding: utf-8 -*-
"""Epson ePOS-Print — the same receipt, over HTTP instead of a raw socket.

Mezze prints by opening a TCP socket to port 9100 and pushing ESC/POS at it. That
covers most network thermal printers and none of the Epson **ePOS** ones: the TM-i
series and the ePOS-capable interface boards do not listen on 9100 at all. They
expose an HTTP endpoint that takes an XML envelope, which is why a shop that already
owns Epson hardware could not use it.

The decision that matters here is what goes INSIDE the envelope.

ePOS-Print XML has elements for text, alignment, barcodes and cutting — a second,
parallel way to describe a receipt. Rendering through it would give Mezze two
receipt renderers, and two renderers drift: the same order printed on the Epson at
the counter and the generic printer in the kitchen would slowly stop matching, and
nobody would notice until a customer compared two pieces of paper. So this does not
render anything. It takes the ESC/POS byte stream Mezze already produces and carries
it in the envelope's ``<command>`` element, which exists for exactly that. One
renderer, two transports.

The other thing worth stating plainly: **ePOS answers 200 for a failure.** The HTTP
request succeeds, and whether the paper moved is in the body — ``success="false"``
with a code like ``EPTR_REC_EMPTY`` (out of paper) or ``EPTR_COVER_OPEN``. A caller
that trusts the status line reports every jammed, empty and open printer in the
estate as printed. Parsing the body is not a nicety here; it is the whole point.

No Odoo imports, no I/O — the transport lives in ``models/hardware_render.py`` and
this stays testable without a printer.
"""
import re
from xml.etree import ElementTree

#: Epson's own namespaces. Fixed by the protocol, not configuration.
NS_SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
NS_EPOS = 'http://www.epson-pos.com/schemas/2011/03/epos-print'

#: The device id an ePOS printer answers to out of the box. A TM-i box hosting
#: several printers gives each one its own id, so it is per-printer configuration.
DEFAULT_DEVICE_ID = 'local_printer'

#: Path of the print service on the device.
SERVICE_PATH = '/cgi-bin/epos/service.cgi'


def service_url(host, port=None, device_id=DEFAULT_DEVICE_ID, https=False,
                timeout_ms=10000):
    """Build the endpoint from its PARTS.

    Deliberately not a free-form URL field. A stored URL is a request the server
    will make on behalf of whoever last edited it, and "printer address" is not a
    field anyone reviews as if it were an outbound webhook. Composing it from a
    host, a port and a device id keeps the scheme, the path and the query out of
    reach — the worst a mistyped value can do is fail to find a printer.
    """
    host = (host or '').strip()
    if not host:
        raise ValueError('missing_host')
    if '/' in host or '@' in host or '?' in host:
        raise ValueError('bad_host')
    scheme = 'https' if https else 'http'
    default_port = 443 if https else 80
    port = int(port or default_port)
    netloc = host if port == default_port else '%s:%d' % (host, port)
    dev = (device_id or DEFAULT_DEVICE_ID).strip() or DEFAULT_DEVICE_ID
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', dev):
        raise ValueError('bad_device_id')
    return '%s://%s%s?devid=%s&timeout=%d' % (
        scheme, netloc, SERVICE_PATH, dev, int(timeout_ms or 10000))


def build_envelope(escpos_bytes):
    """Wrap an ESC/POS stream in the ePOS-Print envelope.

    ``<command>`` carries raw printer commands as a hex string, so the bytes that
    reach the print head are the ones Mezze rendered — the cut, the drawer kick and
    the code-page selection included. Nothing is re-described in XML.
    """
    if not isinstance(escpos_bytes, (bytes, bytearray)):
        raise TypeError('escpos_bytes must be bytes')
    if not escpos_bytes:
        raise ValueError('empty_payload')
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="%s">'
        '<s:Body>'
        '<epos-print xmlns="%s">'
        '<command>%s</command>'
        '</epos-print>'
        '</s:Body>'
        '</s:Envelope>' % (NS_SOAP, NS_EPOS, bytes(escpos_bytes).hex())
    ).encode('utf-8')


#: Codes that will still be true on the next attempt. Retrying a schema error or a
#: device id that does not exist just burns the queue against a wall.
PERMANENT_CODES = frozenset({
    'SchemaError',        # the envelope is wrong — our bug, not the shop's
    'DeviceNotFound',     # no such devid on this box
    'EX_BADPORT',         # the device is not a printer
    'EX_DEVID',           # malformed device id
})

#: Everything else is treated as transient — including codes not listed here.
#: An unknown code from a printer firmware nobody has seen should cost a retry, not
#: a silently dropped receipt.
KNOWN_TRANSIENT_CODES = frozenset({
    'EPTR_COVER_OPEN',    # someone is changing the roll
    'EPTR_REC_EMPTY',     # out of paper
    'EPTR_AUTOMATICAL',   # recoverable printer fault
    'EPTR_UNRECOVERABLE',  # needs a power cycle — still not our decision to drop
    'EPTR_BATTERY_LOW',
    'EPTR_RECEIPT_TIMEOUT',
    'DeviceInUse',        # another job is on the head
    'PrintSystemError',
    'EX_TIMEOUT',
})


class EposError(Exception):
    """A printer that did not print, with the printer's own words attached."""

    def __init__(self, code, status='', permanent=False):
        self.code = code or 'unknown'
        self.status = status or ''
        self.permanent = permanent
        super().__init__('%s%s' % (self.code, ' (%s)' % status if status else ''))


def parse_response(body):
    """Read the printer's verdict out of the response body.

    Returns the ``status`` attribute on success and raises :class:`EposError` on
    anything else. A body that cannot be parsed at all is a failure too: an ePOS
    printer that answers with a login page or a proxy's error document has not
    printed, and reading "no error element found" as "fine" is how a shop discovers
    at closing time that nothing came out.
    """
    if isinstance(body, bytes):
        body = body.decode('utf-8', errors='replace')
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        raise EposError('unparseable_response', (body or '')[:120])
    # ``.//`` never matches the root itself, and a printer that answers with the
    # bare <response> rather than a full SOAP envelope is answering correctly.
    candidates = [root] + list(root.iter())
    node = next((n for n in candidates
                 if n.tag in ('{%s}response' % NS_EPOS, 'response')), None)
    if node is None:
        raise EposError('no_response_element', (body or '')[:120])
    success = (node.get('success') or '').strip().lower()
    code = (node.get('code') or '').strip()
    status = (node.get('status') or '').strip()
    if success == 'true':
        return {'ok': True, 'status': status, 'code': code}
    raise EposError(code or 'print_failed', status,
                    permanent=code in PERMANENT_CODES)
