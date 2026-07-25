"""Hermetic test fixture FACTORIES for the Mezze suite (RC2 / D-2).

Focused, composable record factories. Each factory:
  * creates ONLY what it is asked for,
  * uses deterministic test names,
  * scopes to an explicit company,
  * never searches globally for "some" record,
  * returns the created records explicitly,
  * uses test-only secrets, performs no network calls,
  * is safe under the test transaction (no commit).

Accounting records (journals/accounts) are supplied by the caller from
``AccountTestInvoicingCommon.company_data`` — factories never guess them.

Test-only. Never imported by production code or install hooks.
"""
from odoo.fields import Command

# Deterministic, test-only secrets (never production credentials).
TEST_AGG_SECRET = 'mezze-test-aggregator-secret'
TEST_QR_SECRET = 'mezze-test-qr-signing-secret'


# --------------------------------------------------------------------------- #
# products / menu
# --------------------------------------------------------------------------- #
def make_pos_category(env, name='Mezze Test Menu'):
    return env['pos.category'].create({'name': name})


def make_products(env, category, tax=None):
    """A deterministic minimal menu covering the cases the suite exercises."""
    Tmpl = env['product.product']
    tax_cmd = [Command.set(tax.ids)] if tax else [Command.clear()]
    common = {'available_in_pos': True, 'type': 'consu', 'pos_categ_ids': [Command.set(category.ids)]}
    plain = Tmpl.create({'name': 'Mezze Plain', 'list_price': 10.0, 'taxes_id': [Command.clear()], **common})
    taxed = Tmpl.create({'name': 'Mezze Taxed', 'list_price': 20.0, 'taxes_id': tax_cmd, **common})
    modifier = Tmpl.create({'name': 'Mezze Modifiable', 'list_price': 15.0, 'taxes_id': [Command.clear()], **common})
    kitchen = Tmpl.create({'name': 'Mezze Kitchen Dish', 'list_price': 25.0, 'taxes_id': [Command.clear()], **common})
    unavailable = Tmpl.create({'name': 'Mezze 86 Item', 'list_price': 12.0,
                               'taxes_id': [Command.clear()], 'type': 'consu',
                               'available_in_pos': True, 'pos_categ_ids': [Command.set(category.ids)]})
    return {'plain': plain, 'taxed': taxed, 'modifier': modifier,
            'kitchen': kitchen, 'unavailable': unavailable,
            'all': plain + taxed + modifier + kitchen + unavailable}


def make_basic_tax(env, company, amount=10.0):
    return env['account.tax'].create({
        'name': 'Mezze Test VAT %g' % amount, 'amount': amount, 'amount_type': 'percent',
        'type_tax_use': 'sale', 'company_id': company.id})


# --------------------------------------------------------------------------- #
# payment methods
# --------------------------------------------------------------------------- #
def make_payment_methods(env, company, accounts, label=''):
    """Cash + card(bank) + split-capable credit, wired to the supplied journals/accounts.

    A cash payment method may only belong to ONE pos.config, so each config that needs
    its own methods must call this with a distinct ``label`` (never share a cash method).
    """
    PM = env['pos.payment.method']
    sfx = (' ' + label) if label else ''
    cash = PM.create({
        'name': 'Mezze Cash' + sfx, 'company_id': company.id,
        'journal_id': accounts['journal_cash'].id,
        'receivable_account_id': accounts['account_receivable'].id})
    card = PM.create({
        'name': 'Mezze Card' + sfx, 'company_id': company.id,
        'journal_id': accounts['journal_bank'].id,
        'receivable_account_id': accounts['account_receivable'].id})
    credit = PM.create({
        'name': 'Mezze Credit' + sfx, 'company_id': company.id,
        'receivable_account_id': accounts['account_receivable'].id,
        'split_transactions': True})
    return {'cash': cash, 'card': card, 'credit': credit, 'all': cash + card + credit}


# --------------------------------------------------------------------------- #
# POS config
# --------------------------------------------------------------------------- #
def make_pricelist(env, company, name='Mezze Test Pricelist'):
    return env['product.pricelist'].create({
        'name': name, 'company_id': company.id, 'currency_id': company.currency_id.id})


def make_pos_config(env, company, accounts, payment_methods, pricelist, name='Mezze Test POS',
                    restaurant=False):
    vals = {
        'name': name, 'company_id': company.id,
        'journal_id': accounts['journal_sale'].id,
        'invoice_journal_id': accounts['journal_sale'].id,
        'payment_method_ids': [Command.set(payment_methods.ids)],
        'use_pricelist': True,
        'available_pricelist_ids': [Command.set(pricelist.ids)],
        'pricelist_id': pricelist.id,
    }
    if restaurant:
        vals['module_pos_restaurant'] = True
    return env['pos.config'].create(vals)


# --------------------------------------------------------------------------- #
# restaurant floors / tables
# --------------------------------------------------------------------------- #
def make_floor_and_tables(env, config, n_tables=3, floor_name='Mezze Main Floor'):
    floor = env['restaurant.floor'].create({
        'name': floor_name, 'pos_config_ids': [Command.set(config.ids)]})
    tables = env['restaurant.table']
    for i in range(1, n_tables + 1):
        tables |= env['restaurant.table'].create({
            'table_number': i, 'floor_id': floor.id, 'seats': 2 + i})
    return {'floor': floor, 'tables': tables}


# --------------------------------------------------------------------------- #
# users / roles
# --------------------------------------------------------------------------- #
_ROLE_LOGINS = {
    'host': 'mezze_host', 'server': 'mezze_server', 'cashier': 'mezze_cashier',
    'kitchen': 'mezze_kitchen', 'manager': 'mezze_manager', 'admin': 'mezze_admin',
    'auditor': 'mezze_auditor',
}


def make_role_users(env, company, roles=None):
    """Create deterministic role users, each with a unique login + test password."""
    roles = roles or list(_ROLE_LOGINS)
    Users = env['res.users'].with_context(no_reset_password=True)
    pos_user_group = env.ref('base.group_user')
    pos_manager = env.ref('point_of_sale.group_pos_manager', raise_if_not_found=False)
    pos_user = env.ref('point_of_sale.group_pos_user', raise_if_not_found=False)
    out = {}
    for role in roles:
        login = _ROLE_LOGINS[role]
        groups = pos_user_group
        if role in ('manager', 'admin') and pos_manager:
            groups |= pos_manager
        elif pos_user:
            groups |= pos_user
        out[role] = Users.create({
            'name': 'Mezze %s' % role.capitalize(), 'login': login, 'password': login + '-pw-Test1',
            'company_id': company.id, 'company_ids': [Command.set(company.ids)],
            'group_ids': [Command.set(groups.ids)]})
    return out


# --------------------------------------------------------------------------- #
# omnichannel: aggregator, QR
# --------------------------------------------------------------------------- #
def make_aggregator(env, config, payment_method, product, code='mezzeats', name='MezzeEats'):
    chan = env['mezze.aggregator'].create({
        'code': code, 'name': name, 'config_id': config.id,
        'payment_method_id': payment_method.id, 'secret': TEST_AGG_SECRET, 'active': True})
    pmap = env['mezze.aggregator.product.map'].create({
        'aggregator_id': chan.id, 'external_sku': 'MZ-SKU-1', 'product_id': product.id})
    return {'channel': chan, 'product_map': pmap, 'secret': TEST_AGG_SECRET}
