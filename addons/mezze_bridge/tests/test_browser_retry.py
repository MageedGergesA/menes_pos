# -*- coding: utf-8 -*-
"""The one retry in this suite, and the fence around it.

``MezzeHttpCase.browser_js`` retries once when Chrome is launched but never answers
its first CDP request — the test dies in setup, before a line of its script runs,
and an orphaned Chrome is left for the harness to reap. It happened once in a full
run of this suite and never in isolation.

A retry is a mechanism for hiding real defects, so the interesting tests here are
the ones that prove it *does not* fire. The failure is injected rather than waited
for: a race seen once in ~1800 tests cannot be verified by running the suite again,
and "it passed" would be evidence of nothing.

What must hold:

* a pre-navigation timeout is retried, once, and the test then succeeds;
* a timeout on anything else is re-raised untouched — because once navigation has
  started the script may have run, and plenty of these tests are not idempotent;
* a failing assertion is never retried, no matter how it fails;
* a persistent failure still fails, rather than looping.
"""
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import HttpCase

from .common import MezzeHttpCase

#: A script that asserts nothing about the product — this file is about the harness.
TRIVIAL = "console.log('test successful');"


class _Boom:
    """Raises on the first call only, then gets out of the way."""

    def __init__(self, exc):
        self.exc = exc
        self.calls = 0

    def __call__(self, inner, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise self.exc
        return inner(*args, **kwargs)


@tagged('post_install', '-at_install', 'mezze_harness')
class TestBrowserRetry(MezzeHttpCase):
    fixture_profile = 'POS'

    def _with_first_call_failing(self, exc):
        """Patch HttpCase.browser_js so its FIRST invocation raises ``exc``."""
        boom = _Boom(exc)
        original = HttpCase.browser_js

        def wrapper(case_self, *args, **kwargs):
            return boom(lambda *a, **k: original(case_self, *a, **k), *args, **kwargs)

        return patch.object(HttpCase, 'browser_js', wrapper), boom

    # ── it fires where it should ─────────────────────────────────────────
    def test_01_a_launch_that_never_reached_the_page_is_retried(self):
        """THE case: Chrome came up, never answered, no script ran."""
        ctx, boom = self._with_first_call_failing(
            TimeoutError('Network.setCookie({"name": "test_request_key"})'))
        with ctx:
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(boom.calls, 2, 'the failed launch was not retried')

    def test_02_the_other_pre_navigation_calls_count_too(self):
        for method in ('Network.deleteCookies({})',
                       'Emulation.setCPUThrottlingRate({"rate": 1})'):
            with self.subTest(method=method):
                ctx, boom = self._with_first_call_failing(TimeoutError(method))
                with ctx:
                    self.browser_js('/mezze/pos', TRIVIAL, login='admin')
                self.assertEqual(boom.calls, 2, '%s was not retried' % method)

    # ── and, more importantly, not where it should not ───────────────────
    def test_10_a_timeout_after_navigation_is_never_retried(self):
        """The fence.

        Once the page is navigating the script may have run, and a good number of
        these tests are not idempotent — they advance a kitchen ticket, add a line,
        take a payment. Running one of those twice would be a worse bug than the
        flake the retry exists for.
        """
        ctx, boom = self._with_first_call_failing(
            TimeoutError('Page.navigate({"url": "/mezze/pos"})'))
        with ctx, self.assertRaises(TimeoutError):
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(boom.calls, 1, 'a post-navigation timeout was retried')

    def test_11_an_unknown_cdp_method_is_not_retried(self):
        # The list is a whitelist, not a blacklist: anything unrecognised is
        # assumed to have touched the page.
        ctx, boom = self._with_first_call_failing(
            TimeoutError('Runtime.evaluate({"expression": "1"})'))
        with ctx, self.assertRaises(TimeoutError):
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(boom.calls, 1)

    def test_12_a_failing_assertion_is_never_retried(self):
        """A test that genuinely fails must fail the first time and stay failed."""
        ctx, boom = self._with_first_call_failing(
            AssertionError('the test code failed'))
        with ctx, self.assertRaises(AssertionError):
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(boom.calls, 1, 'a real failure was retried away')

    def test_13_a_bare_timeout_with_no_method_is_not_retried(self):
        ctx, boom = self._with_first_call_failing(TimeoutError())
        with ctx, self.assertRaises(TimeoutError):
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(boom.calls, 1)

    def test_20_a_persistent_failure_still_fails(self):
        """Once, not until it passes. A machine that cannot start Chrome at all
        must produce a red test, not a loop."""
        calls = []
        original = HttpCase.browser_js

        def always_boom(case_self, *args, **kwargs):
            calls.append(1)
            raise TimeoutError('Network.setCookie({})')

        with patch.object(HttpCase, 'browser_js', always_boom):
            with self.assertRaises(TimeoutError):
                self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertEqual(len(calls), 2, 'retried more than once, or not at all')
        self.assertIsNotNone(original, 'the original was not lost')

    def test_21_the_retry_says_so_in_the_log(self):
        """A machine doing this constantly should be visible, not quietly slow."""
        ctx, _boom = self._with_first_call_failing(
            TimeoutError('Network.setCookie({})'))
        with ctx, self.assertLogs('odoo.addons.mezze_bridge.tests.common',
                                  level='WARNING') as logs:
            self.browser_js('/mezze/pos', TRIVIAL, login='admin')
        self.assertTrue(any('retrying once' in m for m in logs.output),
                        'the retry was silent: %r' % logs.output)
