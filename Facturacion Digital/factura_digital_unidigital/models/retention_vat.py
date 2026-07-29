def _prepare_unidigital_retention_json(self):
        """Construye el Payload exacto exigido por la API /createretention."""
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

        # 3. Normalizar moneda (Convertir VED / VEF a VES)
        curr_name = (self.currency_id.name or "VES").upper()
        if curr_name in ('VED', 'VEF', 'BS', 'BS.'):
            curr_name = 'VES'

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

        voucher_num_digits = ''.join(filter(str.isdigit, str(self.name or '1')))
        numeric_voucher_number = int(voucher_num_digits) if voucher_num_digits else 1

        payload = {
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
            "SystemReference": self.name or "RET-001",
            "Documents": documents_payload
        }

        return payload

    def envia_comp_ret_iva(self):
        """Envía el JSON de Retención de IVA a la API Unidigital."""
        self.ensure_one()

        company = self.company_id
        url = getattr(company, 'unidigital_retention_url', False) or 'https://qa.unidigital.global/digitalinvoice-core/documents/createretention'
        token = getattr(company, 'unidigital_token', False)

        if not url:
            raise UserError(_("No se ha configurado la URL de retenciones para Unidigital."))

        payload_data = self._prepare_unidigital_retention_json()
        json_payload = json.dumps(payload_data, indent=2, ensure_ascii=False)
        self.json_enviado = json_payload

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

            try:
                res_json = response.json()
            except Exception:
                res_json = {"raw_response": response.text}

            _logger.info("Respuesta Unidigital (ID %s): %s", self.id, res_json)

            self.result = str(res_json.get('result', ''))
            self.hasErrors = str(res_json.get('hasErrors', response.status_code not in (200, 201)))
            self.information = json.dumps(res_json.get('information', []))

            # Verificar si hubo error
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

                self.errorMessage = error_msg
                raise UserError(_("Error devuelto por la API Unidigital:\n%s") % self.errorMessage)

            else:
                self.errorMessage = False
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