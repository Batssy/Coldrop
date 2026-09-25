from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class DistributionRegion(models.Model):
    _name='distribution.region'; _description='Distribution Region'; _order='name'
    name=fields.Char(required=True); code=fields.Char(required=True,index=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company,index=True)
    manager_id=fields.Many2one('res.users'); active=fields.Boolean(default=True)
    _region_code_company_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'Region code must be unique per company.',
    )

class DistributionSite(models.Model):
    _name='distribution.site'; _description='Distribution Site'; _order='name'
    name=fields.Char(required=True); code=fields.Char(required=True,index=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company,index=True)
    region_id=fields.Many2one('distribution.region',required=True,ondelete='restrict',index=True)
    manager_id=fields.Many2one('res.users'); warehouse_id=fields.Many2one('stock.warehouse')
    latitude=fields.Float(digits=(10,7)); longitude=fields.Float(digits=(10,7)); geofence_radius_m=fields.Integer(default=150)
    active=fields.Boolean(default=True)
    _site_code_company_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'Site code must be unique per company.',
    )

class DistributionSubregion(models.Model):
    _name='distribution.subregion'; _description='Distribution Sub-Region'; _order='region_id,name'
    name=fields.Char(required=True); code=fields.Char(required=True,index=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company,index=True)
    region_id=fields.Many2one('distribution.region',required=True,ondelete='restrict',index=True)
    site_id=fields.Many2one('distribution.site',ondelete='restrict',index=True)
    manager_id=fields.Many2one('res.users'); active=fields.Boolean(default=True)
    _subregion_code_company_uniq = models.Constraint(
        'UNIQUE (code, company_id)',
        'Sub-region code must be unique per company.',
    )

class DistributionRoute(models.Model):
    _name='distribution.route'; _description='Distribution Route'; _order='site_id,name'
    name=fields.Char(required=True); code=fields.Char(required=True,index=True)
    site_id=fields.Many2one('distribution.site',required=True,ondelete='restrict',index=True)
    salesperson_id=fields.Many2one('res.users'); driver_id=fields.Many2one('hr.employee',domain="[('is_distribution_driver','=',True),('active','=',True)]")
    active=fields.Boolean(default=True)
    _route_code_site_uniq = models.Constraint(
        'UNIQUE (code, site_id)',
        'Route code must be unique per site.',
    )

class HrEmployee(models.Model):
    _inherit='hr.employee'
    distribution_region_id=fields.Many2one('distribution.region',string='Distribution Region')
    distribution_site_id=fields.Many2one('distribution.site',string='Distribution Site')
    distribution_route_id=fields.Many2one('distribution.route',string='Default Distribution Route')
    distribution_cost_center=fields.Char(string='Cost Centre')
    distribution_default_warehouse_id=fields.Many2one('stock.warehouse',string='Default Warehouse')
    is_distribution_driver=fields.Boolean(string='Distribution Driver',index=True)
    distribution_employment_type=fields.Selection([('full_time','Full Time'),('contract','Contract'),('temporary','Temporary'),('agent','Sales Agent')],default='full_time',string='Distribution Employment Type')

class ResPartner(models.Model):
    _inherit='res.partner'
    distribution_region_id=fields.Many2one('distribution.region')
    distribution_subregion_id=fields.Many2one('distribution.subregion',domain="[('region_id','=',distribution_region_id)]")
    distribution_site_id=fields.Many2one('distribution.site')
    distribution_route_id=fields.Many2one('distribution.route')
    distribution_onboarded_on=fields.Date(string='Distribution Customer Since',index=True)
    distribution_onboarding_salesperson_id=fields.Many2one('res.users',string='Onboarding Salesperson',index=True)
    geo_latitude=fields.Float(digits=(10,7)); geo_longitude=fields.Float(digits=(10,7)); geofence_radius_m=fields.Integer(default=75)
    location_verified=fields.Boolean(); location_verified_by=fields.Many2one('res.users',readonly=True); location_verified_on=fields.Datetime(readonly=True)
    def action_verify_location(self):
        for rec in self:
            if not rec.geo_latitude or not rec.geo_longitude:
                raise ValidationError(_('Coordinates are required before verification.'))
            rec.write({'location_verified':True,'location_verified_by':self.env.user.id,'location_verified_on':fields.Datetime.now()})

class ProductTemplate(models.Model):
    _inherit='product.template'
    business_line=fields.Selection([('beverage','Core Beverage'),('returnable','Returnable Asset'),('promotion','Promotional Item'),('non_core','Non-Core Merchandise'),('service','Service')],default='beverage',required=True,index=True)
    distribution_sku=fields.Char(string='Distribution SKU',index=True,copy=False)
    supplier_sku=fields.Char(index=True)
    brand_name=fields.Char(index=True); flavour=fields.Char(); container_volume_ml=fields.Integer(); units_per_pack=fields.Integer(default=1)
    packaging_type=fields.Selection([('rgb','Returnable Glass Bottle'),('pet','PET'),('can','Can'),('carton','Carton'),('keg','Keg'),('crate','Crate'),('other','Other')])
    returnable_asset=fields.Boolean(); returnable_units_per_sale_pack=fields.Float(default=0)
    returnable_product_id=fields.Many2one('product.product',domain="[('product_tmpl_id.returnable_asset','=',True)]")
    supplier_owner_id=fields.Many2one('res.partner',domain="[('supplier_rank','>',0)]")
    deposit_value=fields.Monetary(currency_field='currency_id'); replacement_value=fields.Monetary(currency_field='currency_id')
    promotion_eligible=fields.Boolean(); promotion_code=fields.Char(); promotion_start=fields.Date(); promotion_end=fields.Date()
    minimum_customer_shelf_life_days=fields.Integer(default=7)
    _distribution_sku_uniq = models.Constraint(
        'UNIQUE (distribution_sku)',
        'Distribution SKU must be unique.',
    )

class ResConfigSettings(models.TransientModel):
    _inherit='res.config.settings'
    distribution_enable_non_core=fields.Boolean(config_parameter='distribution.enable_non_core')
    distribution_email_notifications=fields.Boolean(default=True,config_parameter='distribution.email_notifications')
    distribution_default_approval_hours=fields.Integer(default=24,config_parameter='distribution.default_approval_hours')
