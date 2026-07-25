"""Built-in outbox consumers — the reliable delivery side of business events.

Consumers are plain functions ``handler(env, event)``. They ACK by returning and
request retry/dead-letter by raising (classified by ``domain.outbox.classify``).
Registering here moves a side effect OFF the request path: business code publishes
in-transaction, the dispatcher delivers here after commit.

These are intentionally conservative — they add a reliable event stream alongside
the existing direct side effects rather than replacing working code in one step.
"""

import hashlib
import hmac
import json
import logging
import socket as _socket
from datetime import timedelta
from urllib.parse import urlsplit

from odoo import fields

from . import hardware_render
from .outbox_event import register_consumer, OutboxRetry
from ..domain import webhook as wh

_logger = logging.getLogger(__name__)


def _payload(event):
    try:
        return json.loads(event.payload) if event.payload else {}
    except (ValueError, TypeError):
        return {}


def _bus_broadcast(env, event):
    """Deliver bus notifications AFTER commit (KDS / waiter / CFD pushes migrated
    off the request path). The payload carries either:

      * ``sends``: a list of ``{channel, message_type, body}`` (KDS fire/pay path,
        rendered by ``mezze.kds.ticket._bus_sends()``), or
      * a single ``channel`` + ``body`` (generic notification) wrapped in an
        event envelope so the receiver gets stable event_id / correlation_id.

    Idempotent: re-delivering a bus message is harmless (bus is fire-and-forget,
    receivers apply latest-state). A missing channel is a permanent payload error
    (``KeyError`` -> dead-letter, not endless retry); a transient bus/DB write
    error propagates as a retryable transport failure.
    """
    data = _payload(event)
    Bus = env['bus.bus']
    sends = data.get('sends')
    if sends is not None:
        for s in sends:
            channel = s.get('channel')
            if not channel:
                raise KeyError('bus_channel_missing')
            Bus._sendone(channel, s.get('message_type', 'mezze_event'), s.get('body'))
        return
    channel = data.get('channel')
    if not channel:
        raise KeyError('bus_channel_missing')
    Bus._sendone(channel, data.get('message_type', 'mezze_event'), {
        'event_id': event.event_id,
        'event_type': event.event_type,
        'aggregate_type': event.aggregate_type,
        'aggregate_id': event.aggregate_id,
        'version': event.payload_version,
        'idempotency_key': event.idempotency_key,
        'correlation_id': event.correlation_id,
        'payload': data.get('body'),
    })


def _audit_projection(env, event):
    """Idempotent internal projection: record that a business event was delivered.
    Keyed by event_id so a duplicate delivery is a no-op (defense in depth on top
    of the outbox's own at-least-once + done-dedup)."""
    Audit = env['mezze.audit.log'].sudo()
    existing = Audit.search([('event', '=', 'outbox.projected'),
                             ('res_uuid', '=', event.event_id)], limit=1)
    if existing:
        return  # already projected -> idempotent no-op
    Audit.log('outbox.projected', severity='info', res_model=event.aggregate_type or False,
              res_uuid=event.event_id,
              detail=json.dumps({'event_type': event.event_type,
                                 'aggregate_id': event.aggregate_id}, default=str))


register_consumer('mezze.bus.broadcast', _bus_broadcast)
register_consumer('order.paid.v1', _audit_projection)
register_consumer('order.refunded.v1', _audit_projection)


# ==========================================================================
# P5.2 — outbound webhook delivery (after commit, SSRF-guarded, credential-safe)
# ==========================================================================
# Permanent-delivery failures must dead-letter. The outbox engine classifies by
# EXCEPTION CLASS NAME, and 'ValueError' maps to the permanent/validation class,
# so we raise ValueError (aliased for readability) rather than a custom subclass
# whose unmapped name would default to retryable.
_PermanentDelivery = ValueError


def _icp_bool(env, key, default=False):
    v = env['ir.config_parameter'].sudo().get_param(key)
    if v is None:
        return default
    return str(v).strip().lower() in ('1', 'true', 'yes', 'on')


def _audit(env, event_code, **vals):
    try:
        env['mezze.audit.log'].sudo().log(event_code, **vals)
    except Exception:  # noqa: BLE001 — audit must never break delivery
        _logger.exception("audit failed: %s", event_code)


