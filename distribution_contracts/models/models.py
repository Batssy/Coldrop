from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class DistributionContract(models.Model):
    _name='distribution.contract'
    _description='Contracts'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='distribution.contract'
    process_key='contracts'
    contract_type=fields.Selection([('supplier','Supplier'),('customer','Customer'),('chain','Customer Chain')],required=True,default='customer',tracking=True)
    partner_id=fields.Many2one('res.partner',required=True,tracking=True)
    start_date=fields.Date(required=True); end_date=fields.Date(required=True)
    territory=fields.Char(); payment_term_id=fields.Many2one('account.payment.term')
    credit_limit=fields.Monetary(currency_field='currency_id'); returnables_required=fields.Boolean(default=True)
    version=fields.Integer(default=1,readonly=True); terms=fields.Html()



