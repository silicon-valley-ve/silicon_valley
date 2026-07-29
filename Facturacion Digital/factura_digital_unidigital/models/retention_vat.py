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
    #proximo_doc = fields.Char(compute='_compute_proximo_valor')
    #proximo_ctrl = fields.Char(compute='_compute_proximo_ctrl')
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
            # Tomar los últimos 8 dígitos para garantizar un entero válido dentro de Int32
            numeric_voucher_number = int(voucher_num_digits[-8:])
        else:
            numeric_voucher_number = self.id

        dto_payload = {
            "DocumentType": "RI",
            "Number": numeric_voucher_number,
            "EmissionDateAndTime": emission_dt,
            "Name": partner.name,
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

        # La API requiere que todo vaya envuelto dentro de 'dto'
        return {"dto": dto_payload}

    def envia_comp_ret_iva(self):
        """Envía el JSON de Retención de IVA a la API Unidigital."""
        self.ensure_one()

        company = self.company_id
        url = getattr(company, 'unidigital_retention_url', False) or 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention'
        token = getattr(company, 'unidigital_token', False)

        if not url:
            raise UserError(_("No se ha configurado la URL de retenciones para Unidigital."))

        # 1. Armar JSON dentro del wrapper 'dto'
        payload_data = self._prepare_unidigital_retention_json()
        json_payload = json.dumps(payload_data, indent=2, ensure_ascii=False)
        
        # 2. Guardar en BD antes de consultar a la API (persistir sin importar respuesta)
        self.write({'json_enviado': json_payload})
        self.env.cr.commit()

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if token:
            headers['Authorization'] = f"Bearer {token}"

        _logger.info("Enviando Retención IVA Unidigital (ID %s): %s", self.id, json_payload)

        try:
            response = requests.post(url, data=json_payload.encode('utf-8'), headers=headers, timeout=30)
            self.write({'code': str(response.status_code)})

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_response": response.text}

            _logger.info("Respuesta Unidigital (ID %s): %s", self.id, res_json)

            val_result = str(res_json.get('result', ''))
            val_has_errors = str(res_json.get('hasErrors', response.status_code not in (200, 201)))
            val_info = json.dumps(res_json.get('information', []))

            self.write({
                'result': val_result,
                'hasErrors': val_has_errors,
                'information': val_info,
            })

            # Verificar si hubo errores en la API
            if res_json.get('hasErrors') or response.status_code not in (200, 201):
                error_msg = ""
                errors_list = res_json.get('errors', [])
                
                if isinstance(errors_list, list) and errors_list:
                    for err in errors_list:
                        if isinstance(err, dict):
                            if 'errors' in err and isinstance(err['errors'], list):
                                for sub_err in err['errors']:
                                    error_msg += f"- [{sub_err.get('whatIsEval')}] {sub_err.get('errorMessage')}\n"
                            else:
                                error_msg += f"- {err.get('message', err.get('errorMessage', str(err)))}\n"
                        else:
                            error_msg += f"- {str(err)}\n"
                else:
                    error_msg = res_json.get('message') or res_json.get('Message') or response.text or "Error desconocido en API Unidigital"

                self.write({'errorMessage': error_msg})
                self.env.cr.commit()
                
                raise UserError(_("Error devuelto por la API Unidigital:\n%s") % error_msg)

            else:
                self.write({'errorMessage': False})
                if self.state == 'draft':
                    self.action_posted()

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

        except requests.exceptions.RequestException as e:
            err_str = str(e)
            self.write({'errorMessage': err_str})
            self.env.cr.commit()
            _logger.error("Error de conexión con API Unidigital: %s", err_str)
            raise UserError(_("No se pudo conectar con el servidor de Unidigital: %s") % err_str)