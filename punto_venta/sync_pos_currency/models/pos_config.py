# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    multi_currency_payment = fields.Boolean('Multi Currency', help='To enable multi currency payment in pos')
    payment_currency_ids = fields.Many2many('res.currency', string="Payment Currency")

    def get_payment_currencies(self):
        return self.payment_currency_ids.read(
            ["id", "name", "symbol", "position", "rounding", "rate", "inverse_rate"]
        )
