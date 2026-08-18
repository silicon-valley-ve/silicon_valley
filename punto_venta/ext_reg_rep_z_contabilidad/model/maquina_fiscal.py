import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class PosNrMaquina(models.Model):
    _name = 'pos.nro.maquina'
    #_order = 'id desc, fecha_fact desc'

    name=fields.Char()
    company_id=fields.Many2one('res.company')