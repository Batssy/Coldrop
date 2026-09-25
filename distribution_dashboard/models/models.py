from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class SalesPerformanceTarget(models.Model):
    _name='sales.performance.target'
    _description='Monthly Sales Performance Target'
    _order='period_start desc,salesperson_id'

    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company,index=True)
    currency_id=fields.Many2one('res.currency',related='company_id.currency_id')
    site_id=fields.Many2one('distribution.site',index=True)
    salesperson_id=fields.Many2one('res.users',required=True,index=True)
    period_start=fields.Date(required=True,index=True)
    period_end=fields.Date(required=True,index=True)
    target_amount=fields.Monetary(required=True,currency_field='currency_id')
    target_new_customers=fields.Integer(default=0)
    active=fields.Boolean(default=True)

    _target_period_user_uniq=models.Constraint(
        'UNIQUE (company_id, salesperson_id, site_id, period_start, period_end)',
        'Only one target is allowed per salesperson, site, and period.',
    )


class DistributionDashboard(models.TransientModel):
    _name='distribution.dashboard'
    _description='Distribution Control Tower'

    company_id=fields.Many2one('res.company',default=lambda self:self.env.company,required=True)
    site_id=fields.Many2one('distribution.site')
    purchase_commitment=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    sales_commitment=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    returnables_value=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    cash_unreconciled=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    pending_approvals=fields.Integer(compute='_compute_kpis')
    product_returns_open=fields.Integer(compute='_compute_kpis')
    active_trips=fields.Integer(compute='_compute_kpis')
    purchase_recommended_qty=fields.Float(compute='_compute_kpis')
    monthly_sales_actual=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    monthly_sales_target=fields.Monetary(compute='_compute_kpis',currency_field='currency_id')
    monthly_target_achievement=fields.Float(compute='_compute_kpis')
    sales_champion_user_id=fields.Many2one('res.users',compute='_compute_kpis',string='Sales Champion This Month')
    previous_champion_user_id=fields.Many2one('res.users',compute='_compute_kpis',string='Sales Champion Previous Month')
    new_customers_month=fields.Integer(compute='_compute_kpis')
    new_customers_quarter=fields.Integer(compute='_compute_kpis')
    currency_id=fields.Many2one('res.currency',related='company_id.currency_id')

    def _sale_domain(self,start,end):
        domain=[('company_id','=',self.company_id.id),('state','in',('sale','done')),('date_order','>=',fields.Datetime.to_datetime(start)),('date_order','<',fields.Datetime.to_datetime(end))]
        if self.site_id:
            routes=self.env['distribution.route'].search([('site_id','=',self.site_id.id)])
            salespeople=routes.mapped('salesperson_id')
            domain.append(('user_id','in',salespeople.ids or [0]))
        return domain

    def _champion(self,start,end):
        groups=self.env['sale.order']._read_group(self._sale_domain(start,end),['user_id'],['amount_total:sum'],order='amount_total:sum desc',limit=1)
        return groups[0][0] if groups and groups[0][0] else self.env['res.users']

    @api.depends('company_id','site_id')
    def _compute_kpis(self):
        controlled_models=('distribution.contract','purchase.commitment','sales.commitment','credit.application','sales.exception','warehouse.control','returnable.asset.transaction','product.return','distribution.trip','cash.collection','fleet.workshop.request','sales.commission.batch','budget.control','site.access.request','non.core.request')
        for record in self:
            site_domain=[('site_id','=',record.site_id.id)] if record.site_id else []
            company_domain=[('company_id','=',record.company_id.id)]
            record.purchase_commitment=sum(self.env['purchase.commitment'].search(company_domain+[('state','in',('approved','processing','reconciled'))]+site_domain).mapped('remaining_value'))
            record.sales_commitment=sum(self.env['sales.commitment'].search(company_domain+[('state','in',('approved','processing','reconciled'))]+site_domain).mapped('remaining_value'))
            record.returnables_value=sum(self.env['returnable.asset.transaction'].search(company_domain+[('state','not in',('cancelled','rejected'))]+site_domain).mapped('asset_value'))
            record.cash_unreconciled=sum(self.env['cash.collection'].search(company_domain+[('state','not in',('reconciled','closed','cancelled','rejected'))]+site_domain).mapped('amount_collected'))
            record.product_returns_open=self.env['product.return'].search_count(company_domain+[('state','not in',('closed','cancelled','rejected'))]+site_domain)
            record.active_trips=self.env['distribution.trip'].search_count(company_domain+[('state','in',('approved','processing'))]+site_domain)
            record.pending_approvals=sum(self.env[model].search_count(company_domain+[('state','in',('submitted','reviewed','closure_requested'))]+site_domain) for model in controlled_models)
            forecasts=self.env['demand.forecast'].search(company_domain+site_domain,order='forecast_date desc',limit=1)
            record.purchase_recommended_qty=sum(forecasts.line_ids.mapped('recommended_purchase_qty')) if forecasts else 0

            today=fields.Date.context_today(record)
            month_start=today.replace(day=1)
            next_month=month_start+relativedelta(months=1)
            previous_month=month_start-relativedelta(months=1)
            sales=self.env['sale.order'].search(record._sale_domain(month_start,next_month))
            record.monthly_sales_actual=sum(sales.mapped('amount_total'))
            target_domain=company_domain+[('active','=',True),('period_start','<=',today),('period_end','>=',today)]
            if record.site_id:
                target_domain += [('site_id','in',[False,record.site_id.id])]
            record.monthly_sales_target=sum(self.env['sales.performance.target'].search(target_domain).mapped('target_amount'))
            record.monthly_target_achievement=(record.monthly_sales_actual*100/record.monthly_sales_target) if record.monthly_sales_target else 0
            record.sales_champion_user_id=record._champion(month_start,next_month)
            record.previous_champion_user_id=record._champion(previous_month,month_start)
            customer_domain=[('customer_rank','>',0),('distribution_onboarded_on','>=',month_start),('distribution_onboarded_on','<',next_month)]
            if record.site_id:
                customer_domain.append(('distribution_site_id','=',record.site_id.id))
            record.new_customers_month=self.env['res.partner'].search_count(customer_domain)
            quarter_start=month_start-relativedelta(months=(month_start.month-1)%3)
            quarter_domain=[('customer_rank','>',0),('distribution_onboarded_on','>=',quarter_start),('distribution_onboarded_on','<',quarter_start+relativedelta(months=3))]
            if record.site_id:
                quarter_domain.append(('distribution_site_id','=',record.site_id.id))
            record.new_customers_quarter=self.env['res.partner'].search_count(quarter_domain)

    def _scoped_domain(self,extra=None):
        domain=[('company_id','=',self.company_id.id)]
        if self.site_id:
            domain.append(('site_id','=',self.site_id.id))
        return domain+(extra or [])

    def _open(self,model,domain,name,view_mode='list,form'):
        return {'type':'ir.actions.act_window','name':name,'res_model':model,'view_mode':view_mode,'domain':domain,'context':{'create':False}}

    def action_purchase(self): return self._open('purchase.commitment',self._scoped_domain([('state','in',('approved','processing','reconciled'))]),_('Purchase Commitments'))
    def action_sales(self): return self._open('sales.commitment',self._scoped_domain([('state','in',('approved','processing','reconciled'))]),_('Sales Commitments'))
    def action_returns(self): return self._open('product.return',self._scoped_domain([('state','not in',('closed','cancelled','rejected'))]),_('Open Product Returns'))
    def action_trips(self): return self._open('distribution.trip',self._scoped_domain([('state','in',('approved','processing'))]),_('Active Trips'))
    def action_cash(self): return self._open('cash.collection',self._scoped_domain([('state','not in',('reconciled','closed','cancelled','rejected'))]),_('Unreconciled Collections'))
    def action_returnables(self): return self._open('returnable.asset.transaction',self._scoped_domain(),_('Returnable Assets'))
    def action_month_sales(self):
        today=fields.Date.context_today(self); start=today.replace(day=1); end=start+relativedelta(months=1)
        return self._open('sale.order',self._sale_domain(start,end),_('Current Month Sales'),'list,pivot,graph,form')
    def action_new_customers(self):
        today=fields.Date.context_today(self); start=today.replace(day=1); end=start+relativedelta(months=1)
        domain=[('customer_rank','>',0),('distribution_onboarded_on','>=',start),('distribution_onboarded_on','<',end)]
        if self.site_id: domain.append(('distribution_site_id','=',self.site_id.id))
        return self._open('res.partner',domain,_('New Customers This Month'))

    @api.model
    def action_open_dashboard(self):
        record=self.create({'company_id':self.env.company.id})
        return {'type':'ir.actions.act_window','name':_('Distribution Control Tower'),'res_model':'distribution.dashboard','view_mode':'form','res_id':record.id,'target':'current','context':{'create':False,'edit':False}}
