import { patch } from '@web/core/utils/patch';
import { usePos } from '@point_of_sale/app/store/pos_hook';
import { PaymentScreenStatus } from '@point_of_sale/app/screens/payment_screen/payment_status/payment_status';

patch(PaymentScreenStatus.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();
    },

    get TextDual() {
        var amount = (this.props.order.get_change()) * (
            this.pos.config.second_currency_rate / this.pos.config.company_rate
        );
        return this.formatCurrencyDual(amount);
    },

    get DueTextDual() {
        var amount = (this.props.order.get_total_with_tax() +
            this.props.order.get_rounding_applied()) * (
                this.pos.config.second_currency_rate / this.pos.config.company_rate
            );
        return this.formatCurrencyDual(amount);
    },

    get remTextDual() {
        var amount = (this.props.order.get_due() > 0 ? this.props.order.get_due() : 0) * (
            this.pos.config.second_currency_rate / this.pos.config.company_rate
        );
        return this.formatCurrencyDual(amount);
    },

    formatCurrencyDual(amount) {
        return `${this.pos.config.second_currency_symbol} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    },
});