# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################
from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = 'pos.config'

    wk_display_stock = fields.Boolean('Mostrar stock en el punto de venta', default=True)
    wk_stock_type = fields.Selection([('available_qty', 'Cantidad disponible (disponible)'), ('forecasted_qty', 'Cantidad prevista'), ('virtual_qty', 'Cantidad disponible - Cantidad saliente')], string='Stock Type', default='available_qty', required=True)
    wk_continous_sale = fields.Boolean('Allow Order When Out-of-Stock')
    wk_deny_val = fields.Integer('Deny order when product stock is lower than ')
    wk_error_msg = fields.Char(string='Custom message', default="Product out of stock")
    wk_hide_out_of_stock = fields.Boolean(string="Ocultar productos fuera de stock", default=True)

    @api.model
    def update_qty_real_time(self, result):
        active_sessions = self.env['pos.session'].search([('state', '!=', 'closed')])
        for session in active_sessions:
            for order in session.order_ids:
                if not order.picking_ids:
                    for line in order.lines:
                        if(line.product_id.id in result.keys()):
                            result[line.product_id.id] -= line.qty
        return result

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_wk_display_stock = fields.Boolean(related='pos_config_id.wk_display_stock', readonly=False)
    pos_wk_stock_type = fields.Selection(related='pos_config_id.wk_stock_type',required=True, readonly=False)
    pos_wk_continous_sale = fields.Boolean(related='pos_config_id.wk_continous_sale', readonly=False)
    pos_wk_deny_val = fields.Integer(related='pos_config_id.wk_deny_val', readonly=False)
    pos_wk_error_msg = fields.Char(related='pos_config_id.wk_error_msg', readonly=False)
    pos_wk_hide_out_of_stock = fields.Boolean(related='pos_config_id.wk_hide_out_of_stock', readonly=False)



class ProductProduct(models.Model):
    _inherit = 'product.product'

    wk_qty_available = fields.Integer()
    original_qty_available = fields.Integer()

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ['qty_available', 'virtual_available', 'outgoing_qty', 'type','wk_qty_available','original_qty_available']
        return fields


    @api.model
    def get_updated_qty_real_time(self):
        active_sessions = self.env['pos.session'].search([('state', '!=', 'closed')])
        product_qty = {}
        for session in active_sessions:
            for order in session.order_ids:
                if not order.picking_ids and order.state not in ['draft','cancel']:
                    for line in order.lines:
                        if product_qty.get(line.product_id.id):
                            product_qty[line.product_id.id]+=line.qty
                        else:
                            product_qty[line.product_id.id] = line.qty
        return product_qty

    def _load_pos_data(self, data):
        res = super()._load_pos_data(data)
        products = res.get('data')
        config_id = self.env['pos.config'].browse(data['pos.config']['data'][0]['id'])
        picking_type = config_id.picking_type_id
        location_id = picking_type.default_location_src_id.id
        wk_stock_type = config_id.wk_stock_type
        wk_product_qtys = self.get_updated_qty_real_time(); 

        for product in products:
            wk_product = self.env['product.product'].browse([product.get('id')])
            if wk_product.type == 'consu':
                product_qtys = wk_product.with_context(location=location_id)._compute_quantities_dict(None, None, None, None, None)
                for pos_product in product_qtys:
                    if wk_stock_type == 'available_qty':
                        if product.get('id') in wk_product_qtys:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('qty_available') - wk_product_qtys.get(product.get('id'))
                            product['original_qty_available'] = product_qtys.get(pos_product).get('qty_available') - wk_product_qtys.get(product.get('id'))
                        else:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('qty_available')
                            product['original_qty_available'] = product_qtys.get(pos_product).get('qty_available')
                    elif wk_stock_type == 'forecasted_qty':
                        if product.get('id') in wk_product_qtys:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('virtual_available') - wk_product_qtys.get(product.get('id'))
                            product['original_qty_available'] = product_qtys.get(pos_product).get('virtual_available') - wk_product_qtys.get(product.get('id'))
                        else:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('virtual_available')
                            product['original_qty_available'] = product_qtys.get(pos_product).get('virtual_available')
                    else:
                        if product.get('id') in wk_product_qtys:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('qty_available') - product_qtys.get(pos_product).get('outgoing_qty') - wk_product_qtys.get(product.get('id'))
                            product['original_qty_available'] = product_qtys.get(pos_product).get('qty_available') - product_qtys.get(pos_product).get('outgoing_qty') - wk_product_qtys.get(product.get('id'))
                        else:
                            product['wk_qty_available'] = product_qtys.get(pos_product).get('qty_available') - product_qtys.get(pos_product).get('outgoing_qty')
                            product['original_qty_available'] = product_qtys.get(pos_product).get('qty_available') - product_qtys.get(pos_product).get('outgoing_qty')
            else:
                if product.get('id') in wk_product_qtys:
                    product['wk_qty_available'] = 1000 + wk_product_qtys.get(product.get('id'))
                    product['original_qty_available'] = 1000 +  wk_product_qtys.get(product.get('id'))
                else:
                    product['wk_qty_available'] = 1000
                    product['original_qty_available'] = 1000
        
        res['data'] = products
        return res


class PosOrder(models.Model):
    _inherit = 'pos.order'

    def _export_for_ui(self, order):
        result = super()._export_for_ui(order)
        result['order_id'] = order.id
        return result
