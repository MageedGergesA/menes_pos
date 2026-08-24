"""Pure ESC/POS receipt builder — no Odoo, no I/O.

Renders the same row list to both an ESC/POS byte stream and a plain-text preview.
Shared by the synchronous hardware endpoints (controllers/hardware.py) and the
outbox print consumer so a queued receipt is byte-identical to a live one.
"""

# ESC/POS command bytes
INIT = b'\x1b\x40'
AL = {'l': b'\x1b\x61\x00', 'c': b'\x1b\x61\x01', 'r': b'\x1b\x61\x02'}
BOLD_ON, BOLD_OFF = b'\x1b\x45\x01', b'\x1b\x45\x00'
BIG_ON, BIG_OFF = b'\x1d\x21\x11', b'\x1d\x21\x00'
CUT = b'\x1d\x56\x00'
DRAWER = b'\x1b\x70\x00\x19\xfa'  # kick drawer pin 0

# CODE PAGES (ESC t n).
#
# The encoder was hardcoded to cp437 with ``errors='replace'``, so every Arabic
# character on a printed receipt came out as "?" — on a product whose screens are
# fully bilingual. Latin text was unaffected, which is why it survived so long.
#
# Two things are needed, and doing only one of them changes nothing: the bytes must
# be encoded in a codepage that HAS the glyphs, and the printer must be told to
# select that page, or it decodes them with whatever page it powered on with.
#
# The page NUMBERS are not a standard anyone follows exactly. Epson's table is the
# closest thing, generic Chinese firmware routinely differs, and Arabic is the worst
# offender for it. So the number is configuration with a sane default rather than a
# constant pretending to be universal: `DEFAULT_CODEPAGE_ID` is the common value, and
# a printer that disagrees can be corrected in its own record without a code change.
DEFAULT_CODEPAGE_ID = {
    'cp437': 0,      # Latin, the ESC/POS default
    'cp850': 2,      # Latin-1
    'cp858': 19,     # Latin-1 + euro
    'cp1252': 16,    # Windows Western
    'cp864': 22,     # Arabic
    'cp1256': 50,    # Windows Arabic — the usual value on generic firmware
}


def codepage_bytes(page_id):
    """``ESC t n`` — select the printer's character code table."""
    try:
        n = int(page_id)
    except (TypeError, ValueError):
        return b''
    if not 0 <= n <= 255:
        return b''
    return b'\x1b\x74' + bytes([n])

# QR code (GS ( k). Four calls: model, module size, error correction, store, print.
# Mezze had no barcode command at all, which is why a signed tax QR could not be put
# on paper — and a ZATCA or ETA receipt is a QR receipt. Text alone does not satisfy
# either authority, and printing the payload as digits is not a substitute.
def qr_bytes(payload, module=6, ec='M'):
    """ESC/POS GS ( k byte sequence for a QR code. Empty payload -> no bytes."""
    if not payload:
        return b''
    data = payload.encode('utf-8') if isinstance(payload, str) else bytes(payload)
    ec_map = {'L': 48, 'M': 49, 'Q': 50, 'H': 51}
    out = b'\x1d\x28\x6b\x04\x00\x31\x41\x32\x00'                    # model 2
    out += b'\x1d\x28\x6b\x03\x00\x31\x43' + bytes([max(1, min(16, int(module)))])
    out += b'\x1d\x28\x6b\x03\x00\x31\x45' + bytes([ec_map.get(ec, 49)])
    n = len(data) + 3
    out += b'\x1d\x28\x6b' + bytes([n % 256, n // 256]) + b'\x31\x50\x30' + data
    out += b'\x1d\x28\x6b\x03\x00\x31\x51\x30'                        # print
    return out


class Ticket:
    """A tiny receipt builder → ESC/POS bytes + plain-text preview from one row list."""

    def __init__(self, width=48, encoding='cp437', codepage_id=None):
        self.width = max(24, int(width or 48))
        self.encoding = (encoding or 'cp437').lower()
        # An explicit page number wins; otherwise the usual one for this encoding.
        self.codepage_id = (DEFAULT_CODEPAGE_ID.get(self.encoding, 0)
                            if codepage_id is None else codepage_id)
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

    def qr(self, payload, caption=''):
        """A real QR on the paper. Falls back to the caption in the text preview,
        which is all a preview can honestly show."""
        if payload:
            self.rows.append(('qr', str(payload), str(caption or '')))
        return self

    def _enc(self, s):
        """Encode in the printer's codepage, falling back rather than exploding.

        ``errors='replace'`` is kept deliberately: a receipt with a few substituted
        characters still tells the customer what they bought and what they paid,
        whereas raising here would mean no receipt at all. The fix for the
        substitutions is to give the printer a codepage that has the glyphs, which is
        now configuration rather than a constant.
        """
        try:
            return s.encode(self.encoding, 'replace')
        except LookupError:
            # An encoding name the platform does not know must not stop the sale.
            return s.encode('cp437', 'replace')

    def to_text(self):
        out = []
        for r in self.rows:
            if r[0] == 'rule':
                out.append('-' * self.width)
            elif r[0] == 'feed':
                out.extend([''] * r[1])
            elif r[0] == 'qr':
                # A preview is text; it cannot show a QR, so it says what the QR is
                # rather than pretending. Never print the payload — a signed tax
                # payload on a preview is noise a cashier would try to read.
                out.append(('[QR: %s]' % (r[2] or 'code')).center(self.width))
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
        buf = bytearray(INIT)
        # Select the code page BEFORE any text, or the printer decodes these bytes
        # with whatever page it happened to power on with.
        buf += codepage_bytes(self.codepage_id)
        for r in self.rows:
            if r[0] == 'rule':
                buf += AL['l'] + self._enc('-' * self.width) + b'\n'
            elif r[0] == 'feed':
                buf += b'\n' * r[1]
            elif r[0] == 'qr':
                buf += AL['c'] + qr_bytes(r[1]) + b'\n'
                if r[2]:
                    buf += AL['c'] + self._enc(r[2]) + b'\n'
            else:
                _, align, text, bold, big = r
                buf += AL.get(align, AL['l'])
                if big:
                    buf += BIG_ON
                if bold:
                    buf += BOLD_ON
                buf += self._enc(text) + b'\n'
                if bold:
                    buf += BOLD_OFF
                if big:
                    buf += BIG_OFF
        buf += b'\n\n\n' + CUT
        if drawer:
            buf += DRAWER
        return bytes(buf)
