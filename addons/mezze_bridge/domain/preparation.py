"""The shape native POS expects in ``pos.order.last_order_preparation_change``.

Mezze wrote the string ``'{}'`` for this field on every order it created. That
reads as "nothing has been sent to the kitchen yet", and server-side it behaves
exactly that way — ``_ensure_to_keep_last_preparation_change`` calls
``json.loads`` and finds no ``metadata``, so it leaves the record alone.

The native POS CLIENT is stricter. ``pos_order.js`` treats a FALSY value as
"absent" and builds the full default itself, but ``'{}'`` is truthy, so it takes
the parse branch instead and stores a bare ``{}`` — an object with no ``lines``
key. ``getOrderChanges`` then reads ``order.last_order_preparation_change.lines``
and hands ``undefined`` to ``Object.entries``:

    TypeError: Cannot convert undefined or null to object
        at getOrderChanges
        at FloorScreen.getChangeCount

The floor screen calls that for every table on render, so ONE Mezze order was
enough to stop the native register from opening at all — and because native POS
caches loaded orders in IndexedDB, cancelling the order server-side did not clear
it from a browser that had already read it.

Writing the same structure native writes costs nothing and keeps both clients
able to read each other's orders. It is deliberately the literal native default
(``point_of_sale/static/src/app/models/pos_order.js``), not an approximation.
"""
import json

# Keep the key order and the values identical to the native client default.
PREPARATION_DEFAULT = {
    'lines': {},
    'metadata': {},
    'general_customer_note': '',
    'internal_note': '',
    'sittingMode': 0,
}


def empty_preparation_change():
    """Serialized "nothing fired yet", in the shape both clients can read.

    Returns a fresh string each call: this goes into ORM write payloads, and a
    shared mutable default is how two orders end up pointing at one dict.
    """
    return json.dumps(PREPARATION_DEFAULT)
