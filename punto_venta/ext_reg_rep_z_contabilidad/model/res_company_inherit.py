# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError




class ResCompany(models.Model):
    _inherit = 'res.company'

    account_receivable_z_id = fields.Many2one('account.account',company_dependent=True)
    account_igtf_z_id = fields.Many2one('account.account',company_dependent=True)
    account_ingreso_merca_id = fields.Many2one('account.account',company_dependent=True)
    crear_asiento_pos = fields.Boolean(company_dependent=True)