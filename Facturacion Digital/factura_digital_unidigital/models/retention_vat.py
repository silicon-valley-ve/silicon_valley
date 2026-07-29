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
        """Construye el Payload plano esperado por la API /createretention de Unidigital."""
        self.ensure_one()

        partner = self.partner_id
        if not partner.vat:
            raise UserError(_("El Partner %s no tiene un número de RIF/CÉDULA configurado.") % partner.name)

        # 1. Separación del RIF/Cédula (Ejemplo: J-600500401 -> J / 600500401)
        raw_vat = str(partner.vat).replace('-', '').replace(' ', '').upper()
        code_rif = raw_vat[0] if raw_vat[0].isalpha() else 'J'
        number_rif = raw_vat[1:] if raw_vat[0].isalpha() else raw_vat

        # 2. Formatear la fecha de emisión (ISO 8601 UTC)
        target_date = self.voucher_delivery_date or self.accouting_date or fields.Date.today()
        emission_dt = datetime.combine(target_date, datetime.min.time()).strftime('%Y-%m-%dT%H:%M:%SZ')

        curr_name = "VES"

        # 3. Mapeo del Listado de Documentos Retenidos
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

            # Alícuota real del IVA (ej. 16.0%)
            tax_percent = round((vat_amount / tax_base * 100), 2) if tax_base > 0 else 16.00

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
                        "TaxPercent": tax_percent,
                        "TaxAmount": round(vat_amount, 2),
                        "RetentionPercent": round(ret_rate, 2),
                        "AmountRetained": round(retained_amt, 2)
                    }
                ],
                "ISLR": []
            })

        # Extraer dígitos para evitar desbordamiento Int32
        voucher_num_digits = ''.join(filter(str.isdigit, str(self.name or '')))
        numeric_voucher_number = int(voucher_num_digits[-8:]) if voucher_num_digits else self.id

        # Payload PLANO (Sin wrapper 'dto')
        return {
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
            "SystemReference": self.name or f"RI-{self.id}",
            "Documents": documents_payload
        }

    def envia_comp_ret_iva(self):
        """Método invocado por el botón de la vista XML."""
        for rec in self:
            company = rec.company_id
            url = getattr(company, 'unidigital_retention_url', False) or 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention'

            # --- OBTENCIÓN DEL TOKEN DESDE RES.COMPANY ---
            token = False
            if hasattr(company, 'unidigital_get_token'):
                token = company.unidigital_get_token()
            elif hasattr(company, 'get_unidigital_token'):
                token = company.get_unidigital_token()
            else:
                token = getattr(company, 'unidigital_token', False)

            if not url:
                raise UserError(_("No se ha configurado la URL de retenciones para Unidigital."))

            # 1. Generar JSON y guardarlo en el campo
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

                # 2. Registrar la respuesta en los campos del modelo
                rec.code = str(res_json.get("code") if res_json.get("code") is not None else http_status)
                rec.hasErrors = str(res_json.get("hasErrors", http_status not in (200, 201)))
                rec.result = json.dumps(res_json.get("result")) if res_json.get("result") is not None else str(res_json.get("result", ""))
                rec.information = json.dumps(res_json.get("information", []))

                # Mapear mensajes de error
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
                    rec.errorMessage = res_json.get("message") or response.text or f"Error HTTP {http_status} en la petición API"
                else:
                    rec.errorMessage = ""

                # 3. Notificación a la interfaz de Odoo
                if http_status in (200, 201) and not res_json.get("hasErrors"):
                    if hasattr(rec, 'state') and rec.state == 'draft' and hasattr(rec, 'action_posted'):
                        rec.action_posted()

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Comprobante Enviado'),
                            'message': _('La retención de IVA fue procesada exitosamente en Unidigital.'),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Error devuelto por la API Unidigital'),
                            'message': rec.errorMessage or _("Error procesando la retención."),
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