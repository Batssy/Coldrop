from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class SalesException(models.Model):
    _name='sales.exception'
    _description='Sales Control'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='sales.exception'
    process_key='sales_exception'
    sale_order_id=fields.Many2one('sale.order',required=True,tracking=True)
    customer_id=fields.Many2one('res.partner',related='sale_order_id.partner_id',store=True); exception_type=fields.Selection([('credit','Credit'),('price','Price'),('discount','Discount'),('deposit','Deposit'),('stock','Stock'),('returnables','Returnables')],required=True)
    requested_override=fields.Monetary(currency_field='currency_id'); justification=fields.Text(required=True)



class SaleOrder(models.Model):
    _inherit='sale.order'
    credit_exposure=fields.Monetary(compute='_compute_credit_exposure',currency_field='currency_id')
    credit_available=fields.Monetary(compute='_compute_credit_exposure',currency_field='currency_id'); credit_hold=fields.Boolean(compute='_compute_credit_exposure')
    @api.depends('partner_id','amount_total')
    def _compute_credit_exposure(self):
        Move=self.env['account.move']
        for r in self:
            receivable=sum(Move.search([('partner_id','=',r.partner_id.commercial_partner_id.id),('move_type','=','out_invoice'),('state','=','posted'),('payment_state','not in',('paid','reversed'))]).mapped('amount_residual')) if r.partner_id else 0
            lim=r.partner_id.approved_credit_limit if r.partner_id else 0
            r.credit_exposure=receivable+r.amount_total; r.credit_available=max(lim-receivable,0); r.credit_hold=bool(r.partner_id and r.partner_id.credit_status=='active' and lim and r.credit_exposure>lim)
    def action_confirm(self):
        for r in self:
            if r.credit_hold: raise UserError(_('Order is on credit hold. Submit a credit exception or obtain approved revised terms before confirmation.'))
            if r.partner_id.credit_status in ('hold','suspended','review'): raise UserError(_('Customer credit status does not permit confirmation.'))
        return super().action_confirm()

