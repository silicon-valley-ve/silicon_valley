{
    'name': 'Invoice Layout Pro',
    'version': '19.0.2.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Custom colors, HTML header blocks, legal terms and custom CSS on invoices',
    'author': 'Expert Odoo - expodo.fr',
    'website': 'https://expodo.fr',
    'support': 'info@expodo.fr',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'depends': ['account'],
    'data': [
        'views/res_company_views.xml',
        'views/base_document_layout_views.xml',
        'views/report_invoice_document_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'invoice_layout_pro/static/src/js/color_field_patch.js',
        ],
    },
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'application': False,
    'auto_install': False,
}
