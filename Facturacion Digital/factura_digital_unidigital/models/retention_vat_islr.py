# -*- coding: utf-8 -*

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger('__name__')

class RetentionVatIslr(models.Model):
    """This is a main model for rentetion vat control."""
    _inherit = 'isrl.retention'

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    code = fields.Char(copy=False, string="Código de respuesta servidor API")
    message = fields.Text(copy=False)

    def envia_comp_ret_islr(self):
        pass