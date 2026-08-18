/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

console.log("validando que este archivo se cargue")



patch(ReceiptScreen.prototype, {
    setup() {
        super.setup.call(this, ...arguments);
        this.pos = usePos();
        console.log("POS data:", this.pos);
        
    },

    ImprimirFiscal_the_factory() {
        const order = this.currentOrder;
        console.log(order);

        if (!order) {
            console.error("No order found.");
            return;
        }

        if (!order.lines || order.lines.length === 0) {
            console.error("No order lines found.");
            return;
        }

        var lineas = [];
        var payment_order_lines = [];

        const client = order.get_partner(); // Cambia a get_partner() si es necesario
        if (client) {
            console.log("Cliente asociado:", client);
        } else {
            console.error("No client associated with the order.");
            return;
        }

        for (const line of order.lines) {
            console.log("Procesando línea de pedido:", line);

            const product = line.get_product ? line.get_product() : line.product;
            if (!product || typeof product !== 'object') {
                console.error("Producto no válido para la línea:", line);
                continue;
            }

            var taxes_ids = line.tax_ids || product.taxes_id || [];
            var valor_impuesto = "0";


            var productName = product.default_code
                ? product.default_code.replace("&", "") + " " + product.display_name.replace("&", "")
                : product.display_name.replace("&", "");

            var precio_total_con_imp = line.get_price_with_tax ? line.get_price_with_tax() : line.price;
            //var precio_unit = line.get_lst_price ? line.get_lst_price() : line.price; // OJO
            var precio_unit = line.get_unit_price();
            var cantidad = line.get_quantity ? line.get_quantity() : line.quantity;
            var precio_unit_con_imp = 0;
            var porcentage_tax = 0;

            precio_unit_con_imp = precio_total_con_imp/cantidad

            porcentage_tax = ((precio_unit_con_imp/precio_unit)-1)*100

            porcentage_tax = Math.round(porcentage_tax);

            console.log(porcentage_tax);

            if (porcentage_tax == 16){
                valor_impuesto=1;
            }

            if (porcentage_tax == 8){
                valor_impuesto=2;
            }

            if (porcentage_tax == 31){
                valor_impuesto=3;
            }

            if (porcentage_tax == 0){
                valor_impuesto=0;
            }



            if (line.discount > 0) {
                var descuento = (line.discount / 100) * precio;
                precio = precio - descuento;
            }

            lineas.push({
                product: productName.slice(0, 57),
                cantidad: cantidad,
                precio: precio_unit,
                impuesto: valor_impuesto,
                descuento: 0,
            });
        }

        console.log("Líneas procesadas:", lineas);

        const paymentLines = this.currentOrder.payment_ids; // Obtener las líneas de pago de la orden actual


        if (Array.isArray(paymentLines)) {
            for (const line of paymentLines) {
                const payment_order_linesb = {
                    name: line.payment_method_id.name,
                    payment_method: line.payment_method_id.name, // ID del método de pago
                    calculate_wh_itf:line.payment_method_id.is_currency_payment, // johan
                    amount: line.amount, 
                };
                payment_order_lines.push(payment_order_linesb);
            }
        }

        var enviar_lineas = JSON.stringify(lineas);
        var line_payments = JSON.stringify(payment_order_lines);

        if (client) {
            const clientName = client.name.replace('&', '');
            const clientPhone = client.phone || '';
            const clientAddress = client.address || '';
            const clientVat = client.vat || '';

            window.open(
                "http://localhost:8080/impresora_fiscal/cargar.php?cid=" + order.pos_reference +
                "&numero_recibo=" + order.pos_reference +
                "&cliente=" + clientName +
                "&telefono=" + clientPhone +
                "&direccion=" + clientAddress +
                "&rif_cedula=" + clientVat +
                "&lineas=" + enviar_lineas +
                "&payment_order_lines=" + line_payments +
                "&order_id=" + 666,
                "width=300,height=500,scrollbars=YES"
            );
        } else {
            console.error("Datos del cliente no disponibles.");
        }
    },



    ImprimirFiscal() {
        const order = this.currentOrder;

        if (!order) {
            console.error("No order found.");
            return;
        }

        if (!order.lines || order.lines.length === 0) {
            console.error("No order lines found.");
            return;
        }

        var lineas = [];
        var payment_order_lines = [];

        const client = order.get_partner(); 
        if (!client) {
            alert("Debe seleccionar un cliente asociado con RIF para la factura fiscal.");
            console.error("No client associated with the order.");
            return;
        }

        // --- PROCESAMIENTO DE LÍNEAS DE PRODUCTOS ---
        for (const line of order.lines) {
            const product = line.get_product ? line.get_product() : line.product;
            if (!product) continue;

            // Lógica de Impuestos (Mapeo para Epson PNP)
            var precio_total_con_imp = line.get_price_with_tax ? line.get_price_with_tax() : line.price;
            var precio_unit = line.get_unit_price();
            var cantidad = line.get_quantity ? line.get_quantity() : line.quantity;
            
            var precio_unit_con_imp = precio_total_con_imp / cantidad;
            //var porcentage_tax = Math.round(((precio_unit_con_imp / precio_unit) - 1) * 100);
            var porcentage_tax = (((precio_unit_con_imp / precio_unit) - 1) * 100).toFixed(2);
            //var var_aux = (precio_unit_con_imp / precio_unit);

            
            var valor_impuesto = "0";
            if (porcentage_tax == 16) {
                valor_impuesto = "1";
            } else if (porcentage_tax == 8) {
                valor_impuesto = "2";
            } else if (porcentage_tax == 31) {
                valor_impuesto = "3";
            } else if (porcentage_tax == 0) {
                valor_impuesto = "0";
            } else {
                // Si no es 16, 8, 31 o 0, entra aquí
                valor_impuesto = "1"; 
            }

            var productName = product.display_name.replace(/&/g, "").replace(/"/g, "");

            lineas.push({
                product: productName.substring(0, 20), // Máximo 20 para el comando 'i'
                cantidad: cantidad,
                precio: precio_unit,
                impuesto: valor_impuesto,
                descuento: 0,
            });
        }

        // --- PROCESAMIENTO DE PAGOS ---
        const paymentLines = order.payment_ids;
        if (Array.isArray(paymentLines)) {
            for (const line of paymentLines) {
                payment_order_lines.push({
                    name: line.payment_method_id.name,
                    calculate_wh_itf: line.payment_method_id.is_currency_payment || false,
                    amount: line.amount, 
                });
            }
        }

        var enviar_lineas = JSON.stringify(lineas);
        var line_payments = JSON.stringify(payment_order_lines);

        // EXTRAER EL SERIAL DESDE LA CONFIGURACIÓN DEL POS
        const serialImpresora = this.pos.config.serial_impresora || '';

        // --- LIMPIEZA DE DATOS DEL CLIENTE ---
        const clientName = client.name.replace(/&/g, '').substring(0, 30);
        const clientAddress = (client.street || 'Caracas').replace(/&/g, '').substring(0, 40);
        const clientVat = "V"+(client.vat || '').replace(/[^a-zA-Z0-9]/g, "");
        //const clientDoc ="V"; //client.doc_tipo || '';

        // --- ENVÍO AL PROXY PYTHON (Puerto 8090) ---
        // Usamos encodeURIComponent para que caracteres especiales no rompan la URL
        const url = "http://localhost:8090/impresora_fiscal/cargar.php?" + 
            "cid=" + encodeURIComponent(order.pos_reference) +
            "&cliente=" + encodeURIComponent(clientName) +
            "&direccion=" + encodeURIComponent(clientAddress) +
            "&rif_cedula=" + encodeURIComponent(clientVat) +
            "&serial=" + encodeURIComponent(serialImpresora) + // NUEVO CAMPO
            "&lineas=" + encodeURIComponent(enviar_lineas) +
            "&payment_order_lines=" + encodeURIComponent(line_payments);

        console.log("Enviando datos a la impresora fiscal...");

        fetch(url)
            .then(response => {
                if (response.ok) {
                    console.log("Respuesta recibida del servidor local.");
                } else {
                    alert("Error en el servidor de impresión. Verifique la consola del .bat");
                }
            })
            .catch(err => {
                console.error("Error de conexión:", err);
                alert("No se pudo conectar con el agente de impresión. Verifique que el archivo .bat esté abierto.");
            });
    },

    get_paymentline_by_uuid(uuid) {
        var lines = this.currentOrder.payment_ids;
        return lines.find(function (line) {
            return line.uuid === uuid;
        });
    }
});
