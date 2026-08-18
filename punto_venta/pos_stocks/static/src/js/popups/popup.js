/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */

import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { Component } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class OutOfStockMessagePopup extends Component {
    static template = "pos_stocks.OutOfStockMessagePopup";
    static components = { Dialog };

    static defaultProps = {
        title: "Confirm ?",
        body: ""
    };

    setup() {
        super.setup();
        this.pos = usePos();
    }

}