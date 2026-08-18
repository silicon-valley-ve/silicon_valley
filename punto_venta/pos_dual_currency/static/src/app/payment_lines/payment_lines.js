import { patch } from '@web/core/utils/patch';
import { PaymentScreenPaymentLines } from '@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines';

patch(PaymentScreenPaymentLines.prototype, {
    LineAmountDual(paymentline) {
        var amount = (paymentline.get_amount()) * (
            this.pos.config.second_currency_rate / this.pos.config.company_rate
        );
        return this.formatCurrencyDual(amount);
    },

    formatCurrencyDual(amount) {
        return `${this.pos.config.second_currency_symbol} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },
});