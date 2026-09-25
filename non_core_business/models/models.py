from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class NonCoreRequest(models.Model):
    _name='non.core.request'
    _description='Non-Core Business'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='non.core.request'
    process_key='non_core'
    request_type=fields.Selection([('purchase','Purchase'),('sale','Sale'),('issue','Internal Issue'),('service','Service')],required=True,default='purchase'); partner_id=fields.Many2one('res.partner'); product_id=fields.Many2one('product.product',domain="[('product_tmpl_id.business_line','in',('non_core','service'))]"); quantity=fields.Float(default=1); unit_price=fields.Monetary(currency_field='currency_id'); purpose=fields.Text(required=True)



