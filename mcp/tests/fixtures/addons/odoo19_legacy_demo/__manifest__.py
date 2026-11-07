{
    'name': 'Legacy 19 demo (intentionally broken)',
    'version': '19.0.1.0.0',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/legacy_views.xml',
        'views/missing_file.xml',
    ],
    'update_xml': [],
    'assets': {
        'web.assets_backend': ['odoo19_legacy_demo/static/src/**/*'],
    },
}
