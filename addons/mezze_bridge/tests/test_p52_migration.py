"""Structural guard for the P5.2 webhook + hardware outbox adoption.

Detects reintroduction of an inline external call on a migrated path and
regression of the safety invariants (SSRF check, TLS verify, timeout, redirect
policy, credential-out-of-payload, print dedup, drawer expiry). Runs standalone
and under Odoo.
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def run_checks():
    f = []
    main = _read('controllers/main.py')
    aggr = _read('controllers/aggregator.py')
    cons = _read('models/outbox_consumers.py')

    # 1) the migrated aggregator outbound path has NO inline HTTP/socket
    if re.search(r'\brequests\.(get|post|put|patch|delete)\b', aggr):
        f.append(('aggregator_inline_http',))
    if re.search(r'\bsocket\.', aggr):
        f.append(('aggregator_inline_socket',))
    if '_publish_webhook' not in aggr:
        f.append(('aggregator_publication_missing',))

    # 2) order_pay hardware side effects are published, not inline
    for needle in ('_publish_receipt_print', '_publish_drawer_open', '_publish_pay_hardware'):
        if needle not in main:
            f.append(('main_missing', needle))
    if re.search(r'\bsocket\.create_connection', main) or re.search(r'\brequests\.post', main):
        f.append(('main_inline_external',))
    # credentials must NOT be resolved/placed in the publisher (server-side only)
    if 'channel.secret' in main or 'notify_url' in main:
        f.append(('credentials_in_publisher',))

    # 3) consumers registered
    for et in ("'integration.webhook.deliver.v1'", "'hardware.print.requested.v1'",
               "'hardware.drawer.open.requested.v1'"):
        if ('register_consumer(%s' % et) not in cons:
            f.append(('consumer_not_registered', et))

    # 4) webhook consumer safety invariants
    if 'verify=True' not in cons:
        f.append(('tls_verify_missing',))
    if 'verify=False' in cons:
        f.append(('tls_verify_disabled',))
    if 'timeout=' not in cons:
        f.append(('timeout_missing',))
    if 'allow_redirects=False' not in cons:
        f.append(('redirect_policy_missing',))
    if 'wh.check_url' not in cons and 'check_url(' not in cons:
        f.append(('ssrf_check_missing',))
    if 'ip_is_blocked' not in cons:
        f.append(('resolved_ip_check_missing',))
    # credentials resolved server-side at delivery
    if 'channel._secret()' not in cons or 'channel.notify_url' not in cons:
        f.append(('server_side_credential_resolution_missing',))

    # 5) hardware consumer safety invariants
    if '.claim(' not in cons:                 # print dedup ledger
        f.append(('print_dedup_missing',))
    if 'drawer_expiry' not in cons:           # stale drawer expiry
        f.append(('drawer_expiry_missing',))

    return f


if __name__ == '__main__':
    fails = run_checks()
    print("P5.2 webhook/hardware migration structural checks")
    print("  failures:", fails if fails else "none")
    print("RESULT:", "PASS" if not fails else "FAIL")
    raise SystemExit(0 if not fails else 1)


try:  # pragma: no cover
    from odoo.tests.common import TransactionCase, tagged

    @tagged("post_install", "-at_install", "mezze_invariants")
    class TestP52Migration(TransactionCase):
        def test_structural(self):
            self.assertEqual(run_checks(), [], "P5.2 migration structural checks failed")
except Exception:  # Odoo not present
    pass
