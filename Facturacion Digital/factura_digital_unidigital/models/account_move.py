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
        """Construye y envía el JSON del documento fiscal hacia Unidigital."""
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

            # Homologación de moneda principal
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
                tax_percent = 16

                # Subtotales e impuestos por línea redondeados
                line_subtotal = round(line.price_subtotal, 2)
                line_tax_amount = round(line.price_total - line.price_subtotal, 2)
                line_total = round(line.price_total, 2)

                # Clasificación por alícuota
                if aliquot == 'exempt' or tax_rate_amount == 0:
                    is_exempt = True
                    tax_code = "E"
                    tax_percent = 0
                    exempt_amount += line_subtotal
                elif aliquot == 'reduced' or tax_rate_amount == 8:
                    tax_code = "R"
                    tax_percent = 8
                    tax_base_reduced += line_subtotal
                    tax_amount_reduced += line_tax_amount
                else:
                    tax_code = "G"
                    tax_percent = 16
                    tax_base_general += line_subtotal
                    tax_amount_general += line_tax_amount

                details.append({
                    "Description": line.name or "Producto/Servicio",
                    "ProductType": 1,
                    "Quantity": line.quantity,
                    "UnitPrice": line.price_unit,
                    "Amount": line_subtotal,
                    "Discount": 0,
                    "AmountPlusDiscount": line_subtotal,
                    "TaxCode": tax_code,
                    "TaxPercent": tax_percent,
                    "TaxAmount": line_tax_amount,
                    "IsExempt": is_exempt,
                    "OperationCode": "C001",
                    "TotalAmount": line_total
                })

            # Redondeo de totales en Moneda Base (VES)
            tax_base_general = round(tax_base_general, 2)
            tax_amount_general = round(tax_amount_general, 2)
            tax_base_reduced = round(tax_base_reduced, 2)
            tax_amount_reduced = round(tax_amount_reduced, 2)
            exempt_amount = round(exempt_amount, 2)

            # Suma total exacta basada en las líneas enviadas (para evitar descalces de 1 céntimo)
            total_doc = round(tax_base_general + tax_base_reduced + exempt_amount + tax_amount_general + tax_amount_reduced, 2)

            # Conversión a Divisa Referencial (USD)
            tax_base_gen_usd = round(tax_base_general / exchange_rate, 2) if exchange_rate else 0.0
            tax_amount_gen_usd = round(tax_amount_general / exchange_rate, 2) if exchange_rate else 0.0
            
            tax_base_red_usd = round(tax_base_reduced / exchange_rate, 2) if exchange_rate else 0.0
            tax_amount_red_usd = round(tax_amount_reduced / exchange_rate, 2) if exchange_rate else 0.0

            exempt_usd = round(exempt_amount / exchange_rate, 2) if exchange_rate else 0.0
            total_usd = round(total_doc / exchange_rate, 2) if exchange_rate else 0.0

            # 6. Payload Final siguiendo la plantilla exacta de Postman
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
                
                # Desglose de Alícuotas
                "ExemptAmount": exempt_amount,
                "TaxBase": tax_base_general,
                "TaxPercent": 16,
                "TaxAmount": tax_amount_general,
                
                "TaxBaseReduced": tax_base_reduced,
                "TaxPercentReduced": 8,
                "TaxAmountReduced": tax_amount_reduced,
                
                "TaxBaseSumptuary": 0.00,
                "TaxPercentSumptuary": 31,
                "TaxAmountSumptuary": 0.00,
                
                # Sin IGTF (Porcentaje en 3 por exigencia de regla de negocio Unidigital)
                "IGTFPercentage": 3,
                "IGTFBaseAmount": 0.00,
                "IGTFAmount": 0.00,
                
                "Total": total_doc,
                "GrandTotal": total_doc,
                "AmountLetters": f"{total_doc:.2f} VES",
                
                "ExchangeRate": exchange_rate,
                "ConversionCurrency": "USD",
                "PreviousBalanceVES": 0,
                "DiscountVES": 0,
                
                # Desglose Divisa Referencial (USD)
                "ExemptAmountVES": exempt_usd,
                "TaxBaseVES": tax_base_gen_usd,
                "TaxPercentVES": 16,
                "TaxAmountVES": tax_amount_gen_usd,
                
                "TaxBaseReducedVES": tax_base_red_usd,
                "TaxPercentReducedVES": 8,
                "TaxAmountReducedVES": tax_amount_red_usd,
                
                "TaxBaseSumptuaryVES": 0.00,
                "TaxPercentSumptuaryVES": 31,
                "TaxAmountSumptuaryVES": 0.00,
                
                "TotalVES": total_usd,
                "GrandTotalVES": total_usd,
                "AmountLettersVES": f"{total_usd:.2f} USD",
                
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

            # Guardar JSON para auditoría
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