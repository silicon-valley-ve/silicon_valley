# -*- coding: utf-8 -*-


import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import re




class ResumenAlicuotaTpv(models.Model):
    _name = 'pos.order.line.resumen'
    _order = 'id desc, fecha_fact desc'


    #session_id=fields.Many2one('pos.session', ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
    state = fields.Selection([('draft', 'Borrador'), ('posted', 'Publicado')],string='State',default='draft',required=True)
    total_con_iva = fields.Float(string=' Total con IVA')
    total_con_iva_nc = fields.Float(string=' Total con IVA')
    total_base = fields.Float(string='Total Base Imponible')

    base_general = fields.Float(string='Total Base General')
    base_reducida = fields.Float(string='Total Base Reducida')
    base_adicional = fields.Float(string='Total Base General + Reducida')
    base_general_nc = fields.Float(string='Total Base General')
    base_reducida_nc = fields.Float(string='Total Base Reducida')
    base_adicional_nc = fields.Float(string='Total Base General + Reducida')

    total_exento = fields.Float(string='Total Excento')
    total_exento_nc = fields.Float(string='Total Excento')
    alicuota_general = fields.Float(string='Alicuota General')
    alicuota_reducida = fields.Float(string='Alicuota Reducida')
    alicuota_adicional = fields.Float(string='Alicuota General + Reducida')
    alicuota_general_nc = fields.Float(string='Alicuota General')
    alicuota_reducida_nc = fields.Float(string='Alicuota Reducida')
    alicuota_adicional_nc = fields.Float(string='Alicuota General + Reducida')

    retenido_general = fields.Float(string='retenido General')
    retenido_reducida = fields.Float(string='retenido Reducida')
    retenido_adicional = fields.Float(string='retenido General + Reducida')    

    #tax_id = fields.Many2one('account.tax', string='Tipo de Impuesto')

    total_valor_iva = fields.Float(string='Total IVA')
    total_valor_iva_nc = fields.Float(string='Total IVA')

    tipo_doc = fields.Char()
    fecha_fact= fields.Datetime(string="Fecha Cierre")   

    nro_doc = fields.Char(string="Nro de documentos")
    nro_doc_nc = fields.Char(string="Nro de nota credito")

    reg_maquina_id = fields.Many2one('pos.nro.maquina')
    reg_maquina = fields.Char(string="Registro de Máquina Fiscal")
    nro_rep_z = fields.Char(string="Número Reporte Z")

    base_imponible_nc = fields.Float(string="Base Imponible NC")
    alicuota_nc =  fields.Float(string='Alicuota NC')
    total_nc= fields.Float(string="Total NC",default=0)
    fact_afectada = fields.Char()
    ################ CAMPOS SOLO PARA REGISTRO ASIENTOS MANUALES REPORTES Z
    sub_total_ventas=fields.Float(default=0)
    sub_total_ventas_nc=fields.Float(default=0)
    total_igtf=fields.Float()
    total_igtf_nc=fields.Float()
    journal_id = fields.Many2one('account.journal', domain="[('type', 'in', ['sale', 'general'])]")
    asiento_id=fields.Many2one('account.move')

    #
    

    @api.onchange('reg_maquina')
    def _onchange_reg_maquina(self):
        """
        Calcula y prellena nro_doc cuando se selecciona un valor en reg_maquina.
        """
        # Solo calculamos si se ha seleccionado un valor en reg_maquina y si nro_doc no está ya lleno
        if self.reg_maquina : # Aquí se puede ajustar la condición si quieres que siempre se recalcule
            last_record = self.search([('state','=','posted'),('reg_maquina','=',self.reg_maquina)], order='nro_rep_z desc', limit=1)
            
            if last_record and last_record.nro_doc:
                last_nro_doc_value = last_record.nro_doc
                match = re.search(r'(\d+)\s*$', last_nro_doc_value)
                
                if match:
                    try:
                        last_number = int(match.group(1))
                        next_number = last_number + 1
                        self.nro_doc = f"{next_number} hasta "
                    except ValueError:
                        self.nro_doc = False # O deja vacío si hay un error
                else:
                    self.nro_doc = False # Si no se encuentra un número en el último registro
            else:
                # Si no hay registros previos o el último nro_doc estaba vacío, puedes iniciar desde 1
                self.nro_doc = "1 hasta " 
        elif not self.reg_maquina:
            # Opcional: limpiar nro_doc si se deselecciona reg_maquina
            self.nro_doc = False 


    @api.onchange('reg_maquina_id')
    def nro_maquina(self):
        self.reg_maquina=self.reg_maquina_id.name

    @api.onchange('total_exento','base_adicional','base_general','base_reducida')
    def calcula_subtotl(self):
        valor=self.total_exento+self.base_general+self.base_reducida+self.base_adicional
        self.sub_total_ventas=valor


    @api.onchange('total_exento_nc','base_adicional_nc','base_general_nc','base_reducida_nc')
    def calcula_subtotl_nc(self):
        valor_nc=self.total_exento_nc+self.base_general_nc+self.base_reducida_nc+self.base_adicional_nc
        self.sub_total_ventas_nc=valor_nc

    @api.onchange('total_exento','base_adicional','base_general','base_reducida','total_igtf')
    def calcula_total_ventas(self):
        valor=self.sub_total_ventas+self.total_igtf+self.alicuota_general+self.alicuota_reducida+self.alicuota_adicional
        self.total_con_iva=valor

    @api.onchange('total_exento_nc','base_adicional_nc','base_general_nc','base_reducida_nc','total_igtf_nc')
    def calcula_total_ventas_nc(self):
        valor_nc=self.sub_total_ventas_nc+self.total_igtf_nc+self.alicuota_general_nc+self.alicuota_reducida_nc+self.alicuota_adicional_nc
        self.total_con_iva_nc=valor_nc

    @api.onchange('base_adicional','base_general','base_reducida')
    def calcula_alicuota(self):
        pg=pr=pa=0
        impuesto=self.env['account.tax'].search([('type_tax_use','=','sale'),('company_id','in',(self.company_id.id,self.company_id.parent_id.id))])
        #raise UserError(_('%s')%impuesto)
        if impuesto:
            for det in impuesto:
                if det.aliquot=='general':
                    pg=det.amount
                    
                if det.aliquot=='reduced':
                    pr=det.amount
                    
                if det.aliquot=='additional':
                    pa=det.amount
                    
        if self.base_general:
            self.alicuota_general=self.base_general*pg/100
        else:
            self.alicuota_general=0
        if self.base_reducida:
            self.alicuota_reducida=self.base_reducida*pr/100
        else:
            self.alicuota_reducida=0
        if self.base_adicional:
            self.alicuota_adicional=self.base_adicional*pa/100
        else:
            self.alicuota_adicional=0

    @api.onchange('base_adicional_nc','base_general_nc','base_reducida_nc')
    def calcula_alicuota_nc(self):
        pg=pr=pa=0
        impuesto=self.env['account.tax'].search([('type_tax_use','=','sale'),('company_id','in',(self.company_id.id,self.company_id.parent_id.id))])
        if impuesto:
            for det in impuesto:
                if det.aliquot=='general':
                    pg=det.amount
                    
                if det.aliquot=='reduced':
                    pr=det.amount
                    
                if det.aliquot=='additional':
                    pa=det.amount
                    
        if self.base_general_nc:
            self.alicuota_general_nc=self.base_general_nc*pg/100
        else:
            self.alicuota_general_nc=0
        if self.base_reducida_nc:
            self.alicuota_reducida_nc=self.base_reducida_nc*pr/100
        else:
            self.alicuota_reducida_nc=0
        if self.base_adicional_nc:
            self.alicuota_adicional_nc=self.base_adicional_nc*pa/100
        else:
            self.alicuota_adicional_nc=0




    def publicar(self):
        if not self.journal_id:
            raise UserError(_('Debe colocar un diario que esta a su lado Derecho.'))
        self.state='posted'
        if self.company_id.crear_asiento_pos!=True:
            self.create_asiento()

    def boton_draft(self):
        if self.asiento_id.state=='posted':
            self.asiento_id.button_draft()
        self.asiento_id.unlink()
        self.state='draft'
        
    def create_asiento(self):
        vals=({
            'name':self.nro_asiento_rep_z(),
            'date':self.fecha_fact,
            'journal_id':self.journal_id.id,
            'move_type':'entry',
            'currency_id':self.company_id.currency_id.id,
            'posted_before':False,
            'ref':"Registro Z nro "+self.nro_rep_z,
            'company_id':self.env.company.id,
            })
        move_id=self.env['account.move'].create(vals)
        # apunte cuta por pagar cliente
        valores=({
            'account_id':self.company_id.account_receivable_z_id.id,
            'debit':(self.total_con_iva-self.total_con_iva_nc),
            'currency_id':self.company_id.currency_id.id,   #self.currency_id.id,
            'move_id':move_id.id,
            'balance':(self.total_con_iva-self.total_con_iva_nc),
            'journal_id':self.journal_id.id,
            'name':"Registro Z nro "+self.nro_rep_z,
            })
        move_id.line_ids.create(valores)
        #apuntes ventas por mercancias exentas
        if self.total_exento!=0:
            valores2=({
                'account_id':self.company_id.account_ingreso_merca_id.id,
                'credit':(self.total_exento-self.total_exento_nc),
                'currency_id':self.company_id.currency_id.id,
                'move_id':move_id.id,
                'balance':-1*(self.total_exento-self.total_exento_nc),
                'journal_id':self.journal_id.id,
                'name':"Monto exentos",
                })
            move_id.line_ids.create(valores2)
        #apuntes ventas por mercancias base inponible general
        if self.base_general!=0:
            valores3=({
                'account_id':self.company_id.account_ingreso_merca_id.id,
                'credit':(self.base_general-self.base_general_nc),
                'currency_id':self.company_id.currency_id.id,
                'move_id':move_id.id,
                'balance':-1*(self.base_general-self.base_general_nc),
                'journal_id':self.journal_id.id,
                'name':"BI General",
                })
            move_id.line_ids.create(valores3)

        #apuntes ventas por mercancias base inponible reducida
        if self.base_reducida!=0:
            valores4=({
                'account_id':self.company_id.account_ingreso_merca_id.id,
                'credit':(self.base_reducida-self.base_reducida_nc),
                'currency_id':self.company_id.currency_id.id,
                'move_id':move_id.id,
                'balance':-1*(self.base_reducida-self.base_reducida_nc),
                'journal_id':self.journal_id.id,
                'name':"BI Reducida",
                })
            move_id.line_ids.create(valores4)

        #apuntes ventas por mercancias base inponible adicional
        if self.base_adicional!=0:
            valores5=({
                'account_id':self.company_id.account_ingreso_merca_id.id,
                'credit':(self.base_adicional-self.base_adicional_nc),
                'currency_id':self.company_id.currency_id.id,
                'move_id':move_id.id,
                'balance':-1*(self.base_adicional-self.base_adicional_nc),
                'journal_id':self.journal_id.id,
                'name':"BI Adicional",
                })
            move_id.line_ids.create(valores5)

        #apuntes debito fiscal general
        if self.alicuota_general!=0:
            tipo_ali='general'
            cta_debit_fiscal_id=self.busca_cta_debito_fiscal(tipo_ali)
            if cta_debit_fiscal_id!=False:
                valores6=({
                    'account_id':cta_debit_fiscal_id.id,
                    'credit':(self.alicuota_general-self.alicuota_general_nc),
                    'currency_id':self.company_id.currency_id.id,
                    'move_id':move_id.id,
                    'balance':-1*(self.alicuota_general-self.alicuota_general_nc),
                    'journal_id':self.journal_id.id,
                    'name':self.busca_porcentage_debito_fiscal(tipo_ali),
                    })
                move_id.line_ids.create(valores6)

        #apuntes debito fiscal reducida
        if self.alicuota_reducida!=0:
            tipo_ali='reduced'
            cta_debit_fiscal_id=self.busca_cta_debito_fiscal(tipo_ali)
            if cta_debit_fiscal_id!=False:
                valores6=({
                    'account_id':cta_debit_fiscal_id.id,
                    'credit':(self.alicuota_reducida-self.alicuota_reducida_nc),
                    'currency_id':self.company_id.currency_id.id,
                    'move_id':move_id.id,
                    'balance':-1*(self.alicuota_reducida-self.alicuota_reducida_nc),
                    'journal_id':self.journal_id.id,
                    'name':self.busca_porcentage_debito_fiscal(tipo_ali),
                    })
                move_id.line_ids.create(valores6)

        #apuntes debito fiscal adicional
        if self.alicuota_adicional!=0:
            tipo_ali='additional'
            cta_debit_fiscal_id=self.busca_cta_debito_fiscal(tipo_ali)
            if cta_debit_fiscal_id!=False:
                valores7=({
                    'account_id':cta_debit_fiscal_id.id,
                    'credit':(self.alicuota_adicional-self.alicuota_adicional_nc),
                    'currency_id':self.company_id.currency_id.id,
                    'move_id':move_id.id,
                    'balance':-1*(self.alicuota_adicional-self.alicuota_adicional_nc),
                    'journal_id':self.journal_id.id,
                    'name':self.busca_porcentage_debito_fiscal(tipo_ali),
                    })
                move_id.line_ids.create(valores7)

         #apuntes impuesto igtf
        if self.total_igtf!=0:
            valores8=({
                'account_id':self.company_id.account_igtf_z_id.id,
                'credit':(self.total_igtf-self.total_igtf_nc),
                'currency_id':self.company_id.currency_id.id,
                'move_id':move_id.id,
                'balance':-1*(self.total_igtf-self.total_igtf_nc),
                'journal_id':self.journal_id.id,
                'name':"Impuesto IGTF",
                })
            move_id.line_ids.create(valores8)

        self.asiento_id=move_id.id
        self.asiento_id.action_post()


    def busca_cta_debito_fiscal(self,tipo_ali):
        tax_id=self.env['account.tax'].search([('type_tax_use','=','sale'),('company_id','=',self.company_id.id),('aliquot','=',tipo_ali)],limit=1)
        if tax_id:
            busca=self.env['account.tax.repartition.line'].search([('tax_id','=',tax_id.id),('document_type','=','invoice')])
            if busca:
                for line in busca:
                    cta=line.account_id
        if not cta:
            return False
        else:
            return cta

    def busca_porcentage_debito_fiscal(self,tipo_ali):
        valor=0
        tax_id=self.env['account.tax'].search([('type_tax_use','=','sale'),('company_id','=',self.company_id.id),('aliquot','=',tipo_ali)],limit=1)
        if tax_id:
            valor=tax_id.amount
        return str(valor)+"%"

    def nro_asiento_rep_z(self):

        self.ensure_one()
        
        company_id = self.env.company.id
        SEQUENCE_CODE = 'nro_asiento_rep_z_'+str(company_id)
        IrSequence = self.env['ir.sequence'].with_context(force_company=company_id)
        name = IrSequence.next_by_code(SEQUENCE_CODE)

        # si aún no existe una secuencia para esta empresa, cree una
        if not name:
            IrSequence.sudo().create({
                'prefix': 'REPZ/',
                'name': 'Localización Venezolana Nro asiento Reporte Z %s' % company_id,
                'code': SEQUENCE_CODE,
                'implementation': 'no_gap',
                'padding': 8,
                'number_increment': 1,
                'company_id': company_id,
            })
            name = IrSequence.next_by_code(SEQUENCE_CODE)
        return name