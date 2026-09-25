from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

WORKFLOW_STATES=[('draft','Draft'),('submitted','Submitted'),('reviewed','Reviewed'),('approved','Approved'),('correction','Correction Required'),('rejected','Rejected'),('processing','Processing'),('reconciled','Reconciled'),('closure_requested','Closure Requested'),('closed','Closed'),('cancelled','Cancelled')]

class ApprovalMatrix(models.Model):
    _name='distribution.approval.matrix'; _description='Distribution Approval Matrix'; _order='process_key, company_id, min_amount desc'
    name=fields.Char(required=True); active=fields.Boolean(default=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company,index=True)
    process_key=fields.Char(required=True,index=True); department_id=fields.Many2one('hr.department'); site_id=fields.Many2one('distribution.site')
    min_amount=fields.Monetary(default=0); max_amount=fields.Monetary(default=0); currency_id=fields.Many2one('res.currency',related='company_id.currency_id')
    reviewer_id=fields.Many2one('res.users',required=True); final_approver_id=fields.Many2one('res.users',required=True); escalation_user_id=fields.Many2one('res.users')
    approval_hours=fields.Integer(default=24)

    @api.model
    def _cron_escalate_overdue_approvals(self):
        model_names=[
            'distribution.contract','purchase.commitment','sales.commitment','credit.application','sales.exception',
            'warehouse.control','returnable.asset.transaction','product.return','distribution.trip','cash.collection',
            'fleet.workshop.request','sales.commission.batch','budget.control','site.access.request','non.core.request',
        ]
        now=fields.Datetime.now()
        for model_name in model_names:
            if model_name not in self.env:
                continue
            # Use the model's own key so escalation matches the same matrix rows as _resolve_approvers
            process_key=self.env[model_name].process_key
            records=self.env[model_name].sudo().search([('state','in',('submitted','reviewed','closure_requested'))])
            for record in records:
                amount=record.amount or 0
                matrix=self.search([('active','=',True),('company_id','=',record.company_id.id),('process_key','in',(process_key,'budget_close') if record.state == 'closure_requested' else (process_key,)),('min_amount','<=',amount),'|',('max_amount','=',0),('max_amount','>=',amount)],order='min_amount desc',limit=1)
                hours=matrix.approval_hours or int(self.env['ir.config_parameter'].sudo().get_param('distribution.default_approval_hours','24'))
                started=record.reviewed_at if record.state == 'reviewed' else record.submitted_at
                if record.state == 'closure_requested' and 'closure_requested_at' in record._fields:
                    started=record.closure_requested_at
                if not started or started+relativedelta(hours=hours) > now:
                    continue
                assignee=matrix.escalation_user_id or (record.final_approver_id if record.state in ('reviewed','closure_requested') else record.reviewer_id)
                if not assignee:
                    continue
                summary=_('Overdue approval: %s')%record.display_name
                if not record.activity_ids.filtered(lambda activity:activity.summary == summary and activity.user_id == assignee):
                    record.activity_schedule('mail.mail_activity_data_todo',user_id=assignee.id,summary=summary,note=_('This approval exceeded its %s-hour target. Current stage: %s.')%(hours,record.state),date_deadline=fields.Date.context_today(record))
                    record.message_post(body=_('Approval escalation generated at %s for %s after exceeding the %s-hour target.')%(now,assignee.display_name,hours))

class WorkflowEvent(models.Model):
    _name='distribution.workflow.event'; _description='Immutable Workflow Event'; _order='event_at desc,id desc'
    document_model=fields.Char(required=True,index=True); document_id=fields.Integer(required=True,index=True); document_name=fields.Char(index=True)
    company_id=fields.Many2one('res.company',required=True,index=True); event_at=fields.Datetime(default=fields.Datetime.now,required=True,index=True)
    user_id=fields.Many2one('res.users',required=True,default=lambda s:s.env.user,index=True)
    from_state=fields.Char(); to_state=fields.Char(); action=fields.Char(required=True); note=fields.Text(); site_id=fields.Many2one('distribution.site')
    def unlink(self):
        if self.env.context.get('module_uninstall'):
            return super().unlink()
        raise UserError(_('Workflow audit events are immutable and cannot be deleted.'))
    def write(self, vals):
        if self.env.context.get('module_uninstall'):
            return super().write(vals)
        raise UserError(_('Workflow audit events are immutable and cannot be modified.'))

