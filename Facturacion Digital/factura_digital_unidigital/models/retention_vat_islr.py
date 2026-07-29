# -*- coding: utf-8 -*

import logging
import requests
import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger('__name__')

class RetentionVatIslr(models.Model):
    """This is a main model for rentetion vat control."""
    _inherit = 'isrl.retention'

    nro_ctrol_novus = fields.Char()

    def action_post(self):
        super().action_post()
        self.envia_comp_ret_iva()

    def envia_comp_ret_iva(self):
        if self.company_id.billing_type == 'digital' and self.invoice_id.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
            if self.state == "done":
                for rec in self:
                    # 1. Validaciones previas de la configuración de la compañía
                    if not rec.company_id.token:
                        raise UserError(_("No se ha configurado el Token de Autenticación en la Compañía."))
                    
                    if not rec.company_id.rif_autenticacion:
                        raise UserError(_("No se ha configurado el RIF de Autenticación en la Compañía."))

                    rif_emisor = rec.company_id.rif_autenticacion.strip().upper()

                    # 2. Manejo seguro de la fecha de emisión
                    fecha_fuente = rec.invoice_id.date or rec.date_move or rec.date_isrl or datetime.now().date()
                    fecha_emision = datetime.combine(fecha_fuente, datetime.min.time())
                    fecha_emision_str = fecha_emision.strftime("%Y-%m-%d %H:%M:%S")

                    # 3. Asignación del Número Interno Fiscal real de la retención (Tu gran hallazgo)
                    nro_interno_fiscal = str(rec.name or '').strip()
                    if not nro_interno_fiscal or nro_interno_fiscal == '/':
                        ano_mes = fecha_emision.strftime("%Y%m")
                        nro_secuencia = rec.company_id.x_nro_interno_comp_ret_islr or 150
                        secuencia_8_digitos = str(nro_secuencia).zfill(8)
                        nro_interno_fiscal = f"{ano_mes}{secuencia_8_digitos}"

                    # 4. Construcción del Bloque Details calcado de Postman
                    details_list = []
                    
                    for line in rec.lines_id:
                        type_transaction = 1
                        if rec.invoice_id.move_type == 'in_refund':
                            type_transaction = 3
                        elif rec.invoice_id.move_type == 'in_receipt':
                            type_transaction = 2

                        fecha_doc_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if rec.invoice_id.invoice_date:
                            fecha_doc_str = datetime.combine(rec.invoice_id.invoice_date, datetime.min.time()).strftime("%Y-%m-%d %H:%M:%S")

                        nro_documento_odoo = rec.invoice_id.invoice_number_next or "0000"
                        factura_afectada_odoo = rec.invoice_id.fact_afect or ""

                        # Formato de 3 dígitos estricto para el código de concepto (ej: "022")
                        codigo_concepto_str = str(line.code or '').strip().zfill(3) if line.code else "000"

                        line_data = {
                            "code": codigo_concepto_str,  
                            "date_document": fecha_doc_str,
                            "internal_number": nro_documento_odoo,
                            "type_transaction": int(type_transaction),
                            "affected_document": factura_afectada_odoo,
                            "control_number": rec.invoice_id.invoice_number_control or "0000",
                            "amount": round(rec.invoice_id.amount_total, 2), 
                            "tax_income": round(line.base, 2),  
                            "extra_purchases": "0.00",  
                            "tax": round(line.cantidad, 2),  
                            "tax_amount": 0.00,  
                            "amount_withheld": round(line.total, 2),  
                            "percentage_of_retention": 100.00,  
                            "concept": str(line.name.name or '') if line.name else '',  
                            "subtract": str(line.sustraendo), 
                        }
                        details_list.append(line_data)

                    # 5. Totales acumulados para la sección 'amount'
                    total_base_islr = round(sum(l.base for l in rec.lines_id), 2)
                    total_retenido_islr = round(sum(l.retention for l in rec.lines_id), 2)
                    tasa_concepto_principal = round(rec.lines_id[0].cantidad if rec.lines_id else 0.00, 2)

                    rif_proveedor = rec.partner_id.vat.replace('-', '').replace(' ', '').upper() if rec.partner_id.vat else "V000000000"

                    # 6. Payload Estructurado perfectamente cerrado
                    payload = {
                        "rif": rif_emisor,
                        "client": {
                            "company_name": rec.partner_id.name or "Proveedor de Pruebas ISLR",
                            "document": rif_proveedor,
                            "idtypedocument": 1,
                            "direction": rec.partner_id.street or "Caracas, Venezuela",
                            "phone": rec.partner_id.phone or rec.partner_id.mobile or "02120000000",
                            "email": rec.partner_id.email or "correo@predeterminado.com"
                        },
                        "document": {
                            "emision_date": fecha_emision_str,
                            "delivery_date": fecha_emision_str,
                            "id_document": 7,  
                            "internal_number": nro_interno_fiscal,  
                            "sucursal": "",
                            "serie": ""
                        },
                        "amount": {
                            "percentage_of_retention": 0,  
                            "tax": tasa_concepto_principal,   
                            "tax_income": total_base_islr,    
                            "amount_tax": 0.00,               
                            "amount_withheld": total_retenido_islr, 
                            "total": round(rec.invoice_id.amount_total, 2) 
                        },
                        "details": details_list,
                        "sendemail": False
                    }

                    # 7. Envío del Request por método POST
                    #raise UserError(_("Valor:%s")%payload)
                    url_retencion_islr=rec.company_id.url_api+rec.company_id.x_end_point_doc_rete
                    #url_retencion_islr = "http://api-test.novusfactura.net/facturacion/retencion/V4"
                    headers = {
                        'Authorization': f'Bearer {rec.company_id.token.strip()}',
                        'Content-Type': 'application/json'
                    }

                    try:
                        _logger.info(">>> ENVIANDO RETENCION ISLR (V4): %s", json.dumps(payload))
                        response = requests.post(url_retencion_islr, headers=headers, data=json.dumps(payload), timeout=20)
                        
                        _logger.info(">>> NOVUS RESPUESTA STATUS: %s", response.status_code)
                        _logger.info(">>> NOVUS RESPUESTA TEXT: %s", response.text)

                        if response.status_code not in (200, 201):
                            try:
                                err_json = response.json()
                                errors = err_json.get('errors', [])
                                if isinstance(errors, dict):
                                    msg_err = errors.get('message', '')
                                elif isinstance(errors, list) and errors:
                                    msg_err = ", ".join([e.get('message', '') for e in errors])
                                else:
                                    msg_err = err_json.get('message', response.text)
                                    err = err_json.get('error', _("Error interno desconocido en el API de Novus."))
                            except Exception:
                                msg_err = response.text
                                
                            raise UserError(_("Error de Validación Fiscal Novus ISLR: (Código %s): %s, %s") % (response.status_code, msg_err,err))
                        
                        res_data = response.json()
                        
                        # 8. Procesamiento del éxito de la transacción
                        if res_data.get('status') or res_data.get('success'):
                            datos = res_data.get('data', {})
                            num_fiscal = datos.get('numerodocumento')
                            
                            
                            if 'nro_ctrol_novus' in rec._fields:
                                rec.nro_ctrol_novus = num_fiscal
                            
                            if not rec.name or rec.name == '/':
                                rec.name = nro_interno_fiscal
                                if 'x_nro_interno_comp_ret_islr' in rec.company_id._fields:
                                    rec.company_id.x_nro_interno_comp_ret_islr += 1
                                elif 'x_nro_interno_comp_ret_iva' in rec.company_id._fields:
                                    rec.company_id.x_nro_interno_comp_ret_iva += 1
                        else:
                            msg_err = res_data.get('message', _("Error interno desconocido en el API de Novus."))
                            err = res_data.get('error', _("Error interno desconocido en el API de Novus."))
                            raise UserError(_("Error de Validación Fiscal Novus ISLR: %s, %s") % (msg_err,err))

                    except requests.exceptions.RequestException as e:
                        _logger.error("Error de comunicación con Novus en Retenciones ISLR: %s", str(e))
                        raise UserError(_("No se pudo conectar con el servicio de Novus Factura V4. Detalles: %s") % str(e))