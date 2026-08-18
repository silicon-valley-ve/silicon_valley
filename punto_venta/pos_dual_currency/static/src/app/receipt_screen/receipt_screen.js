import { patch } from '@web/core/utils/patch';
import { ReceiptScreen } from '@point_of_sale/app/screens/receipt_screen/receipt_screen';

patch(ReceiptScreen.prototype, {
    get orderAmountDual() {
        const order = this.currentOrder;
        if (!order) {
            return "";
        }
        const orderTotalAmount = order.get_total_with_tax();
        const tip_product_id = this.pos.config.tip_product_id?.[0];
        const tipLine = order
            .get_orderlines()
            .find((line) => tip_product_id && line.product.id === tip_product_id);
        const tipAmount = tipLine ? tipLine.get_all_prices().priceWithTax : 0;
        const orderAmountStr = this.formatCurrencyDual(orderTotalAmount - tipAmount);
        if (!tipAmount) {
            return orderAmountStr;
        }
        const tipAmountStr = this.formatCurrencyDual(tipAmount);
        return `${orderAmountStr} + ${tipAmountStr} tip`;
    },

    formatCurrencyDual(amount) {
        if (!this.pos.config.dual_currency || !this.pos.config.second_currency_rate) {
            return "";
        }
        var amt = (amount || 0) * (
            this.pos.config.second_currency_rate / (this.pos.config.company_rate || 1)
        );
        return `${this.pos.config.second_currency_symbol} ${amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },
});