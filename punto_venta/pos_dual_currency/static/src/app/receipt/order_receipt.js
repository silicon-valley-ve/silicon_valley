import { patch } from '@web/core/utils/patch';
import { usePos } from '@point_of_sale/app/store/pos_hook';
import { OrderReceipt } from '@point_of_sale/app/screens/receipt_screen/receipt/order_receipt';

patch(OrderReceipt.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
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