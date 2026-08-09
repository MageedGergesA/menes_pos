"""Mezze pilot preflight — READ-ONLY go-live + data-integrity check.

Run against a target database via Odoo's shell (never mutates any record):

    odoo-bin shell -c odoo.conf --addons-path=...,.../mezze/addons \
        -d <DB> --no-http < docs/pilot/mezze_preflight.py | tee preflight.out
    grep -q 'PREFLIGHT_RESULT: GO' preflight.out   # shell exit 0 == GO

It prints:
  * the go-live CONFIGURATION validator report (mezze.golive.validator.run)
  * the DATA-integrity report (mezze.golive.validator.integrity)
  * a compact financial snapshot (orders / payments by tender / open drafts)
and a final `PREFLIGHT_RESULT: GO|BLOCKED` line. BLOCKED if either the config
validator or the integrity validator reports an overall FAIL. Exposes no secrets.
"""
V = env['mezze.golive.validator']

print('=' * 72)
print(V.report_text('golive'))
print('=' * 72)
print(V.integrity_text())
print('=' * 72)

# compact, non-secret financial snapshot
Order = env['pos.order'].sudo()
Payment = env['pos.payment'].sudo()
completed = Order.search([('state', 'in', ('paid', 'done', 'invoiced'))])
drafts = Order.search([('state', '=', 'draft')])
gross = round(sum(completed.mapped('amount_total')), 2)
by_tender = {}
for p in Payment.search([('pos_order_id', 'in', completed.ids)]):
    m = p.payment_method_id.name or 'Unknown'
    by_tender[m] = round(by_tender.get(m, 0.0) + p.amount, 2)
print('FINANCIAL SNAPSHOT')
print('  completed orders : %d  (gross %.2f)' % (len(completed), gross))
print('  open drafts      : %d' % len(drafts))
print('  payments by tender:')
for m, amt in sorted(by_tender.items()):
    print('    %-20s %.2f' % (m, amt))
print('=' * 72)

cfg = V.run('golive')
integ = V.integrity()
blocked = cfg['overall'] == 'FAIL' or integ['overall'] == 'FAIL'
print('CONFIG overall  : %s (%d fail)' % (cfg['overall'], cfg['fails']))
print('INTEGRITY overall: %s (%d fail)' % (integ['overall'], integ['fails']))
print('PREFLIGHT_RESULT: %s' % ('BLOCKED' if blocked else 'GO'))
