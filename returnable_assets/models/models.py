from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class ReturnableAssetTransaction(models.Model):
    _name='returnable.asset.transaction'
    _description='Returnable Assets'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='returnable.asset.transaction'
    process_key='returnables'
    transaction_type=fields.Selection([('supplier_receipt','Supplier Receipt'),('customer_issue','Customer Issue'),('customer_collection','Empty Collection'),('driver_issue','Driver Custody'),('driver_return','Driver Return'),('supplier_return','Supplier Return'),('breakage','Breakage/Loss')],required=True,default='customer_issue')
    partner_id=fields.Many2one('res.partner',tracking=True); driver_id=fields.Many2one('hr.employee',domain="[('is_distribution_driver','=',True),('active','=',True)]"); route_id=fields.Many2one('distribution.route')
    asset_product_id=fields.Many2one('product.product',required=True,domain="[('product_tmpl_id.returnable_asset','=',True)]"); quantity=fields.Float(required=True); asset_value=fields.Monetary(currency_field='currency_id')
    source_location_id=fields.Many2one('stock.location'); destination_location_id=fields.Many2one('stock.location'); picking_id=fields.Many2one('stock.picking',readonly=True); supplier_credit_move_id=fields.Many2one('account.move',readonly=True)
    @api.onchange('asset_product_id','quantity')
    def _onchange_value(self):
        for r in self:
            if r.asset_product_id: r.asset_value=(r.asset_product_id.product_tmpl_id.replacement_value or r.asset_product_id.product_tmpl_id.deposit_value)*r.quantity
    def action_start_processing(self):
        for r in self:
            super(ReturnableAssetTransaction,r).action_start_processing()
            if r.source_location_id and r.destination_location_id and not r.picking_id:
                ptype=r.warehouse_id.int_type_id if r.warehouse_id else self.env['stock.picking.type'].search([('code','=','internal'),('company_id','=',r.company_id.id)],limit=1)
                if ptype:
                    p=self.env['stock.picking'].create({'picking_type_id':ptype.id,'location_id':r.source_location_id.id,'location_dest_id':r.destination_location_id.id,'origin':r.name})
                    self.env['stock.move'].create({'product_id':r.asset_product_id.id,'product_uom_qty':r.quantity,'product_uom':r.asset_product_id.uom_id.id,'location_id':r.source_location_id.id,'location_dest_id':r.destination_location_id.id,'picking_id':p.id}); p.action_confirm(); r.with_context(workflow_system=True).write({'picking_id':p.id})
        return True
