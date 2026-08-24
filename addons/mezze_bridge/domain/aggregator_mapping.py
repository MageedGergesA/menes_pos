# -*- coding: utf-8 -*-
"""Turning a delivery platform's order JSON into Mezze's — as configuration.

The inbound webhook was already hardened: per-channel HMAC, replay-safe on the
vendor's own order id, every SKU mapped before anything is created, an unmapped
item rejecting the whole order rather than half-selling it. What it could not do
was accept a payload it had not designed. It read ``external_id``, ``items[].sku``
and ``customer{}`` — Mezze's own shape — so integrating a real platform meant
writing a translator, releasing it, and doing that again for the next platform.

**Why this is a mapping table and not a Talabat adapter.**

Talabat's and Jahez's order APIs are partner-gated: you get the specification after
you sign, and it is not public. Writing a module called ``talabat.py`` full of field
names nobody here has seen would produce something that looks finished, passes its
own tests, and is wrong in a way that only shows up on the first live order. This
codebase has refused that trade all the way through and it refuses it here.

So the vendor-specific part is DATA. A channel carries a mapping — where in that
platform's JSON the order id lives, where the items array is, which key holds the
SKU, the quantity, the price, the customer's name and phone — and onboarding a new
platform is filling that in from their specification, not a code change and a
release. The parts that are actually hard and actually shared (authentication,
idempotency, SKU resolution, rejection, money) stay in one place and stay tested.

A path is dotted, with numeric segments indexing a list: ``order.items``,
``customer.contact.phone``, ``payment.0.amount``. That is enough for every REST
order payload the author has seen and small enough to reason about; anything a path
cannot reach is a sign the platform needs a real adapter, and the caller is told so
rather than being handed a half-mapped order.
"""

#: The canonical shape the rest of Mezze already speaks.
CANONICAL_KEYS = ('external_id', 'items', 'customer')

#: Mezze's own native payload, expressed as a mapping like any other — so the
#: existing format is not a special case in the code, just the default row.
NATIVE = {
    'external_id': 'external_id',
    'items': 'items',
    'item_sku': 'sku',
    'item_qty': 'qty',
    'item_price': 'price',
    'customer_name': 'customer.name',
    'customer_phone': 'customer.phone',
    'customer_address': 'customer.address',
}


class MappingError(Exception):
    """The payload does not fit the mapping. Never a half-translated order."""

    def __init__(self, reason, detail=''):
        self.reason = reason
        self.detail = detail or ''
        super().__init__('%s%s' % (reason, ' (%s)' % detail if detail else ''))


def dig(payload, path, default=None):
    """Read a dotted path out of nested dicts and lists.

    Returns ``default`` for anything missing rather than raising: a payload that
    omits an optional field is normal, and the REQUIRED ones are checked by name
    afterwards so the error says which field was missing instead of where the
    traversal happened to stop.
    """
    if not path:
        return default
    node = payload
    for part in str(path).split('.'):
        if node is None:
            return default
        if isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(node, dict):
            if part not in node:
                return default
            node = node[part]
        else:
            return default
    return default if node is None else node


def _number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def translate(payload, mapping=None):
    """Vendor payload -> Mezze's canonical order dict.

    Raises :class:`MappingError` rather than returning a partial order. A delivery
    platform's order is prepaid and already promised to a customer, so the failure
    modes are not symmetric: rejecting one Mezze can't read is a phone call, while
    accepting one it half-read is food out of the door against a bill that does not
    match what the guest paid.
    """
    m = dict(NATIVE)
    m.update(mapping or {})

    external_id = dig(payload, m.get('external_id'))
    if external_id in (None, '', []):
        raise MappingError('missing_external_id', str(m.get('external_id')))
    external_id = str(external_id)

    raw_items = dig(payload, m.get('items'))
    if not isinstance(raw_items, list) or not raw_items:
        raise MappingError('no_items', str(m.get('items')))

    items = []
    for idx, row in enumerate(raw_items):
        if not isinstance(row, dict):
            raise MappingError('bad_item', 'index %d' % idx)
        sku = dig(row, m.get('item_sku'))
        if sku in (None, '', []):
            raise MappingError('missing_sku', 'item %d' % idx)
        qty = _number(dig(row, m.get('item_qty')), 1.0)
        if qty is None or qty <= 0:
            raise MappingError('bad_quantity', 'item %d' % idx)
        item = {'sku': str(sku), 'qty': qty}
        price = _number(dig(row, m.get('item_price')))
        if price is not None:
            item['price'] = price
        items.append(item)

    return {
        'external_id': external_id,
        'items': items,
        'customer': {
            'name': dig(payload, m.get('customer_name')) or '',
            'phone': dig(payload, m.get('customer_phone')) or '',
            'address': dig(payload, m.get('customer_address')) or '',
        },
    }