class ControlledWorkflow(models.AbstractModel):
    _name='distribution.controlled.workflow'; _description='Controlled Distribution Workflow'; _inherit=['mail.thread','mail.activity.mixin']
    name=fields.Char(default='New',readonly=True,copy=False,index=True,tracking=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company,index=True)
    initiator_id=fields.Many2one('res.users',default=lambda s:s.env.user,required=True,readonly=True,tracking=True)
    employee_id=fields.Many2one('hr.employee',readonly=True); department_id=fields.Many2one('hr.department',readonly=True,index=True)
    manager_id=fields.Many2one('res.users',readonly=True); reviewer_id=fields.Many2one('res.users',readonly=True,tracking=True); final_approver_id=fields.Many2one('res.users',readonly=True,tracking=True)
    region_id=fields.Many2one('distribution.region',readonly=True,index=True); site_id=fields.Many2one('distribution.site',readonly=True,index=True); warehouse_id=fields.Many2one('stock.warehouse',readonly=True)
    cost_center=fields.Char(readonly=True); process_date=fields.Date(default=fields.Date.context_today,required=True,index=True)
    state=fields.Selection(WORKFLOW_STATES,default='draft',required=True,index=True,tracking=True)
    submission_note=fields.Text(); review_note=fields.Text(); approval_note=fields.Text(); action_reason=fields.Text(tracking=True)
    submitted_at=fields.Datetime(readonly=True); reviewed_at=fields.Datetime(readonly=True); approved_at=fields.Datetime(readonly=True); closed_at=fields.Datetime(readonly=True)
    amount=fields.Monetary(currency_field='currency_id',tracking=True); currency_id=fields.Many2one('res.currency',related='company_id.currency_id',store=True)
    event_count=fields.Integer(compute='_compute_event_count')
    sequence_code='distribution.generic'; process_key='generic'

    @api.depends('name')
    def _compute_event_count(self):
        E=self.env['distribution.workflow.event']
        for r in self: r.event_count=E.search_count([('document_model','=',r._name),('document_id','=',r.id)]) if r.id else 0

    @api.model_create_multi
    def create(self, vals_list):
        employee=self.env['hr.employee'].sudo().search([('user_id','=',self.env.uid),('company_id','in',[False,self.env.company.id])],limit=1)
        for vals in vals_list:
            vals.setdefault('name', self.env['ir.sequence'].next_by_code(self.sequence_code) or _('New'))
            vals.setdefault('initiator_id', self.env.uid)
            if employee:
                vals.setdefault('employee_id',employee.id); vals.setdefault('department_id',employee.department_id.id)
                vals.setdefault('region_id',employee.distribution_region_id.id); vals.setdefault('site_id',employee.distribution_site_id.id)
                vals.setdefault('warehouse_id',employee.distribution_default_warehouse_id.id or employee.distribution_site_id.warehouse_id.id)
                vals.setdefault('cost_center',employee.distribution_cost_center)
                vals.setdefault('manager_id',employee.parent_id.user_id.id or employee.department_id.manager_id.user_id.id)
        recs=super().create(vals_list); recs._resolve_approvers(); return recs

    def _resolve_approvers(self):
        Matrix=self.env['distribution.approval.matrix'].sudo()
        for r in self:
            amount=r.amount or 0
            domain=[('active','=',True),('company_id','=',r.company_id.id),('process_key','=',r.process_key),('min_amount','<=',amount),'|',('max_amount','=',0),('max_amount','>=',amount)]
            if r.department_id: domain += ['|',('department_id','=',False),('department_id','=',r.department_id.id)]
            matrix=Matrix.search(domain,order='min_amount desc, department_id desc',limit=1)
            reviewer=matrix.reviewer_id or r.manager_id
            approver=matrix.final_approver_id or r.site_id.manager_id or r.region_id.manager_id
            r.with_context(workflow_system=True).write({'reviewer_id':reviewer.id if reviewer else False,'final_approver_id':approver.id if approver else False})

    def _event(self, action, old, new, note=None):
        for r in self:
            self.env['distribution.workflow.event'].sudo().create({'document_model':r._name,'document_id':r.id,'document_name':r.display_name,'company_id':r.company_id.id,'user_id':self.env.user.id,'from_state':old,'to_state':new,'action':action,'note':note,'site_id':r.site_id.id})

    def _notify_user(self,user,subject,body):
        if not user: return
        self.activity_schedule('mail.mail_activity_data_todo',user_id=user.id,summary=subject,note=body)
        self.message_post(body=body,subject=subject,partner_ids=user.partner_id.ids)
        if self.env['ir.config_parameter'].sudo().get_param('distribution.email_notifications','True') == 'True' and user.partner_id.email:
            self.env['mail.mail'].sudo().create({'subject':subject,'body_html':'<p>%s</p>' % body,'email_to':user.partner_id.email,'auto_delete':True})

    def _require_assignee(self,field):
        self.ensure_one(); user=getattr(self,field)
        if not user: raise UserError(_('No assigned user is configured for this action.'))
        if user != self.env.user and not self.env.user.has_group('workflow_approval.group_workflow_manager'):
            raise UserError(_('Only the assigned user can perform this action.'))

    def write(self, vals):
        if not self.env.context.get('workflow_system'):
            workflow_fields={'state','review_note','approval_note','action_reason','submitted_at','reviewed_at','approved_at','closed_at','reviewer_id','final_approver_id','closure_note','closure_approver_id','closure_requested_at','closure_approved_at'}
            for r in self:
                if r.state not in ('draft','correction') and any(k not in workflow_fields for k in vals):
                    if not self.env.user.has_group('workflow_approval.group_workflow_manager'):
                        raise UserError(_('This record is locked after submission. Return it for correction or use an authorised reopen process.'))
        return super().write(vals)

    def action_submit(self):
        for r in self:
            if r.state not in ('draft','correction'): raise UserError(_('Only Draft or Correction Required records can be submitted.'))
            r._resolve_approvers()
            if not r.reviewer_id: raise UserError(_('Reviewer is not configured. Check the employee manager or approval matrix.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'submitted','submitted_at':fields.Datetime.now(),'action_reason':False})
            r._event('Submit',old,'submitted',r.submission_note); r._notify_user(r.reviewer_id,_('Review required: %s')%r.name,_('A submitted request requires your review.'))
        return True
    def action_review(self):
        for r in self:
            r._require_assignee('reviewer_id')
            if r.state!='submitted': raise UserError(_('Only submitted records can be reviewed.'))
            if not r.final_approver_id: raise UserError(_('Final approver is not configured.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'reviewed','reviewed_at':fields.Datetime.now()})
            r._event('Review',old,'reviewed',r.review_note); r._notify_user(r.final_approver_id,_('Final approval required: %s')%r.name,_('The request has passed review and requires final approval.'))
        return True
    def action_approve(self):
        for r in self:
            r._require_assignee('final_approver_id')
            if r.state!='reviewed': raise UserError(_('Only reviewed records can receive final approval.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'approved','approved_at':fields.Datetime.now()})
            r._event('Approve',old,'approved',r.approval_note); r._notify_user(r.initiator_id,_('Approved: %s')%r.name,_('Your request received final approval.'))
        return True
    def action_return_correction(self):
        for r in self:
            if not r.action_reason: raise ValidationError(_('A correction reason is mandatory.'))
            if r.state=='submitted': r._require_assignee('reviewer_id')
            elif r.state=='reviewed': r._require_assignee('final_approver_id')
            else: raise UserError(_('This record cannot be returned from its current state.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'correction'})
            r._event('Return for Correction',old,'correction',r.action_reason); r._notify_user(r.initiator_id,_('Correction required: %s')%r.name,r.action_reason)
        return True
    def action_reject(self):
        for r in self:
            if not r.action_reason: raise ValidationError(_('A rejection reason is mandatory.'))
            if r.state=='submitted': r._require_assignee('reviewer_id')
            elif r.state=='reviewed': r._require_assignee('final_approver_id')
            else: raise UserError(_('This record cannot be rejected from its current state.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'rejected'})
            r._event('Reject',old,'rejected',r.action_reason); r._notify_user(r.initiator_id,_('Rejected: %s')%r.name,r.action_reason)
        return True
    def action_start_processing(self):
        for r in self:
            if r.state!='approved': raise UserError(_('Only approved records can start processing.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'processing'}); r._event('Start Processing',old,'processing')
        return True
    def action_reconcile(self):
        for r in self:
            if r.state!='processing': raise UserError(_('Only processing records can be reconciled.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'reconciled'}); r._event('Reconcile',old,'reconciled')
        return True
    def action_close(self):
        for r in self:
            if r.state not in ('approved','processing','reconciled'): raise UserError(_('Record is not ready for closure.'))
            old=r.state; r.with_context(workflow_system=True).write({'state':'closed','closed_at':fields.Datetime.now()}); r._event('Close',old,'closed')
        return True
    def action_open_reopen_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('workflow_approval.group_workflow_manager'):
            raise UserError(_('Only an authorised workflow manager can reopen a controlled record.'))
        if self.state == 'draft':
            raise UserError(_('A Draft record does not need to be reopened.'))
        return {
            'type':'ir.actions.act_window',
            'name':_('Reopen Controlled Record'),
            'res_model':'distribution.workflow.reopen.wizard',
            'view_mode':'form',
            'target':'new',
            'context':{'default_document_model':self._name,'default_document_id':self.id},
        }
    def action_view_events(self):
        self.ensure_one(); return {'type':'ir.actions.act_window','name':_('Approval History'),'res_model':'distribution.workflow.event','view_mode':'list,form','domain':[('document_model','=',self._name),('document_id','=',self.id)],'context':{'create':False}}


class WorkflowReopenWizard(models.TransientModel):
    _name='distribution.workflow.reopen.wizard'
    _description='Controlled Workflow Reopen'

    document_model=fields.Char(required=True,readonly=True)
    document_id=fields.Integer(required=True,readonly=True)
    target=fields.Selection([('previous','Previous Stage'),('draft','Initial Draft'),('correction','Correction Required')],required=True,default='previous')
    reason=fields.Text(required=True)
    downstream_acknowledged=fields.Boolean(string='I understand linked operational and accounting documents are preserved',required=True)

    def _target_state(self, record):
        if self.target != 'previous':
            return self.target
        latest=self.env['distribution.workflow.event'].sudo().search([
            ('document_model','=',record._name),('document_id','=',record.id),('to_state','=',record.state)
        ],order='event_at desc,id desc',limit=1)
        previous=latest.from_state if latest and latest.from_state else 'draft'
        return previous if previous in dict(WORKFLOW_STATES) else 'draft'

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('workflow_approval.group_workflow_manager'):
            raise UserError(_('Only an authorised workflow manager can reopen a controlled record.'))
        if not self.downstream_acknowledged:
            raise ValidationError(_('Acknowledge that linked downstream documents will be preserved.'))
        if not self.reason or len(self.reason.strip()) < 5:
            raise ValidationError(_('Enter a meaningful reopen reason of at least five characters.'))
        if self.document_model not in self.env:
            raise UserError(_('The source model is unavailable.'))
        record=self.env[self.document_model].browse(self.document_id).exists()
        if not record or not hasattr(record,'state') or not hasattr(record,'_event'):
            raise UserError(_('The controlled record no longer exists.'))
        old=record.state
        new=self._target_state(record)
        if old == new:
            raise UserError(_('The selected target is already the current stage.'))
        values={'state':new,'action_reason':self.reason.strip()}
        if new == 'draft':
            values.update({'submitted_at':False,'reviewed_at':False,'approved_at':False,'closed_at':False})
        elif new != 'closed':
            values['closed_at']=False
        record.with_context(workflow_system=True).write(values)
        record._event('Reopen / Reset',old,new,self.reason.strip())
        record.message_post(body=_('Record reopened from %s to %s by %s. Reason: %s') % (old,new,self.env.user.display_name,self.reason.strip()))
        users=(record.initiator_id|record.reviewer_id|record.final_approver_id).filtered(lambda u:u and u!=self.env.user)
        for user in users:
            record._notify_user(user,_('Record reopened: %s')%record.display_name,_('The record was reopened to %s. Reason: %s')%(new,self.reason.strip()))
        return {'type':'ir.actions.act_window_close'}
