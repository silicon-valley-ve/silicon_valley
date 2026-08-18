# -*- coding: utf-8 -*-
{
    'name': 'POS Dual Currency Display',
    'summary': 'POS Dual Currency Display',
    'description': """POS Dual Currency Display""",
    'category': 'Point Of Sale',
    'version': '19.0.1.0.0',
    'author': "Khaled Hassan",
    'website': "https://apps.odoo.com/apps/modules/browse?search=Khaled+hassan",
    'depends': ['point_of_sale'],
    'data': ['views/pos_config_view.xml'],
    "assets": {
        "point_of_sale._assets_pos": [
            # Cargamos solo los scripts JS y estilos para aislar el error de las vistas XML
            'pos_dual_currency/static/src/app/**/*.js',
            'pos_dual_currency/static/src/css/pos.css',
            # 'pos_dual_currency/static/src/app/**/*.xml',  # Comentado temporalmente
        ],
    },
    'images': ['static/description/main_screenshot.png'],
    'license': 'OPL-1',
    "price": 75,
    "currency": 'EUR',
}