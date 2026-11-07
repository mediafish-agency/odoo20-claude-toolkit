{
    'name': "Library (Odoo 20 reference)",
    'summary': "Clean Odoo 20 module used by the odoo20 toolkit tests",
    'version': '1.0',
    'category': 'Hidden',
    'depends': ['mail'],
    'data': [
        'views/library_book_views.xml',
        'views/library_menus.xml',
        'security/ir.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'odoo20_clean_demo/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'odoo20_clean_demo/static/tests/**/*',
        ],
    },
    'author': "odoo20 toolkit",
    'license': 'LGPL-3',
}
