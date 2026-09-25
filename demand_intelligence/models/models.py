from datetime import timedelta
from odoo import api, fields, models, _

class DemandForecast(models.Model):
    _name='demand.forecast'; _description='Demand Forecast'; _inherit=['mail.thread','mail.activity.mixin']; _order='forecast_date desc,id desc'
    name=fields.Char(default='New',readonly=True); company_id=fields.Many2one('res.company',default=lambda s:s.env.company,required=True); site_id=fields.Many2one('distribution.site'); warehouse_id=fields.Many2one('stock.warehouse'); forecast_date=fields.Date(default=fields.Date.context_today,required=True); horizon_days=fields.Integer(default=30); line_ids=fields.One2many('demand.forecast.line','forecast_id')
    @api.model_create_multi
    def create(self, vals_list):
        for v in vals_list: v['name']=self.env['ir.sequence'].next_by_code('demand.forecast') or 'New'
        return super().create(vals_list)
    def action_generate(self):
        SOL=self.env['sale.order.line']; Quant=self.env['stock.quant']; POL=self.env['purchase.order.line']; SCL=self.env['sales.commitment.line']
        today=fields.Date.context_today(self)
        for rec in self:
            rec.line_ids.unlink()
            products=self.env['product.product'].search([('product_tmpl_id.business_line','=','beverage'),('active','=',True)])
            for p in products:
                start=today-timedelta(days=max(rec.horizon_days*3,90))
                hist_lines=SOL.search([('product_id','=',p.id),('order_id.state','in',('sale','done')),('order_id.date_order','>=',start)])
                hist_qty=sum(hist_lines.mapped('qty_delivered')) or sum(hist_lines.mapped('product_uom_qty'))
                daily=hist_qty/max((today-start).days,1); baseline=daily*rec.horizon_days
                committed=sum(SCL.search([('product_id','=',p.id),('commitment_id.state','in',('approved','processing'))]).mapped('committed_qty'))
                location=rec.warehouse_id.lot_stock_id if rec.warehouse_id else False
                qdom=[('product_id','=',p.id)]+([('location_id','child_of',location.id)] if location else [('location_id.usage','=','internal')])
                onhand=sum(Quant.search(qdom).mapped('available_quantity'))
                incoming=sum(POL.search([('product_id','=',p.id),('order_id.state','in',('purchase','done'))]).mapped(lambda x:max(x.product_qty-x.qty_received,0)))
                demand=max(baseline,committed); safety=daily*7; recommended=max(demand+safety-onhand-incoming,0)
                self.env['demand.forecast.line'].create({'forecast_id':rec.id,'product_id':p.id,'historical_qty':hist_qty,'baseline_forecast':baseline,'committed_demand':committed,'recommended_forecast':demand,'onhand_qty':onhand,'incoming_qty':incoming,'safety_stock':safety,'recommended_purchase_qty':recommended,'confidence':'high' if hist_qty>100 else ('medium' if hist_qty>20 else 'low')})
        return True
class DemandForecastLine(models.Model):
    _name='demand.forecast.line'; _description='Demand Forecast Line'; _order='recommended_purchase_qty desc'
    forecast_id=fields.Many2one('demand.forecast',required=True,ondelete='cascade'); product_id=fields.Many2one('product.product',required=True); historical_qty=fields.Float(); baseline_forecast=fields.Float(); committed_demand=fields.Float(); recommended_forecast=fields.Float(); onhand_qty=fields.Float(); incoming_qty=fields.Float(); safety_stock=fields.Float(); recommended_purchase_qty=fields.Float(); confidence=fields.Selection([('high','High'),('medium','Medium'),('low','Low')])
