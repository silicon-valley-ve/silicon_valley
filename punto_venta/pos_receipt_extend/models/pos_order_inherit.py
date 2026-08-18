# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from odoo.fields import Datetime #
import re
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import pytz # Importante para la zona horaria




class PosConfig(models.Model):
    _inherit = 'pos.order'


    #nb_caja_comp=fields.Char(string="Registro de Máquina Fiscal",compute='_compute_nb_caja')
    nb_caja=fields.Char(string="Registro de nombre de la caja")
    nro_nc_seniat = fields.Char()
    nro_fact_seniat = fields.Char()
    nro_fact_afectada = fields.Char()
    status_impresora = fields.Char(default="no")
    tipo = fields.Char(default="venta")
    tasa_dia = fields.Float(compute="_compute_tasa")

    url_nota_credito=fields.Char(string="Imprimir Nota de Credito",readonly="True")
    id_order_afectado=fields.Char()
    link=fields.Char(compute='_compute_link')

    def refund(self):
        res=super().refund()
        if self.env.user.x_hacer_nota=='no':
            raise UserError(_("No esta Autorizado para hacer una devolucion o Nota de credito"))
        return res

    def action_emitir_factura(self):
        self.ensure_one()

        # 1. Validaciones
        if not self.lines:
            raise UserError(_("La orden no tiene productos para imprimir."))

        if not self.partner_id:
            raise UserError(_("Debe asociar un cliente a la orden."))

        # 2. Factores de conversión / Tasa
        # Ajusta esta lógica si manejas multimoneda/tasa en tu POS
        factor = 1.0

        serpList = []
        desc = 0

        # 3. Mapeo de Líneas de Productos
        for line in self.lines:
            impuesto = 0
            
            # Detección de alícuotas de impuesto
            if line.tax_ids_after_fiscal_position:
                tax = line.tax_ids_after_fiscal_position[0]
                # Verificación por atributo 'aliquot' si existe en tu localización
                aliquot = getattr(tax, 'aliquot', False)
                
                if aliquot == 'exempt':
                    impuesto = 0
                elif aliquot == 'general':
                    impuesto = 1
                elif aliquot == 'reduced':
                    impuesto = 2
                elif aliquot == 'additional':
                    impuesto = 3
                else:
                    # Fallback por porcentaje (16% = 1, 8% = 2, 31% = 3, 0% = 0)
                    amount = round(tax.amount)
                    if amount >= 15:
                        impuesto = 1
                    elif amount == 8:
                        impuesto = 2
                    elif amount > 20:
                        impuesto = 3

            product_name = (line.product_id.display_name or line.product_id.name or '').replace("&", "")

            line_data = {
                'product': product_name[:57],
                'cantidad': line.qty,
                'precio': line.price_unit * factor,
                'impuesto': impuesto,
            }
            serpList.append(line_data)

            if line.discount:
                desc += (line.price_unit * line.discount / 100.0)

        enviar_lineas = json.dumps(serpList)

        # 4. Formateo de Pagos (IGTF / Métodos de pago)
        payment_order_lines = []
        for payment in self.payment_ids:
            method = payment.payment_method_id
            is_currency = getattr(method, 'is_currency_payment', False) or getattr(method, 'is_igtf', False)
            payment_order_lines.append({
                'name': method.name or '',
                'payment_method': method.name or '',
                'calculate_wh_itf': is_currency,
                'amount': payment.amount,
            })
        enviar_pagos = json.dumps(payment_order_lines)

        # 5. Datos del cliente
        partner = self.partner_id
        phone = partner.phone or '0000000'
        vat = (partner.vat or '0000000').replace('V-', '').replace('V', '')
        street = partner.street or partner.contact_address or '*********'
        street = street.replace("&", "")
        client_name = (partner.name or '').replace("&", "")

        # 6. Construcción de Query String
        puerto = getattr(self.config_id, 'puerto_impresora', 'COM3')
        serial = getattr(self.config_id, 'serial_impresora', 'Z7C7045880')

        valor = f"?cid={self.pos_reference or self.id}"
        valor += f"&numero_recibo={self.pos_reference or self.id}"
        valor += f"&cliente={client_name}"
        valor += f"&telefono={phone}"
        valor += f"&direccion={street}"
        valor += f"&rif_cedula={vat}"
        valor += f"&lineas={enviar_lineas}"
        valor += f"&payment_order_lines={enviar_pagos}"
        valor += f"&vendedor={self.create_uid.name or ''}"
        valor += f"&puerto={puerto}"
        valor += f"&serial={serial}"
        valor += f"&order_id={self.id}"

        # 7. Retornar ir.actions.act_url para que la Petición HTTP NAVEGUE desde la PC local
        # Cambia el puerto '8090' u '8080' según el puerto donde esté corriendo tu Python local
        local_service_url = f"http://localhost:8080/impresora_fiscal/cargar.php{valor}"

        return {
            'type': 'ir.actions.act_url',
            'target': '_blank',
            'url': local_service_url,
        }


    """@api.model
    def create(self, vals):
        # Si el campo 'nro_fact_seniat' no viene explícitamente en la creación
        if not vals.get('nro_fact_seniat'):
            # Buscamos el último pedido registrado que ya tenga un nro_fact_seniat asignado
            last_order = self.search([
                ('nro_fact_seniat', '!=', False),
                ('nro_fact_seniat', '!=', '')
            ], order='id desc', limit=1)

            if last_order and last_order.nro_fact_seniat:
                val_actual = last_order.nro_fact_seniat.strip()
                
                # Caso A: Si el valor es puramente numérico (ej. "000125" o "125")
                if val_actual.isdigit():
                    longitud = len(val_actual)
                    siguiente_numero = int(val_actual) + 1
                    # Conservamos el relleno de ceros a la izquierda si lo tenía
                    vals['nro_fact_seniat'] = str(siguiente_numero).zfill(longitud)
                
                # Caso B: Si incluye prefijos con letras o guiones (ej. "FACT-000125")
                else:
                    # Busca el último bloque numérico en la cadena
                    match = re.search(r'(\d+)(?=\D*$)', val_actual)
                    if match:
                        num_str = match.group(1)
                        longitud = len(num_str)
                        nuevo_num = str(int(num_str) + 1).zfill(longitud)
                        # Reemplaza únicamente ese bloque numérico
                        start, end = match.span(1)
                        vals['nro_fact_seniat'] = val_actual[:start] + nuevo_num + val_actual[end:]
                    else:
                        # Si no hay números, inicializamos en 1
                        vals['nro_fact_seniat'] = "1"
            else:
                # Si es el primer registro de la base de datos
                vals['nro_fact_seniat'] = "00000001"

        return super().create(vals)"""

    def action_emitir_nota_credito(self):
        self.ensure_one()

        user_tz = self.env.user.tz or 'America/Caracas'
        local_dt = Datetime.context_timestamp(self, self.date_order).astimezone(pytz.timezone(user_tz))
        fecha_formateada = local_dt.strftime('%d%m%y')
        
        # 1. Verificamos que sea una devolución (monto negativo)
        if self.amount_total >= 0:
            raise UserError("Esta orden no es una devolución (monto positivo).")

        # 2. Datos de la Impresora y Factura Original
        nro_original = self.nro_fact_seniat or "00000001" 
        if self.session_id.config_id.serial_impresora:
            serial_fisico = self.session_id.config_id.serial_impresora
        else:
            raise UserError(_("Falta el serial de la impresora, Configure es la session del pos"))
        
        # 3. Preparar los datos del Cliente
        cliente = self.partner_id.name or "CONSUMIDOR FINAL"
        rif = self.partner_id.vat or "V000000000"
        
        # 4. Preparar las Líneas de Producto
        lineas_datos = []
        for line in self.lines:
            lineas_datos.append({
                'product': line.product_id.name,
                'cantidad': abs(line.qty),
                'precio': abs(line.price_unit),
                'impuesto': self.tipo_imp(line.tax_ids_after_fiscal_position)
            })

        # --- NUEVA SECCIÓN: Preparar Métodos de Pago ---
        pagos_datos = []
        for payment in self.payment_ids:
            pagos_datos.append({
                'name': payment.payment_method_id.name,
                'metodo': payment.payment_method_id.name,
                'monto': abs(payment.amount), # Enviamos el monto positivo para la lógica de la impresora
                'calculate_wh_itf':payment.payment_method_id.is_currency_payment,
                'tipo': payment.payment_method_id.type or 'cash' # Útil para identificar si es efectivo o banco
            })
        # -----------------------------------------------

        # 5. Construir los parámetros para la URL
        params = {
            'order_id': self.id,
            'cliente': cliente,
            'rif_cedula': rif,
            'factura_original': nro_original,
            'serial_impresora': serial_fisico,
            'fecha_factura': fecha_formateada,
            'lineas': json.dumps(lineas_datos),
            'pagos': json.dumps(pagos_datos) # Agregamos los pagos como JSON
        }

        # Construimos la URL manual para tu script local
        base_url = "http://localhost:8090/impresora_fiscal/nota_credito.php"
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        url_final = f"{base_url}?{query_string}"

        # 6. Retornar la acción
        return {
            'type': 'ir.actions.act_url',
            'url': url_final,
            'target': 'new',
        }


    def tipo_imp(self, tax_ids_after_fiscal_position):
        # Verificamos que exista al menos un impuesto
        if not tax_ids_after_fiscal_position:
            return 0 # Por defecto exento si no hay impuestos definidos
            
        impuesto = tax_ids_after_fiscal_position[0] # Tomamos el primero de la lista
        if impuesto.aliquot == 'exempt':
            return 0
        elif impuesto.aliquot == 'general':
            return 1
        elif impuesto.aliquot == 'reduced':
            return 2
        elif impuesto.aliquot == 'additional':
            return 3
        return 1 # Fallback a Tasa General si algo falla




    def _compute_tasa(self):
        tasa=0
        for selff in self:
            #lista_tasa = selff.env['res.currency.rate'].search([('currency_id', '=', self.env.company.currency_secundaria_id.id),('hora','<=',selff.date_order)],order='id ASC')
            lista_tasa = selff.env['res.currency.rate'].search([('currency_id', '=',self.env.company.currency_sec_id.id )],order='id desc')
            if lista_tasa[0]:
                for det in lista_tasa[0]:
                    tasa=det.rate
            selff.tasa_dia=tasa



    """def refund(self):
        super().refund()
        self.nro_fact_seniat=0"""


    def abrir_link_externo(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.link,
            'target': 'new',
        }


    #@api.depends('state')
    @api.onchange('state')
    def _compute_link(self):
        valor_url='http://localhost:8080/impresora_fiscal/nota_credito.php'
        for selff in self:
            #selff.link=valor_url+'?id_order_afectado='+str(selff.id_order_afectado)+'&order_nc='+str(selff.id)+'&pos_reference='+str(selff.pos_reference) 
            selff.link=valor_url+'?id_order_afectado='+str(selff.id_order_afectado)+'&order_nc='+str(selff.id)+'&pos_reference='+str(selff.pos_reference) 
            selff.url_nota_credito=selff.link


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    status_impresora=fields.Char(related='order_id.status_impresora')
    tipo = fields.Char(related='order_id.tipo')


class PosMakePayment(models.TransientModel):
    _inherit = 'pos.make.payment'

    def check(self):
        res = super(PosMakePayment, self).check()
        ordenes = self.env['pos.order'].browse(self.env.context.get('active_id', False))
        pos_reference=ordenes.pos_reference
        actualiza=self.env['pos.order'].search([('pos_reference','=',pos_reference),('amount_total','>','0')])
        for det in actualiza:
            id_order_org=det.id
            amount_total_org=det.amount_total
            amount_paid_org=det.amount_paid
        ordenes.id_order_afectado=id_order_org
        ordenes.tipo="devolucion"
        ordenes.amount_total=-1*amount_total_org
        ordenes.amount_paid=-1*amount_paid_org

        #raise UserError(_('pos_reference= %s')%ordenes.pos_reference)
