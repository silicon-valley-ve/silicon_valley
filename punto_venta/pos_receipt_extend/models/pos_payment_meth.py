from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PosPaymentMeth(models.Model):
    _inherit = "pos.payment.method"

    """  
        no hago uso del campo 'split_transactions' nativo de odoo porque es usado
        para otro comportamiento en el sistema, el cual no necesariamente se desea
    """
    is_currency_payment = fields.Boolean('Pago en Divisas')
    

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super(PosPaymentMeth, self)._load_pos_data_fields(config_id)
        fields.append('is_currency_payment')
        return fields