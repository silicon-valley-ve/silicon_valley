import { ProductInfoBanner } from "@point_of_sale/app/components/product_info_banner/product_info_banner";
import { patch } from "@web/core/utils/patch";

patch(ProductInfoBanner.prototype, {
    getCurrencyDual(amt) {
        var amount = (amt || 0) * (
            this.pos.config.second_currency_rate / (this.pos.config.company_rate || 1)
        );
        return `${this.pos.config.second_currency_symbol} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },
});