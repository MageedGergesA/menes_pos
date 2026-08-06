# Part of the Mezze POS platform. See LICENSE (LGPL-3).
import secrets

from odoo import api, fields, models


class MezzeTerminal(models.Model):
    """A registered POS terminal (an offline-capable install).

    Each terminal owns its local sales and syncs to cloud HQ. Identity is minted
    at first ``/mezze/sync/v1/register``; ``token`` authenticates that terminal's
    push/pull. ``identifier`` also namespaces the terminal's ``pos_reference``
    sequence so two offline terminals never mint the same receipt number.

    See ``docs/SYNC.md``.
    """
    _name = 'mezze.terminal'
    _description = "Mezze POS Terminal"
    _order = 'id desc'

    name = fields.Char(required=True, index=True,
                       help="Human label, e.g. 'Front counter 1'.")
    identifier = fields.Char(string="Terminal ID", index=True, copy=False,
                             help="Stable global id; also the pos_reference namespace.")
    token = fields.Char(string="Sync Token", copy=False,
                        help="Per-terminal secret for push/pull auth.")
    branch_id = fields.Many2one('pos.config', string="Branch", ondelete='set null',
                                help="The pos.config (branch) this terminal belongs to.")
    last_seen = fields.Datetime(string="Last Sync")
    last_acked_seq = fields.Integer(
        string="Last Acked Outbox Seq", default=0,
        help="Highest terminal outbox seq the cloud has ingested (exactly-once cursor).")
    active = fields.Boolean(default=True)

    # P6.1 — least-privilege machine principal. The principal's capabilities come
    # from this role (authz.ROLE_CAPS), so a normal terminal gets POS caps only
    # (pay/fire/print/drawer/sync) and NEVER needs the universal shared-admin token.
    role = fields.Selection(
        [('terminal', 'POS Terminal'), ('kitchen', 'Kitchen Display'),
         ('integration', 'Integration'), ('backoffice', 'Back-office service')],
        default='terminal', required=True, index=True,
        help="Principal class; drives the capability set (least privilege). "
             "'kitchen' holds ONLY kitchen.read/kitchen.update (+orders.read) — a KDS "
             "screen can view + bump tickets but never pay/refund/void/admin.")

    # P6.1 — signing key lifecycle. ``token`` is the ACTIVE signing secret; ``kid``
    # identifies it; on rotation the outgoing secret is kept in ``prev_token`` and
    # accepted only within a bounded grace window after ``key_rotated_at``.
    kid = fields.Char(string="Key ID", copy=False, index=True,
                      help="Identifier of the active signing key (sent as X-Mezze-Key-Id).")
    prev_token = fields.Char(string="Previous Key", copy=False,
                             help="Outgoing secret accepted only during the rotation grace window.")
    prev_kid = fields.Char(string="Previous Key ID", copy=False)
    key_rotated_at = fields.Datetime(string="Key Rotated At")

    # Pilot P6.5 — the bearer token is NEVER stored in plaintext. On write it is
    # replaced by a non-reversible keyed fingerprint (HMAC under the master key,
    # outside the DB); lookup is by fingerprint and signature verification uses the
    # token PRESENTED in the request (the bearer token IS its own signing key).
    token_fingerprint = fields.Char(string="Token Fingerprint", copy=False, index=True,
                                    help="Keyed HMAC of the bearer token (non-reversible).")
    prev_token_fingerprint = fields.Char(string="Previous Token Fingerprint", copy=False, index=True)

    _identifier_uniq = models.Constraint(
        'unique(identifier)',
        "Terminal ID must be unique.",
    )

    def _secure_token_vals(self, vals):
        """Replace any plaintext token in ``vals`` with a keyed fingerprint and blank
        the plaintext. If the master key is unavailable the plaintext is kept
        (degraded dev mode) so the module still works, but a pilot/production sets
        MEZZE_MASTER_KEY so nothing plaintext is ever persisted."""
        Store = self.env['mezze.secret.store']
        for src, fp in (('token', 'token_fingerprint'), ('prev_token', 'prev_token_fingerprint')):
            if vals.get(src):
                h = Store.token_hash(vals[src])
                if h:
                    vals[fp] = h
                    vals[src] = False   # never persist the plaintext bearer token

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('kid'):
                vals['kid'] = 'k-' + secrets.token_urlsafe(6)
            self._secure_token_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        if 'token' in vals or 'prev_token' in vals:
            self._secure_token_vals(vals)
        return super().write(vals)

    def rotate_token(self, new_token=None):
        """Rotate the signing secret with a bounded grace window. The outgoing key's
        FINGERPRINT is kept as prev (no plaintext) and accepted only within the grace
        window. Returns the new plaintext token ONCE (to hand to the terminal); the
        server keeps only its fingerprint."""
        self.ensure_one()
        new = new_token or secrets.token_urlsafe(24)
        self.write({
            'prev_token_fingerprint': self.token_fingerprint, 'prev_kid': self.kid,
            'token': new, 'kid': 'k-' + secrets.token_urlsafe(6),
            'key_rotated_at': fields.Datetime.now(),
        })
        self.env['mezze.audit.log'].sudo().log(
            'security.key_rotated', severity='warning', res_model=self._name, res_id=self.id,
            detail='{"terminal": "%s", "new_kid": "%s", "prev_kid": "%s"}'
                   % (self.identifier, self.kid, self.prev_kid or ''))
        return new

    def revoke_key(self):
        """Immediate revocation: drop the previous key fingerprint and close the
        grace window (only the active key works; deactivating blocks entirely)."""
        self.ensure_one()
        self.write({'prev_token': False, 'prev_token_fingerprint': False, 'prev_kid': False,
                    'key_rotated_at': fields.Datetime.now()})
        self.env['mezze.audit.log'].sudo().log(
            'security.key_revoked', severity='warning', res_model=self._name, res_id=self.id,
            detail='{"terminal": "%s"}' % self.identifier)

    @api.model
    def _migrate_plaintext_tokens(self):
        """Idempotently fingerprint any legacy plaintext token/prev_token and blank
        the plaintext. Fails closed (does nothing) without the master key; never
        logs a token value. Verifies the fingerprint before clearing the plaintext."""
        Store = self.env['mezze.secret.store']
        if not Store.available():
            return 0
        migrated = 0
        cr = self.env.cr
        for src, fp in (('token', 'token_fingerprint'), ('prev_token', 'prev_token_fingerprint')):
            cr.execute("SELECT id, %s FROM mezze_terminal WHERE %s IS NOT NULL AND %s <> ''"
                       % (src, src, src))
            for tid, plain in cr.fetchall():
                h = Store.token_hash(plain)
                if h:
                    cr.execute("UPDATE mezze_terminal SET %s=%%s, %s=NULL WHERE id=%%s"
                               % (fp, src), (h, tid))
                    migrated += 1
        return migrated
