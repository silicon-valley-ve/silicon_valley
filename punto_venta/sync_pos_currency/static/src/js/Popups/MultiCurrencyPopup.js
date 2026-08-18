/** @odoo-module **/

import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MultiCurrencyPopup extends Component {
    static components = { Dialog };
    static template = "sync_pos_currency.MultiCurrencyPopup";

    setup() {
        this.pos = useService("pos");
        const multicurrencies = this.pos.multicurrencypayment || [];
        const firstCurr = multicurrencies.length > 0 ? multicurrencies[0] : {};

        this.state = useState({
            values: multicurrencies,
            default_currency: this.pos.currency,
            selected_curr_id: firstCurr.id || 0,
            selected_curr_name: firstCurr.name || "",
            selected_rate: firstCurr.rate || 0,
            inverse_rate: firstCurr.inverse_rate || 0,
            symbol: firstCurr.symbol || "",
            AmountTotal: this.pos.get_order().get_due(),
            amount_total_currency: 0,
            selectedPaymentMethodId: 0,
        });

        this.state.amount_total_currency = (this.state.selected_rate * this.state.AmountTotal).toFixed(2);

        onMounted(() => {
            console.log("MÉTODOS DE PAGO RECIBIDOS:", this.props.payment_method);
            if (this.state.selected_curr_id) {
                this._syncPaymentMethod(this.state.selected_curr_id);
            }
        });
    }

    _syncPaymentMethod(currencyId) {
        if (!this.props.payment_method) return;

        // Convertimos currencyId a número puro por si acaso
        const targetId = parseInt(currencyId);

        const matchingMethod = this.props.payment_method.find((m) => {
            // Extraemos el ID: Odoo lo envía como [id, "nombre"] o solo id
            let mCurrencyId = Array.isArray(m.currency_id) ? m.currency_id[0] : m.currency_id;
            
            // Si sigue siendo undefined, intentamos buscarlo en el raw del objeto
            if (mCurrencyId === undefined && m.raw) {
                mCurrencyId = Array.isArray(m.raw.currency_id) ? m.raw.currency_id[0] : m.raw.currency_id;
            }

            return parseInt(mCurrencyId) === targetId;
        });

        if (matchingMethod) {
            this.state.selectedPaymentMethodId = matchingMethod.id;
        } else {
            this.state.selectedPaymentMethodId = 0;
        }
    }

    onCurrencyChange(event) {
        const id = parseInt(event.target.value);
        const curr = this.state.values.find((v) => v.id === id);
        if (curr) {
            this.state.selected_curr_id = id;
            this.state.selected_curr_name = curr.name;
            this.state.selected_rate = curr.rate;
            this.state.inverse_rate = curr.inverse_rate;
            this.state.symbol = curr.symbol;
            this.state.amount_total_currency = (this.state.selected_rate * this.state.AmountTotal).toFixed(2);
            
            this._syncPaymentMethod(id);
        }
    }

    onPaymentMethodChange(event) {
        this.state.selectedPaymentMethodId = parseInt(event.target.value);
    }

    confirm() {
        const amountInput = document.querySelector('.pay_amount');
        this.props.confirm({
            confirmed: true,
            payload: {
                currency_name: this.state.selected_curr_name,
                selected_rate: this.state.selected_rate,
                symbol: this.state.symbol,
                payment_method_id: this.state.selectedPaymentMethodId,
                entered_amount: parseFloat(amountInput ? amountInput.value : 0),
            },
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}