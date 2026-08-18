from odoo import models, exceptions, _

class PosSession(models.Model):
    _inherit = 'pos.session'


    def action_pos_session_closing_control(self, bank_payment_method_diff_pairs=None):
        """
        Sobrescribimos el control de cierre para validar que todos los pedidos
        tengan asignado el campo nro_fact_seniat.
        """
        for session in self:
            # Buscamos los pedidos de la sesión actual donde el campo esté vacío o False
            orders_missing_seniat = session.order_ids.filtered(
                lambda order: not order.nro_fact_seniat or not order.nro_fact_seniat.strip()
            )

            # Si encontramos al menos uno, lanzamos un error bloqueante
            if orders_missing_seniat:
                order_names = ", ".join(orders_missing_seniat.mapped('name'))
                raise exceptions.UserError(_(
                    "No se puede cerrar la sesión del POS.\n\n"
                    "Los siguientes pedidos no tienen asignado un 'Número de Factura SENIAT':\n%s\n\n"
                    "Por favor, asigna el valor correspondiente antes de intentar cerrar nuevamente."
                ) % order_names)

        # Si todas las órdenes están correctas, se ejecuta la lógica original de Odoo
        return super().action_pos_session_closing_control(bank_payment_method_diff_pairs)