# ---------------------------------------------------------------------------
# Outbound: telling the platform what happened
# ---------------------------------------------------------------------------
#
# The inbound half above was the loud gap; this is the quiet one. Mezze pushed a
# status callback for exactly two moments — accepted and cancelled — in its own
# shape. Meanwhile the delivery moves through preparing, ready, assigned, out for
# delivery and delivered, and the platform hears none of it. For an aggregator
# order that is most of the point of integrating: their app is what the customer is
# staring at, and a restaurant that never reports "on its way" looks broken from the
# only screen the guest can see.
#
# Two things are configurable per channel and both have to be, because platforms
# disagree about each independently: WHAT a status is called, and WHERE in the body
# each field goes.

#: Mezze's own lifecycle, which is the delivery FSM's vocabulary.
STATUSES = ('accepted', 'preparing', 'ready', 'assigned', 'out_for_delivery',
            'delivered', 'cancelled', 'rejected')

#: The native outbound shape — again just the default row, not a special case.
NATIVE_STATUS = {
    'external_id': 'external_id',
    'status': 'status',
    'order_ref': 'pos_reference',
    'total': 'gross_total',
}


def place(body, path, value):
    """Write ``value`` at a dotted path, creating the dicts on the way.

    The inverse of :func:`dig`, and deliberately dict-only: a platform that wants a
    value inside an array is past what a mapping table should try to express, and
    saying so beats emitting something almost right.
    """
    if not path:
        return body
    parts = str(path).split('.')
    node = body
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value
    return body


def build_status(canonical, mapping=None, status_names=None):
    """Mezze's status -> the body this platform expects.

    ``status_names`` renames the status itself (``{'out_for_delivery': 'ON_THE_WAY'}``);
    ``mapping`` says where each field lands. A status with no name of its own is sent
    through unchanged rather than dropped: a platform receiving a word it does not
    know will say so, and that is a better failure than silence, which looks
    identical to a restaurant that never bothered.
    """
    m = dict(NATIVE_STATUS)
    m.update(mapping or {})
    names = dict(status_names or {})

    status = canonical.get('status') or ''
    body = {}
    place(body, m.get('external_id'), canonical.get('external_id') or '')
    place(body, m.get('status'), names.get(status, status))
    if canonical.get('pos_reference') is not None and m.get('order_ref'):
        place(body, m['order_ref'], canonical.get('pos_reference'))
    if canonical.get('gross_total') is not None and m.get('total'):
        place(body, m['total'], canonical.get('gross_total'))
    return body


def validate_status_mapping(mapping):
    """Refuse an outbound mapping that could never say anything useful."""
    if mapping in (None, {}, ''):
        return []
    if not isinstance(mapping, dict):
        return ['status mapping must be an object']
    problems = []
    for key in ('external_id', 'status'):
        value = mapping.get(key, NATIVE_STATUS[key])
        if not value or not isinstance(value, str):
            problems.append('%s must be a path' % key)
    unknown = sorted(set(mapping) - set(NATIVE_STATUS))
    if unknown:
        problems.append('unknown status mapping key(s): %s' % ', '.join(unknown))
    return problems


def validate_mapping(mapping):
    """Reject a mapping that could never produce an order.

    Checked when the channel is SAVED rather than when the first live order
    arrives, because the second one is somebody's dinner.
    """
    if mapping in (None, {}, ''):
        return []
    if not isinstance(mapping, dict):
        return ['mapping must be an object']
    problems = []
    for key in ('external_id', 'items', 'item_sku'):
        value = mapping.get(key, NATIVE[key])
        if not value or not isinstance(value, str):
            problems.append('%s must be a path' % key)
    unknown = sorted(set(mapping) - set(NATIVE))
    if unknown:
        problems.append('unknown mapping key(s): %s' % ', '.join(unknown))
    return problems
