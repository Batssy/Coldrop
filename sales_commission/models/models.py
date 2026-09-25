from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SalesCommissionPlan(models.Model):
    _name='sales.commission.plan'
    _description='Sales Commission Plan'
    _order='sequence,name'

    name=fields.Char(required=True)
    active=fields.Boolean(default=True)
    sequence=fields.Integer(default=10)
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    currency_id=fields.Many2one('res.currency',related='company_id.currency_id')
    date_start=fields.Date()
    date_end=fields.Date()
    salesperson_ids=fields.Many2many('res.users',string='Eligible Salespeople')
    employment_type=fields.Selection([('all','All'),('full_time','Full Time'),('contract','Contract'),('temporary','Temporary'),('agent','Sales Agent')],default='all',required=True)
    basis=fields.Selection([('ordered','Confirmed Sales'),('delivered','Delivered Sales'),('invoiced','Invoiced Sales'),('paid','Paid Sales')],default='paid',required=True)
    rate_type=fields.Selection([('per_unit','Amount per Unit'),('percentage','Percentage of Net Sales')],default='percentage',required=True)
    rate=fields.Float(required=True,digits=(16,4))
    product_id=fields.Many2one('product.product')
    product_category_id=fields.Many2one('product.category')
    target_amount=fields.Monetary(currency_field='currency_id')
    minimum_achievement_percent=fields.Float(default=0)
    cap_amount=fields.Monetary(currency_field='currency_id')
    include_refund_clawback=fields.Boolean(default=True)

    @api.constrains('rate','minimum_achievement_percent','cap_amount','date_start','date_end')
    def _check_values(self):
        for record in self:
            if record.rate < 0 or record.minimum_achievement_percent < 0 or record.cap_amount < 0:
                raise ValidationError(_('Commission rates, thresholds, and caps cannot be negative.'))
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_('The commission plan end date cannot precede its start date.'))

    def matches(self, salesperson, employee, product, order_date):
        self.ensure_one()
        if self.salesperson_ids and salesperson not in self.salesperson_ids:
            return False
        if self.employment_type != 'all' and employee.distribution_employment_type != self.employment_type:
            return False
        if self.product_id and self.product_id != product:
            return False
        if self.product_category_id and self.product_category_id != product.categ_id:
            return False
        if self.date_start and order_date < self.date_start:
            return False
        if self.date_end and order_date > self.date_end:
            return False
        return True


