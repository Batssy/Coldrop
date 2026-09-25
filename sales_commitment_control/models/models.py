from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class SalesCommitment(models.Model):
    _name='sales.commitment'
    _description='Sales Commitments'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='sales.commitment'
    process_key='sales_commitment'
    customer_id=fields.Many2one('res.partner',required=True,domain="[('customer_rank','>',0)]",tracking=True)
    start_date=fields.Date(required=True); end_date=fields.Date(required=True); commitment_type=fields.Selection([('quantity','Quantity'),('value','Value'),('hybrid','Hybrid')],default='hybrid',required=True)
    payment_term_id=fields.Many2one('account.payment.term'); line_ids=fields.One2many('sales.commitment.line','commitment_id'); release_ids=fields.One2many('sales.delivery.release','commitment_id')
    committed_value=fields.Monetary(currency_field='currency_id'); released_value=fields.Monetary(compute='_compute_values'); delivered_value=fields.Monetary(compute='_compute_values'); remaining_value=fields.Monetary(compute='_compute_values')
    @api.depends('committed_value','release_ids.sale_order_id.amount_total','release_ids.sale_order_id.order_line.qty_delivered')
    def _compute_values(self):
        for r in self:
            r.released_value=sum(r.release_ids.mapped('sale_order_id.amount_total'))
            r.delivered_value=sum(sum(l.qty_delivered*l.price_unit for l in so.order_line) for so in r.release_ids.mapped('sale_order_id'))
            r.remaining_value=max(r.committed_value-r.released_value,0)



class SalesCommitmentLine(models.Model):
    _name='sales.commitment.line'; _description='Sales Commitment Line'
    commitment_id=fields.Many2one('sales.commitment',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); committed_qty=fields.Float(); unit_price=fields.Float()
class SalesDeliveryRelease(models.Model):
    _name='sales.delivery.release'; _description='Sales Delivery Release'; _order='id desc'
    name=fields.Char(default='New',readonly=True); commitment_id=fields.Many2one('sales.commitment',required=True,ondelete='cascade'); requested_date=fields.Date(default=fields.Date.context_today,required=True)
    line_ids=fields.One2many('sales.delivery.release.line','release_id'); sale_order_id=fields.Many2one('sale.order',readonly=True); state=fields.Selection([('draft','Draft'),('order','Sales Order Created')],default='draft')
    @api.model_create_multi
    def create(self,vals_list):
        for v in vals_list: v['name']=self.env['ir.sequence'].next_by_code('sales.delivery.release') or 'New'
        return super().create(vals_list)
    def action_create_sale_order(self):
        for r in self:
            if r.sale_order_id: continue
            if r.commitment_id.state not in ('approved','processing','reconciled','closed'): raise UserError(_('The sales commitment must be approved.'))
            so=self.env['sale.order'].create({'partner_id':r.commitment_id.customer_id.id,'origin':r.name,'payment_term_id':r.commitment_id.payment_term_id.id})
            for l in r.line_ids:
                self.env['sale.order.line'].create({'order_id':so.id,'product_id':l.product_id.id,'product_uom_qty':l.quantity,'price_unit':l.unit_price or l.product_id.lst_price})
            r.write({'sale_order_id':so.id,'state':'order'}); r.commitment_id.message_post(body=_('Sales Order %s created from release %s.')%(so.name,r.name))
        return True
class SalesDeliveryReleaseLine(models.Model):
    _name='sales.delivery.release.line'; _description='Sales Delivery Release Line'
    release_id=fields.Many2one('sales.delivery.release',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); quantity=fields.Float(required=True); unit_price=fields.Float()

