# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Bhagyadev KP (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PosConfig(models.Model):
    """Used to add new fields to the settings"""
    _inherit = "pos.config"

    serial_impresora_epson=fields.Char()
    serial_impresora=fields.Char()
    puerto_impresora=fields.Char()

    """@api.model
    def _load_pos_data_fields(self, config_id):
        # Cargamos los campos base[cite: 3]
        res = super(PosConfig, self)._load_pos_data_fields(config_id)
        # Añadimos nuestro campo para que esté disponible en el JS[cite: 3]
        res.append('serial_impresora')
        return res"""