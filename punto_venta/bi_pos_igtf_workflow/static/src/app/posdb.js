/** @odoo-module */

import { PosStore } from "@point_of_sale/app/store/pos_store";
// import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        var prods = this.data.models["product.product"].getAll()
        for(var i = 0, len = prods.length; i < len; i++){
                if(prods[i].default_code == 'bi_igtf'){
                    prods[i].not_returnable = true;
                    this.env.igtf_product = prods[i];
                }
        }
    }
});


