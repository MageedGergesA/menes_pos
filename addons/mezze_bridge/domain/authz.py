"""Canonical, pure authorization + request-integrity rules (RFC-000 authority).

No Odoo, no I/O: deterministic, unit/property/mutation-testable, importable by the
controller so identity/permission/scope/replay decisions live in ONE place and no
endpoint decides them independently.

  * Capabilities are the vocabulary of authorization (orders.pay, orders.refund…).
  * ROLE_CAPS maps a cashier role -> the capabilities it holds.
  * check_scope enforces company/branch isolation from SERVER-resolved ids.
  * replay window / signature comparison helpers back the request-integrity layer.
"""

import hmac
from collections import namedtuple

# ---- stable, machine-readable reason codes -----------------------------------
AUTHENTICATION_REQUIRED = "authentication_required"
AUTHENTICATION_FAILED = "authentication_failed"
PERMISSION_DENIED = "permission_denied"
INVALID_SIGNATURE = "invalid_signature"
SIGNATURE_REQUIRED_CODE = "signature_required"
EXPIRED_SIGNATURE = "expired_signature"
FUTURE_SIGNATURE = "future_timestamp"
UNKNOWN_KEY = "unknown_key"
REVOKED_KEY = "revoked_key"
REPLAYED_REQUEST = "replayed_request"
BRANCH_MISMATCH = "branch_mismatch"
COMPANY_MISMATCH = "company_mismatch"
TERMINAL_MISMATCH = "terminal_mismatch"
SESSION_MISMATCH = "session_mismatch"
DEVICE_REVOKED = "device_revoked"
TERMINAL_REVOKED = "terminal_revoked"
PRINCIPAL_DISABLED = "principal_disabled"
SECURITY_CONFIGURATION_ERROR = "security_configuration_error"
OK = "ok"

# ---- capability vocabulary ---------------------------------------------------
ORDERS_READ = "orders.read"
ORDERS_WRITE = "orders.write"
ORDERS_PAY = "orders.pay"
ORDERS_REFUND = "orders.refund"
ORDERS_COMP = "orders.comp"
ORDERS_FIRE = "orders.fire"
ORDERS_CANCEL = "orders.cancel"
ORDERS_VOID = "orders.void"
ORDERS_DISCOUNT = "orders.discount"
KITCHEN_READ = "kitchen.read"
KITCHEN_UPDATE = "kitchen.update"
TABLES_READ = "tables.read"
TABLES_MANAGE = "tables.manage"
RESERVATIONS_READ = "reservations.read"
RESERVATIONS_MANAGE = "reservations.manage"
DELIVERY_READ = "delivery.read"
DELIVERY_MANAGE = "delivery.manage"
LOYALTY_READ = "loyalty.read"
LOYALTY_ADJUST = "loyalty.adjust"
REPORTS_READ = "reports.read"
REPORTS_EXPORT = "reports.export"
FINANCE_READ = "finance.read"
COMPLIANCE_READ = "compliance.read"
HARDWARE_PRINT = "hardware.print"
HARDWARE_DRAWER = "hardware.drawer"
SYNC_READ = "sync.read"
SYNC_WRITE = "sync.write"
INTEGRATIONS_RECEIVE = "integrations.receive"
INTEGRATIONS_MANAGE = "integrations.manage"
ADMIN_SETTINGS = "admin.settings"

ALL_CAPABILITIES = frozenset({
    ORDERS_READ, ORDERS_WRITE, ORDERS_PAY, ORDERS_REFUND, ORDERS_COMP, ORDERS_FIRE,
    ORDERS_CANCEL, ORDERS_VOID, ORDERS_DISCOUNT, KITCHEN_READ, KITCHEN_UPDATE,
    TABLES_READ, TABLES_MANAGE, RESERVATIONS_READ, RESERVATIONS_MANAGE,
    DELIVERY_READ, DELIVERY_MANAGE, LOYALTY_READ, LOYALTY_ADJUST,
    REPORTS_READ, REPORTS_EXPORT, FINANCE_READ, COMPLIANCE_READ,
    HARDWARE_PRINT, HARDWARE_DRAWER, SYNC_READ, SYNC_WRITE,
    INTEGRATIONS_RECEIVE, INTEGRATIONS_MANAGE, ADMIN_SETTINGS,
})

