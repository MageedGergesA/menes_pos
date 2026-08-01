"""Hermetic test base classes for the Mezze suite (RC2 / D-2).

Provides a self-provisioning fixture layer so the whole suite runs on a freshly
installed ``--without-demo=all`` database with NO manual business provisioning.

Base classes:
  * ``MezzeTransactionCase`` — light (no accounting chart); CORE / pure-domain tests.
  * ``MezzePosCase``         — POS/restaurant/omnichannel model tests (full chart via
                               ``AccountTestInvoicingCommon``).
  * ``MezzeHttpCase``        — real HTTP/controller tests needing POS + the chart.

A class declares ``fixture_profile`` (see ``profiles.py``) and optionally
``open_session_in_setup = True``. Expensive shared setup happens in ``setUpClass``;
per-method savepoints restore the intended starting state automatically.

Test-only. Never imported by production code or install hooks.
"""
from odoo.fields import Command
from odoo.tests import TransactionCase, HttpCase, tagged  # noqa: F401
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from . import factories, profiles
from .profiles import (C_ACCOUNTING, C_ADMIN, C_KDS, C_OMNICHANNEL, C_POS, C_RESTAURANT)


class MezzeFixtureMixin:
    """Provision a deterministic environment for the declared ``fixture_profile``."""

    fixture_profile = 'CORE'
    open_session_in_setup = False

    # ------------------------------------------------------------------ setup
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._mezze_components = profiles.resolve(cls.fixture_profile)
        cls._provision_fixture()
        cls._bind_fixture_aliases()
        cls._assert_fixture_integrity()

    @classmethod
    def _mezze_company(cls):
        # POS bases build a dedicated company via AccountTestInvoicingCommon.
        data = getattr(cls, 'company_data', None)
        return data['company'] if data else cls.env.company

    @classmethod
    def _mezze_accounts(cls):
        data = getattr(cls, 'company_data', None)
        if not data:
            return None
        return {
            'journal_cash': data['default_journal_cash'],
            'journal_bank': data['default_journal_bank'],
            'journal_sale': data['default_journal_sale'],
            'account_receivable': data['default_account_receivable'],
            'account_revenue': data['default_account_revenue'],
        }

    @classmethod
    def _provision_fixture(cls):
        comps = cls._mezze_components
        company = cls._mezze_company()
        cls.company = company
        cls.currency = company.currency_id
        # a company timezone (validator + scheduling correctness)
        if not company.partner_id.tz:
            company.partner_id.tz = 'Asia/Riyadh'
        # AccountTestInvoicingCommon provisions a DEDICATED company; the HTTP API runs
        # as base.user_admin and non-HTTP creates run as the test user. Grant both
        # membership in the fixture company so config-scoped (allowed_company_ids) writes
        # succeed — a standard multi-company TEST setup, not a production change.
        api_user = cls.env.ref('base.user_admin', raise_if_not_found=False)
        for u in (cls.env.user, api_user):
            if u and company not in u.company_ids:
                u.sudo().company_ids = [Command.link(company.id)]
        # the accounting test user lacks POS rights; grant them so factory creates work
        # as the test principal (mirrors core CommonPosTest) — POS profiles only.
        if C_POS in comps:
            pos_mgr = cls.env.ref('point_of_sale.group_pos_manager', raise_if_not_found=False)
            if pos_mgr:
                cls.env.user.sudo().group_ids = [Command.link(pos_mgr.id)]

        # base users always available (cheap)
        cls._fixture_users = factories.make_role_users(cls.env, company)

        if C_ACCOUNTING in comps and not cls._mezze_accounts():
            raise AssertionError(
                "fixture_profile %r needs accounting but this base has no company_data; "
                "use MezzePosCase / MezzeHttpCase." % cls.fixture_profile)

        if C_POS in comps:
            accounts = cls._mezze_accounts()
            cls._fixture_tax = factories.make_basic_tax(cls.env, company)
            cls._fixture_category = factories.make_pos_category(cls.env)
            cls._fixture_products = factories.make_products(cls.env, cls._fixture_category, tax=cls._fixture_tax)
            cls._fixture_pms = factories.make_payment_methods(cls.env, company, accounts)
            cls._fixture_pricelist = factories.make_pricelist(cls.env, company)
            cls._fixture_pos_config = factories.make_pos_config(
                cls.env, company, accounts, cls._fixture_pms['all'], cls._fixture_pricelist,
                restaurant=(C_RESTAURANT in comps))

        if C_RESTAURANT in comps:
            cls._fixture_restaurant = factories.make_floor_and_tables(cls.env, cls._fixture_pos_config)

        if C_OMNICHANNEL in comps:
            cls._fixture_aggregator = factories.make_aggregator(
                cls.env, cls._fixture_pos_config, cls._fixture_pms['card'], cls._fixture_products['plain'])

        if C_ADMIN in comps:
            # R-1: the 101-setting authoritative catalog is now materialised by the
            # MODULE INSTALL (data/settings_catalog_bootstrap.xml), so the fixture no
            # longer seeds it — it ASSERTS the module installed it. This keeps the suite
            # honest: if install regresses, admin/governance tests fail loudly.
            assert cls.env['mezze.setting.def'].sudo().search_count([]) > 0, \
                'settings catalog not installed by the module (R-1 regression)'

        if cls.open_session_in_setup and C_POS in comps:
            cls._open_session_for(cls._fixture_pos_config)

    @classmethod
    def _bind_fixture_aliases(cls):
        comps = cls._mezze_components
        u = getattr(cls, '_fixture_users', {})
        for role in ('host', 'server', 'cashier', 'kitchen', 'manager', 'admin', 'auditor'):
            setattr(cls, '%s_user' % role, u.get(role))
        if C_POS in comps:
            cls.pos_config = cls._fixture_pos_config
            cls.pricelist = cls._fixture_pricelist
            cls.pos_category = cls._fixture_category
            cls.products = cls._fixture_products['all']
            cls.product = cls._fixture_products['plain']
            cls.cash_payment_method = cls._fixture_pms['cash']
            cls.card_payment_method = cls._fixture_pms['card']
        if C_RESTAURANT in comps:
            cls.floor = cls._fixture_restaurant['floor']
            cls.tables = cls._fixture_restaurant['tables']
        if C_OMNICHANNEL in comps:
            cls.aggregator = cls._fixture_aggregator['channel']

    @classmethod
    def _assert_fixture_integrity(cls):
        comps = cls._mezze_components
        assert cls.company, 'fixture company missing'
        if C_POS in comps:
            cfg = cls.pos_config
            assert cfg.exists(), 'fixture POS config missing'
            assert cfg.company_id == cls.company, 'fixture POS not in fixture company'
            assert cfg.payment_method_ids, 'fixture POS has no payment methods'
            assert cfg.pricelist_id, 'fixture POS has no pricelist'
            assert cls.product.available_in_pos, 'fixture product not available in POS'

    # -------------------------------------------------------- session helpers
    @classmethod
    def _open_session_for(cls, config):
        """Create+open a session for THIS config only. Never touches other configs."""
        Session = cls.env['pos.session']
        sess = Session.search([('config_id', '=', config.id), ('state', '!=', 'closed')], limit=1)
        if not sess:
            sess = Session.with_context(allowed_company_ids=config.company_id.ids).create(
                {'config_id': config.id, 'user_id': cls.env.uid})
        if sess.state == 'opening_control':
            try:
                sess.set_opening_control(0, None)
            except Exception:  # noqa: BLE001 — opening control varies; state is enough for these tests
                pass
        return sess

    def assert_no_foreign_session(self, config=None):
        """No open session belongs to any config other than ``config`` (the fixture's)."""
        config = config or self.pos_config
        foreign = self.env['pos.session'].sudo().search(
            [('config_id', '!=', config.id), ('state', 'in', ('opening_control', 'opened', 'closing_control'))])
        assert not foreign, 'a foreign POS session is open: %s' % foreign.mapped('config_id.name')

    def open_test_session(self, config=None):
        """Return an OPEN session for the fixture config (creating one if needed)."""
        config = config or self.pos_config
        return self._open_session_for(config)

    def get_test_session(self, config=None):
        """Return the current non-closed session for the fixture config (may be empty)."""
        config = config or self.pos_config
        return self.env['pos.session'].sudo().search(
            [('config_id', '=', config.id), ('state', '!=', 'closed')], limit=1)

    def close_test_session(self, config=None):
        """Close ONLY the fixture config's session."""
        config = config or self.pos_config
        sess = self.get_test_session(config)
        if sess and sess.state != 'closed':
            sess.write({'state': 'closed'})
        return sess

    def create_order_in_test_session(self, product=None, qty=1, price=10.0, channel=None, session=None):
        """Create a draft pos.order in the fixture config's session (config-scoped)."""
        config = self.pos_config
        session = session or self.open_test_session(config)
        product = product or self.product
        vals = {
            'session_id': session.id, 'company_id': config.company_id.id,
            'lines': [(0, 0, {'product_id': product.id, 'qty': qty, 'price_unit': price,
                              'price_subtotal': price * qty, 'price_subtotal_incl': price * qty,
                              'tax_ids': [(6, 0, [])]})],
            'amount_total': price * qty, 'amount_paid': 0.0, 'amount_tax': 0.0, 'amount_return': 0.0,
            'pricelist_id': config.pricelist_id.id or False,
        }
        if channel:
            vals['mezze_channel'] = channel
        return self.env['pos.order'].sudo().create(vals)

    @classmethod
    def make_second_pos_config(cls, name='Mezze Test POS 2'):
        """A second, independent fixture-owned POS config for isolation tests.

        Gets its OWN cash/bank journals AND payment methods — a cash method cannot be
        shared across configs, and two cash methods cannot share one journal.
        """
        accounts = dict(cls._mezze_accounts())
        Journal = cls.env['account.journal']
        accounts['journal_cash'] = Journal.create({
            'name': 'Mezze Cash Journal 2', 'type': 'cash', 'code': 'MZC2',
            'company_id': cls.company.id})
        accounts['journal_bank'] = Journal.create({
            'name': 'Mezze Bank Journal 2', 'type': 'bank', 'code': 'MZB2',
            'company_id': cls.company.id})
        pms2 = factories.make_payment_methods(cls.env, cls.company, accounts, label='POS2')
        return factories.make_pos_config(
            cls.env, cls.company, accounts, pms2['all'], cls._fixture_pricelist, name=name)


# --------------------------------------------------------------------------- #
# concrete base classes
# --------------------------------------------------------------------------- #
class MezzeTransactionCase(MezzeFixtureMixin, TransactionCase):
    """Light base (no accounting chart). Use for CORE / pure-domain tests."""
    fixture_profile = 'CORE'


class MezzePosCase(MezzeFixtureMixin, AccountTestInvoicingCommon):
    """POS/restaurant/omnichannel model tests — full accounting chart + POS records."""
    fixture_profile = 'POS'


class MezzeHttpCase(MezzeFixtureMixin, AccountTestInvoicingCommon, HttpCase):
    """Real HTTP/controller tests needing POS + the accounting chart."""
    fixture_profile = 'POS'
