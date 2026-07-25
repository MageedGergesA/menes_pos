"""Pure transactional-outbox dispatch policy (RFC-002 events, RFC-000 reliability).

No Odoo, no I/O: deterministic, unit/property/mutation-testable. The durable
model + dispatcher (models/outbox_event.py) delegate every *decision* here so
retry/backoff/dead-letter/ordering rules live in ONE testable place.
"""

# ---- event status ------------------------------------------------------------
PENDING = "pending"      # published, not yet delivered
INFLIGHT = "inflight"    # claimed by a worker (locked_until guards crash recovery)
DONE = "done"            # delivered + acked
FAILED = "failed"        # a retryable failure; awaits next_retry
DEAD = "dead"            # exhausted retries / permanent failure -> dead-letter
STATUSES = frozenset({PENDING, INFLIGHT, DONE, FAILED, DEAD})

# ---- failure classification --------------------------------------------------
RETRYABLE = "retryable"
TRANSPORT = "transport"
TIMEOUT = "timeout"
CONSUMER_REJECTION = "consumer_rejection"
PERMANENT = "permanent"
CONFIGURATION = "configuration"
SECURITY = "security"
VALIDATION = "validation"

RETRYABLE_CLASSES = frozenset({RETRYABLE, TRANSPORT, TIMEOUT, CONSUMER_REJECTION})
PERMANENT_CLASSES = frozenset({PERMANENT, CONFIGURATION, SECURITY, VALIDATION})

# map common exception/type names -> a failure class (retryable vs permanent).
_EXC_MAP = {
    "TimeoutError": TIMEOUT, "Timeout": TIMEOUT, "ReadTimeout": TIMEOUT,
    "ConnectionError": TRANSPORT, "ConnectionResetError": TRANSPORT,
    "OperationalError": TRANSPORT, "SerializationFailure": TRANSPORT,
    "DeadlockDetected": TRANSPORT, "OutboxRetry": RETRYABLE,
    "ValueError": VALIDATION, "ValidationError": VALIDATION, "TypeError": VALIDATION,
    "KeyError": CONFIGURATION, "OutboxNoConsumer": CONFIGURATION,
    "AccessError": SECURITY, "UserError": PERMANENT,
}


def classify(exc_name):
    """Map an exception/type name to a failure class. Unknown -> RETRYABLE
    (fail-open on delivery so a transient/unknown error retries rather than
    silently dead-lettering a real event)."""
    return _EXC_MAP.get(exc_name, RETRYABLE)


def is_retryable(failure_class):
    return failure_class in RETRYABLE_CLASSES


def next_backoff(attempt, base_seconds=2, factor=2, cap_seconds=3600):
    """Exponential backoff for the Nth attempt (1-indexed), capped and floored.
    attempt<=0 -> base. Deterministic; never negative."""
    a = max(1, int(attempt))
    delay = base_seconds * (factor ** (a - 1))
    return int(min(max(base_seconds, delay), cap_seconds))


def decide(failure_class, attempt, max_attempts):
    """Given a failure and the current attempt count, decide the next status.

    Returns (next_status, backoff_seconds_or_None):
      * permanent failure                -> (DEAD, None)
      * retryable but attempts exhausted -> (DEAD, None)
      * retryable with attempts left     -> (FAILED, backoff)
    """
    if not is_retryable(failure_class):
        return (DEAD, None)
    if int(attempt) >= int(max_attempts):
        return (DEAD, None)
    return (FAILED, next_backoff(attempt))


def blocks_aggregate(status):
    """An earlier event with this status blocks later events of the same
    aggregate (strict per-aggregate ordering; a dead-letter halts the stream)."""
    return status != DONE
