from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class BudgetControl(models.Model):
    _name='budget.control'
    _description='Budgets & Profitability'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='budget.control'
    process_key='budget'
    period_start=fields.Date(required=True); period_end=fields.Date(required=True); line_ids=fields.One2many('budget.control.line','budget_id'); budget_total=fields.Monetary(compute='_compute_total',currency_field='currency_id'); actual_total=fields.Monetary(compute='_compute_total',currency_field='currency_id'); variance_total=fields.Monetary(compute='_compute_total',currency_field='currency_id')
    closure_approver_id=fields.Many2one('res.users',readonly=True,tracking=True)
    closure_note=fields.Text(tracking=True)
    closure_requested_at=fields.Datetime(readonly=True)
    closure_approved_at=fields.Datetime(readonly=True)
    @api.depends('line_ids.budget_amount','line_ids.actual_amount')
    def _compute_total(self):
        for r in self:
            r.budget_total=sum(r.line_ids.mapped('budget_amount')); r.actual_total=sum(r.line_ids.mapped('actual_amount')); r.variance_total=r.actual_total-r.budget_total

    def _resolve_closure_approver(self):
        Matrix=self.env['distribution.approval.matrix'].sudo()
        for record in self:
            amount=abs(record.budget_total or record.amount or 0)
            domain=[('active','=',True),('company_id','=',record.company_id.id),('process_key','=','budget_close'),('min_amount','<=',amount),'|',('max_amount','=',0),('max_amount','>=',amount)]
            if record.department_id:
                domain += ['|',('department_id','=',False),('department_id','=',record.department_id.id)]
            if record.site_id:
                domain += ['|',('site_id','=',False),('site_id','=',record.site_id.id)]
            matrix=Matrix.search(domain,order='min_amount desc,department_id desc,site_id desc',limit=1)
            approver=matrix.final_approver_id or record.final_approver_id
            record.with_context(workflow_system=True).write({'closure_approver_id':approver.id if approver else False})

    def action_request_closure(self):
        for record in self:
            if record.state != 'reconciled':
                raise UserError(_('Only a reconciled budget can be submitted for closure approval.'))
            if not record.closure_note or len(record.closure_note.strip()) < 5:
                raise ValidationError(_('Enter a closure note explaining the final budget and variance position.'))
            record._resolve_closure_approver()
            if not record.closure_approver_id:
                raise UserError(_('No closure approver is configured. Add a budget_close approval matrix or final approver.'))
            old=record.state
            record.with_context(workflow_system=True).write({'state':'closure_requested','closure_requested_at':fields.Datetime.now()})
            record._event('Request Closure',old,'closure_requested',record.closure_note)
            record._notify_user(record.closure_approver_id,_('Budget closure approval required: %s')%record.name,_('Review the reconciled budget, final variance, and closure evidence.'))
        return True

    def action_approve_closure(self):
        for record in self:
            if record.state != 'closure_requested':
                raise UserError(_('Only a budget awaiting closure approval can be closed.'))
            if record.closure_approver_id != self.env.user and not self.env.user.has_group('workflow_approval.group_workflow_manager'):
                raise UserError(_('Only the assigned closure approver can close this budget.'))
            old=record.state
            now=fields.Datetime.now()
            record.with_context(workflow_system=True).write({'state':'closed','closed_at':now,'closure_approved_at':now})
            record._event('Approve Closure',old,'closed',record.closure_note)
            record._notify_user(record.initiator_id,_('Budget closed: %s')%record.name,_('The reconciled budget received closure approval.'))
        return True

    def action_close(self):
        return self.action_approve_closure()



class BudgetControlLine(models.Model):
    _name='budget.control.line'; _description='Budget Control Line'
    budget_id=fields.Many2one('budget.control',required=True,ondelete='cascade'); account_id=fields.Many2one('account.account'); product_id=fields.Many2one('product.product'); budget_amount=fields.Monetary(currency_field='currency_id'); actual_amount=fields.Monetary(currency_field='currency_id'); variance=fields.Monetary(compute='_compute_var',currency_field='currency_id'); currency_id=fields.Many2one('res.currency',related='budget_id.currency_id')
    @api.depends('budget_amount','actual_amount')
    def _compute_var(self):
        for r in self: r.variance=r.actual_amount-r.budget_amount
