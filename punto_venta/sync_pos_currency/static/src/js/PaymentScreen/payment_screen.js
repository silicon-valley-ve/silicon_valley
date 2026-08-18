/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { MultiCurrencyPopup } from "../Popups/MultiCurrencyPopup";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";
import { _t } from "@web/core/l10n/translation";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
    },

    async payMultipleCurrencyClickHandler() {
        if (!this.pos.multicurrencypayment || this.pos.multicurrencypayment.length === 0) {
            return; 
        }

        const payment_method_data = this.payment_methods_from_config;
        
        await makeAwaitable(this.dialog, MultiCurrencyPopup, {
            payment_method: payment_method_data,
            title: _t("Multi-Currency Payment"),
            confirm: async ({ confirmed, payload }) => {
                if (confirmed && payload.entered_amount > 0) {
                    const paymentMethodSelected = this.payment_methods_from_config.find(
                        (m) => m.id === payload.payment_method_id
                    );

                    if (!paymentMethodSelected) return;

                    let amountInBase = payload.entered_amount / payload.selected_rate;

                    const paymentLine = this.currentOrder.add_paymentline(paymentMethodSelected);
                    paymentLine.set_amount(amountInBase);
                    paymentLine.currency_amount_total = payload.entered_amount;
                    paymentLine.selected_currency = payload.currency_name;
                    paymentLine.selected_currency_symbol = payload.symbol;
                    paymentLine.selected_currency_rate = payload.selected_rate;
                }
            },
        });
    }
});