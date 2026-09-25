from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class DistributionTrip(models.Model):
    _name='distribution.trip'
    _description='Distribution Trips'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='distribution.trip'
    process_key='trip'
    route_id=fields.Many2one('distribution.route',required=True); vehicle_id=fields.Many2one('fleet.vehicle',required=True); driver_id=fields.Many2one('hr.employee',required=True,domain="[('is_distribution_driver','=',True),('active','=',True)]")
    planned_departure=fields.Datetime(); actual_departure=fields.Datetime(); actual_return=fields.Datetime(); odometer_start=fields.Float(); odometer_end=fields.Float(); fuel_issued=fields.Float(); fuel_consumed=fields.Float()
    stop_ids=fields.One2many('distribution.trip.stop','trip_id'); loaded_value=fields.Monetary(currency_field='currency_id'); cash_expected=fields.Monetary(currency_field='currency_id'); cash_collected=fields.Monetary(compute='_compute_cash',currency_field='currency_id')
    @api.depends('stop_ids.cash_collected')
    def _compute_cash(self):
        for r in self: r.cash_collected=sum(r.stop_ids.mapped('cash_collected'))



class DistributionTripStop(models.Model):
    _name='distribution.trip.stop'; _description='Distribution Trip Stop'; _order='sequence,id'
    trip_id=fields.Many2one('distribution.trip',required=True,ondelete='cascade'); sequence=fields.Integer(default=10); customer_id=fields.Many2one('res.partner',required=True); sale_order_id=fields.Many2one('sale.order'); picking_id=fields.Many2one('stock.picking'); planned_arrival=fields.Datetime(); actual_arrival=fields.Datetime(); actual_departure=fields.Datetime(); geofence_status=fields.Selection([('pending','Pending'),('verified','Verified'),('outside','Outside Geofence'),('unverified','Unverified')],default='pending'); pod_reference=fields.Char(); cash_collected=fields.Monetary(currency_field='currency_id'); currency_id=fields.Many2one('res.currency',related='trip_id.currency_id')