class SalesCommissionBatch(models.Model):
    _name='sales.commission.batch'
    _description='Sales Commissions'
    _inherit='distribution.controlled.workflow'
    _order='id desc'
    sequence_code='sales.commission.batch'
    process_key='commission'

    period_start=fields.Date(required=True)
    period_end=fields.Date(required=True)
    line_ids=fields.One2many('sales.commission.line','batch_id')
    total_commission=fields.Monetary(compute='_compute_total',currency_field='currency_id')

    @api.depends('line_ids.commission_amount')
    def _compute_total(self):
        for record in self:
            record.total_commission=sum(record.line_ids.mapped('commission_amount'))

    @api.constrains('period_start','period_end')
    def _check_period(self):
        for record in self:
            if record.period_end < record.period_start:
                raise ValidationError(_('The commission period end cannot precede its start.'))

    def _paid_ratio(self, order):
        invoices=order.invoice_ids.filtered(lambda move:move.state == 'posted' and move.move_type == 'out_invoice')
        total=sum(invoices.mapped('amount_total'))
        paid=sum(max(move.amount_total-move.amount_residual,0) for move in invoices)
        return min(paid/total,1.0) if total else 0.0

    def _refund_values(self, sale_line):
        refund_lines=sale_line.invoice_lines.filtered(lambda line:line.move_id.state == 'posted' and line.move_id.move_type == 'out_refund')
        return sum(abs(line.quantity) for line in refund_lines),sum(abs(line.price_subtotal) for line in refund_lines)

    def action_generate_lines(self):
        Plan=self.env['sales.commission.plan']
        SaleLine=self.env['sale.order.line']
        Employee=self.env['hr.employee'].sudo()
        for batch in self:
            if batch.state not in ('draft','correction'):
                raise UserError(_('Commission lines can only be regenerated in Draft or Correction Required.'))
            batch.line_ids.sudo().unlink()
            plans=Plan.search([('active','=',True),('company_id','=',batch.company_id.id),'|',('date_start','=',False),('date_start','<=',batch.period_end),'|',('date_end','=',False),('date_end','>=',batch.period_start)],order='sequence,id')
            lines=SaleLine.search([('order_id.company_id','=',batch.company_id.id),('order_id.state','in',('sale','done')),('order_id.date_order','>=',fields.Datetime.to_datetime(batch.period_start)),('order_id.date_order','<',fields.Datetime.add(fields.Datetime.to_datetime(batch.period_end),days=1)),('display_type','=',False)])
            values=[]
            for line in lines:
                salesperson=line.order_id.user_id
                if not salesperson:
                    continue
                employee=Employee.search([('user_id','=',salesperson.id),('company_id','in',[False,batch.company_id.id])],limit=1)
                order_date=line.order_id.date_order.date()
                plan=plans.filtered(lambda candidate:candidate.matches(salesperson,employee,line.product_id,order_date))[:1]
                if not plan:
                    continue
                if plan.target_amount:
                    achieved=sum(SaleLine.search([('order_id.user_id','=',salesperson.id),('order_id.company_id','=',batch.company_id.id),('order_id.state','in',('sale','done')),('order_id.date_order','>=',fields.Datetime.to_datetime(batch.period_start)),('order_id.date_order','<',fields.Datetime.add(fields.Datetime.to_datetime(batch.period_end),days=1)),('display_type','=',False)]).mapped('price_subtotal'))
                    if achieved*100/plan.target_amount < plan.minimum_achievement_percent:
                        continue
                refund_qty,refund_amount=batch._refund_values(line) if plan.include_refund_clawback else (0,0)
                if plan.basis == 'ordered':
                    quantity=line.product_uom_qty; source=line.price_subtotal
                elif plan.basis == 'delivered':
                    ratio=line.qty_delivered/line.product_uom_qty if line.product_uom_qty else 0
                    quantity=line.qty_delivered; source=line.price_subtotal*ratio
                elif plan.basis == 'invoiced':
                    ratio=line.qty_invoiced/line.product_uom_qty if line.product_uom_qty else 0
                    quantity=max(line.qty_invoiced-refund_qty,0); source=max(line.price_subtotal*ratio-refund_amount,0)
                else:
                    paid_ratio=batch._paid_ratio(line.order_id)
                    quantity=max(line.qty_invoiced-refund_qty,0)*paid_ratio; source=max((line.price_subtotal-refund_amount)*paid_ratio,0)
                amount=quantity*plan.rate if plan.rate_type == 'per_unit' else source*plan.rate/100
                if plan.cap_amount:
                    amount=min(amount,plan.cap_amount)
                values.append({'batch_id':batch.id,'plan_id':plan.id,'salesperson_id':salesperson.id,'sale_order_id':line.order_id.id,'product_id':line.product_id.id,'basis':plan.basis,'quantity':quantity,'source_amount':source,'rate_type':plan.rate_type,'rate':plan.rate,'adjustment_amount':0,'calculated_amount':amount,'calculation_note':_('%s basis; refunds %s; plan %s')%(plan.basis,'included' if plan.include_refund_clawback else 'excluded',plan.name)})
            self.env['sales.commission.line'].create(values)
            batch.with_context(workflow_system=True).write({'amount':sum(v['calculated_amount'] for v in values)})
            batch.message_post(body=_('Generated %s commission lines from eligible sales activity.')%len(values))
        return True


class CommissionLine(models.Model):
    _name='sales.commission.line'
    _description='Sales Commission Line'

    batch_id=fields.Many2one('sales.commission.batch',required=True,ondelete='cascade')
    plan_id=fields.Many2one('sales.commission.plan')
    salesperson_id=fields.Many2one('res.users',required=True)
    sale_order_id=fields.Many2one('sale.order')
    product_id=fields.Many2one('product.product')
    basis=fields.Selection([('ordered','Confirmed Sales'),('delivered','Delivered Sales'),('invoiced','Invoiced Sales'),('paid','Paid Sales')],default='paid')
    quantity=fields.Float()
    source_amount=fields.Monetary(currency_field='currency_id')
    rate_type=fields.Selection([('per_unit','Amount per Unit'),('percentage','Percentage')],default='per_unit')
    rate=fields.Float(digits=(16,4))
    calculated_amount=fields.Monetary(currency_field='currency_id')
    adjustment_amount=fields.Monetary(currency_field='currency_id')
    commission_amount=fields.Monetary(currency_field='currency_id',compute='_compute_amount',store=True)
    calculation_note=fields.Char()
    currency_id=fields.Many2one('res.currency',related='batch_id.currency_id')

    @api.depends('quantity','source_amount','rate','rate_type','calculated_amount','adjustment_amount')
    def _compute_amount(self):
        for record in self:
            base=record.calculated_amount
            if not record.plan_id:
                base=record.quantity*record.rate if record.rate_type == 'per_unit' else record.source_amount*record.rate/100
            record.commission_amount=base+record.adjustment_amount
