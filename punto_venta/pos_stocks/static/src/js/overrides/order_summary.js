/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { OutOfStockMessagePopup } from "@pos_stocks/js/popups/popup";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onMounted } from "@odoo/owl";
import { ProductConfiguratorPopup } from "@point_of_sale/app/store/product_configurator_popup/product_configurator_popup";
import { useService } from "@web/core/utils/hooks";

patch(ProductConfiguratorPopup.prototype,{
    setup(){
        super.setup();
        this.dialog = useService("dialog");
    },

    confirm(){
        if (!this.pos.config.wk_continous_sale && this.pos.config.wk_display_stock && !this.pos.get_order().is_return_order) {
            if (this.pos.get_open_orders() && this.pos.get_open_orders().length) {
                var total_qty = 1;
                this.pos.get_open_orders().forEach(order => {
                    order.get_orderlines().forEach(line => {
                        if (line.product_id.id == this.state.product.id) total_qty += line.qty;
                    });
                });
                const temp_product =  this.pos.models['product.product'].find(p=>p.id === this.state.product.id)
                if ((temp_product.wk_qty_available != undefined)) {
                    var final_qty = temp_product.original_qty_available - total_qty;
                    if (temp_product.type != 'consu') {
                        super.confirm();
                    } else if (!(1 < 0 && opts.refunded_orderline_id) && final_qty < this.pos.config.wk_deny_val) {
                        this.dialog.add(OutOfStockMessagePopup, {
                            title: _t("Warning!!!!"),
                            body: _t("(" + temp_product.display_name + ")" + this.pos.config.wk_error_msg + "."),
                            product_id: temp_product.id,
                        });
                        return false
                    } else {
                        temp_product.wk_qty_available = final_qty
                        super.confirm();
                    }
                }
            }
            else{
                super.confirm();
            }
        } 
        else{
            super.confirm();
        }
    }
})

patch(ProductScreen.prototype,{
    setup(){
        super.setup(...arguments)
        onMounted(()=>{
            this.pos.wk_change_qty_css();
        })
    },


    get productsToDisplay() {
        const result = super.productsToDisplay;
    
        if (!this.pos.config.wk_display_stock) {
            return result;
        }
    
        const availableProducts = [];
    
        result.forEach(product => {
            const wkTotalQty = [];
            if (product.isConfigurable()) {
                const productVariants = [];
                
                product.attribute_line_ids.forEach(attrLine => {
                    attrLine.product_template_value_ids.forEach(valueId => {
                        const variants = this.pos.models['product.product'].filter(pp => 
                            pp.raw.product_template_variant_value_ids.includes(valueId.id)
                        );
                        productVariants.push(...variants);
                    });
                });
                const uniqueVariants = productVariants.filter(
                    (variant, index, self) => self.findIndex(v => v.id === variant.id) === index
                );
    
                if (uniqueVariants.length > 2) {
                    product.dot_dot = true;
                }
    
                for (let i = 0; i < Math.min(uniqueVariants.length, 3); i++) {
                    wkTotalQty.push(uniqueVariants[i].wk_qty_available);
                }
    
                product.wk_total_qty_arr = wkTotalQty;
            }
    
            if (product.type === 'combo' && product.combo_ids.length) {
                const allComboItemsAvailable = product.combo_ids.every(comboId => {
                    const combo = this.pos.models['product.combo'].find(c => c.id === comboId.id);
                    return combo.combo_item_ids.some(comboItemId => {
                        const productDetails = this.pos.models['product.product'].find(pp =>
                            pp.id === this.pos.models['product.combo.item'].find(ci => ci.id === comboItemId.id).product_id.id
                        );
                        return productDetails.original_qty_available > 0 || productDetails.detailed_type !== 'product';
                    });
                });
    
                if (allComboItemsAvailable || !this.pos.config.wk_hide_out_of_stock || product.dot_dot) {
                    if (product.original_qty_available > 0 || !this.pos.config.wk_hide_out_of_stock) {
                        availableProducts.push(product);
                    }
                }
            } 
            else {
                if (product.original_qty_available > 0 || !this.pos.config.wk_hide_out_of_stock || product.dot_dot) {
                    availableProducts.push(product);
                }
            }
        });
        return availableProducts;
    }
})

patch(OrderSummary.prototype,{
    _setValue(val) {
        const { numpadMode } = this.pos;
        let selectedLine = this.currentOrder.get_selected_orderline();
        if(numpadMode === 'quantity' && selectedLine){
            if (this.stock_location_id && val && val != "remove") {
                this.dialog.add(OutOfStockMessagePopup, {
                    title: _t("Warning !!!!"),
                    body: _t("Selected orderline product have different stock location, you can't update the qty of this orderline"),
                    product_id: selectedLine.product_id.id,
                });
                this.numberBuffer.reset();
                return;
            }

            let order_list = this.pos.get_open_orders();
            if (order_list.length) {
                var total_qty = 0;
                if (val == 'remove'){
                    total_qty += 0;
                }
                else {
                    if (!val){
                        total_qty = 0;
                    } 
                    else{
                        total_qty = val*1;
                    }
                }

                order_list.forEach(order => {
                    order.get_orderlines().forEach(line => {
                        if (line.product_id.id == selectedLine.id) {
                            total_qty += line.qty
                        }
                    });
                });

                if (this.pos.config.wk_display_stock && selectedLine.product_id.wk_qty_available != undefined) {
                    
                    var final_qty = selectedLine.product_id.original_qty_available - total_qty;
                    
                    if (selectedLine.product_id.type != 'consu') {
                        return super._setValue(...arguments);
                    }
                    if (this.pos.config.wk_continous_sale) {
                        selectedLine.product_id.wk_qty_available = final_qty
                    } else if (val > 0 && final_qty < this.pos.config.wk_deny_val) {
                        this.dialog.add(OutOfStockMessagePopup, {
                            title: _t("Warning !!!!"),
                            body: _t("(" + selectedLine.product_id.display_name + ")" + this.pos.config.wk_error_msg + "."),
                            product_id: selectedLine.product_id.id,
                        });
                        this.numberBuffer.reset();
                        return;
                    } else selectedLine.product_id.wk_qty_available = final_qty
                }
            }
        }
        super._setValue(...arguments);
    }
})
