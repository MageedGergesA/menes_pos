"""P6.2 Phase 1 — explicit target-scope classification for EVERY protected route.

Each protected endpoint is classified exactly once, with a written policy, so no
protected route has ambiguous target scope. The structural test asserts the
registry covers exactly the protected routes in domain.authz.ENDPOINT_CAPABILITY.

Categories:
  A  target-record scoped  — operates on ONE durable business record (needs a
                             resolver: (target_model, id_param))
  B  collection scoped     — lists / searches / aggregates / reports / exports;
                             the query MUST start from the principal's authoritative
                             scope (branch/company), client filters only narrow it
  C  configuration scoped  — reads/writes config at company/branch/terminal/
                             integration scope; writes MUST use a field allowlist
  D  principal-self scoped — operates only on the authenticated principal's own
                             state (its cashier/terminal), no tenant target id
  E  scope-free protected  — genuinely no tenant-owned target (justified)

For Category A the tuple is (A, target_model, id_param).  For B/C/D/E it is a
1-tuple (category,) plus a short justification in ROUTE_NOTES.
"""

A, B, C, D, E = 'A', 'B', 'C', 'D', 'E'

# eid -> (category[, target_model, id_param])
ROUTE_SCOPE = {
    # ---- A: target-record ---------------------------------------------------
    'orders/pay':            (A, 'pos.order', 'order_or_uuid'),
    # S2C-3 integrated terminal — all scoped to the transaction's pos.order (start
    # resolves by uuid/order_id; complete/cancel/status/force_done resolve the order
    # via the durable request_id). Controllers pass target_order explicitly.
    'terminal/start':        (A, 'pos.order', 'order_or_uuid'),
    'terminal/complete':     (A, 'pos.order', 'request_id'),
    'terminal/cancel':       (A, 'pos.order', 'request_id'),
    'terminal/status':       (A, 'pos.order', 'request_id'),
    'terminal/force_done':   (A, 'pos.order', 'request_id'),
    # S2C-4 bank-app QR — generate resolves by uuid/order_id; confirm/cancel/status
    # resolve the order via the QR token. Controllers pass target_order explicitly.
    # S2C-7 cash machine — start resolves by uuid/order_id; complete/cancel/status/
    # force_done resolve the order via the durable request_id (target passed explicitly).
    'cashmachine/start':     (A, 'pos.order', 'order_or_uuid'),
    'cashmachine/complete':  (A, 'pos.order', 'request_id'),
    'cashmachine/cancel':    (A, 'pos.order', 'request_id'),
    'cashmachine/status':    (A, 'pos.order', 'request_id'),
    'cashmachine/force_done': (A, 'pos.order', 'request_id'),
    'payment/qr/generate':   (A, 'pos.order', 'order_or_uuid'),
    'payment/qr/confirm':    (A, 'pos.order', 'token'),
    'payment/qr/cancel':     (A, 'pos.order', 'token'),
    'payment/qr/status':     (A, 'pos.order', 'token'),
    # S2C-6 customer account — summary/deposit/settle act on ONE customer partner.
    'customer/summary':      (A, 'res.partner', 'partner_id'),
    'customer/deposit':      (A, 'res.partner', 'partner_id'),
    'customer/settle':       (A, 'res.partner', 'partner_id'),
    'orders/refund':         (A, 'pos.order', 'original_order_id'),
    'orders/comp':           (A, 'pos.order', 'order_or_uuid'),
    'orders/fire':           (A, 'pos.order', 'uuid'),
    'orders/get':            (A, 'pos.order', 'order_or_uuid'),
    'orders/exchange':       (A, 'pos.order', 'original_order_id'),
    'orders/sync':           (A, 'pos.order', 'uuid'),
    'orders/recent':         (A, 'pos.session', 'session_id'),
    'courses/fire':          (A, 'restaurant.table', 'table_id'),
    'courses/hold':          (A, 'restaurant.table', 'table_id'),
    'courses/board':         (A, 'restaurant.table', 'table_id'),
    'tables/merge':          (A, 'pos.session', 'session_id'),
    'tables/transfer':       (A, 'pos.session', 'session_id'),
    'print/receipt':         (A, 'pos.order', 'order_or_uuid'),
    'print/kitchen':         (A, 'pos.order', 'order_or_uuid'),
    'drawer/open':           (A, 'mezze.printer', 'printer_id'),
    'einvoice/submit':       (A, 'pos.order', 'order_id'),
    'einvoice/status':       (A, 'pos.order', 'order_uuid'),
    'sessions/<int:session_id>/close': (A, 'pos.session', 'session_id'),
    'reservations/state':    (A, 'mezze.reservation', 'reservation_id'),
    'waitlist/state':        (A, 'restaurant.table', 'table_id'),
    'kds/transition':        (A, 'mezze.kds.ticket', 'ticket_id'),
    'delivery/create':       (A, 'pos.session', 'session_id'),
    'delivery/state':        (A, 'mezze.delivery', 'delivery_id'),
    'drivethru/create':      (A, 'pos.session', 'session_id'),
    'drivethru/stage':       (A, 'pos.order', 'uuid'),
    'giftcard/issue':        (A, 'res.partner', 'partner_id'),
    'loyalty/redeem':        (A, 'res.partner', 'partner_id'),
    'promo/apply':           (A, 'pos.order', 'uuid'),
    'reservations/create':   (A, 'pos.config', 'config_id'),
    'waitlist/add':          (A, 'pos.config', 'config_id'),
    'payment/void':          (A, 'pos.order', 'order_id'),
    'payment/intent':        (A, 'pos.config', 'config_id'),
    'reversals/resolve':     (A, 'pos.order', 'reversal_id'),
    # ---- B: collection / report / list -------------------------------------
    'reports/summary': (B,), 'gl/summary': (B,), 'gl/sessions': (B,),
    'gl/export.csv': (B,), 'reports/refunds.csv': (B,), 'reversals': (B,),
    'branches': (B,), 'delivery/list': (B,), 'delivery/zones': (B,),
    'feedback/list': (B,), 'floors': (B,), 'reservations/list': (B,),
    'reservations/availability': (B,), 'waitlist/list': (B,), 'waste/list': (B,),
    'waste/products': (B,), 'promo/list': (B,), 'marketing/campaigns': (B,),
    'marketing/segments': (B,), 'loyalty/search': (B,), 'hq/summary': (B,),
    'ops/summary': (B,), 'manager/dashboard': (B,), 'clock/list': (B,),
    'customer/search': (B,),
    'ck/board': (B,), 'bds/queue': (B,), 'drivethru/board': (B,), 'kds/state': (B,),
    'orders/kds': (B,), 'payment/methods': (B,), 'payment/status': (B,),
    'menu/quickkeys': (B,), 'giftcard/balance': (B,), 'audit/log': (B,),
    'delivery/zones': (B,), 'feedback/list': (B,), 'promo/list': (B,),
    'reconcile': (B,), 'orders/kds': (B,), 'ai/upsell': (B,),
    # S2 payment reconciliation / external-refund (branch-scoped via principal)
    'reconciliation/settlement': (B,), 'reconciliation/finalize': (B,),
    'payment/external_refund/confirm': (B,),
    # ---- C: configuration ---------------------------------------------------
    'config/tax': (C,), 'printers': (C,), 'register': (C,), 'pull': (C,),
    'push': (C,), 'delivery/zone/save': (C,), 'marketing/send': (C,),
    'menu/eightysix': (C,), 'test': (C,),
    # ---- D: principal-self --------------------------------------------------
    'clock/toggle': (D,), 'approve': (D,),
    # D1 design platform — a principal reads/writes only its OWN effective settings
    'settings/effective': (D,), 'settings/save': (D,), 'settings/reset': (D,),
    # D1 admin console — configuration administration (validated setting keys +
    # policy enum only; never a raw client dict into create/write)
    'admin/templates': (C,), 'admin/assignments': (C,), 'admin/locks': (C,),
    'admin/permissions': (C,), 'admin/audit': (C,), 'admin/template/create': (C,),
    'admin/template/duplicate': (C,), 'admin/template/publish': (C,),
    'admin/template/archive': (C,), 'admin/lock': (C,), 'admin/assign': (C,),
    # ---- E: scope-free protected operation ---------------------------------
    'ck/produce': (E,), 'ck/receive': (E,), 'ck/request': (E,), 'ck/dispatch': (E,),
    'drivethru/stage': (A, 'pos.order', 'uuid'),  # (kept as A above)
    'bus/poll': (E,), 'waste/log': (C,),
}

