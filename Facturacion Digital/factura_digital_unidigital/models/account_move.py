# -*- coding: utf-8 -*-

import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    result = fields.Char()
    hasErrors = fields.Char()
    errorMessage = fields.Char()
    information = fields.Char()
    json_enviado = fields.Text(string="JSON Enviado")
    proximo_doc = fields.Char(compute='_compute_proximo_valor')

    @api.onchange('journal_id')
    def _compute_proximo_valor(self):
        for rec in self:
            rec.proximo_doc = rec.journal_id.doc_sequence_number_next

    def enviar_fact_digital(self):
        """Construye y envía el JSON del documento fiscal (FA, NC, ND) hacia Unidigital."""
        for move in self:
            company = move.company_id

            # 1. Obtener Token y Serie
            company.unidg_get_token()
            if not company.unidg_jwt_token or not company.seriestrongid:
                raise UserError(_("No se pudo obtener el Token o la Serie de Unidigital."))

            # 2. Tipo de documento
            doc_type_mapping = {
                'out_invoice': 'FA',
                'out_refund': 'NC',
                'out_receipt': 'ND',
            }
            document_type = doc_type_mapping.get(move.move_type)
            if not document_type:
                raise UserError(_("El tipo de documento '%s' no está soportado.") % move.move_type)

            # Homologación de moneda
            raw_currency = (move.currency_id.name or '').upper().strip()
            currency_code = 'VES' if raw_currency in ('VED', 'VEF', 'BS', 'BS.S', 'VES') else raw_currency

            # 3. Datos del Cliente / RIF
            partner = move.partner_id
            vat_clean = (partner.vat or '').replace('-', '').strip().upper()
            fiscal_code = vat_clean[0] if vat_clean and vat_clean[0].isalpha() else 'J'
            fiscal_registry = vat_clean[1:] if vat_clean and vat_clean[0].isalpha() else vat_clean

            # 4. Tasa y Fecha
            exchange_rate = getattr(move, 'tasa', 1.0) or 1.0
            emission_date = (move.invoice_date or fields.Date.today()).strftime('%Y-%m-%dT%H:%M:%S.000Z')

            # 5. Filtrar líneas válidas
            lines = move.invoice_line_ids.filtered(lambda l: l.display_type not in ('line_section', 'line_note'))
            if not lines:
                raise UserError(_("La factura no contiene líneas de productos/servicios válidas para enviar."))

            details = []
            tax_base_general = 0.0
            tax_amount_general = 0.0
            tax_base_reduced = 0.0
            tax_amount_reduced = 0.0
            exempt_amount = 0.0

            for line in lines:
                line_tax = line.tax_ids[:1]
                aliquot = line_tax.aliquot if line_tax else False
                tax_rate_amount = line_tax.amount if line_tax else 0.0
                
                is_exempt = False
                tax_code = "G"
                tax_percent = 16.0

                # Clasificación estricta por alícuotas
                if aliquot == 'exempt' or tax_rate_amount == 0:
                    is_exempt = True
                    tax_code = "E"
                    tax_percent = 0.0
                    exempt_amount += line.price_subtotal
                elif aliquot == 'reduced' or tax_rate_amount == 8:
                    tax_code = "R"
                    tax_percent = 8.0
                    tax_base_reduced += line.price_subtotal
                    tax_amount_reduced += (line.price_total - line.price_subtotal)
                else:
                    tax_code = "G"
                    tax_percent = 16.0
                    tax_base_general += line.price_subtotal
                    tax_amount_general += (line.price_total - line.price_subtotal)

                line_amount = round(line.price_subtotal, 2)
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

            # Redondeos principales VES
            tax_base_general = round(tax_base_general, 2)
            tax_amount_general = round(tax_amount_general, 2)
            tax_base_reduced = round(tax_base_reduced, 2)
            tax_amount_reduced = round(tax_amount_reduced, 2)
            exempt_amount = round(exempt_amount, 2)

            total_tax_amount = tax_amount_general + tax_amount_reduced
            total_doc = tax_base_general + tax_base_reduced + exempt_amount + total_tax_amount

            igtf_percentage = 3.0
            igtf_amount = round(total_doc * (igtf_percentage / 100.0), 2)
            grand_total = round(total_doc + igtf_amount, 2)

            # Conversión a USD
            tax_base_gen_usd = round(tax_base_general / exchange_rate, 2) if exchange_rate else 0.0
            tax_amount_gen_usd = round(tax_amount_general / exchange_rate, 2) if exchange_rate else 0.0
            
            tax_base_red_usd = round(tax_base_reduced / exchange_rate, 2) if exchange_rate else 0.0
            tax_amount_red_usd = round(tax_amount_reduced / exchange_rate, 2) if exchange_rate else 0.0

            exempt_usd = round(exempt_amount / exchange_rate, 2) if exchange_rate else 0.0
            total_usd = round(total_doc / exchange_rate, 2) if exchange_rate else 0.0
            igtf_usd = round(igtf_amount / exchange_rate, 2) if exchange_rate else 0.0
            grand_total_usd = round(grand_total / exchange_rate, 2) if exchange_rate else 0.0

            # 6. Payload Final adaptado a la validación de Unidigital
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
                "PaymentType": "CONTADO",
                "Currency": currency_code,
                "PreviousBalance": 0,
                "Discount": 0,
                
                # Desglose de Bases e Impuestos por separado
                "ExemptAmount": exempt_amount,
                "TaxBase": tax_base_general,               # Solo Base 16%
                "TaxAmount": tax_amount_general,           # Solo Impuesto 16%
                "TaxPercent": 16.0,
                
                "TaxBaseReduced": tax_base_reduced,         # Solo Base 8%
                "TaxAmountReduced": tax_amount_reduced,     # Solo Impuesto 8%
                "TaxPercentReduced": 8.0,
                
                "TaxPercentSumptuary": 31.0,
                "Total": total_doc,
                "IGTFBaseAmount": total_doc,
                "IGTFAmount": igtf_amount,
                "IGTFPercentage": igtf_percentage,
                "GrandTotal": grand_total,
                "AmountLetters": f"{grand_total:.2f} VES",
                
                # Conversión USD
                "ConversionCurrency": "USD",
                "PreviousBalanceVES": 0,
                "DiscountVES": 0,
                "ExemptAmountVES": exempt_usd,
                "TaxBaseVES": tax_base_gen_usd,             # Base 16% en USD
                "TaxAmountVES": tax_amount_gen_usd,         # Impuesto 16% en USD (1.60 USD)
                "TaxPercentVES": 16.0,
                
                "TaxBaseReducedVES": tax_base_red_usd,       # Base 8% en USD
                "TaxAmountReducedVES": tax_amount_red_usd,   # Impuesto 8% en USD
                "TaxPercentReducedVES": 8.0,
                
                "TotalVES": total_usd,
                "IGTFBaseAmountVES": total_usd,
                "IGTFAmountVES": igtf_usd,
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

            if document_type in ('NC', 'ND'):
                origin_doc_number = move.reversed_entry_id.proximo_doc or move.ref or "0"
                origin_number_clean = ''.join(filter(str.isdigit, str(origin_doc_number)))
                payload["AffectedDocumentNumber"] = int(origin_number_clean) if origin_number_clean else 0

            # Guardar payload en el campo de auditoría
            move.json_enviado = json.dumps(payload, indent=4, ensure_ascii=False)

            # 7. Envío HTTP
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