# role -> capabilities (least-privilege; financially-sensitive ops are NOT in the
# broad orders.write — cashiers sell/fire but cannot refund/void/comp/discount).
_CASHIER = frozenset({ORDERS_READ, ORDERS_WRITE, ORDERS_PAY, ORDERS_FIRE,
                      KITCHEN_READ, TABLES_READ, RESERVATIONS_READ,
                      DELIVERY_READ, LOYALTY_READ, HARDWARE_PRINT})
_WAITER = frozenset({ORDERS_READ, ORDERS_WRITE, ORDERS_FIRE, KITCHEN_READ,
                     TABLES_READ, TABLES_MANAGE, RESERVATIONS_READ})
_KITCHEN = frozenset({ORDERS_READ, KITCHEN_READ, KITCHEN_UPDATE})
_SUPERVISOR = _CASHIER | {ORDERS_COMP, ORDERS_REFUND, ORDERS_VOID, ORDERS_CANCEL,
                          ORDERS_DISCOUNT, REPORTS_READ, LOYALTY_ADJUST,
                          TABLES_MANAGE, RESERVATIONS_MANAGE, DELIVERY_MANAGE,
                          HARDWARE_DRAWER}
_MANAGER = _SUPERVISOR | {REPORTS_EXPORT, FINANCE_READ, ADMIN_SETTINGS}
_FINANCE = frozenset({FINANCE_READ, REPORTS_READ, REPORTS_EXPORT, COMPLIANCE_READ,
                      ORDERS_READ})
_COMPLIANCE = frozenset({COMPLIANCE_READ, REPORTS_READ, ORDERS_READ, FINANCE_READ})
_TERMINAL = frozenset({ORDERS_READ, ORDERS_WRITE, ORDERS_PAY, ORDERS_FIRE,
                       KITCHEN_READ, KITCHEN_UPDATE, TABLES_READ, TABLES_MANAGE,
                       RESERVATIONS_READ, DELIVERY_READ, LOYALTY_READ,
                       HARDWARE_PRINT, HARDWARE_DRAWER, SYNC_READ, SYNC_WRITE})
_INTEGRATION = frozenset({INTEGRATIONS_RECEIVE, INTEGRATIONS_MANAGE, ORDERS_WRITE,
                          DELIVERY_MANAGE})
ROLE_CAPS = {
    "cashier": _CASHIER,
    "waiter": _WAITER,
    "kitchen": _KITCHEN,
    "supervisor": _SUPERVISOR,
    "manager": _MANAGER,
    # human administrative principals (D1.1) — reach the Admin Console via the
    # ADMIN_SETTINGS capability; the fine-grained scoped admin role (org_admin /
    # store_manager / auditor) is derived server-side in the settings controller.
    # 'auditor' holds ADMIN_SETTINGS to READ admin routes; its writes are refused
    # by the controller's capability check (read-only).
    "admin": _MANAGER,
    "auditor": frozenset({ADMIN_SETTINGS, COMPLIANCE_READ, REPORTS_READ, ORDERS_READ, FINANCE_READ}),
    # R1 front-of-house roles. Host runs the door (reservations/waitlist/tables) and
    # may open orders, but NOT pay/refund/void. Server is the existing waiter set.
    "host": frozenset({RESERVATIONS_READ, RESERVATIONS_MANAGE, TABLES_READ, TABLES_MANAGE, ORDERS_READ}),
    "server": _WAITER,
    "finance": _FINANCE,
    "compliance": _COMPLIANCE,
    "terminal": _TERMINAL,
    "integration": _INTEGRATION,
    "administrator": ALL_CAPABILITIES,
}


