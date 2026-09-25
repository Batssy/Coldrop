import base64

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError


class DistributionCustomerPortal(http.Controller):
    def _partner(self):
        return request.env.user.partner_id.commercial_partner_id

    def _order(self, order_id):
        partner=self._partner()
        return request.env['sale.order'].sudo().search([('id','=',order_id),('partner_id.commercial_partner_id','=',partner.id)],limit=1)

    @http.route('/my/distribution',type='http',auth='user',website=True)
    def portal_distribution(self, **kwargs):
        partner=self._partner()
        orders=request.env['sale.order'].sudo().search([('partner_id.commercial_partner_id','=',partner.id)],order='date_order desc',limit=50)
        invoices=request.env['account.move'].sudo().search([('commercial_partner_id','=',partner.id),('move_type','in',('out_invoice','out_refund')),('state','=','posted')],order='invoice_date desc,id desc',limit=50)
        balance=sum(invoices.mapped('amount_residual_signed'))
        message=request.session.pop('distribution_portal_message',False)
        return request.render('distribution_customer_portal.portal_distribution_home',{'orders':orders,'invoices':invoices,'statement_balance':balance,'portal_message':message,'page_name':'distribution'})

    @http.route('/my/distribution/order/<int:order_id>/reorder',type='http',auth='user',website=True,methods=['POST'],csrf=True)
    def portal_reorder(self, order_id, **post):
        order=self._order(order_id)
        if not order:
            return request.not_found()
        try:
            new_order=order.action_create_distribution_reorder()
            request.session['distribution_portal_message']=_('Reorder quotation %s was created for internal review.')%new_order.name
        except (UserError,ValidationError) as error:
            request.session['distribution_portal_message']=str(error)
        return request.redirect('/my/distribution')

    @http.route('/my/distribution/order/<int:order_id>/accept',type='http',auth='user',website=True,methods=['POST'],csrf=True)
    def portal_accept(self, order_id, signer=None, signature=None, **post):
        order=self._order(order_id)
        if not order:
            return request.not_found()
        try:
            encoded=signature.split(',',1)[1] if signature and ',' in signature else signature
            if encoded:
                base64.b64decode(encoded,validate=True)
            order.action_distribution_portal_accept(signer,encoded)
            request.session['distribution_portal_message']=_('Signed acceptance recorded for %s.')%order.name
        except (ValueError,UserError,ValidationError) as error:
            request.session['distribution_portal_message']=str(error)
        return request.redirect('/my/distribution')
