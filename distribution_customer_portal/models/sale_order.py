from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit='sale.order'

    distribution_portal_approved=fields.Boolean(string='Customer Signed Approval',readonly=True,tracking=True)
    distribution_signature=fields.Binary(string='Customer Signature',attachment=True,readonly=True)
    distribution_signed_by=fields.Char(readonly=True,tracking=True)
    distribution_signed_on=fields.Datetime(readonly=True,tracking=True)
    distribution_reorder_source_id=fields.Many2one('sale.order',readonly=True,copy=False)

    def action_distribution_portal_accept(self, signer, signature):
        self.ensure_one()
        if self.state not in ('draft','sent','sale'):
            raise UserError(_('Only an active quotation or sales order can be accepted.'))
        if self.distribution_portal_approved:
            raise UserError(_('This order already has a signed customer acceptance.'))
        if not signer or len(signer.strip()) < 2 or not signature:
            raise ValidationError(_('Signer name and signature are required.'))
        now=fields.Datetime.now()
        self.sudo().write({'distribution_portal_approved':True,'distribution_signature':signature,'distribution_signed_by':signer.strip(),'distribution_signed_on':now})
        self.message_post(body=_('Customer portal acceptance signed by %s at %s.')%(signer.strip(),now))
        return True

    def action_create_distribution_reorder(self):
        self.ensure_one()
        if self.state not in ('sale','done'):
            raise UserError(_('Reorders can only be created from confirmed or completed sales orders.'))
        values={'origin':_('Reorder of %s')%self.name,'state':'draft','date_order':fields.Datetime.now(),'distribution_reorder_source_id':self.id,'distribution_portal_approved':False,'distribution_signature':False,'distribution_signed_by':False,'distribution_signed_on':False}
        order=self.sudo().copy(values)
        order.message_post(body=_('Created through the customer portal as a reorder of %s.')%self.name)
        return order
