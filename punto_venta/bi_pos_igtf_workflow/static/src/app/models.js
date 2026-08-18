/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";
import { accountTaxHelpers } from "@account/helpers/account_tax";
import { parseUTCString, qrCodeSrc, random5Chars, uuidv4, gte, lt } from "@point_of_sale/utils";

patch(PosOrder.prototype, {

    setup(vals) {
        super.setup(vals);
        this.igtf_amount = this.igtf_amount || "";        
    },

    set_igtf_amount(igtf_amount){
        if(igtf_amount){
            this.igtf_amount = igtf_amount; 
        }
        else{
            this.igtf_amount  = 0.00;
        }
        
    },
    get_igtf_amount_org(){
        let self = this;
        let currentOrder = this.models["pos.order"].getBy("uuid", this.selectedOrderUuid);
        let plines = this.payment_ids;
        let igtf_tax= this.config.igtf_tax;
        var rounding = this.currency.rounding;
        let igtf_tax_amount = 0.00;

        for (let i = 0; i < plines.length; i++) {
            if (plines[i].payment_method_id.is_igtf === true) {
                let amount = plines[i].amount
                igtf_tax_amount = (amount * igtf_tax)/100;
                /*plines[i].amount=igtf_tax_amount;*/
                self.set_igtf_amount(igtf_tax_amount)
            }
        }
        return roundPrecision(igtf_tax_amount, rounding);     
    },

    get_igtf_amount(){
        let plines = this.payment_ids;
        let igtf_tax = this.config.igtf_tax;
        var rounding = this.currency.rounding;
        let total_igtf_tax_amount = 0.00; // Iniciamos acumulador

        for (let i = 0; i < plines.length; i++) {
            if (plines[i].payment_method_id.is_igtf === true) {
                let amount = plines[i].amount;
                // Sumamos el impuesto de cada línea que sea IGTF
                total_igtf_tax_amount += (amount * igtf_tax) / 100;
            }
        }
        
        // Guardamos el total sumado de todos los pagos
        this.set_igtf_amount(total_igtf_tax_amount);
        return roundPrecision(total_igtf_tax_amount, rounding);     
    },

    get_change(paymentline) {
        let igtf_amount = 0.0;
        if(this.igtf_amount){
            igtf_amount= this.igtf_amount   
        }
        else{
            igtf_amount = 0.0;
        }
        if (!paymentline) {
            var change =
                this.get_total_paid() - (this.get_total_with_tax() 
                + igtf_amount) - this.get_rounding_applied();
        } else {
            change = -this.get_total_with_tax();
            var lines = this.payment_ids;
            for (var i = 0; i < lines.length; i++) {
                change += lines[i].get_amount();
                if (lines[i] === paymentline) {
                    break;
                }
            }
        }
        return roundPrecision(Math.max(0, change), this.currency.rounding);
    },

    get_due(paymentline) {
        let igtf_amount = 0.0;
        if(this.igtf_amount){
            igtf_amount= this.igtf_amount   
        }
        else{
            igtf_amount = 0.0;
        }
        let due = 0;
        if (!paymentline) {
            due = this.get_total_with_tax() - igtf_amount- this.get_total_paid() + this.get_rounding_applied();
        } else {
            due = this.get_total_with_tax();

            for (const payment of this.payment_ids) {
                if (payment.uuid !== paymentline.uuid) {
                    due -= payment.get_amount();
                }
            }
        }
        return roundPrecision(due, this.currency.rounding);
    },

    get taxTotals() {
        const currency = this.config.currency_id;
        const company = this.company;
        const orderLines = this.lines;

        // If each line is negative, we assume it's a refund order.
        // It's a normal order if it doesn't contain a line (useful for pos_settle_due).
        // TODO: Properly differentiate refund orders from normal ones.
        const documentSign =
            this.lines.length === 0 ||
            !this.lines.every((l) => lt(l.qty, 0, { decimals: currency.decimal_places }))
                ? 1
                : -1;

        const baseLines = orderLines.map((line) =>
            accountTaxHelpers.prepare_base_line_for_taxes_computation(
                line,
                line.prepareBaseLineForTaxesComputationExtraValues({
                    quantity: documentSign * line.qty,
                })
            )
        );
        accountTaxHelpers.add_tax_details_in_base_lines(baseLines, company);
        accountTaxHelpers.round_base_lines_tax_details(baseLines, company);

        // For the generic 'get_tax_totals_summary', we only support the cash rounding that round the whole document.
        const cashRounding =
            !this.config.only_round_cash_method && this.config.cash_rounding
                ? this.config.rounding_method
                : null;

        const taxTotals = accountTaxHelpers.get_tax_totals_summary(baseLines, currency, company, {
            cash_rounding: cashRounding,
        });

        taxTotals.order_sign = documentSign;
        taxTotals.order_total =
            taxTotals.total_amount_currency - (taxTotals.cash_rounding_base_amount_currency || 0.0) + this.igtf_amount;

        let order_rounding = 0;
        let remaining = taxTotals.order_total;
        const validPayments = this.payment_ids.filter((p) => p.is_done() && !p.is_change);
        for (const [payment, isLast] of validPayments.map((p, i) => [
            p,
            i === validPayments.length - 1,
        ])) {
            const paymentAmount = documentSign * payment.get_amount();
            if (isLast) {
                if (this.config.cash_rounding) {
                    const roundedRemaining = this.getRoundedRemaining(
                        this.config.rounding_method,
                        remaining
                    );
                    if (!floatIsZero(paymentAmount - remaining, this.currency.decimal_places)) {
                        order_rounding = roundedRemaining - remaining;
                    }
                }
            }
            remaining -= paymentAmount;
        }

        taxTotals.order_rounding = order_rounding;
        taxTotals.order_remaining = remaining;

        const remaining_with_rounding = remaining + order_rounding;
        if (floatIsZero(remaining_with_rounding, currency.decimal_places)) {
            taxTotals.order_has_zero_remaining = true;
        } else {
            taxTotals.order_has_zero_remaining = false;
        }
        return taxTotals;
    }

    
});





