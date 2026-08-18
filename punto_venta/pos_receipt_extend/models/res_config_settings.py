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


class ResConfigSettings(models.TransientModel):
    """Used to add new fields to the settings"""
    _inherit = "res.config.settings"

    serial_impresora_epson=fields.Char(related="pos_config_id.serial_impresora_epson", readonly=False)
    serial_impresora=fields.Char(related="pos_config_id.serial_impresora", readonly=False)
    puerto_impresora=fields.Char(related="pos_config_id.puerto_impresora", readonly=False)


    """@api.model
    def _load_pos_data_fields(self, config_id):
        fields = super(ResConfigSettings, self)._load_pos_data_fields(config_id)
        fields.append('serial_impresora')
        return fields"""