"""mezze_bridge.domain — pure, dependency-free executable business rules.

This package is the single executable source of truth for domain invariants
(RFC-001 / RFC-002). It contains NO Odoo imports and NO I/O, so it is:
  * deterministic and replay-safe,
  * unit-testable without bootstrapping Odoo,
  * importable by models/controllers so business rules are never duplicated.
"""
from . import order_fsm  # noqa: F401
from . import order_guard  # noqa: F401
from . import refund  # noqa: F401
from . import authz  # noqa: F401
