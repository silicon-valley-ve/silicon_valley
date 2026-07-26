# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, float_is_zero, date_utils, email_split, html_escape, is_html_empty
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.osv import expression

from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import contextmanager
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import ast
import json
import re
import warnings


import requests
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    result = fields.Char()
    hasErrors = fields.Char()
    errorMessage = fields.Char()
    information = fields.Char()
    proximo_doc = fields.Char(compute='_compute_proximo_valor')

    @api.onchange('journal_id')
    def _compute_proximo_valor(self):
        for rec in self: #se coloco esto para evitar el error siglenton - Darrell
            rec.proximo_doc=rec.journal_id.doc_sequence_number_next

    

    def enviar_fact_digital(self):
        raise UserError(_("Tipo=%s")%self.move_type)
        pass