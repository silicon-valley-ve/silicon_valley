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
    proximo_doc = fields.Char(compute='_compute_proximo_valor')
    proximo_ctrl = fields.Char(compute='_compute_proximo_ctrl')
    code = fields.Char(copy=False, string="Código de respuesta servidor API")

    def _prepare_unidigital_retention_json(self):
        """Construye el Payload exacto exigido por la API /createretention."""
        self.ensure_one()

        partner = self.partner_id
        if not partner.vat:
            raise UserError(_("El Partner %s no tiene un número de RIF/CEDULA configurado.") % partner.name)

        # 1. Separación del RIF/Cédula en Letra (FiscalRegistryCode) y Número (FiscalRegistry)
        raw_vat = str(partner.vat).replace('-', '').replace(' ', '').upper()
        code_rif = raw_vat[0] if raw_vat[0].isalpha() else 'J'
        number_rif = raw_vat[1:] if raw_vat[0].isalpha() else raw_vat

        # 2. Formatear la fecha de emisión en ISO UTC (Ej: 2026-07-29T12:00:00Z)
        target_date = self.voucher_delivery_date or self.accouting_date or fields.Date.today()
        emission_dt = datetime.combine(target_date, datetime.min.time()).strftime('%Y-%m-%dT%H:%M:%SZ')

        # 3. Mapeo del Listado de Documentos Retenidos (Documents)
        documents_payload = []
        total_tax_base = 0.0
        total_tax_amount = 0.0
        total_retained = 0.0

        for line in self.retention_line_ids:
            invoice = line.invoice_id
            
            # Datos de la factura origen
            inv_date = invoice.invoice_date.strftime('%d/%m/%Y') if invoice and invoice.invoice_date else target_date.strftime('%d/%m/%Y')
            inv_number = invoice.name or line.invoice_number or "00000001"
            ctrl_number = invoice.nro_control if hasattr(invoice, 'nro_control') and invoice.nro_control else "00-00000001"
            
            # Mapeo de Tipo de Documento Fiscal (FA = Factura, NC = Nota de Crédito, ND = Nota de Débito)
            doc_type_map = {
                'out_invoice': 'FA',
                'in_invoice': 'FA',
                'out_refund': 'NC',
                'in_refund': 'NC',
            }
            doc_type = doc_type_map.get(invoice.move_type if invoice else self.type, 'FA')

            # Cálculo de exento y montos según la línea de retención
            exempt_amt = line.valida_excento() if hasattr(line, 'valida_excento') else 0.0
            tax_base = line.base_imponible if line.base_imponible else line.amount_untaxed
            vat_amount = line.amount_vat_ret
            ret_rate = line.retention_rate or 75.00
            retained_amt = line.retention_amount

            # Acumuladores generales del comprobante
            total_tax_base += tax_base
            total_tax_amount += vat_amount
            total_retained += retained_amt

            # Documento en sub-arreglo
            documents_payload.append({
                "EmissionDate": inv_date,
                "Number": inv_number,
                "DocumentType": doc_type,
                "Serie": "0",
                "ControlNumber": ctrl_number,
                "AffectedDocumentNumber": getattr(invoice, 'fact_afect', '') or "",
                "Currency": self.currency_id.name or "VES",
                "ExemptAmount": round(exempt_amt, 2),
                "Total": round(tax_base + vat_amount + exempt_amt, 2),
                "IVA": [
                    {
                        "TaxCode": "G", # Impuesto General IVA (16%)
                        "TaxBase": round(tax_base, 2),
                        "TaxPercent": round(ret_rate, 2), # Se envía el % de retención según regla Unidigital
                        "TaxAmount": round(vat_amount, 2),
                        "RetentionPercent": round(ret_rate, 2), # 75.00 o 100.00
                        "AmountRetained": round(retained_amt, 2)
                    }
                ],
                "ISLR": []
            })

        # 4. Limpiar el número del comprobante para extraer solo dígitos (Ej: "00000102" -> 102)
        voucher_num_digits = ''.join(filter(str.isdigit, str(self.name or '1')))
        numeric_voucher_number = int(voucher_num_digits) if voucher_num_digits else 1

        # 5. Armado de la estructura JSON Principal
        payload = {
            "DocumentType": "RI", # RI = Retención de IVA
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
            "SystemReference": self.name or "RET-001",
            "Documents": documents_payload
        }

        return payload

    def envia_comp_ret_iva(self):
        """Envía el JSON de Retención de IVA a la API Unidigital."""
        self.ensure_one()

        # 1. Obtener parámetros/credenciales de la compañía
        company = self.company_id
        # Reemplazar/adaptar según la ubicación real de tus campos de token/URL en res.company o ir.config_parameter
        url = getattr(company, 'unidigital_retention_url', 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention')
        token = getattr(company, 'unidigital_token', False)

        if not url:
            raise UserError(_("No se ha configurado la URL de retenciones para Unidigital."))

        # 2. Construir JSON Payload
        payload_data = self._prepare_unidigital_retention_json()
        json_payload = json.dumps(payload_data, indent=2, ensure_ascii=False)
        self.json_enviado = json_payload

        # 3. Preparar Headers y Petición HTTP
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if token:
            headers['Authorization'] = f"Bearer {token}"

        _logger.info("Enviando Retención IVA Unidigital (ID %s): %s", self.id, json_payload)

        try:
            response = requests.post(url, data=json_payload.encode('utf-8'), headers=headers, timeout=30)
            self.code = str(response.status_code)
            res_json = response.json() if response.content else {}

            _logger.info("Respuesta Unidigital (ID %s): %s", self.id, res_json)

            # 4. Manejo de Respuesta de la API
            self.result = str(res_json.get('result'))
            self.hasErrors = str(res_json.get('hasErrors', False))
            self.information = json.dumps(res_json.get('information', []))

            if res_json.get('hasErrors') or response.status_code not in (200, 201):
                # Extraer mensaje detallado de error de la API
                errors_list = res_json.get('errors', [])
                error_msg = ""
                
                for err in errors_list:
                    if 'errors' in err and isinstance(err['errors'], list):
                        for sub_err in err['errors']:
                            error_msg += f"- [{sub_err.get('whatIsEval')}] {sub_err.get('errorMessage')}\n"
                    else:
                        error_msg += f"- {err.get('message', 'Error desconocido')}\n"

                self.errorMessage = error_msg or str(res_json)
                raise UserError(_("Error devuelto por la API Unidigital:\n%s") % self.errorMessage)

            else:
                self.errorMessage = False
                # Confirmar estado o publicar comprobante en Odoo tras emisión exitosa
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
            self.errorMessage = str(e)
            _logger.error("Error de conexión con API Unidigital: %s", str(e))
            raise UserError(_("No se pudo conectar con el servidor de Unidigital: %s") % str(e))