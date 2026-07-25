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


class Ticket:
    """A tiny receipt builder → ESC/POS bytes + plain-text preview from one row list."""

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
        buf = bytearray(INIT)
        for r in self.rows:
            if r[0] == 'rule':
                buf += AL['l'] + self._enc('-' * self.width) + b'\n'
            elif r[0] == 'feed':
                buf += b'\n' * r[1]
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
