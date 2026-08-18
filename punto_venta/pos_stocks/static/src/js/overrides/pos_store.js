/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";
import { OutOfStockMessagePopup } from "@pos_stocks/js/popups/popup";


patch(PosStore.prototype, {
    wk_change_qty_css() {
        var self = this;
        var products_qty = {};
        this.get_open_orders().forEach(order => {
            order.get_orderlines().forEach(line => {
                if (line.product_id && !line.stock_location_id) {
                    if (products_qty[line.product_id.id] == undefined) {
                        products_qty[line.product_id.id] = line.qty
                    } else {
                        products_qty[line.product_id.id] += line.qty
                    }
                }
            });
        });
        if (Object.keys(products_qty).length) {
            Object.keys(products_qty).forEach(product_id => {
                let product = self.models['product.product'].find(p=>p.id == product_id);
                if ((product.wk_qty_available != undefined)) {
                    var final_qty = product.original_qty_available - products_qty[product_id];
                    if (!(final_qty < self.config.wk_deny_val)) {
                        product.wk_qty_available = final_qty;
                    }
                }
            });
        }
        self.values_updated_on_load = true
    },

    async addLineToOrder(vals, order, opts = {}, configure = true) {
        var self = this;
        opts = opts || {};
        let product = vals.product_id;        
        // warehouse management compatiblity code start---------------
        for (var i = 0; i < this.orderlines; i++) {
            if ((self.orderlines[i].product.id == product.id) && self.orderlines[i].stock_location_id) {
                opts.merge = false;
            }
        }
        // warehouse management compatiblity code end---------------


        // ---------------
        if(product.isConfigurable()){
            return super.addLineToOrder(...arguments);
        }
        // ----------------

        if (!self.config.wk_continous_sale && self.config.wk_display_stock && !self.get_order().is_return_order) {
            if (self.get_open_orders() && self.get_open_orders().length) {
                var total_qty = 1;

                self.get_open_orders().forEach(order => {
                    order.get_orderlines().forEach(line => {
                        if (line.product_id.id == product.id) total_qty += line.qty;
                    });
                });


                const temp_product =  self.models['product.product'].find(p=>p.id === product.id)
                if ((temp_product.wk_qty_available != undefined)) {
                    var final_qty = temp_product.original_qty_available - total_qty;
                    if (temp_product.type != 'consu') {
                        return super.addLineToOrder(vals, order, opts = {}, configure = true)
                    } else if (!(opts && opts.quantity < 0 && opts.refunded_orderline_id) && final_qty < self.config.wk_deny_val) {
                        this.dialog.add(OutOfStockMessagePopup, {
                            title: _t("Warning!!!!"),
                            body: _t("(" + temp_product.display_name + ")" + self.config.wk_error_msg + "."),
                            product_id: temp_product.id,
                        });
                        return false
                    } else {
                        temp_product.wk_qty_available = final_qty
                        return super.addLineToOrder(vals, order, opts = {}, configure = true)
                    }
                }
            }
        } 
        else{
            return super.addLineToOrder(vals, order, opts = {}, configure = true)
        }
    },

    async syncAllOrders(options = {}) {
        const orders = await super.syncAllOrders(...arguments);
        if(orders && orders.length){
            orders.forEach((order)=>{
                if (order && order.finalized) {
                    if (!order.is_return_order) {
                        var wk_order_line = order.get_orderlines();
                        for (var j = 0; j < wk_order_line.length; j++) {
                            let wk_product = this.models['product.product'].find(p=>p.id == wk_order_line[j].product_id.id);
                            if (!wk_order_line[j].stock_location_id) {
                                if (wk_product) {
                                    wk_product.original_qty_available = wk_product.original_qty_available - wk_order_line[j].qty;
                                }
                            }
                        }
                    } else {
                        var wk_order_line = order.get_orderlines();
                        for (var j = 0; j < wk_order_line.length; j++) {
                            let wk_product = this.models['product.product'].find(p=>p.id == wk_order_line[j].product_id.id);
                            if (wk_product) {
                                wk_product.original_qty_available = wk_product.original_qty_available + wk_order_line[j].qty;
                            }
                        }
                    }
                }
            })
        }
        return orders;
    }

});