def _webhook_deliver(env, event):
    """Deliver an outbound integration webhook AFTER commit.

    Destination + credentials are resolved SERVER-SIDE from the integration record
    (never from the event payload). The URL is SSRF-checked (scheme allowlist +
    resolved-IP validation). Responses are classified per policy: 408/425/429/5xx
    and network errors retry; 4xx/config errors dead-letter. Secrets, signatures
    and auth headers are never logged.
    """
    import requests  # noqa: PLC0415 — lazy (core dep)

    data = _payload(event)
    integration_id = data.get('integration_id')
    topic = data.get('topic') or event.event_type
    channel = env['mezze.aggregator'].sudo().browse(int(integration_id)) if integration_id else None
    if not channel or not channel.exists():
        raise _PermanentDelivery('unknown_integration')

    # branch/company scope: the event's branch must be the integration's branch
    if event.branch_id and channel.config_id and event.branch_id.id != channel.config_id.id:
        raise _PermanentDelivery('branch_mismatch')

    url = channel.notify_url  # SERVER-SIDE only
    if not url:
        raise _PermanentDelivery('missing_destination')

    allow_http = _icp_bool(env, 'mezze_bridge.webhook_allow_http')
    allow_loopback = _icp_bool(env, 'mezze_bridge.webhook_allow_loopback')
    allow_private = _icp_bool(env, 'mezze_bridge.webhook_allow_private')
    ok, reason = wh.check_url(url, allow_http=allow_http, allow_loopback=allow_loopback,
                              allow_private=allow_private)
    if not ok:
        _audit(env, 'webhook.blocked', res_model='mezze.aggregator', res_id=channel.id,
               detail=json.dumps({'reason': reason, 'event_id': event.event_id}))
        raise _PermanentDelivery('unsafe_destination:%s' % reason)

    # resolve DNS + re-check every address (DNS-rebind / SSRF defence)
    host = urlsplit(url).hostname
    try:
        infos = _socket.getaddrinfo(host, None)
    except OSError:
        raise OutboxRetry('dns_failure')     # transient -> retry
    for info in infos:
        if wh.ip_is_blocked(info[4][0], allow_loopback, allow_private):
            raise _PermanentDelivery('unsafe_resolved_ip')

    body = json.dumps(data.get('payload') or {}, default=str, sort_keys=True).encode()
    headers = {
        'Content-Type': 'application/json',
        'Idempotency-Key': event.idempotency_key or event.event_id,
        'X-Mezze-Event-Id': event.event_id,
        'X-Mezze-Correlation-Id': event.correlation_id or '',
        'X-Mezze-Topic': topic,
        'X-Mezze-Payload-Version': str(event.payload_version or 1),
    }
    _secret = channel._secret()   # decrypted only here (envelope at rest)
    if _secret:   # HMAC per existing integration policy (secret stays server-side)
        headers['X-Mezze-Signature'] = hmac.new(
            _secret.encode(), body, hashlib.sha256).hexdigest()

    timeout = float(env['ir.config_parameter'].sudo().get_param('mezze_bridge.webhook_timeout', 5) or 5)
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=timeout,
                             verify=True, allow_redirects=False)
    except requests.exceptions.SSLError:
        raise _PermanentDelivery('tls_error')           # cert/config -> dead
    except requests.exceptions.TooManyRedirects:
        raise _PermanentDelivery('too_many_redirects')
    except (requests.exceptions.MissingSchema, requests.exceptions.InvalidURL,
            requests.exceptions.InvalidSchema):
        raise _PermanentDelivery('invalid_url')
    except requests.exceptions.Timeout:
        raise OutboxRetry('timeout')                    # transient -> retry
    except requests.exceptions.ConnectionError:
        raise OutboxRetry('connection_error')           # incl. DNS -> retry
    except requests.exceptions.RequestException:
        raise OutboxRetry('request_error')

    status = resp.status_code
    if 300 <= status < 400:
        raise _PermanentDelivery('redirect_not_followed:%s' % status)
    fclass = wh.classify_status(status)
    if fclass is None:
        _audit(env, 'webhook.delivered', res_model='mezze.aggregator', res_id=channel.id,
               detail=json.dumps({'status': status, 'event_id': event.event_id,
                                  'topic': topic, 'idempotency_key': event.idempotency_key}))
        return
    body_snip = (resp.text or '')[:200]
    _audit(env, 'webhook.failed', res_model='mezze.aggregator', res_id=channel.id,
           detail=json.dumps({'status': status, 'event_id': event.event_id,
                              'class': fclass, 'body': body_snip}))
    if wh.is_retryable(fclass):
        raise OutboxRetry('http_%s' % status)
    raise _PermanentDelivery('http_%s' % status)


# ==========================================================================
# P5.2 — hardware print + drawer (after commit, ledger-deduped, scope-checked)
# ==========================================================================
def _resolve_printer(env, data, event):
    printer = env['mezze.printer'].sudo().with_context(active_test=False).browse(
        int(data['printer_config_id'])) if data.get('printer_config_id') else None
    if not printer or not printer.exists():
        raise _PermanentDelivery('missing_printer')
    if not printer.active:
        raise _PermanentDelivery('printer_disabled')
    # company / branch scope resolved from the authoritative printer record
    if event.company_id and printer.config_id.company_id.id != event.company_id.id:
        raise _PermanentDelivery('company_mismatch')
    if event.branch_id and printer.config_id.id != event.branch_id.id:
        raise _PermanentDelivery('branch_mismatch')
    if not printer.host:
        raise _PermanentDelivery('printer_unconfigured')
    return printer


