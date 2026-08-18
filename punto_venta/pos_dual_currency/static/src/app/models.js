import { patch } from '@web/core/utils/patch';
import { Product } from '@point_of_sale/app/store/models';

patch(Product.prototype, {
    getUnitPriceDual() {
        if (!this.pos?.config?.dual_currency || !this.pos?.config?.second_currency_rate) {
            return "";
        }
        
        const rate = this.pos.config.second_currency_rate / (this.pos.config.company_rate || 1);
        const amount = (this.get_display_price() || 0) * rate;
        const symbol = this.pos.config.second_currency_symbol || "";
        
        return `${symbol} ${amount.toLocaleString(undefined, { 
            minimumFractionDigits: 2, 
            maximumFractionDigits: 2 
        })}`;
    },
});