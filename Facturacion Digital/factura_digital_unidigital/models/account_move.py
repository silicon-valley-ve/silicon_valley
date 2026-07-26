# -*- coding: utf-8 -*-

import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Char(copy=False)
    information = fields.Char(copy=False)
    proximo_doc = fields.Char(compute='_compute_proximo_valor')

    @api.onchange('journal_id')
    def _compute_proximo_valor(self):
        for rec in self:  # evita el error singleton - Darrell
            rec.proximo_doc = rec.journal_id.doc_sequence_number_next

    def enviar_fact_digital(self):
        """Construye y envía el JSON del documento fiscal (FA, NC, ND) hacia Unidigital."""
        for move in self:
            company = move.company_id

            # 1. Obtener/actualizar Token JWT y SerieStrongId invocando el método de res.company
            company.unidg_get_token()

            if not company.unidg_jwt_token or not company.seriestrongid:
                raise UserError(_("No se pudo obtener el Token o la Serie de Unidigital. Verifique sus credenciales."))

            # 2. Definir tipo de documento
            # out_invoice -> FA (Factura), out_refund -> NC (Nota de Crédito), out_receipt -> ND (Nota de Débito)
            doc_type_mapping = {
                'out_invoice': 'FA',
                'out_refund': 'NC',
                'out_receipt': 'ND',
            }
            document_type = doc_type_mapping.get(move.move_type)
            if not document_type:
                raise UserError(_("El tipo de documento '%s' no está soportado para emisión digital.") % move.move_type)

            # 3. Datos del Cliente / RIF
            partner = move.partner_id
            vat_clean = (partner.vat or '').replace('-', '').strip().upper()
            fiscal_code = vat_clean[0] if vat_clean and vat_clean[0].isalpha() else 'J'
            fiscal_registry = vat_clean[1:] if vat_clean and vat_clean[0].isalpha() else vat_clean

            # 4. Tasa y Fecha
            exchange_rate = getattr(move, 'tasa', 1.0) or 1.0
            emission_date = (move.invoice_date or fields.Date.today()).strftime('%Y-%m-%dT%H:%M:%S.000Z')

            # 5. Construcción de los detalles (Details) y acumulación de impuestos
            details = []
            tax_base_general = 0.0
            tax_amount_general = 0.0
            tax_base_reduced = 0.0
            tax_amount_reduced = 0.0
            exempt_amount = 0.0

            for line in move.invoice_line_ids.filtered(lambda l: not l.display_type):
                line_tax = line.tax_ids[:1]  # Tomamos el impuesto principal
                aliquot = line_tax.aliquot if line_tax else False
                
                is_exempt = False
                tax_code = "G"
                tax_percent = 16.0

                if aliquot == 'exempt' or (line_tax and line_tax.amount == 0):
                    is_exempt = True
                    tax_code = "E"
                    tax_percent = 0.0
                    exempt_amount += line.price_subtotal
                elif aliquot == 'reduced' or (line_tax and line_tax.amount == 8):
                    tax_code = "R"
                    tax_percent = 8.0
                    tax_base_reduced += line.price_subtotal
                    tax_amount_reduced += (line.price_total - line.price_subtotal)
                else:
                    # General por defecto (16%)
                    tax_code = "G"
                    tax_percent = 16.0
                    tax_base_general += line.price_subtotal
                    tax_amount_general += (line.price_total - line.price_subtotal)

                line_amount = round(line.quantity * line.price_unit, 2)
                line_tax_amount = round(line.price_total - line.price_subtotal, 2)

                details.append({
                    "Description": line.name or "Producto/Servicio",
                    "Quantity": line.quantity,
                    "UnitPrice": line.price_unit,
                    "Amount": line_amount,
                    "Discount": 0,
                    "AmountPlusDiscount": line_amount,
                    "TaxAmount": line_tax_amount,
                    "TaxPercent": tax_percent,
                    "TaxCode": tax_code,
                    "IsExempt": is_exempt,
                    "OperationCode": "C001",
                    "TotalAmount": round(line.price_total, 2),
                    "ProductType": 1
                })

            # Totales de Impuesto en VES
            total_tax_base = tax_base_general + tax_base_reduced
            total_tax_amount = tax_amount_general + tax_amount_reduced
            total_doc = total_tax_base + exempt_amount + total_tax_amount

            # Cálculo de IGTF (Si aplica, por defecto 3% sobre el total)
            igtf_percentage = 3.0
            igtf_amount = round(total_doc * (igtf_percentage / 100.0), 2)
            grand_total = total_doc + igtf_amount

            # Conversión a Divisa secundaria (USD)
            tax_base_usd = round(total_tax_base / exchange_rate, 2) if exchange_rate else 0.0
            tax_amount_usd = round(total_tax_amount / exchange_rate, 2) if exchange_rate else 0.0
            total_usd = round(total_doc / exchange_rate, 2) if exchange_rate else 0.0
            igtf_amount_usd = round(igtf_amount / exchange_rate, 2) if exchange_rate else 0.0
            grand_total_usd = round(grand_total / exchange_rate, 2) if exchange_rate else 0.0

            # 6. Estructura final del Payload JSON
            payload = {
                "SerieStrongId": company.seriestrongid,
                "SucursalStrongId": company.sucursal_strong_id or "81e836fe-eff1-4ca7-bcfd-5f079a44a503",
                "DocumentType": document_type,
                "Number": int(move.proximo_doc or 0),
                "EmissionDateAndTime": emission_date,
                "Name": partner.name or "Cliente Generico",
                "FiscalRegistryCode": fiscal_code,
                "FiscalRegistry": fiscal_registry,
                "Address": partner.street or "Caracas, Venezuela",
                "Phone": partner.phone or partner.mobile or "02120000000",
                "EmailTo": partner.email or "api@unidigital.global",
                "EmailCc": company.email or "api@unidigital.global",
                "PaymentType": "CONTADO",  # Método de pago fijo por ahora
                "Currency": "VES",
                "PreviousBalance": 0,
                "Discount": 0,
                "ExemptAmount": round(exempt_amount, 2),
                "TaxBase": round(total_tax_base, 2),
                "TaxAmount": round(total_tax_amount, 2),
                "TaxPercent": 16.0,
                "TaxPercentReduced": 8.0,
                "TaxPercentSumptuary": 31.0,
                "Total": round(total_doc, 2),
                "IGTFBaseAmount": round(total_doc, 2),
                "IGTFAmount": igtf_amount,
                "IGTFPercentage": igtf_percentage,
                "GrandTotal": grand_total,
                "AmountLetters": f"{grand_total:.2f} VES",
                "ConversionCurrency": "USD",
                "PreviousBalanceVES": 0,
                "DiscountVES": 0,
                "ExemptAmountVES": round(exempt_amount / exchange_rate, 2) if exchange_rate else 0.0,
                "TaxBaseVES": tax_base_usd,
                "TaxAmountVES": tax_amount_usd,
                "TaxPercentVES": 16.0,
                "TotalVES": total_usd,
                "IGTFBaseAmountVES": total_usd,
                "IGTFAmountVES": igtf_amount_usd,
                "GrandTotalVES": grand_total_usd,
                "AmountLettersVES": f"{grand_total_usd:.2f} USD",
                "ExchangeRate": exchange_rate,
                "SystemReference": move.name or "",
                "Note1": f"Documento emitido desde Odoo: {move.name}",
                "Note2": "",
                "Note3": "",
                "Extra": {},
                "ShippingAddress": partner.street or "Caracas, Venezuela",
                "Details": details
            }

            # Si es Nota de Crédito (NC) o Nota de Débito (ND), incluir AffectedDocumentNumber
            if document_type in ('NC', 'ND'):
                # Intenta tomar el número de documento afectado de la factura reversed_entry_id o del origen
                origin_doc_number = move.reversed_entry_id.proximo_doc or move.ref or "0"
                # Limpiar cualquier caracter no numérico por seguridad
                origin_number_clean = ''.join(filter(str.isdigit, str(origin_doc_number)))
                payload["AffectedDocumentNumber"] = int(origin_number_clean) if origin_number_clean else 0

            # 7. Envío del HTTP POST a Unidigital
            target_url = "https://qa.unidigital.global/digitalinvoice-core/documents/createandapprove"
            headers = {
                "Authorization": f"Bearer {company.unidg_jwt_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            try:
                _logger.info("Unidigital: Enviando documento %s a %s", move.name, target_url)
                response = requests.post(target_url, data=json.dumps(payload), headers=headers, timeout=20)
                res_json = response.json() if response.content else {}

                # Guardar respuestas en los campos del modelo
                move.hasErrors = str(res_json.get("hasErrors", False))
                move.result = json.dumps(res_json.get("result", {}))
                move.information = json.dumps(res_json.get("information", []))

                if response.status_code in (200, 201) and not res_json.get("hasErrors"):
                    _logger.info("Unidigital: Documento %s procesado con éxito.", move.name)
                    move.errorMessage = ""
                else:
                    errors = res_json.get("errors", [])
                    error_msg = json.dumps(errors) if errors else response.text
                    move.errorMessage = error_msg
                    _logger.error("Unidigital Error al emitir %s: %s", move.name, error_msg)

            except requests.exceptions.RequestException as e:
                move.hasErrors = "True"
                move.errorMessage = f"Error de conexión con la API: {str(e)}"
                _logger.error("Unidigital Excepción de Red: %s", str(e))