from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class WarehouseControl(models.Model):
    _name='warehouse.control'
    _description='Warehouse Control'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='warehouse.control'
    process_key='warehouse_control'
    operation_type=fields.Selection([('transfer','Controlled Transfer'),('quarantine','Quarantine'),('release','Release from Quarantine'),('writeoff','Write-Off Request')],required=True,default='transfer')
    picking_type_id=fields.Many2one('stock.picking.type',required=True); source_location_id=fields.Many2one('stock.location',required=True); destination_location_id=fields.Many2one('stock.location',required=True)
    line_ids=fields.One2many('warehouse.control.line','control_id'); picking_id=fields.Many2one('stock.picking',readonly=True)
    def action_create_transfer(self):
        for r in self:
            if r.state!='approved': raise UserError(_('Approval is required before creating the transfer.'))
            if r.picking_id: continue
            picking=self.env['stock.picking'].create({'picking_type_id':r.picking_type_id.id,'location_id':r.source_location_id.id,'location_dest_id':r.destination_location_id.id,'origin':r.name})
            for l in r.line_ids:
                self.env['stock.move'].create({'product_id':l.product_id.id,'product_uom_qty':l.quantity,'product_uom':l.product_id.uom_id.id,'location_id':r.source_location_id.id,'location_dest_id':r.destination_location_id.id,'picking_id':picking.id})
            r.with_context(workflow_system=True).write({'picking_id':picking.id}); picking.action_confirm(); r.action_start_processing()
        return True


class WarehouseControlLine(models.Model):
    _name='warehouse.control.line'; _description='Warehouse Control Line'
    control_id=fields.Many2one('warehouse.control',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); quantity=fields.Float(required=True); lot_id=fields.Many2one('stock.lot')
