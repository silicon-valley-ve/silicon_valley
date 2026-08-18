# -*- coding: utf-8 -*-
{
    'name': "Módulo regi rep Z localizacion contable  18",

    'summary': """Módulo regi rep Z localizacion contable  18""",

    'description': """
       Módulo regi rep Z localizacion contable  18
       Colaborador: Ing. Darrell Sojo
    """,
    'version': '18.0',
    'author': 'Darrell Sojo/ Frank service',
    'category': 'Módulo registro rep Z localizacion contable  18',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'base_contable',
        'account',
        'account_accountant',
        ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'vista/vista_tabla_libro_pos.xml',
        'vista/res_company_inherit.xml',
        'vista/vista_nro_maquina.xml',
        'wizards/wizard_libro_ventas_pos.xml',
        ##'data/data.xml',
    ],
    'application': True,
    'license': 'OEEL-1',
}
