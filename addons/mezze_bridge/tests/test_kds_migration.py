"""Structural guard for the P5 KDS/payment/refund adoption.

Detects reintroduction of a direct bus push on a migrated business-write path and
regression of the publications. Runs standalone (python3) and under Odoo.

Rule: the order write paths (fire / pay / refund, in controllers/*.py) must NEVER
call ``._broadcast()`` or push the KDS bus directly — they publish to the outbox
and the dispatcher's consumer performs the push after commit. The kitchen-side
``_broadcast`` in models/kds_ticket.py (action_advance / action_recall) is out of
scope for this migration and is allowed.
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_CTRL = os.path.join(_ROOT, 'controllers')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def run_checks():
    failures = []
    main = _read(os.path.join(_CTRL, 'main.py'))
    aggr = _read(os.path.join(_CTRL, 'aggregator.py'))
    consumers = _read(os.path.join(_ROOT, 'models', 'outbox_consumers.py'))

    # 1) no direct ticket broadcast on any migrated controller path
    for name, src in (('main.py', main), ('aggregator.py', aggr)):
        n = len(re.findall(r'\._broadcast\(\)', src))
        if n:
            failures.append(('direct_broadcast_reintroduced', name, n))
        # a direct KDS/waiter bus push in a controller would also bypass the outbox
        if re.search(r"_sendone\(\s*['\"]mezze_kds", src) or re.search(r"_sendone\([^)]*_kds_channel", src):
            failures.append(('direct_kds_sendone', name))

    # 2) the payment path publishes order.paid.v1
    if '_publish_order_paid' not in main or 'order.paid:%s' not in main:
        failures.append(('payment_publication_missing',))
    # 3) the refund path publishes order.refunded.v1
    if '_publish_order_refunded' not in main or 'order.refunded:%s' not in main:
        failures.append(('refund_publication_missing',))
    # 4) every migrated fire/pay path publishes KDS through the outbox (>=5 sites:
    #    counter-pay, table-fire, shop, delivery, aggregator)
    kds_calls = len(re.findall(r'_publish_kds\(', main)) + len(re.findall(r'_publish_kds\(', aggr))
    if kds_calls < 5:
        failures.append(('kds_publications_missing', kds_calls))
    # 5) the consumers are registered for the migrated event types
    for et in ("'mezze.bus.broadcast'", "'order.paid.v1'", "'order.refunded.v1'"):
        if ('register_consumer(%s' % et) not in consumers:
            failures.append(('consumer_not_registered', et))
    return failures


if __name__ == '__main__':
    fails = run_checks()
    print("KDS/payment/refund migration structural checks")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestKdsMigration(TransactionCase):
        def test_no_direct_broadcast_and_publications_present(self):
            self.assertEqual(run_checks(), [], "KDS migration structural checks failed")
except Exception:  # Odoo not present
    pass
