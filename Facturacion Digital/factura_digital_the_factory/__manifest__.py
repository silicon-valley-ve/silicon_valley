# -*- coding: utf-8 -*-

{
        'name': 'Factura Digital The factory',
        'version': '15.0.1.0',
        'author': 'Ing. Darrell Sojo',
        'contribuitors': "Darrell Sojo <dsojo.tanfe@gmail.com>",
        'summary': '',
        'description': """""",
        'category': 'Customizations',
        'website': 'http://soluciones-tecno.com/',
        'depends': ['base','account','l10n_ve_base','l10n_ve_account','l10n_ve_account_sequence_number'],
        'data': [
                'views/company_views.xml',
                'views/account_move_views.xml',
                #'views/solicutud_reposicion.xml',
                #'views/solicutud_reposicion_lote.xml',
                #'views/wizard_lote.xml',
                #'security/security.xml',
                #'security/ir.model.access.csv',
                #'views/menu_reposicion.xml',
                #'data/data.xml',
                #'data/ir_sequence.xml',
                #'views/sucursal_views.xml',
                
        ],
        'license': 'LGPL-3',
        'installable': True,
        'application': True,
        'auto_install': False,
                      
}
