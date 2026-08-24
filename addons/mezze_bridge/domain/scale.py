# -*- coding: utf-8 -*-
"""Reading a weight off a shop scale — the parsing, with no I/O.

Mezze can already SELL by weight: the catalogue ships ``to_weight``, the quantity
survives the round trip as a measurement, and the till has a pad that takes a
decimal. What it could not do is ask the scale, so the weight was whatever the
cashier read off a display and typed — which is fine until it isn't, and it is the
one number on the line that nobody can check afterwards.

Scales are driven the same way printers are: over the network, from the server. The
protocols below are the two that most retail hardware speaks or imitates.

Three rules decide what this module refuses, and all three are about money:

* **An unstable reading is not a weight.** Every scale worth buying says whether the
  pan has settled. Taking the number anyway charges the guest for the bounce as the
  item is put down, and the error is always in the shop's favour, which is exactly
  the kind of bug that goes unreported for a year.
* **A unit is never converted.** If the scale answers in pounds and the product is
  priced by the kilogram, that is a 2.2x error on the bill. Refusing is a cashier
  ringing it up by hand; guessing is a wrong number nobody sees.
* **Zero or negative is not a sale.** An empty pan, or a tare left in, reads as
  nothing or as less than nothing. Neither is a quantity.
"""
import re

#: Toledo 8217 and the very large family of scales that imitate it. The host sends
#: ``W``; the scale answers STX, a status byte, the weight as ASCII, CR LF ETX.
TOLEDO = 'toledo'
#: The other common shape: a plain ASCII line such as ``ST,GS,   0.400kg``. Used by
#: CAS, AND, Excell and most of the generic bench scales sold with them.
LINE = 'line'

ENQUIRE = {TOLEDO: b'W\r', LINE: b'\r'}

STX, ETX = 0x02, 0x03

#: Toledo status bits, in the byte after STX.
_TOLEDO_MOTION = 0x01        # the pan has not settled
_TOLEDO_OVER = 0x02          # over capacity or under zero


class ScaleError(Exception):
    """A reading that must not become a line on a bill."""

    def __init__(self, code, detail=''):
        self.code = code
        self.detail = detail or ''
        super().__init__('%s%s' % (code, ' (%s)' % detail if detail else ''))


def _finish(weight, unit, stable, want_unit):
    if not stable:
        # Not an error the cashier caused, and it fixes itself in a second — so it
        # is reported as its own thing rather than as a broken scale.
        raise ScaleError('unstable')
    if weight is None:
        raise ScaleError('unreadable')
    if want_unit and unit and unit.lower() != want_unit.lower():
        raise ScaleError('unit_mismatch', '%s != %s' % (unit, want_unit))
    if weight <= 0:
        raise ScaleError('not_positive', str(weight))
    return {'weight': round(weight, 3), 'unit': unit or (want_unit or ''),
            'stable': True}


def parse_toledo(raw, want_unit=None):
    """Parse an 8217-style frame: ``STX <status> <weight> CR LF ETX``."""
    if not raw:
        raise ScaleError('no_reply')
    data = bytes(raw)
    start = data.find(bytes([STX]))
    if start < 0:
        raise ScaleError('bad_frame', repr(data[:32]))
    end = data.find(bytes([ETX]), start)
    body = data[start + 1:end if end > 0 else len(data)]
    if not body:
        raise ScaleError('bad_frame', repr(data[:32]))
    status = body[0]
    text = body[1:].decode('ascii', 'replace').strip()
    if status & _TOLEDO_OVER:
        raise ScaleError('out_of_range')
    stable = not (status & _TOLEDO_MOTION)
    m = re.search(r'-?\d+(?:\.\d+)?', text)
    weight = float(m.group(0)) if m else None
    unit = 'lb' if 'lb' in text.lower() else ('kg' if 'kg' in text.lower() else None)
    return _finish(weight, unit, stable, want_unit)


def parse_line(raw, want_unit=None):
    """Parse an ASCII line such as ``ST,GS,   0.400kg``.

    The leading token is the stability word: ``ST`` steady, ``US`` unsteady, ``OL``
    overload. A scale that sends no such token is taken at its word — some do not
    have the concept — but one that says ``US`` is believed.
    """
    if raw is None:
        raise ScaleError('no_reply')
    text = (raw.decode('ascii', 'replace') if isinstance(raw, (bytes, bytearray))
            else str(raw)).strip()
    if not text:
        raise ScaleError('no_reply')
    upper = text.upper()
    if upper.startswith('OL') or 'OVERLOAD' in upper:
        raise ScaleError('out_of_range')
    stable = not upper.startswith('US')
    m = re.search(r'-?\d+(?:\.\d+)?', text)
    weight = float(m.group(0)) if m else None
    unit = None
    u = re.search(r'(kg|lb|g)\b', text, re.I)
    if u:
        unit = u.group(1).lower()
    if unit == 'g' and weight is not None:
        # Grams are a display choice, not a different measurement — and unlike
        # pounds the conversion is exact, so it is arithmetic rather than a guess.
        weight, unit = weight / 1000.0, 'kg'
    return _finish(weight, unit, stable, want_unit)


PARSERS = {TOLEDO: parse_toledo, LINE: parse_line}


def parse(protocol, raw, want_unit=None):
    parser = PARSERS.get(protocol)
    if not parser:
        raise ScaleError('unknown_protocol', str(protocol))
    return parser(raw, want_unit=want_unit)
