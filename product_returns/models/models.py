from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ProductReturn(models.Model):
    _name='product.return'
    _description='Product Returns'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='product.return'
    process_key='product_return'
    return_direction=fields.Selection([('customer','Customer Return'),('vendor','Vendor Return')],required=True,default='customer'); partner_id=fields.Many2one('res.partner',required=True)
    original_sale_id=fields.Many2one('sale.order'); original_purchase_id=fields.Many2one('purchase.order'); original_picking_id=fields.Many2one('stock.picking')
    reason=fields.Selection([('damage','Damaged'),('expiry','Expired / Short Dated'),('quality','Quality'),('wrong','Wrong SKU'),('rejection','Customer Rejection'),('recall','Recall'),('other','Other')],required=True)
    source_location_id=fields.Many2one('stock.location'); quarantine_location_id=fields.Many2one('stock.location'); line_ids=fields.One2many('product.return.line','return_id')
    return_picking_id=fields.Many2one('stock.picking',readonly=True); customer_credit_note_id=fields.Many2one('account.move',readonly=True); supplier_credit_note_id=fields.Many2one('account.move',readonly=True)
    def action_create_return_picking(self):
        for r in self:
            if r.state!='approved': raise UserError(_('Return requires approval first.'))
            if r.return_picking_id: continue
            if not r.source_location_id or not r.quarantine_location_id: raise UserError(_('Source and quarantine locations are required.'))
            ptype=r.warehouse_id.int_type_id if r.warehouse_id else self.env['stock.picking.type'].search([('code','=','internal'),('company_id','=',r.company_id.id)],limit=1)
            p=self.env['stock.picking'].create({'picking_type_id':ptype.id,'location_id':r.source_location_id.id,'location_dest_id':r.quarantine_location_id.id,'origin':r.name})
            for l in r.line_ids:
                self.env['stock.move'].create({'product_id':l.product_id.id,'product_uom_qty':l.quantity,'product_uom':l.product_id.uom_id.id,'location_id':r.source_location_id.id,'location_dest_id':r.quarantine_location_id.id,'picking_id':p.id})
            p.action_confirm(); r.with_context(workflow_system=True).write({'return_picking_id':p.id}); r.action_start_processing()
        return True


class ProductReturnLine(models.Model):
    _name='product.return.line'; _description='Product Return Line'
    return_id=fields.Many2one('product.return',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); lot_id=fields.Many2one('stock.lot'); quantity=fields.Float(required=True); disposition=fields.Selection([('quarantine','Quarantine'),('resalable','Resalable'),('supplier','Return to Supplier'),('dispose','Dispose')],default='quarantine')
