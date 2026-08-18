# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
    "name"              :  "POS Stock",
    "summary"           :  """The user can display the product quantities on the Odoo POS with the module. If set, The user cannot add out of stock products to the POS cart.Show product quantity in POS|Out of stock products|Added product quantities|POS product stock|Show stock pos.""",
    "category"          :  "Point of Sale",
    "version"           :  "1.0.0",
    "sequence"          :  1,
    "author"            :  "Webkul Software Pvt. Ltd.",
    "license"           :  "Other proprietary",
    "website"           :  "https://store.webkul.com/Odoo-POS-Stock.html",
    "description"       :  """Odoo POS Stock
                            Show product quantity in POS
                            Out of stock products
                            Out-of-stock products POS
                            Added product quantities
                            POS product stock
                            Show stock pos
                            Manage POS stock
                            Product management POS""",
    "live_test_url"     :  "http://odoodemo.webkul.com/?module=pos_stocks&custom_url=/pos/auto",
    "depends"           :  ['point_of_sale'],
    "data"              :  ['views/res_config_view.xml'],
    'demo'              : [
                            'demo/demo.xml',
                        ],
    'assets'            :  {
                                'point_of_sale._assets_pos':[
                                    'pos_stocks/static/src/js/overrides/pos_store.js',
                                    'pos_stocks/static/src/js/overrides/order_summary.js',
                                    'pos_stocks/static/src/js/popups/popup.js',
                                    'pos_stocks/static/src/xml/pos.xml',
                                    'pos_stocks/static/src/css/pos_stocks.css',
                                ],
                            },
    "images"            :  ['static/description/Banner.png'],
    "application"       :  True,
    "installable"       :  True,
    "auto_install"      :  False,
    "price"             :  47,
    "currency"          :  "USD",
    "pre_init_hook"     :  "pre_init_check",
}
