# -*- coding: utf-8 -*-

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

class RetentionVatIslr(models.Model):
    """Herencia del modelo de retenciones para integración con Unidigital (ISLR)."""
    _inherit = 'isrl.retention'

    result = fields.Char(copy=False)
    hasErrors = fields.Char(copy=False)
    errorMessage = fields.Text(copy=False)
    information = fields.Char(copy=False)
    json_enviado = fields.Text(string="JSON Enviado", copy=False)
    code = fields.Char(copy=False, string="Código de respuesta servidor API")
    message = fields.Text(copy=False)

    def envia_comp_ret_islr(self):
        """Prepara el JSON de ISLR y lo envía a la API de Unidigital."""
        for rec in self:
            company = rec.company_id or self.env.company
            partner = rec.partner_id
            invoice = rec.invoice_id

            if not invoice:
                rec.message = "Error: El comprobante no tiene una factura asociada."
                rec.hasErrors = "True"
                continue

            # 1. Obtener Token de Autenticación de la compañía
            token = False
            try:
                if hasattr(company, 'unidg_get_token'):
                    token_res = company.unidg_get_token()
                    # Manejar si devuelve un diccionario {'token': '...'} o directamente el string
                    if isinstance(token_res, dict):
                        token = token_res.get('token') or token_res.get('access_token')
                    else:
                        token = token_res
            except Exception as e_tok:
                _logger.error("Error ejecutando unidg_get_token(): %s", str(e_tok))

            if not token:
                rec.message = "Error al obtener Token de Unidigital"
                rec.errorMessage = "No se pudo obtener el token de autenticación desde res.company. Verifique los logs o la configuración del módulo."
                rec.hasErrors = "True"
                rec.code = "401"
                continue

            # 2. Mapeo de RIF del Proveedor / Cliente
            raw_vat = (partner.vat or '').replace('-', '').strip()
            fiscal_code = raw_vat[0].upper() if raw_vat and raw_vat[0].isalpha() else 'J'
            fiscal_number = raw_vat[1:] if raw_vat and raw_vat[0].isalpha() else raw_vat

            # 3. Formato de Fechas
            date_isrl_dt = rec.date_isrl or fields.Date.context_today(rec)
            emission_datetime = datetime.combine(date_isrl_dt, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%SZ")
            
            inv_date = invoice.invoice_date or invoice.date
            emission_date_str = inv_date.strftime("%d/%m/%Y") if inv_date else datetime.now().strftime("%d/%m/%Y")

            # 4. Construir arreglo de líneas ISLR
            islr_lines = []
            for line in rec.lines_id:
                concept_code = str(line.code or '001').zfill(3)
                islr_lines.append({
                    "ConceptCode": concept_code,
                    "TaxBase": round(line.base, 2),
                    "Total": round(invoice.amount_total, 2),
                    "TaxPercent": round(line.cantidad, 2),
                    "AmountRetained": round(line.total, 2),
                    "SubtrahendPN": round(line.sustraendo, 2),
                    "Extra": {}
                })

            # 5. Construir el documento único dentro del arreglo Documents
            control_num = getattr(invoice, 'nro_control', False) or getattr(invoice, 'l10n_ve_control_number', False) or invoice.name or ''

            doc_payload = {
                "EmissionDate": emission_date_str,
                "Number": invoice.name or rec.invoice_number or '',
                "DocumentType": "FA" if invoice.move_type in ('in_invoice', 'out_invoice') else "ND",
                "Serie": "0",
                "ControlNumber": control_num,
                "AffectedDocumentNumber": "",
                "Currency": invoice.currency_id.name or "VES",
                "ExemptAmount": 0.00,
                "Total": round(invoice.amount_total, 2),
                "IVA": [],
                "ISLR": islr_lines
            }

            # 6. Construir Payload Principal (Estructura "RR" Unidigital)
            seq_num = ''.join(filter(str.isdigit, str(rec.name or '0')))
            doc_number = int(seq_num) if seq_num else 1

            payload = {
                "DocumentType": "RR",
                "Number": doc_number,
                "EmissionDateAndTime": emission_datetime,
                "Name": partner.name or '',
                "FiscalRegistryCode": fiscal_code,
                "FiscalRegistry": fiscal_number,
                "Address": rec.get_address_partner() or 'Caracas, Venezuela',
                "Phone": partner.phone or partner.mobile or '00000000000',
                "EmailTo": partner.email or 'sin_correo@dominio.com',
                "PerceiverType": "PJ-DOMICILIADA",
                "TaxBase": round(rec.amount_untaxed, 2),
                "TaxAmount": 0.00,
                "TotalIGTF": 0.00,
                "AmountRetained": round(rec.vat_retentioned, 2),
                "SystemReference": f"ISLR-{rec.name or doc_number}",
                "Documents": [doc_payload]
            }

            # 7. Envío HTTP POST a la API
            url = "https://qa.unidigital.global/digitalinvoice-core/documents/createretention"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }

            payload_json_str = json.dumps(payload, indent=4)
            rec.json_enviado = payload_json_str

            try:
                _logger.info("Enviando Retención ISLR Unidigital ID %s: %s", rec.id, payload_json_str)
                response = requests.post(url, data=payload_json_str, headers=headers, timeout=30)
                
                rec.code = str(response.status_code)
                res_data = response.json()

                rec.hasErrors = str(res_data.get('hasErrors', False))
                rec.result = str(res_data.get('result', ''))
                rec.information = str(res_data.get('information', ''))

                if res_data.get('hasErrors'):
                    errors_list = res_data.get('errors', [])
                    err_msg = ""
                    for err in errors_list:
                        err_msg += f"{err.get('message', '')}\n"
                    rec.errorMessage = err_msg or str(res_data)
                    rec.message = "Error en emisión de Retención ISLR"
                else:
                    rec.errorMessage = ""
                    rec.message = "Comprobante emitido exitosamente"

            except Exception as e:
                _logger.error("Error al conectar con Unidigital ISLR: %s", str(e))
                rec.code = "500"
                rec.hasErrors = "True"
                rec.errorMessage = str(e)
                rec.message = "Excepción de conexión/red al enviar a Unidigital"