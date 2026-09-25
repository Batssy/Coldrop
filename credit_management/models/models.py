from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class CreditApplication(models.Model):
    _name='credit.application'
    _description='Credit Management'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='credit.application'
    process_key='credit_application'
    customer_id=fields.Many2one('res.partner',required=True,domain="[('customer_rank','>',0)]",tracking=True)
    request_type=fields.Selection([('new','New Facility'),('limit','Limit Change'),('terms','Payment Terms Change'),('temporary','Temporary Increase'),('exception','One-Off Exception'),('suspend','Suspend'),('reactivate','Reactivate')],required=True,default='new')
    current_credit_limit=fields.Monetary(related='customer_id.approved_credit_limit',currency_field='currency_id',readonly=True); requested_credit_limit=fields.Monetary(currency_field='currency_id')
    current_payment_term_id=fields.Many2one('account.payment.term',related='customer_id.property_payment_term_id',readonly=True); requested_payment_term_id=fields.Many2one('account.payment.term')
    requested_credit_days=fields.Integer(); effective_date=fields.Date(default=fields.Date.context_today); review_date=fields.Date(); justification=fields.Text(required=True)
    def _on_approved_apply(self):
        for r in self:
            vals={'approved_credit_limit':r.requested_credit_limit,'approved_credit_days':r.requested_credit_days,'credit_effective_date':r.effective_date,'credit_review_date':r.review_date,'credit_status':'active'}
            if r.requested_payment_term_id: vals['property_payment_term_id']=r.requested_payment_term_id.id
            r.customer_id.sudo().write(vals)
    def action_approve(self):
        res=super().action_approve(); self._on_approved_apply(); return res


class ResPartner(models.Model):
    _inherit='res.partner'
    credit_currency_id=fields.Many2one('res.currency',related='company_id.currency_id',readonly=True); approved_credit_limit=fields.Monetary(currency_field='credit_currency_id'); approved_credit_days=fields.Integer(); credit_effective_date=fields.Date(); credit_review_date=fields.Date()
    credit_status=fields.Selection([('cash','Cash Only'),('active','Credit Active'),('hold','Credit Hold'),('suspended','Suspended'),('review','Under Review')],default='cash',index=True)