def _hw_print(env, event):
    """Deliver a receipt print AFTER commit. Re-renders from the authoritative
    order (no document stored). Deduped by a persistent job ledger so a duplicate
    outbox delivery does NOT produce a second physical receipt (at-most-once
    physical print per idempotency key; at-least-once delivery attempts)."""
    data = _payload(event)
    printer = _resolve_printer(env, data, event)
    order = env['pos.order'].sudo().browse(int(data['order_id'])) if data.get('order_id') else None
    if not order or not order.exists():
        raise _PermanentDelivery('missing_order')

    Job = env['mezze.hw.job']
    job, is_new = Job.claim(event.idempotency_key, 'print', {
        'printer_id': printer.id, 'company_id': printer.config_id.company_id.id,
        'branch_id': printer.config_id.id, 'order_ref': str(order.id),
        'purpose': data.get('purpose') or 'receipt', 'terminal': event.terminal})
    if not is_new and job.status == 'done':
        _audit(env, 'print.duplicate_suppressed', res_model='mezze.hw.job', res_id=job.id,
               detail=json.dumps({'idempotency_key': event.idempotency_key}))
        return   # physical dedup: already printed
    job.sudo().write({'attempts': job.attempts + 1})

    tk = hardware_render.receipt_ticket(order, printer.width or 48)
    payload_bytes = tk.to_escpos(drawer=bool(data.get('drawer')))
    try:
        n = hardware_render.raw_send(printer.host, printer.port, payload_bytes)
    except OSError as exc:
        job.sudo().write({'status': 'failed', 'last_error': str(exc)[:200]})
        _audit(env, 'print.failed', res_model='mezze.hw.job', res_id=job.id,
               detail=json.dumps({'error': 'device_unavailable'}))
        raise OutboxRetry('printer_unreachable')     # transient device outage -> retry
    job.sudo().write({'status': 'done', 'executed_at': fields.Datetime.now(),
                      'last_error': False})
    _audit(env, 'print.delivered', res_model='mezze.hw.job', res_id=job.id,
           detail=json.dumps({'printer': printer.name, 'bytes': n, 'order_ref': str(order.id)}))


# a drawer-open older than this is stale and must NOT auto-execute (operator replay
# only). Configurable via 'mezze_bridge.drawer_expiry_seconds'.
_DRAWER_EXPIRY_DEFAULT = 120


def _hw_drawer(env, event):
    """Open a cash drawer AFTER commit. Physically non-idempotent, so: stale
    commands EXPIRE (a delayed dead-letter replay must not pop a drawer), commands
    are terminal-scoped and audited with their authorising principal, and a
    duplicate delivery of the same operation is suppressed via the job ledger."""
    data = _payload(event)
    expiry = int(env['ir.config_parameter'].sudo().get_param(
        'mezze_bridge.drawer_expiry_seconds', _DRAWER_EXPIRY_DEFAULT) or _DRAWER_EXPIRY_DEFAULT)
    age = (fields.Datetime.now() - event.created_at).total_seconds() if event.created_at else 0
    Job = env['mezze.hw.job']
    if age > expiry:
        Job.claim(event.idempotency_key, 'drawer', {
            'status': 'expired', 'terminal': event.terminal,
            'reason': data.get('reason'), 'principal': event.principal,
            'last_error': 'stale_%ds' % int(age)})
        _audit(env, 'drawer.expired', detail=json.dumps(
            {'terminal': event.terminal, 'age': int(age), 'idempotency_key': event.idempotency_key}))
        return   # ACK — do NOT open a stale drawer

    printer = _resolve_printer(env, data, event)
    job, is_new = Job.claim(event.idempotency_key, 'drawer', {
        'printer_id': printer.id, 'company_id': printer.config_id.company_id.id,
        'branch_id': printer.config_id.id, 'terminal': event.terminal,
        'reason': data.get('reason'), 'principal': event.principal,
        'order_ref': data.get('source_ref')})
    if not is_new and job.status == 'done':
        return   # duplicate command suppressed
    job.sudo().write({'attempts': job.attempts + 1})
    _audit(env, 'drawer.requested', res_model='mezze.hw.job', res_id=job.id,
           detail=json.dumps({'terminal': event.terminal, 'reason': data.get('reason'),
                              'principal': event.principal}))
    try:
        hardware_render.raw_send(printer.host, printer.port, hardware_render.drawer_bytes())
    except OSError as exc:
        job.sudo().write({'status': 'failed', 'last_error': str(exc)[:200]})
        raise OutboxRetry('drawer_printer_unreachable')
    job.sudo().write({'status': 'done', 'executed_at': fields.Datetime.now()})
    _audit(env, 'drawer.executed', res_model='mezze.hw.job', res_id=job.id,
           detail=json.dumps({'terminal': event.terminal}))


register_consumer('integration.webhook.deliver.v1', _webhook_deliver)
register_consumer('hardware.print.requested.v1', _hw_print)
register_consumer('hardware.drawer.open.requested.v1', _hw_drawer)
