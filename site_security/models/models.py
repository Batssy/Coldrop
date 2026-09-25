from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class SiteAccessRequest(models.Model):
    _name='site.access.request'
    _description='Site & Security'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='site.access.request'
    process_key='site_access'
    access_type=fields.Selection([('visitor','Visitor'),('contractor','Contractor'),('vehicle','Vehicle'),('supplier','Supplier Delivery'),('dispatch','Dispatch Exit'),('return','Return Entry')],required=True,default='visitor'); person_name=fields.Char(); partner_id=fields.Many2one('res.partner'); vehicle_registration=fields.Char(); host_user_id=fields.Many2one('res.users'); expected_entry=fields.Datetime(); actual_entry=fields.Datetime(); actual_exit=fields.Datetime(); purpose=fields.Char(required=True); pass_reference=fields.Char()



