# Part of the Mezze POS platform. See LICENSE (LGPL-3).
"""Marketing campaigns — reach customers over email / SMS / WhatsApp.

A campaign targets an audience segment (all reachable customers, loyalty members,
or recent diners) and dispatches a message on one channel:
  - email    → native ``mail.mail`` (real; needs SMTP configured to leave)
  - sms      → native ``sms.sms``  (real; needs an SMS gateway / Odoo IAP)
  - whatsapp → queued, pending a Meta Cloud API token (externally gated, like
               card payments and the ETA token)
The campaign record keeps the audience + sent count for a back-office history.
"""
from odoo import fields, models


class MezzeCampaign(models.Model):
    _name = 'mezze.campaign'
    _description = 'Mezze Marketing Campaign'
    _order = 'create_date desc, id desc'

    name = fields.Char()
    config_id = fields.Many2one('pos.config', index=True)
    channel = fields.Selection(
        [('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')],
        required=True, default='email')
    segment = fields.Selection(
        [('all', 'All customers'), ('loyalty', 'Loyalty members'),
         ('recent', 'Recent diners')],
        required=True, default='all')
    subject = fields.Char()
    body = fields.Text()
    state = fields.Selection(
        [('draft', 'Draft'), ('sent', 'Sent'), ('queued', 'Queued')],
        default='draft', required=True)
    audience_count = fields.Integer()
    sent_count = fields.Integer()
