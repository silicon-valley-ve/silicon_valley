# -*- coding: utf-8 -*-
{
    'name': "Modulo de resumen totales por alicuotas en las lineas de la factura V19",

    'summary': """Modulo de resumen totales por alicuotas en las lineas de la factura V19""",

    'description': """
       Modulo de resumen totales por alicuotas en las lineas de la factura V19
    """,
    'version': '19.0',
    'author': 'Ing. Darrell Sojo / Silicon Valley',
    'category': 'Tools',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'account',
        'account_accountant',
        'base_contable',
        'account_debit_note',
        'iva_retention',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'view/account_move_view.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
