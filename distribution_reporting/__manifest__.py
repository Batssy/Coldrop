{
    'name': 'Distribution Operational Reports',
    'version': '19.0.1.0.0',
    'summary': 'Filtered operational and audit reports across every controlled distribution module.',
    'author': 'Broadspace',
    'website': 'https://broadspacesolutions.com',
    'category': 'Broadspace Distribution',
    'license': 'LGPL-3',
    'depends': ['distribution_dashboard'],
    'data': ['security/security.xml', 'security/ir.model.access.csv', 'views/report_views.xml', 'report/operational_report.xml'],
    'application': True,
    'installable': True,
    'auto_install': False,
}
