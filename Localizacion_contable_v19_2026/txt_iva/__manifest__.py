# -*- coding: utf-8 -*-
{
    'name': "Archivo txt iva proveedores seniat v18",

    'summary': """Archivo txt iva proveedores seniat v18""",

    'description': """
       Archivo txt iva proveedores seniat
    """,
    'version': '18.0',
    'author': 'Ing. Darrell Sojo / Alianza Frank Service',
    'category': 'Tools',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'base_contable',
        'account',
        'account_accountant',
        'iva_retention',
        'resumen_alicuota_libros',
    ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'wizard/wizard_generar_txt_view.xml',
        'vista/res_company_inherit.xml',
    ],
    'application': True,
}
