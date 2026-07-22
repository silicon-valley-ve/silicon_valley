# -*- coding: utf-8 -*-

from odoo import fields, models, api,_
import requests
import json
import logging
from odoo.exceptions import UserError # Necesaria si lo integras en un módulo de Odoo

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"


    # --- CAMPOS DE CONFIGURACIÓN DE TFHKA ---
    
    # Campo para seleccionar el ambiente de la API (Producción o Demo)
    usar_fact_digi = fields.Boolean(default=False)
    unidg_environment = fields.Selection([
        ('demo', 'DEMO'),
        ('prod', 'PRODUCCIÓN'),
    ], string='Ambiente TFHKA', default='demo', required=True)

    # Campos para las credenciales de la Imprenta Digital
    enpoint = fields.Char(string="Enpoint autenticación",copy=False,default="/user/login")
    url = fields.Char(string="URL",copy=False,default='https://qa.unidigital.global/digitalinvoice-core')
    unidg_api_user = fields.Char(string='Usuario API ',default="siliconvalleyvzla@unidigital.global")
    unidg_api_password = fields.Char(string='Clave API', default="1VTYmLZs0,cKt8;1J67#")
    
    # Campo para almacenar el token JWT y su vigencia (opcional, pero útil)
    unidg_jwt_token = fields.Char(string='Token JWT Actual', readonly=True, copy=False)
    unidg_token_expiry = fields.Char(string='Vigencia del Token', readonly=True, copy=False)
    codigo = fields.Char(readonly=True, copy=False)
    mensaje = fields.Char(readonly=True, copy=False)

    enpoint_emision=fields.Char(string="Enpoint Emision",copy=False,default='/api/Emision')
    enpoint_ultimo_doc=fields.Char(string="Enpoint Ultimo Documento",copy=False)

    def unidg_get_token_vacio(self):
        pass

    def unidg_get_token(self):
        """
        Genera y retorna el token JWT para la compañía actual.
        Si el token es válido, lo usa. Si no, solicita uno nuevo a la API.
        """
        #self.ensure_one()

        # 1. Definir URL Base según el ambiente
        
        url_base = self.url
        enpoint = self.enpoint

        url = url_base + self.enpoint
        
        # 2. Obtener credenciales
        usuario = self.unidg_api_user
        clave = self.unidg_api_password
        
        if not usuario or not clave:
            raise UserError(_("Las credenciales de usuario y clave de la API de TFHKA deben estar configuradas en la Compañía."))

        auth_data = {
            'usuario': usuario,
            'clave': clave
        }
        
        headers = {'Content-Type': 'application/json'}
        
        _logger.info("Intentando obtener Token Unidigital para la compañía %s", self.name)
        
        try:
            # 3. Solicitud POST a la API
            response = requests.post(url, headers=headers, json=auth_data, timeout=30)
            response.raise_for_status() 
            
            token_data = response.json()
            
            if token_data.get('token'):
                token = token_data.get('token')
                expiracion = token_data.get('expiracion')
                mensaje = token_data.get('mensaje')
                codigo = token_data.get('codigo')
                
                # Opcional: Guardar el token y la vigencia en el modelo de la compañía
                self.write({
                    'unidg_jwt_token': token,
                    'unidg_token_expiry': expiracion,
                    'mensaje': mensaje,
                    'codigo' : codigo,
                    # Nota: La vigencia se guarda como texto, deberías convertirla a datetime si la usas para chequeos.
                    # 'tfhka_token_expiry': token_data.get('vigencia') 
                })
                
                _logger.info("Token JWT de Unidigital obtenido con éxito.")
                return token
            else:
                error_msg = token_data.get('mensaje', 'Respuesta de Autenticación inválida sin token.')
                raise Exception(error_msg)
        
        except requests.exceptions.HTTPError as e:
            # Captura errores HTTP (401, 404, etc.)
            error_response = response.text
            _logger.error("Error HTTP al obtener token: %s. Respuesta: %s", e, error_response)
            raise UserError(_("Error de Autenticación Unidigital (HTTP %s). Verifique usuario y clave.") % response.status_code)
            
        except requests.exceptions.RequestException as e:
            # Captura errores de conexión
            _logger.error("Error de conexión al obtener token de Unidigital: %s", e)
            raise UserError(_("Error de conexión con la Imprenta Digital (Autenticación)."))
        except Exception as e:
            _logger.error("Error al procesar la respuesta del Token: %s", e)
            raise UserError(_("Error interno al procesar el Token: %s") % str(e))



    def limpia(self):
        self.codigo=''
        self.mensaje=''
        self.unidg_jwt_token=''
        self.unidg_token_expiry=''