# -*- coding: utf-8 -*-
"""The first real payment-terminal adapter.

Mezze's terminal spine was finished and had nothing behind it — deliberately,
because the only alternative to "no adapter" was accepting a browser's claim that a
card had been approved, and a POS that can be told it was paid is not a POS.

The tests below are lopsided on purpose. Approved and declined are the easy half and
every integration gets them right. The half that costs restaurants money is
**uncertain**: the request left, the customer may have tapped, and no answer came
back. There are only three things a till can do about that — charge again (and
double-charge a guest), wave them through (and lose the money), or ASK. This adapter
asks, and these tests are mostly about the asking:

* the transaction's own durable ``request_id`` is the idempotency key, so asking
  again cannot become charging again;
* a transport failure is never a decline — from a socket, "I did not hear back" and
  "the card was refused" are identical, and they are opposite facts about a guest's
  money;
* an unrecognised failure code stays UNKNOWN rather than becoming a decline. A
  decline tells the cashier to try again, and if the first attempt did go through,
  the guest has now paid twice;
* when even the reconcile call fails, the attempt stays uncertain. That is the
  honest answer, and it is what the manager override exists for.

No live Stripe account has answered any of this. The provider is mocked at the HTTP
boundary, so what is proven is Mezze's half of the contract — the state machine, the
idempotency and the refusals — not the wire.
"""
import json

from odoo.tests import tagged

from .common import MezzeHttpCase
from ..domain import terminal_adapters as ta
from ..models import terminal_stripe


@tagged('post_install', '-at_install', 'mezze_terminal_adapter')
class TestAdapterMapping(MezzeHttpCase):
    """The mapping, with no Odoo and no network."""
    fixture_profile = 'POS'

    def test_01_money_becomes_an_integer_once(self):
        # Rounded here so the amount asked of the terminal and the amount written to
        # the bill share one rounding — half a cent between them is a reconciliation
        # nobody can close.
        self.assertEqual(ta.minor_units(12.34), 1234)
        self.assertEqual(ta.minor_units(0.1 + 0.2), 30)

    def test_02_the_intent_carries_our_own_id(self):
        body = ta.intent_payload(10.0, 'AED', 'mzt-abc', decimal_places=2)
        self.assertEqual(body['amount'], 1000)
        self.assertEqual(body['currency'], 'aed')
        self.assertEqual(body['metadata[mezze_request_id]'], 'mzt-abc')

    def test_03_a_real_decline_is_a_decline(self):
        self.assertEqual(ta.classify_error('insufficient_funds'), ta.DECLINED)
        self.assertEqual(ta.classify_error('expired_card'), ta.DECLINED)

    def test_04_an_unknown_code_is_not_a_decline(self):
        # THE rule. A decline tells a cashier to charge again.
        self.assertEqual(ta.classify_error('some_code_from_2029'), ta.UNKNOWN)

    def test_05_a_reader_that_was_never_reached_is_harmless(self):
        # No charge can exist, so the order simply stays payable.
        self.assertEqual(ta.classify_error('terminal_reader_offline'), ta.CANCELLED)

    def test_06_the_intent_is_the_money_truth(self):
        self.assertEqual(ta.state_from_intent({'status': 'succeeded'}), ta.APPROVED)
        self.assertEqual(ta.state_from_intent({'status': 'canceled'}), ta.CANCELLED)
        self.assertEqual(ta.state_from_intent({'status': 'processing'}), ta.PROCESSING)

    def test_07_an_intent_nobody_recognises_is_unknown(self):
        self.assertEqual(ta.state_from_intent({'status': 'invented'}), ta.UNKNOWN)
        self.assertEqual(ta.state_from_intent(None), ta.UNKNOWN)

    def test_08_the_receipt_label_carries_a_brand_not_a_card(self):
        label = ta.card_of({'charges': {'data': [{'payment_method_details': {
            'card_present': {'brand': 'visa', 'last4': '4242'}}}]}})
        self.assertEqual(label, 'VISA 4242')

    def test_09_an_unsupported_provider_is_still_unsupported(self):
        self.assertFalse(ta.supported('some_acquirer'))
        self.assertTrue(ta.supported(ta.STRIPE))


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if self._payload is _BAD_JSON:
            raise ValueError('not json')
        return self._payload


