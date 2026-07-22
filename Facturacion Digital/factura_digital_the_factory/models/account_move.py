# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, float_is_zero, date_utils, email_split, email_re, html_escape, is_html_empty
from odoo.tools.misc import formatLang, format_date, get_lang
from odoo.osv import expression

from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import contextmanager
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import ast
import json
import re
import warnings


import requests
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    validaciones=fields.Char(copy=False)
    codigo=fields.Char(copy=False)
    mensaje=fields.Char(copy=False)
    resultado=fields.Char(copy=False)
    token=fields.Char(copy=False)
    urlConsulta = fields.Char(copy=False)

    def doc_type_conv(self,valor):
        if valor=='v':
            result='V'
        if valor=='c':
            result='C'
        if valor=="g":
            result="G"
        if valor=="j":
            result="J"
        if valor=="e":
            result="E"
        if valor=="p":
            result="P"
        return result

##################################################################
    def button_draft(self):
        res=super().button_draft()
        if self.company_id.usar_fact_digi==True:
            if self.move_type in ('out_invoice','out_refund'):
                raise UserError("No puede revertir esta factura o llevarla a borrador. Cree una Nota de credito y luego realice una nueva factura")
        return res

    def action_post(self):
        res=super().action_post()
        self.simular()
        return res

    def simular(self):
        if self.company_id.usar_fact_digi==True:
            if self.move_type not in ('entry','in_invoice','in_refund'):
                self.company_id.tfhka_get_token()
                self.token=self.company_id.tfhka_jwt_token
                self.enviar_fact_digital()

    def monto_eqv_bs(self,valor):
        if self.currency_id==self.company_id.currency_id:
            result=valor
        else:
            result=valor*self.os_currency_rate
        return round(result,2)

    def enviar_fact_digital(self):
        """
        Envía el JSON de emisión fijo (tal como fue proporcionado) a la API de TFHKA.
        """
        self.ensure_one()

        # Construcción parametros
        fecha_emision_dt = fields.Date.today()
        fecha_emision_tfhka = fecha_emision_dt.strftime('%d/%m/%Y')
        fecha_vencimiento = self.invoice_date_due.strftime('%d/%m/%Y')
        hora_emision_tfhka = datetime.now().strftime('%I:%M:%S %p').lower()
        transaccion_id=format(self.id, 'x')
        #raise UserError(_("transaccion_id=%s")%transaccion_id)
        address_parts = [
            self.partner_id.street or '',
            self.partner_id.street2 or '',
            self.partner_id.city or '',
            self.partner_id.state_id.name or '',
        ]
        direccion_comprador = ", ".join(filter(None, address_parts))
        detalles_items = []
        for index, line in enumerate(self.invoice_line_ids.filtered(lambda l: not l.display_type)):
            codigo_impuesto="G" if line.price_total-line.price_subtotal!=0 else "E"
            tasa_iva="16" if line.price_total-line.price_subtotal!=0 else "0"
            item = {
                "NumeroLinea": str(index + 1),
                "CodigoCIIU": None,
                "CodigoPLU": line.product_id.default_code or '', # Código de producto de Odoo
                "IndicadorBienoServicio": "2", # 1=Bien, 2=Servicio (ajustar según tu necesidad)
                "Descripcion": line.product_id.name,
                "Cantidad": str(round(line.quantity, 2)),
                "UnidadMedida": None,
                "PrecioUnitario": str(round(self.monto_eqv_bs(line.price_unit), 2)),
                "DescuentoMonto": None,
                "RecargoMonto": None,
                "PrecioItem": str(round(self.monto_eqv_bs(line.price_subtotal), 2)), # Subtotal antes de impuestos
                "PrecioAntesDescuento": None,
                "CodigoImpuesto": codigo_impuesto,
                "TasaIVA": tasa_iva,
                "ValorIVA": str(round(self.monto_eqv_bs(line.price_total-line.price_subtotal), 2)),
                "ValorTotalItem": str(round(self.monto_eqv_bs(line.price_total), 2)), # Total con impuestos
                "InfoAdicionalItem": None,
                "ListaItemOTI": None
            }
            detalles_items.append(item)
        
        # 1. Configuración de la Solicitud (NO DINÁMICA)
        url = self.company_id.url + self.company_id.enpoint_emision
        token = self.token

        # CONFIGURA EL TIPO DE DOCUMENTO SI ES FACTURA, NOTA DE CRÉDITO O DÉBITO
        #raise UserError(_("%s")%self.move_type)
        if self.move_type=="out_invoice":
            if self.journal_id.code!="ND-CL":
                tipo_documento='01'
            else:
                tipo_documento='03'
        #if self.move_type=="out_invoice":
            #tipo_documento='01'
        if self.move_type=="out_refund":
            tipo_documento='02'
        #if self.move_type=="out_receipt":
            #tipo_documento='03'

        monto_fact=None
        fecha_fact=None
        nro_fact=None
        comentario_factura_afectada=None
        serie_factura_afectada=None
        if self.move_type in ('out_receipt','out_refund') or self.journal_id.code=="ND-CL":
            #raise UserError(_("xx"))
            busca_fact_org=self.env['account.move'].search([('invoice_number_next','=',self.reason),('move_type','=','out_invoice')],limit=1)
            #raise UserError(_("busca_fact_org)%s")%busca_fact_org)
            if busca_fact_org:
                monto_fact=str(self.monto_eqv_bs(busca_fact_org.total_pagar))
                fecha_fact=busca_fact_org.invoice_date.strftime('%d/%m/%Y')
                nro_fact=str(self.reason)
                comentario_factura_afectada="Aplicar Nota credito para devolucion parcial o total"
                serie_factura_afectada="A"

        #raise UserError(_("Monto factura=%s, fech=%s, Nro Factura afectada=%s")%(monto_fact,fecha_fact,nro_fact))
        if not token:
            raise UserError(_("No se encontró el token JWT. Por favor, asegúrese de que la autenticación fue exitosa."))

        # 2. Encabezados (Headers)
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        # 3. JSON de Emisión (TEXTUALMENTE EL PROPORCIONADO POR EL USUARIO)
        invoice_json = {
            "DocumentoElectronico": {
                "Encabezado": {
                    "IdentificacionDocumento": {
                        "TipoDocumento": tipo_documento,
                        "NumeroDocumento": None,
                        "TipoProveedor": None,
                        "TipoTransaccion": "01",
                        "NumeroPlanillaImportacion": None,
                        "NumeroExpedienteImportacion": None,
                        "SerieFacturaAfectada": serie_factura_afectada,
                        "NumeroFacturaAfectada": nro_fact,
                        "FechaFacturaAfectada": fecha_fact,
                        "MontoFacturaAfectada": monto_fact,
                        "ComentarioFacturaAfectada": comentario_factura_afectada,
                        "RegimenEspTributacion": None,
                        "FechaEmision": fecha_emision_tfhka,
                        "FechaVencimiento": fecha_vencimiento,
                        "HoraEmision": hora_emision_tfhka,
                        "Anulado": None,
                        "TipoDePago": "CONTADO",
                        "Serie": "",
                        "Sucursal": None,
                        "TipoDeVenta": "EN LINEA",
                        "Moneda": "BSD",
                        "TransaccionId": transaccion_id, #"141",
                        "UrlPdf": None
                    },
                    "Vendedor": {
                        "Codigo": None,
                        "Nombre":self.company_id.name,
                        "NumCajero": None
                    },
                    "Comprador": {
                        "TipoIdentificacion":self.doc_type_conv(self.partner_id.doc_type),
                        "NumeroIdentificacion": self.partner_id.vat,
                        "RazonSocial": self.partner_id.name,
                        "Direccion": direccion_comprador,
                        "Ubigeo": None,
                        "Pais": "VE",
                        "Notificar": None,
                        "Telefono": [
                            self.partner_id.phone
                        ],
                        "Correo": [
                            str(self.partner_id.email)
                        ],
                        "OtrosEnvios": None
                    },
                    "SujetoRetenido": None,
                    "Tercero": None,
                    "Totales": {
                        "NroItems": "2",
                        "MontoGravadoTotal": str(self.monto_eqv_bs(self.base_imponible_org)),
                        "MontoExentoTotal": str(self.monto_eqv_bs(self.exemto_org)),
                        "MontoPercibidoTotal": "0.00",
                        "SubtotalAntesDescuento":str(self.monto_eqv_bs(self.total_lineas_org)),
                        "TotalDescuento": None,
                        "TotalRecargos": None,
                        "Subtotal": str(self.monto_eqv_bs(self.total_lineas_org)),
                        "TotalIVA": str(self.monto_eqv_bs(self.total_impuesto_org)),
                        "MontoTotalConIVA": str(self.monto_eqv_bs(self.total_pagar)),
                        "TotalAPagar": str(self.monto_eqv_bs(self.total_pagar)),
                        "MontoEnLetras": None,
                        "ListaRecargo": None,
                        "ListaDescBonificacion": None,
                        "ImpuestosSubtotal": [
                            {
                                "CodigoTotalImp": "G",
                                "AlicuotaImp": "16.00",
                                "BaseImponibleImp": str(self.monto_eqv_bs(self.base_imponible_org)),
                                "ValorTotalImp": str(self.monto_eqv_bs(self.total_impuesto_org))
                            },
                            {
                                "CodigoTotalImp": "E",
                                "AlicuotaImp": "0.00",
                                "BaseImponibleImp": str(self.monto_eqv_bs(self.exemto_org)),
                                "ValorTotalImp": "0.00"
                            }
                        ],
                        "OtrosImpuestosSubtotal": None,
                        "formasPago": [
                            {
                                "descripcion": "string",
                                "fecha": fecha_emision_tfhka,
                                "forma": "05",
                                "monto": str(self.monto_eqv_bs(self.total_pagar)),
                                "moneda": "BSD",
                                "tipoCambio": None
                            }
                        ],
                        "TotalIGTF": None,
                        "TotalIGTF_VES": None,
                        "MontoTotalOTI": None,
                        "MontoTotalIVAyOTI": None
                    },
                    "TotalesRetencion": None,
                    "TotalesOtraMoneda": None,
                    "Orden": None
                },
                "DetallesItems":detalles_items,
                "DetallesRetencion": None,
                "Viajes": None,
                "InfoAdicional": [
                    {
                        "Campo": "Informativo",
                        "Valor": "De conformidad con la Providencia SNAT/2022/000013 publicada en la G.O.N 42.339 del 17-03- 2022, este pago está sujeto al cobro adicional del 3% del Impuesto a las Grandes Transacciones Financieras (IGTF)."
                    }
                ],
                "GuiaDespacho": None,
                "Transporte": None,
                "EsLote": None,
                "EsMinimo": None
            }
        }

        # 4. Llamada a la API y Manejo de Respuesta
        try:
            _logger.info("Enviando factura %s a TFHKA. URL: %s", self.name, url)
            response = requests.post(url, headers=headers, json=invoice_json, timeout=60)
            response.raise_for_status()

            response_data = response.json()

            resultado_data = response_data.get('resultado', {})
            url_consulta = resultado_data.get('urlConsulta')
            numeroControl = resultado_data.get('numeroControl')
            numeroDocumento = resultado_data.get('numeroDocumento')
            
            # 5. Actualizar campos de Odoo
            self.write({
                'codigo': response_data.get('codigo', 'N/A'),
                'mensaje': response_data.get('mensaje', 'Respuesta exitosa sin mensaje.'),
                'resultado': json.dumps(response_data.get('resultado', {})),
                'validaciones': json.dumps(response_data.get('validaciones', [])) if response_data.get('validaciones') else False,
                'urlConsulta': url_consulta or False,
                'invoice_number_control':numeroControl,
                'invoice_number_next':numeroDocumento, 
                'name':numeroDocumento,
            })
            
            

            _logger.info("Factura %s enviada. Código de respuesta: %s", self.name, self.codigo)
            
        except requests.exceptions.HTTPError as e:
            # Captura errores HTTP (400, 401, etc.)
            error_msg = f"Error HTTP {response.status_code}: {response.text}"
            self.write({'codigo': str(response.status_code), 'mensaje': error_msg})
            _logger.error(error_msg)
            raise UserError(_("Error HTTP al enviar factura digital: %s,%s") % (response.status_code,response.text))

        except requests.exceptions.RequestException as e:
            # Captura errores de conexión
            error_msg = f"Error de conexión con la Imprenta Digital: {e}"
            self.write({'mensaje': error_msg})
            _logger.error(error_msg)
            raise UserError(_("Error de conexión al enviar factura digital."))




    def asigna_secuencia(self):
        if self.company_id.usar_fact_digi!=True:
            #raise UserError(_("Data"))
            if self.move_type!='entry':
                if self.is_delivery_note:
                    if not self.delivery_note_next_number:
                        self.delivery_note_next_number = self.get_nro_nota_entrega()
                    self.name=self.journal_id.code+ "/" + self.delivery_note_next_number
                else:
                    self.invoice_number_seq()
                    self.invoice_control()
                    self.name= self.invoice_number_next
                    #self.name= self.journal_id.code + "/" +self.invoice_number_next
                    #self.payment_reference=self.invoice_number_next
                for det_line_asiento in self.line_ids:
                    if det_line_asiento.account_id.user_type_id.type in ('receivable','payable'):
                        #det_line_asiento.name = self.journal_id.code + "/" + self.delivery_note_next_number if self.delivery_note_next_number else self.invoice_number_next
                        det_line_asiento.name = self.journal_id.code + "/" + self.delivery_note_next_number if self.delivery_note_next_number else self.invoice_number_next
                        #det_line_asiento.nro_doc=nro_factura

    def print_digital(self):
        """
        Abre en una nueva pestaña la URL de consulta de la factura digital 
        almacenada en el campo urlConsulta.
        """
        if self.company_id.usar_fact_digi==True:
            if self.urlConsulta:
                self.ensure_one()
                
                url = self.urlConsulta
                
                if not url:
                    # Puedes usar _logger.warning en lugar de UserError si solo quieres un mensaje
                    raise UserError("No se encontró la URL de consulta de la factura digital. Asegúrese de que la factura se haya emitido correctamente.")
                    
                # Devolver el diccionario de acción para abrir la URL
                return {
                    'type': 'ir.actions.act_url',
                    'url': url,
                    'target': 'new',  # Recomendado para abrir en una pestaña nueva
                }
            else:
                raise UserError(_("No hay documento fiscal recibido de la imprenta digital"))
        else:
            raise UserError(_("No esta habilitada esta compañia para trabajar con factura digital sino factura forma libre."))