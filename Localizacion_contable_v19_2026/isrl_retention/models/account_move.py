# -*- coding: utf-8 -*-

import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger('__name__')

class AccountMove(models.Model):
    _inherit = 'account.move'

    isrl_ret_id = fields.Many2one('isrl.retention', string='ISLR', copy=False, help='ISLR')
    isrl_ret_aux_id = fields.Char(default='',copy=False, tracking=True)
    #vat_isrl_line_id = fields.Many2many(comodel_name='isrl.retention.invoice.linet')

    # Main Function
    def action_post(self):
        super().action_post()
        self.create_retention()
            #self.unifica_alicuota_iguales_islr()


    def create_retention(self):
        for selff in self:
            ban=0
            ban=selff.verifica_lineas_islr()
            if selff.move_type !='entry':
                if selff.partner_id.ret_agent_isrl==True and not self.isrl_ret_id.id and ban!=0:
                    if selff.partner_id.people_type=='na':
                        raise UserError("Defina en la ficha del cliente/Proveedor el tipo de persona")
                    else:
                        selff.isrl_ret_id = selff.env['isrl.retention'].create({
                            'invoice_id': selff.id,
                            'partner_id': selff.partner_id.id,
                            #'move_id':self.id,
                            'invoice_number':selff.invoice_number_next,
                            'date_move':selff.date,
                            'date_isrl':selff.date,
                            'type':selff.move_type,
                        })
                        for item in selff.invoice_line_ids:
                            if item.concept_isrl_id:
                                for rate in item.concept_isrl_id.rate_ids:
                                    if selff.partner_id.people_type == rate.people_type and  selff.conv_div_nac(item.price_subtotal) > rate.min  :
                                        base = item.price_subtotal * (rate.subtotal / 100)
                                        subtotal =  base * (rate.retention_percentage / 100)
                                        ####
                                        #raise UserError("prueba 1")
                                        ban=selff.verifica_islr_repetido(rate.code)
                                        if ban==False:
                                            direcc=({
                                                'name': item.concept_isrl_id.id,
                                                'code':rate.code,
                                                'retention_id': selff.isrl_ret_id.id,
                                                'cantidad': rate.retention_percentage,
                                                'base': selff.conv_div_nac(base),
                                                'retention': selff.conv_div_nac(subtotal),
                                                'sustraendo': rate.subtract,
                                                'total': selff.conv_div_nac(subtotal) - rate.subtract,
                                            })
                                            selff.isrl_ret_id.lines_id.create(direcc)
                                        else:
                                            objeto_line=selff.env['isrl.retention.invoice.line'].search([('retention_id','=',selff.isrl_ret_id.id),('code','=',rate.code)])
                                            objeto_line.write({
                                                'base': objeto_line.base+selff.conv_div_nac(base),
                                                'retention': objeto_line.retention+selff.conv_div_nac(subtotal),
                                                'total': objeto_line.retention+selff.conv_div_nac(subtotal) - rate.subtract,
                                                })
                        if selff.move_type in ('in_invoice','in_refund','in_receipt'):
                            selff.isrl_ret_id.action_post()
                            selff.isrl_ret_aux_id = selff.isrl_ret_id.name



    def conv_div_nac(self,valor):
        if self.currency_id==self.company_id.currency_id:
            resultado=valor
        else:
            resultado=valor*self.tasa
        return resultado

    def verifica_islr_repetido(self,code):
        busca=''
        busca=self.env['isrl.retention.invoice.line'].search([('retention_id','=',self.isrl_ret_id.id),('code','=',code)]) 
        if busca:
            result=True
        else:
            result=False
        return result

    def button_draft(self):
        super().button_draft()
        #self.isrl_ret_id.action_draft()
        self.isrl_ret_id.move_id.with_context(force_delete=True).unlink()
        self.isrl_ret_id.state='draft'
        self.isrl_ret_id.with_context(force_delete=True).unlink()

    def verifica_lineas_islr(self):
        for selff in self:
            acum=0
            #raise UserError(_('self = %s')%self.id)
            puntero_move_line = selff.invoice_line_ids.search([('move_id','=',selff.id)])
            for det_puntero in puntero_move_line:
                if det_puntero.product_id.product_tmpl_id.concept_isrl_id.id:
                    acum=acum+1
            #raise UserError(_('acum: %s ')%acum)
            return acum