_BAD_JSON = object()


class _FakeStripe:
    """Scripted Stripe. Records every call so idempotency can be asserted."""

    def __init__(self):
        self.calls = []
        self.script = {}
        self.default = _Resp({})

    def _answer(self, method, url, headers):
        self.calls.append({'method': method, 'url': url,
                           'idem': (headers or {}).get('Idempotency-Key')})
        # Longest fragment first: '/v1/payment_intents' is a prefix of
        # '/v1/payment_intents/pi_7', and matching the general one first would send
        # the create response back for a lookup — a bug in the fake that reads
        # exactly like a bug in the adapter.
        for fragment in sorted(self.script, key=len, reverse=True):
            reply = self.script[fragment]
            if fragment in url:
                if isinstance(reply, list):
                    return reply.pop(0) if len(reply) > 1 else reply[0]
                if isinstance(reply, Exception):
                    raise reply
                return reply
        return self.default

    def post(self, url, data=None, headers=None, timeout=None):
        return self._answer('POST', url, headers)

    def get(self, url, headers=None, timeout=None):
        return self._answer('GET', url, headers)


@tagged('post_install', '-at_install', 'mezze_terminal_adapter')
class TestStripeTerminal(MezzeHttpCase):
    fixture_profile = 'POS'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.pos_sess = cls._open_session_for(cls.pos_config)
        cls.method = cls.pos_config.payment_method_ids.filtered(
            lambda m: not m.is_cash_count)[:1]
        if not cls.method:
            cls.method = env['pos.payment.method'].sudo().create({
                'name': 'ST Card', 'company_id': cls.pos_config.company_id.id})
            cls.pos_config.sudo().write({'payment_method_ids': [(4, cls.method.id)]})
        cls.device = env['mezze.payment.device'].sudo().create({
            'name': 'Counter Reader', 'code': 'ST-READER-1',
            'config_id': cls.pos_config.id, 'mode': 'odoo_terminal',
            'integration_type': 'odoo_terminal',
            'provider_adapter': 'stripe_terminal',
            'provider_reader_id': 'tmr_simulated'})
        cls.device.set_provider_secret('sk_test_notarealkey')
        env.flush_all()

    def setUp(self):
        super().setUp()
        self.stripe = _FakeStripe()
        self._orig = terminal_stripe.requests
        terminal_stripe.requests = self.stripe
        self.addCleanup(self._restore)

    def _restore(self):
        terminal_stripe.requests = self._orig

    def _order(self, total=25.0):
        order = self.env['pos.order'].sudo().create({
            'session_id': self.pos_sess.id,
            'company_id': self.pos_config.company_id.id,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1,
                              'price_unit': total, 'price_subtotal': total,
                              'price_subtotal_incl': total, 'tax_ids': [(6, 0, [])]})],
            'amount_total': total, 'amount_paid': 0.0, 'amount_tax': 0.0,
            'amount_return': 0.0})
        self.env.flush_all()
        return order

    def _txn(self, total=25.0):
        order = self._order(total)
        return self.env['mezze.terminal.transaction'].sudo().mezze_start(
            order, self.method, self.device, total, 'stripe_terminal')

    def _paid(self, txn):
        txn.pos_order_id.invalidate_recordset()
        return sum(txn.pos_order_id.payment_ids.mapped('amount'))

    # ── the easy half ────────────────────────────────────────────────────
    def test_20_an_approved_card_becomes_exactly_one_payment(self):
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_1', 'status': 'succeeded'}),
            'process_payment_intent': _Resp({'id': 'tmr_simulated'}),
            '/v1/terminal/readers/': _Resp(
                {'action': {'status': 'succeeded'}}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'approved', txn.error_code)
        self.assertFalse(txn.uncertain)
        self.assertEqual(self._paid(txn), 25.0)

    def test_21_a_declined_card_takes_no_money(self):
        self.stripe.script = {
            '/v1/payment_intents/pi_2': _Resp({
                'id': 'pi_2', 'status': 'requires_payment_method',
                'last_payment_error': {'decline_code': 'card_declined'}}),
            '/v1/payment_intents': _Resp({'id': 'pi_2',
                                          'status': 'requires_confirmation'}),
            'process_payment_intent': _Resp({'id': 'tmr_simulated'}),
            '/v1/terminal/readers/': _Resp({'action': {
                'status': 'failed', 'failure_code': 'card_declined'}}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'declined')
        self.assertFalse(txn.uncertain)
        self.assertEqual(self._paid(txn), 0.0)

    # ── the half that costs money ────────────────────────────────────────
    def test_30_the_request_id_is_the_idempotency_key(self):
        # What makes asking again safe instead of charging again.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_3', 'status': 'succeeded'}),
            'process_payment_intent': _Resp({'id': 'tmr_simulated'}),
            '/v1/terminal/readers/': _Resp({'action': {'status': 'succeeded'}}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        create = [c for c in self.stripe.calls
                  if c['url'].endswith('/v1/payment_intents')]
        self.assertTrue(create, 'no intent was created')
        self.assertEqual(create[0]['idem'], txn.request_id,
                         'the create call was not idempotent on our own id')

    def test_31_a_transport_failure_is_not_a_decline(self):
        # From a socket these look the same and they are opposite facts.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_4', 'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertNotEqual(txn.state, 'declined',
                            'a lost connection was reported as a refused card')

    def test_32_a_lost_answer_is_resolved_by_asking(self):
        # The whole reason this adapter is shaped the way it is: the customer tapped,
        # the answer never came back, and the money is knowable.
        self.stripe.script = {
            '/v1/payment_intents/pi_5': _Resp({'id': 'pi_5', 'status': 'succeeded'}),
            '/v1/payment_intents': _Resp({'id': 'pi_5', 'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'approved',
                         'a payment that HAD gone through was not recovered')
        self.assertEqual(self._paid(txn), 25.0)
        self.assertFalse(txn.uncertain)

    def test_33_asking_finds_out_it_was_declined_too(self):
        self.stripe.script = {
            '/v1/payment_intents/pi_6': _Resp({
                'id': 'pi_6', 'status': 'requires_payment_method',
                'last_payment_error': {'decline_code': 'insufficient_funds'}}),
            '/v1/payment_intents': _Resp({'id': 'pi_6', 'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'declined')
        self.assertEqual(txn.error_code, 'insufficient_funds')
        self.assertEqual(self._paid(txn), 0.0)

    def test_34_when_even_asking_fails_it_stays_uncertain(self):
        # The honest answer, and what the manager override exists for.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_7', 'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
            '/v1/payment_intents/pi_7': OSError('still down'),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertTrue(txn.uncertain, 'an unknowable payment was reported as settled')
        self.assertEqual(txn.error_code, 'reconcile_failed')
        self.assertEqual(self._paid(txn), 0.0, 'money was booked on a guess')

    def test_35_an_intent_nobody_presented_a_card_to_is_not_a_decline(self):
        # A brand-new PaymentIntent and a refused one share a status. Reading the
        # first as a decline would report a refusal for an attempt that never
        # happened — and it is reachable, because the reconcile path can create an
        # intent it has never used.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_7b',
                                          'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
            '/v1/payment_intents/pi_7b': _Resp({'id': 'pi_7b',
                                                'status': 'requires_payment_method'}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'cancelled')
        self.assertEqual(txn.error_code, 'not_started')
        self.assertFalse(txn.uncertain)
        self.assertEqual(self._paid(txn), 0.0)

    def test_35b_a_reference_lost_mid_flight_is_recovered_by_the_key(self):
        # The process died between creating the intent and writing it down. Asking
        # again under the same idempotency key returns the ORIGINAL intent, so the
        # answer is authoritative and only one intent has ever existed.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_lost', 'status': 'succeeded'}),
        }
        txn = self._txn()
        txn.sudo().write({'provider_reference': False})
        txn.mezze_stripe_reconcile()
        self.assertEqual(txn.state, 'approved',
                         'a payment with no stored reference was written off')
        self.assertEqual(self._paid(txn), 25.0)
        creates = [c for c in self.stripe.calls
                   if c['url'].endswith('/v1/payment_intents')]
        self.assertTrue(creates and creates[-1]['idem'] == txn.request_id,
                        'the recovery call was not idempotent')

    def test_35c_a_provider_that_cannot_be_reached_at_all_stays_uncertain(self):
        self.stripe.script = {'/v1/payment_intents': OSError('down before we began')}
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertTrue(txn.uncertain)
        self.assertEqual(self._paid(txn), 0.0)

    def test_36_a_payment_still_live_is_not_force_done_eligible(self):
        # Overriding a payment that is about to succeed on its own is how a bill gets
        # paid twice by two different mechanisms.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_8', 'status': 'requires_confirmation'}),
            'process_payment_intent': OSError('connection reset'),
            '/v1/payment_intents/pi_8': _Resp({'id': 'pi_8', 'status': 'processing'}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(txn.state, 'processing')
        self.assertFalse(txn.uncertain)

    def test_37_a_retry_of_an_already_paid_attempt_pays_once(self):
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_9', 'status': 'succeeded'}),
            'process_payment_intent': _Resp({'id': 'tmr_simulated'}),
            '/v1/terminal/readers/': _Resp({'action': {'status': 'succeeded'}}),
            '/v1/payment_intents/pi_9': _Resp({'id': 'pi_9', 'status': 'succeeded'}),
        }
        txn = self._txn()
        txn.mezze_stripe_run()
        txn.mezze_stripe_run()
        txn.mezze_stripe_run()
        self.assertEqual(self._paid(txn), 25.0, 'the guest was charged more than once')

    # ── the browser still cannot mint a payment ──────────────────────────
    def test_40_a_client_claim_of_success_is_recorded_not_obeyed(self):
        # The invariant the whole model exists for, now that a real provider is
        # behind it: the till may say what it saw on the customer's screen, and the
        # provider says what was charged.
        self.stripe.script = {
            '/v1/payment_intents': _Resp({'id': 'pi_10', 'status': 'requires_confirmation'}),
            '/v1/payment_intents/pi_10': _Resp({
                'id': 'pi_10', 'status': 'requires_payment_method',
                'last_payment_error': {'decline_code': 'card_declined'}}),
        }
        txn = self._txn()
        txn.sudo().write({'provider_reference': 'pi_10'})
        txn.mezze_apply_result(claimed_outcome='approved')
        self.assertEqual(txn.state, 'declined',
                         'the browser talked the server into a payment')
        self.assertEqual(self._paid(txn), 0.0)

    def test_41_a_provider_with_no_adapter_is_still_refused(self):
        from odoo.exceptions import UserError
        self.device.sudo().write({'provider_adapter': False})
        txn = self._txn()
        with self.assertRaises(UserError):
            txn.mezze_apply_result(claimed_outcome='approved')
        self.assertEqual(self._paid(txn), 0.0)

    def test_42_a_device_with_no_key_takes_no_payment(self):
        self.device.sudo().write({'provider_secret_enc': False})
        txn = self._txn()
        txn.mezze_stripe_run()
        self.assertEqual(self._paid(txn), 0.0)
        self.assertNotEqual(txn.state, 'approved')

    def test_43_the_api_key_is_not_stored_in_plaintext(self):
        self.env.cr.execute(
            "SELECT provider_secret_enc FROM mezze_payment_device WHERE id = %s",
            (self.device.id,))
        stored = self.env.cr.fetchone()[0] or ''
        self.assertNotIn('sk_test_notarealkey', stored,
                         'the provider key is readable in the database')
        self.assertEqual(self.device._provider_secret(), 'sk_test_notarealkey')
