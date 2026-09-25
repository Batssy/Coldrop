from odoo import fields, models, _


PROCESS_MODELS=[
    ('distribution.contract','Contracts'),('purchase.commitment','Purchase Commitments'),('sales.commitment','Sales Commitments'),
    ('credit.application','Credit Applications'),('sales.exception','Sales Exceptions'),('warehouse.control','Warehouse Controls'),
    ('returnable.asset.transaction','Returnable Assets'),('product.return','Product Returns'),('distribution.trip','Distribution Trips'),
    ('cash.collection','Cash and Collections'),('fleet.workshop.request','Fleet Workshop'),('sales.commission.batch','Sales Commissions'),
    ('budget.control','Budgets and Profitability'),('site.access.request','Site and Security'),('non.core.request','Non-Core Business'),
]


class DistributionOperationalReportWizard(models.TransientModel):
    _name='distribution.operational.report.wizard'
    _description='Distribution Operational Report'

    process_model=fields.Selection(PROCESS_MODELS,required=True,default='sales.commitment')
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    site_id=fields.Many2one('distribution.site')
    date_from=fields.Date()
    date_to=fields.Date()
    state=fields.Selection([('draft','Draft'),('submitted','Submitted'),('reviewed','Reviewed'),('approved','Approved'),('correction','Correction Required'),('rejected','Rejected'),('processing','Processing'),('reconciled','Reconciled'),('closure_requested','Closure Requested'),('closed','Closed'),('cancelled','Cancelled')])
    include_event_details=fields.Boolean(default=True)

    def _domain(self):
        self.ensure_one()
        domain=[('company_id','=',self.company_id.id)]
        if self.site_id: domain.append(('site_id','=',self.site_id.id))
        if self.date_from: domain.append(('process_date','>=',self.date_from))
        if self.date_to: domain.append(('process_date','<=',self.date_to))
        if self.state: domain.append(('state','=',self.state))
        return domain

    def report_rows(self):
        self.ensure_one()
        events=self.env['distribution.workflow.event'].sudo()
        rows=[]
        for record in self.env[self.process_model].sudo().search(self._domain(),order='process_date desc,id desc'):
            history=events.search([('document_model','=',self.process_model),('document_id','=',record.id)],order='event_at,id')
            rows.append({'name':record.display_name,'date':record.process_date,'state':dict(record._fields['state'].selection).get(record.state,record.state),'site':record.site_id.display_name or '','initiator':record.initiator_id.display_name or '','reviewer':record.reviewer_id.display_name or '','approver':record.final_approver_id.display_name or '','amount':record.amount,'currency':record.currency_id.name or '','event_count':len(history),'latest_event':history[-1].event_at if history else False,'events':history if self.include_event_details else events.browse()})
        return rows

    def action_open(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','name':dict(PROCESS_MODELS)[self.process_model],'res_model':self.process_model,'view_mode':'list,form,pivot,graph','domain':self._domain(),'context':{'create':False}}

    def action_print(self):
        self.ensure_one()
        return self.env.ref('distribution_reporting.action_distribution_operational_report').report_action(self)
