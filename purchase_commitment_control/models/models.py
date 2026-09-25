from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class PurchaseCommitment(models.Model):
    _name='purchase.commitment'
    _description='Purchase Commitments'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='purchase.commitment'
    process_key='purchase_commitment'
    vendor_id=fields.Many2one('res.partner',required=True,domain="[('supplier_rank','>',0)]",tracking=True)
    start_date=fields.Date(required=True); end_date=fields.Date(required=True); commitment_type=fields.Selection([('quantity','Quantity'),('value','Value'),('hybrid','Hybrid')],default='hybrid',required=True)
    line_ids=fields.One2many('purchase.commitment.line','commitment_id'); calloff_ids=fields.One2many('purchase.calloff','commitment_id')
    committed_value=fields.Monetary(currency_field='currency_id'); called_off_value=fields.Monetary(compute='_compute_values'); received_value=fields.Monetary(compute='_compute_values'); remaining_value=fields.Monetary(compute='_compute_values')
    @api.depends('committed_value','calloff_ids.purchase_order_id.amount_total','calloff_ids.purchase_order_id.order_line.qty_received')
    def _compute_values(self):
        for r in self:
            r.called_off_value=sum(r.calloff_ids.mapped('purchase_order_id.amount_total'))
            r.received_value=sum(sum(l.qty_received*l.price_unit for l in po.order_line) for po in r.calloff_ids.mapped('purchase_order_id'))
            r.remaining_value=max(r.committed_value-r.called_off_value,0)



class PurchaseCommitmentLine(models.Model):
    _name='purchase.commitment.line'; _description='Purchase Commitment Line'
    commitment_id=fields.Many2one('purchase.commitment',required=True,ondelete='cascade')
    product_id=fields.Many2one('product.product',required=True); committed_qty=fields.Float(default=0); unit_price=fields.Float(default=0)
    called_off_qty=fields.Float(compute='_compute_called',store=False); received_qty=fields.Float(compute='_compute_called',store=False)
    @api.depends('commitment_id.calloff_ids.purchase_order_id.order_line.qty_received')
    def _compute_called(self):
        for l in self:
            pols=l.commitment_id.calloff_ids.mapped('purchase_order_id.order_line').filtered(lambda x:x.product_id==l.product_id)
            l.called_off_qty=sum(pols.mapped('product_qty')); l.received_qty=sum(pols.mapped('qty_received'))

class PurchaseCalloff(models.Model):
    _name='purchase.calloff'; _description='Purchase Call-Off'; _order='id desc'
    name=fields.Char(default='New',readonly=True); commitment_id=fields.Many2one('purchase.commitment',required=True,ondelete='cascade')
    requested_date=fields.Date(required=True,default=fields.Date.context_today); warehouse_id=fields.Many2one('stock.warehouse',required=True)
    line_ids=fields.One2many('purchase.calloff.line','calloff_id'); purchase_order_id=fields.Many2one('purchase.order',readonly=True); state=fields.Selection([('draft','Draft'),('po','PO Created')],default='draft')
    @api.model_create_multi
    def create(self,vals_list):
        for v in vals_list: v['name']=self.env['ir.sequence'].next_by_code('purchase.calloff') or 'New'
        return super().create(vals_list)
    def action_create_po(self):
        for r in self:
            if r.purchase_order_id: continue
            if r.commitment_id.state not in ('approved','processing','reconciled','closed'): raise UserError(_('The purchase commitment must be approved.'))
            po=self.env['purchase.order'].create({'partner_id':r.commitment_id.vendor_id.id,'date_planned':fields.Datetime.now(),'picking_type_id':r.warehouse_id.in_type_id.id,'origin':r.name})
            for l in r.line_ids:
                self.env['purchase.order.line'].create({'order_id':po.id,'product_id':l.product_id.id,'product_qty':l.quantity,'price_unit':l.unit_price or l.product_id.standard_price,'date_planned':fields.Datetime.now()})
            r.write({'purchase_order_id':po.id,'state':'po'}); r.commitment_id.message_post(body=_('Purchase Order %s created from call-off %s.')%(po.name,r.name))
        return True
class PurchaseCalloffLine(models.Model):
    _name='purchase.calloff.line'; _description='Purchase Call-Off Line'
    calloff_id=fields.Many2one('purchase.calloff',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); quantity=fields.Float(required=True); unit_price=fields.Float()

