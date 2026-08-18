import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    getCurrencyDual(amt) {
        var amount = amt * (
            this.pos.config.second_currency_rate / this.pos.config.company_rate
        );
        return `${this.pos.config.second_currency_symbol} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },
});