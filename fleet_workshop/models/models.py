from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class FleetWorkshopRequest(models.Model):
    _name='fleet.workshop.request'
    _description='Fleet Workshop'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='fleet.workshop.request'
    process_key='fleet_maintenance'
    vehicle_id=fields.Many2one('fleet.vehicle',required=True); reported_by_id=fields.Many2one('hr.employee'); defect_description=fields.Text(required=True); severity=fields.Selection([('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')],default='medium',required=True); diagnosis=fields.Text(); estimated_cost=fields.Monetary(currency_field='currency_id'); service_log_id=fields.Many2one('fleet.vehicle.log.services',readonly=True)
    def action_log_service(self):
        for r in self:
            if r.state!='approved': raise UserError(_('Approval is required before logging service.'))
            if r.service_log_id: continue
            log=self.env['fleet.vehicle.log.services'].create({'vehicle_id':r.vehicle_id.id,'date':r.process_date,'amount':r.estimated_cost,'description':r.diagnosis or r.defect_description})
            r.with_context(workflow_system=True).write({'service_log_id':log.id}); r.action_start_processing()
        return True


