from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class CashCollection(models.Model):
    _name='cash.collection'
    _description='Cash & Collections'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='cash.collection'
    process_key='cash_collection'
    collection_type=fields.Selection([('cash','Cash'),('mpesa','M-Pesa'),('card','Card'),('bank','Bank Transfer')],required=True,default='cash'); partner_id=fields.Many2one('res.partner',required=True); trip_id=fields.Many2one('distribution.trip'); collector_id=fields.Many2one('res.users',default=lambda s:s.env.user)
    amount_expected=fields.Monetary(currency_field='currency_id'); amount_collected=fields.Monetary(currency_field='currency_id'); variance=fields.Monetary(compute='_compute_variance',currency_field='currency_id'); external_reference=fields.Char(); journal_id=fields.Many2one('account.journal',domain="[('type','in',('cash','bank'))]"); payment_id=fields.Many2one('account.payment',readonly=True)
    @api.depends('amount_expected','amount_collected')
    def _compute_variance(self):
        for r in self: r.variance=r.amount_collected-r.amount_expected
    def action_create_payment(self):
        for r in self:
            if r.state!='approved': raise UserError(_('Approval is required before posting a payment.'))
            if r.payment_id: continue
            if not r.journal_id or not r.partner_id: raise UserError(_('Customer and journal are required.'))
            payment=self.env['account.payment'].create({'payment_type':'inbound','partner_type':'customer','partner_id':r.partner_id.id,'amount':r.amount_collected,'currency_id':r.currency_id.id,'journal_id':r.journal_id.id,'date':r.process_date,'memo':r.name})
            payment.action_post(); r.with_context(workflow_system=True).write({'payment_id':payment.id}); r.action_start_processing()
        return True


