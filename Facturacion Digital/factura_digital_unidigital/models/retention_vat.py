# -*- coding: utf-8 -*-

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class RetentionVat(models.Model):
    """Integración con API Unidigital para Comprobantes de Retención de IVA SENIAT."""
    _inherit = 'vat.retention'

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    code = fields.Char(copy=False, string="Código de respuesta servidor API")

    def _prepare_unidigital_retention_json(self):
        """Construye el Payload envuelto en 'dto' exigido por la API /createretention."""
        self.ensure_one()

        partner = self.partner_id
        if not partner.vat:
            raise UserError(_("El Partner %s no tiene un número de RIF/CÉDULA configurado.") % partner.name)

        # 1. Separación del RIF/Cédula
        raw_vat = str(partner.vat).replace('-', '').replace(' ', '').upper()
        code_rif = raw_vat[0] if raw_vat[0].isalpha() else 'J'
        number_rif = raw_vat[1:] if raw_vat[0].isalpha() else raw_vat

        # 2. Formatear la fecha
        target_date = self.voucher_delivery_date or self.accouting_date or fields.Date.today()
        emission_dt = datetime.combine(target_date, datetime.min.time()).strftime('%Y-%m-%dT%H:%M:%SZ')

        # 3. Forzar moneda a VES
        curr_name = "VES"

        # 4. Mapeo del Listado de Documentos Retenidos
        documents_payload = []
        total_tax_base = 0.0
        total_tax_amount = 0.0
        total_retained = 0.0

        for line in self.retention_line_ids:
            invoice = line.invoice_id
            
            inv_date = invoice.invoice_date.strftime('%d/%m/%Y') if invoice and invoice.invoice_date else target_date.strftime('%d/%m/%Y')
            inv_number = invoice.name or line.invoice_number or "00000001"
            ctrl_number = getattr(invoice, 'nro_control', False) or getattr(invoice, 'l10n_ve_control_number', False) or "00-00000001"
            
            doc_type_map = {
                'out_invoice': 'FA',
                'in_invoice': 'FA',
                'out_refund': 'NC',
                'in_refund': 'NC',
            }
            doc_type = doc_type_map.get(invoice.move_type if invoice else self.type, 'FA')

            exempt_amt = line.valida_excento() if hasattr(line, 'valida_excento') else 0.0
            tax_base = line.base_imponible if line.base_imponible else line.amount_untaxed
            vat_amount = line.amount_vat_ret
            ret_rate = line.retention_rate or 75.00
            retained_amt = line.retention_amount

            total_tax_base += tax_base
            total_tax_amount += vat_amount
            total_retained += retained_amt

            documents_payload.append({
                "EmissionDate": inv_date,
                "Number": inv_number,
                "DocumentType": doc_type,
                "Serie": "0",
                "ControlNumber": ctrl_number,
                "AffectedDocumentNumber": getattr(invoice, 'fact_afect', '') or "",
                "Currency": curr_name,
                "ExemptAmount": round(exempt_amt, 2),
                "Total": round(tax_base + vat_amount + exempt_amt, 2),
                "IVA": [
                    {
                        "TaxCode": "G",
                        "TaxBase": round(tax_base, 2),
                        "TaxPercent": round(ret_rate, 2),
                        "TaxAmount": round(vat_amount, 2),
                        "RetentionPercent": round(ret_rate, 2),
                        "AmountRetained": round(retained_amt, 2)
                    }
                ],
                "ISLR": []
            })

        # Evitar desbordamiento de Int32 (máx 2.147.483.647) en 'Number'
        voucher_num_digits = ''.join(filter(str.isdigit, str(self.name or '')))
        if voucher_num_digits:
            numeric_voucher_number = int(voucher_num_digits[-8:])
        else:
            numeric_voucher_number = self.id

        dto_payload = {
            "DocumentType": "RI",
            "Number": numeric_voucher_number,
            "EmissionDateAndTime": emission_dt,
            "Name": partner.name or "",
            "FiscalRegistryCode": code_rif,
            "FiscalRegistry": number_rif,
            "Address": partner.street or "Caracas, Venezuela",
            "Phone": partner.phone or partner.mobile or "02120000000",
            "EmailTo": partner.email or "comprobantes@dominio.com",
            "PerceiverType": "PJ-DOMICILIADA",
            "TaxBase": round(total_tax_base, 2),
            "TaxAmount": round(total_tax_amount, 2),
            "TotalIGTF": 0,
            "AmountRetained": round(total_retained, 2),
            "SystemReference": self.name or f"RET-{self.id}",
            "Documents": documents_payload
        }

        # Estructura requerida por Unidigital
        return {"dto": dto_payload}

    def envia_comp_ret_iva(self):
        """Envía el JSON de Retención de IVA a la API Unidigital guardando respuesta al estilo AccountMove."""
        for rec in self:
            company = rec.company_id
            url = getattr(company, 'unidigital_retention_url', False) or 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention'
            token = getattr(company, 'unidigital_token', False)

            if not url:
                raise UserError(_("No se ha configurado la URL de retenciones para Unidigital."))

            # 1. Armar y guardar JSON de envío de forma persistente
            payload_data = rec._prepare_unidigital_retention_json()
            json_payload = json.dumps(payload_data, indent=4, ensure_ascii=False)
            rec.json_enviado = json_payload

            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            if token:
                headers['Authorization'] = f"Bearer {token}"

            _logger.info("Enviando Retención IVA Unidigital (ID %s): %s", rec.id, json_payload)

            try:
                response = requests.post(url, data=json_payload.encode('utf-8'), headers=headers, timeout=30)
                http_status = response.status_code
                
                try:
                    res_json = response.json() if response.content else {}
                except Exception:
                    res_json = {"raw_response": response.text}

                _logger.info("Respuesta Unidigital (ID %s): %s", rec.id, res_json)

                # Guardado de variables de respuesta exactamente igual que en Facturas (account_move)
                rec.code = str(res_json.get("code") if res_json.get("code") is not None else http_status)
                rec.hasErrors = str(res_json.get("hasErrors", http_status not in (200, 201)))
                rec.result = json.dumps(res_json.get("result")) if res_json.get("result") is not None else str(res_json.get("result", ""))
                rec.information = json.dumps(res_json.get("information", []))

                # Procesamiento y formateo de errores
                errors_data = res_json.get("errors", [])
                if errors_data:
                    if isinstance(errors_data, list):
                        error_lines = []
                        for err in errors_data:
                            if isinstance(err, dict):
                                msg = err.get('message') or err.get('errorMessage') or str(err)
                                error_lines.append(f"- {msg}")
                            else:
                                error_lines.append(f"- {str(err)}")
                        rec.errorMessage = "\n".join(error_lines)
                    else:
                        rec.errorMessage = str(errors_data)
                elif http_status not in (200, 201) or res_json.get("hasErrors"):
                    rec.errorMessage = res_json.get("message") or response.text or "Error en la petición API"
                else:
                    rec.errorMessage = ""

                # Evaluar resultado para respuesta en UI sin lanzar UserError que borre los datos
                if http_status in (200, 201) and not res_json.get("hasErrors"):
                    if rec.state == 'draft':
                        rec.action_posted()

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Comprobante Enviado'),
                            'message': _('La retención de IVA fue procesada exitosamente.'),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    # En lugar de raise UserError, enviamos una notificación de advertencia.
                    # Esto permite que la ventana actualice los campos guardados en la BD.
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error devuelto por la API Unidigital'),
                            'message': rec.errorMessage or _("Error procesando el comprobante en Unidigital."),
                            'type': 'danger',
                            'sticky': True,
                        }
                    }

            except requests.exceptions.RequestException as e:
                rec.hasErrors = "True"
                rec.code = "500"
                rec.errorMessage = f"Error de conexión con la API: {str(e)}"
                _logger.error("Unidigital Excepción de Red: %s", str(e))
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error de Conexión'),
                        'message': rec.errorMessage,
                        'type': 'danger',
                        'sticky': True,
                    }
                }