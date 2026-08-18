# -*- coding: utf-8 -*-
from odoo import fields, models, api

class PosConfig(models.Model):
    _inherit = "pos.config"

    dual_currency = fields.Boolean(default=False)
    company_rate = fields.Float(related='currency_id.rate')
    second_currency = fields.Many2one('res.currency')
    second_currency_rate = fields.Float(related='second_currency.rate')
    second_currency_symbol = fields.Char(related='second_currency.symbol')

class PosSession(models.Model):
    _inherit = "pos.session"

    def _loader_params_pos_config(self):
        result = super()._loader_params_pos_config()
        # Aseguramos que los campos se envíen al diccionario del JS en el POS
        result['search_params']['fields'].extend([
            'dual_currency',
            'company_rate',
            'second_currency',
            'second_currency_rate',
            'second_currency_symbol'
        ])
        return result