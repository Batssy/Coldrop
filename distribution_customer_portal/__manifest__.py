{
    'name': 'Distribution Customer Portal',
    'version': '19.0.1.0.0',
    'summary': 'Customer statements, order history, controlled reorders, and signed order acceptance.',
    'author': 'Broadspace',
    'website': 'https://broadspacesolutions.com',
    'category': 'Broadspace Distribution',
    'license': 'LGPL-3',
    'depends': ['distribution_core', 'portal', 'sale_management', 'account'],
    'data': ['views/sale_order_views.xml', 'views/portal_templates.xml'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