def capabilities_for(role):
    """All capabilities held by a role (empty for an unknown/None role)."""
    return ROLE_CAPS.get(role, frozenset())


def can(role, capability):
    """True iff ``role`` holds ``capability``. Unknown role/capability -> False
    (default-deny)."""
    if capability not in ALL_CAPABILITIES:
        return False
    return capability in ROLE_CAPS.get(role, frozenset())


ScopeVerdict = namedtuple("ScopeVerdict", ["ok", "reason"])


def check_scope(caller_company, caller_branch, target_company, target_branch,
                allow_cross_company=False, allow_cross_branch=False):
    """Enforce company/branch isolation from SERVER-resolved ids.

    A ``None`` target means "not scoped to a specific record" -> allowed. Company
    is checked before branch. Ids must be equal unless explicitly allowed.
    """
    if target_company is not None and not allow_cross_company:
        if caller_company is None or int(caller_company) != int(target_company):
            return ScopeVerdict(False, COMPANY_MISMATCH)
    if target_branch is not None and not allow_cross_branch:
        if caller_branch is None or int(caller_branch) != int(target_branch):
            return ScopeVerdict(False, BRANCH_MISMATCH)
    return ScopeVerdict(True, OK)


def replay_window_ok(request_ts, now_ts, skew_seconds):
    """True iff |now - request_ts| <= skew_seconds. Guards against expired and
    far-future (clock-skew) timestamps. Non-numeric input fails closed."""
    try:
        return abs(float(now_ts) - float(request_ts)) <= float(skew_seconds)
    except (TypeError, ValueError):
        return False


def signatures_equal(expected_hex, provided_hex):
    """Constant-time comparison of two hex signatures (no crypto invented — uses
    hmac.compare_digest). Fails closed on missing/garbage input."""
    if not expected_hex or not provided_hex:
        return False
    try:
        return hmac.compare_digest(str(expected_hex), str(provided_hex))
    except Exception:  # noqa: BLE001
        return False


# ---- the ONE endpoint classification registry --------------------------------
# Every data route is classified exactly once: PUBLIC (anonymous by design),
# INTEGRATION (protected by its own HMAC scheme), or capability-mapped. Endpoints
# never decide their own permission. A structural test asserts this covers every
# real route, so a new route cannot ship unclassified.

PUBLIC_ROUTES = frozenset({
    "health",            # liveness
    "bootstrap",         # non-sensitive app-init metadata
    "pos",               # production Owl cashier app shell (Odoo auth=user)
    "design/pos",        # non-production design-prototype shell (Odoo auth=user)
    "cashier/login",     # the authentication endpoint itself (PIN -> token)
    # customer-facing surfaces (self-order / display / feedback)
    "shop/link", "shop/config", "shop/menu", "shop/image", "shop/order", "shop/status",
    "delivery/availability",  # S3: public server-authoritative zone/fee/min/ETA lookup
    "selforder/status",       # S4: public self-order channel availability
    "qr/table_link", "qr/menu", "qr/order", "qr/bill", "qr/pay",
    "cfd/push", "cfd/state", "feedback/submit",
    # S2C-5 online customer payment — public + tokenized (status/QR/store token);
    # the payment itself is owned by Odoo's native /pos/pay/<id> page.
    "checkout/online/create", "checkout/online/pay", "checkout/status",
    "checkout/table/pay_online", "checkout/s/<string:status_token>",
})

# Integration routes carry their own signed scheme (HMAC), not the token gate.
INTEGRATION_ROUTES = frozenset({
    "<string:code>/webhook", "orders",
})