ROUTE_NOTES = {
    'B': "collection queries begin from the principal's authoritative branch/company "
         "scope; client params only narrow (never widen) it; export routes need a "
         "separate reports.export capability.",
    'C': "configuration writes use an explicit field allowlist; company/branch/"
         "terminal reassignment and credential/security fields are rejected.",
    'D': "operates on the caller's own cashier/terminal state only (approval verifies "
         "the approver's own PIN; clock toggles the caller's attendance).",
    'E': "central-kitchen production/bus-poll operations with no single tenant-owned "
         "target record; still authn + capability gated.",
}

CATEGORY_A = frozenset(e for e, v in ROUTE_SCOPE.items() if v[0] == A)

# Category-A routes with authoritative object authorization WIRED into the gate
# (target-record scope enforced before business logic). The structural test
# asserts each of these calls _security_gate with a target/target_order. The
# remaining Category-A routes are classified but object-scope wiring is pending
# (tracked honestly, not silently).
OBJECT_SCOPED = frozenset({
    'orders/pay', 'orders/refund', 'orders/comp', 'orders/fire',      # money (target_order)
    'print/receipt', 'print/kitchen', 'drawer/open',                  # hardware (target=order/printer)
    'sessions/<int:session_id>/close',                                # session (target=session)
})


def classify(eid):
    return ROUTE_SCOPE.get(eid)


def is_target_record(eid):
    v = ROUTE_SCOPE.get(eid)
    return bool(v) and v[0] == A


def target_of(eid):
    """(model, id_param) for a Category A route, else None."""
    v = ROUTE_SCOPE.get(eid)
    return (v[1], v[2]) if v and v[0] == A else None
