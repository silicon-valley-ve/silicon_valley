# -*- coding: utf-8 -*

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger('__name__')


class RetentionVat(models.Model):
    """This is a main model for rentetion vat control."""
    _inherit = 'vat.retention'

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    proximo_doc = fields.Char(compute='_compute_proximo_valor')
    proximo_ctrl = fields.Char(compute='_compute_proximo_ctrl')
    code = fields.Char(copy=False, string="Codigo de respuesta del servidor api")

    def action_posted(self):
        pass
        #res = super().action_posted()

    