ENDPOINT_CAPABILITY = {
    # --- S2 payment reconciliation / external-refund mutations ---
    "reconciliation/settlement": ADMIN_SETTINGS, "reconciliation/finalize": ADMIN_SETTINGS,
    "payment/external_refund/confirm": ORDERS_REFUND,
    # --- S2C-3 integrated payment terminal orchestration ---
    "terminal/start": ORDERS_PAY, "terminal/complete": ORDERS_PAY,
    "terminal/cancel": ORDERS_PAY, "terminal/force_done": ORDERS_PAY,
    "terminal/status": ORDERS_READ,
    # --- S2C-7 automated cash machine orchestration ---
    "cashmachine/start": ORDERS_PAY, "cashmachine/complete": ORDERS_PAY,
    "cashmachine/cancel": ORDERS_PAY, "cashmachine/force_done": ORDERS_PAY,
    "cashmachine/status": ORDERS_READ,
    # --- S2C-4 bank-app payment QR ---
    "payment/qr/generate": ORDERS_PAY, "payment/qr/confirm": ORDERS_PAY,
    "payment/qr/cancel": ORDERS_PAY, "payment/qr/status": ORDERS_READ,
    # --- S2C-6 customer account / credit ---
    "customer/search": ORDERS_READ, "customer/summary": ORDERS_READ,
    "customer/deposit": ORDERS_PAY, "customer/settle": ORDERS_PAY,
    # --- financial mutations (also signature-required) ---
    "orders/pay": ORDERS_PAY, "orders/refund": ORDERS_REFUND,
    "orders/comp": ORDERS_COMP, "orders/exchange": ORDERS_REFUND,
    "payment/void": ORDERS_VOID, "payment/intent": ORDERS_PAY,
    "reversals/resolve": ORDERS_REFUND, "promo/apply": ORDERS_DISCOUNT,
    "loyalty/redeem": LOYALTY_ADJUST, "giftcard/issue": LOYALTY_ADJUST,
    "drawer/open": HARDWARE_DRAWER, "config/tax": ADMIN_SETTINGS,
    "sessions/<int:session_id>/close": ADMIN_SETTINGS,
    "register": SYNC_WRITE, "push": SYNC_WRITE, "einvoice/submit": ADMIN_SETTINGS,
    "approve": ADMIN_SETTINGS, "marketing/send": ADMIN_SETTINGS,
    # --- order lifecycle / kitchen ---
    "orders/fire": ORDERS_FIRE, "orders/sync": ORDERS_WRITE,
    "orders/get": ORDERS_READ, "orders/recent": ORDERS_READ,
    "orders/kds": KITCHEN_READ, "courses/fire": ORDERS_FIRE,
    "courses/hold": ORDERS_FIRE, "courses/board": KITCHEN_READ,
    "kds/state": KITCHEN_READ, "kds/transition": KITCHEN_UPDATE,
    "bds/queue": KITCHEN_READ, "menu/eightysix": ORDERS_WRITE,
    "menu/quickkeys": ORDERS_READ, "bus/poll": ORDERS_READ, "ai/upsell": ORDERS_READ,
    # --- tables / floor ---
    "tables/transfer": TABLES_MANAGE, "tables/merge": TABLES_MANAGE, "floors": TABLES_READ,
    # --- reservations / waitlist ---
    "reservations/list": RESERVATIONS_READ, "reservations/availability": RESERVATIONS_READ,
    "reservations/create": RESERVATIONS_MANAGE, "reservations/state": RESERVATIONS_MANAGE,
    "waitlist/list": RESERVATIONS_READ, "waitlist/add": RESERVATIONS_MANAGE,
    "waitlist/state": RESERVATIONS_MANAGE,
    # --- delivery / drive-thru / central kitchen ---
    "delivery/zones": DELIVERY_READ, "delivery/list": DELIVERY_READ,
    "delivery/create": DELIVERY_MANAGE, "delivery/state": DELIVERY_MANAGE,
    "delivery/zone/save": DELIVERY_MANAGE, "drivethru/board": KITCHEN_READ,
    # S3 delivery v1 — collection/dispatch (manage) + report (read)
    "delivery/collect": DELIVERY_MANAGE, "delivery/couriers": DELIVERY_MANAGE,
    "delivery/report": DELIVERY_READ,
    # S4 self-order — pause (config admin) + report (read)
    "selforder/pause": ADMIN_SETTINGS, "selforder/report": ORDERS_READ,
    "drivethru/create": ORDERS_WRITE, "drivethru/stage": ORDERS_WRITE,
    "ck/board": KITCHEN_READ, "ck/request": ORDERS_WRITE, "ck/produce": KITCHEN_UPDATE,
    "ck/dispatch": DELIVERY_MANAGE, "ck/receive": ORDERS_WRITE,
    # --- loyalty / promo reads ---
    "loyalty/search": LOYALTY_READ, "giftcard/balance": LOYALTY_READ, "promo/list": ORDERS_READ,
    # --- marketing / reporting / management ---
    "marketing/segments": REPORTS_READ, "marketing/campaigns": REPORTS_READ,
    "ops/summary": REPORTS_READ, "manager/dashboard": REPORTS_READ,
    "hq/summary": REPORTS_READ, "branches": REPORTS_READ,
    "reports/summary": REPORTS_READ, "reports/refunds.csv": REPORTS_EXPORT,
    "reconcile": REPORTS_READ, "clock/list": REPORTS_READ, "clock/toggle": ORDERS_WRITE,
    "waste/log": ORDERS_WRITE, "waste/list": REPORTS_READ, "waste/products": ORDERS_READ,
    "feedback/list": REPORTS_READ,
    # --- finance / compliance ---
    "gl/sessions": FINANCE_READ, "gl/summary": FINANCE_READ, "gl/export.csv": REPORTS_EXPORT,
    "reversals": FINANCE_READ, "einvoice/status": COMPLIANCE_READ, "audit/log": COMPLIANCE_READ,
    "payment/status": ORDERS_READ, "payment/methods": ORDERS_READ,
    # --- hardware / sync reads ---
    "print/receipt": HARDWARE_PRINT, "print/kitchen": HARDWARE_PRINT,
    "printers": HARDWARE_PRINT, "test": HARDWARE_PRINT, "pull": SYNC_READ,
    # --- D1 design platform: settings (any authenticated POS principal manages
    #     their OWN prefs) + admin console (config administration) ---
    "settings/effective": ORDERS_READ, "settings/save": ORDERS_READ, "settings/reset": ORDERS_READ,
    "admin/templates": ADMIN_SETTINGS, "admin/assignments": ADMIN_SETTINGS,
    "admin/locks": ADMIN_SETTINGS, "admin/permissions": ADMIN_SETTINGS, "admin/audit": ADMIN_SETTINGS,
    "admin/template/create": ADMIN_SETTINGS, "admin/template/duplicate": ADMIN_SETTINGS,
    "admin/template/publish": ADMIN_SETTINGS, "admin/template/archive": ADMIN_SETTINGS,
    "admin/lock": ADMIN_SETTINGS, "admin/assign": ADMIN_SETTINGS,
}

# Signature-required (sensitive mutations): unsigned traffic rejected in enforce.
SIGNATURE_REQUIRED = frozenset({
    "orders/pay", "orders/refund", "orders/comp", "orders/exchange",
    "terminal/start", "terminal/complete", "terminal/cancel", "terminal/force_done",
    "cashmachine/start", "cashmachine/complete", "cashmachine/cancel", "cashmachine/force_done",
    "payment/qr/generate", "payment/qr/confirm", "payment/qr/cancel",
    "payment/void", "payment/intent", "reversals/resolve", "promo/apply",
    "loyalty/redeem", "giftcard/issue", "drawer/open", "config/tax",
    "sessions/<int:session_id>/close", "register", "push", "einvoice/submit",
    "approve", "marketing/send",
})
