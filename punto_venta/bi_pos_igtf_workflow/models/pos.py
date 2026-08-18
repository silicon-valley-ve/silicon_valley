# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta
from functools import partial
from itertools import groupby
from collections import defaultdict

import psycopg2
import pytz
import re

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero, float_round, float_repr, float_compare
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND
import base64

_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = 'pos.config'


    igtf_journal_id = fields.Many2one('account.journal', 'Partial Payment Journal',domain="[('is_igtf', '=', True)]")
    igtf_tax = fields.Float(
        string='IGTF Tax%', default=3.00)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    igtf_journal_id = fields.Many2one(related='pos_config_id.igtf_journal_id', readonly=False)
    igtf_tax = fields.Float(related='pos_config_id.igtf_tax', readonly=False)

    @api.model_create_multi
    def create(self, vals_list):
        res=super(ResConfigSettings, self).create(vals_list)
        for vals in vals_list:
            igtf_tax =vals.get('igtf_tax')
            if igtf_tax:
                    if (igtf_tax < 0.2 or igtf_tax > 20):
                        raise ValidationError(_('IGTF Tax should in between 0.2% to 20%'))
        return res


    def write(self, vals):
        res=super(ResConfigSettings, self).write(vals)
        if self.igtf_tax:
            if (self.igtf_tax < 0.2 or self.igtf_tax > 20):
                raise ValidationError(_('IGTF Tax should in between 0.2% to 20%'))
        return res
    
class account_journal(models.Model):
    _inherit = 'account.journal'

    is_igtf = fields.Boolean(string='Is IGTF')


class pos_payment_method(models.Model):
    _inherit = 'pos.payment.method'
    

    is_igtf = fields.Boolean(string='Is IGTF', related='journal_id.is_igtf', readonly=False)

    @api.model
    def _load_pos_data_fields(self, config_id):
        params = super()._load_pos_data_fields(config_id)
        params += ['is_igtf']
        return params

    @api.constrains('is_igtf')
    def validate_single_api_key(self):
        records = self.search([])
        count = 0
        for record in records:
            if record.is_igtf == True:
                count += 1
        if(count >2):
            raise ValidationError("You can not make multiple IGTF payment method")

class pos_order(models.Model):
    _inherit = 'pos.order'


    def _default_journal_id(self):
        return self.env['account.journal'].search([('company_id', '=', self.env.company.id), ('is_igtf', '=', True)], limit=1)

    igtf_order_tax = fields.Float(
        string='% IGTF Tax',readonly=True
    )
    payment_method_id = fields.Many2one(
        'pos.payment.method',
        string='IGTF Payment Method',readonly=True
    )
    igtf_amount = fields.Float(
        string='IGTF Amount',readonly=True
    )
    total_amount_with_igtf = fields.Float(
        string='Total Amount + IGTF',readonly=True
    )
    igtf_journal_id = fields.Many2one(
        'account.journal',
        string='IGTF Journal',readonly=True ,default=_default_journal_id
    )

    @api.model
    def _order_fields(self, ui_order):
        res = super(pos_order, self)._order_fields(ui_order)
        res['igtf_amount'] = ui_order.get('igtf_amount',0.0)
        return res


    def _export_for_ui(self, order):
        result = super(pos_order, self)._export_for_ui(order)
        result['igtf_amount'] = order.igtf_amount
        return result


    
    #@api.model
    def _process_order_org(self, order, existing_order):
        new = super(pos_order,self)._process_order(order, existing_order)
        Pos_Order = self.browse(new)
        # order = order['data']
        pos_session = self.env['pos.session'].browse(order['session_id'])
        pos_config = pos_session.config_id
        payment_method_id=self.env['pos.payment.method'].search([('is_igtf','=',True)])
        if Pos_Order.igtf_amount:
            Pos_Order.write({'igtf_order_tax':pos_config.igtf_tax,
                              'payment_method_id':payment_method_id.id,
                              'total_amount_with_igtf':Pos_Order.amount_total,
                              'igtf_journal_id':pos_config.igtf_journal_id,
                            })
        return new

    @api.model
    def _process_order(self, order, existing_order):
        new = super(pos_order, self)._process_order(order, existing_order)
        Pos_Order = self.browse(new)
        pos_session = self.env['pos.session'].browse(order['session_id'])
        pos_config = pos_session.config_id
        
        # BUSCR EL MÉTODO DE PAGO USADO: 
        # En lugar de buscar todos los que existen, buscamos cuál de los usados en la orden tiene IGTF
        payment_method = Pos_Order.payment_ids.mapped('payment_method_id').filtered(lambda l: l.is_igtf)
        
        if Pos_Order.igtf_amount:
            Pos_Order.write({
                'igtf_order_tax': pos_config.igtf_tax,
                # Usamos .id[:1] para asegurarnos de pasar solo un ID (el primero) y evitar el error Singleton
                'payment_method_id': payment_method[:1].id, 
                'total_amount_with_igtf': Pos_Order.amount_total,
                'igtf_journal_id': pos_config.igtf_journal_id,
            })
        return new
        

    def _prepare_invoice_lines(self):
        res= super(pos_order, self)._prepare_invoice_lines()
        prod = self.env['product.product'].search([('default_code','=','bi_igtf')])
        if self.igtf_amount:
            res.append((0, None, {
                'product_id': prod.id,
                'quantity': 1,
                'price_unit': float(self.igtf_amount),
                'tax_ids': [(6, 0, [])],
                'is_igtf_line': True,
            }))

        return res


    def _generate_pos_order_invoice(self):
        moves = self.env['account.move']

        for order in self:
            # Force company for all SUPERUSER_ID action
            if order.account_move:
                moves += order.account_move
                continue

            if not order.partner_id:
                raise UserError(_('Please provide a partner for the sale.'))

            move_vals = order._prepare_invoice_vals()
            new_move = order._create_invoice(move_vals)


            if order.igtf_amount:
                new_move.update({
                    'is_igtf_invoice':True,
                    'invoice_igtf_amount':order.igtf_amount,
                })

            order.write({'account_move': new_move.id, 'state': 'invoiced'})
            new_move.sudo().with_company(order.company_id).with_context(skip_invoice_sync=True)._post()

            moves += new_move
            payment_moves = order._apply_invoice_payments(order.session_id.state == 'closed')

            # Send and Print
            if self.env.context.get('generate_pdf', True):
                new_move.with_context(skip_invoice_sync=True)._generate_and_send()

            if order.session_id.state == 'closed':  # If the session isn't closed this isn't needed.
                # If a client requires the invoice later, we need to revers the amount from the closing entry, by making a new entry for that.
                order._create_misc_reversal_move(payment_moves)

        if not moves:
            return {}

        return {
            'name': _('Customer Invoice'),
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_move_form').id,
            'res_model': 'account.move',
            'context': "{'move_type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': moves and moves.ids[0] or False,
        }


class account_move_line(models.Model):
    _inherit = 'account.move'


    is_igtf_invoice = fields.Boolean('Is IGTF Invoice',default=False)
    invoice_igtf_amount = fields.Monetary('IGTF Amount')


class account_move_line(models.Model):
    _inherit = 'account.move.line'

    is_igtf_line = fields.Boolean(help="Technical field used to exclude some lines from the invoice_line_ids tab in the form view.")


class POSSession(models.Model):
    _inherit = "pos.session"


    def _accumulate_amounts(self, data):
        if self.config_id.igtf_journal_id:
            # Accumulate the amounts for each accounting lines group
            # Each dict maps `key` -> `amounts`, where `key` is the group key.
            # E.g. `combine_receivables_bank` is derived from pos.payment records
            # in the self.order_ids with group key of the `payment_method_id`
            # field of the pos.payment record.
            AccountTax = self.env['account.tax']
            amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0}
            tax_amounts = lambda: {'amount': 0.0, 'amount_converted': 0.0, 'base_amount': 0.0, 'base_amount_converted': 0.0}
            split_receivables_bank = defaultdict(amounts)
            split_receivables_cash = defaultdict(amounts)
            split_receivables_pay_later = defaultdict(amounts)
            combine_receivables_bank = defaultdict(amounts)
            combine_receivables_cash = defaultdict(amounts)
            combine_receivables_pay_later = defaultdict(amounts)
            combine_invoice_receivables = defaultdict(amounts)
            split_invoice_receivables = defaultdict(amounts)
            sales = defaultdict(amounts)
            taxes = defaultdict(tax_amounts)
            stock_expense = defaultdict(amounts)
            stock_return = defaultdict(amounts)
            stock_output = defaultdict(amounts)
            split_receivables_online = defaultdict(amounts)
            rounding_difference = {'amount': 0.0, 'amount_converted': 0.0}
            # Track the receivable lines of the order's invoice payment moves for reconciliation
            # These receivable lines are reconciled to the corresponding invoice receivable lines
            # of this session's move_id.
            combine_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])
            split_inv_payment_receivable_lines = defaultdict(lambda: self.env['account.move.line'])
            pos_receivable_account = self.company_id.account_default_pos_receivable_account_id
            currency_rounding = self.currency_id.rounding
            closed_orders = self._get_closed_orders()
            for order in closed_orders:
                order_is_invoiced = order.is_invoiced
                for payment in order.payment_ids:
                    amount = payment.amount
                    if float_is_zero(amount, precision_rounding=currency_rounding):
                        continue
                    date = payment.payment_date
                    payment_method = payment.payment_method_id
                    is_split_payment = payment.payment_method_id.split_transactions
                    payment_type = payment_method.type

                    # If not pay_later, we create the receivable vals for both invoiced and uninvoiced orders.
                    #   Separate the split and aggregated payments.
                    # Moreover, if the order is invoiced, we create the pos receivable vals that will balance the
                    # pos receivable lines from the invoice payments.
                    if payment_type != 'pay_later':
                        if is_split_payment and payment_type == 'cash':
                            split_receivables_cash[payment] = self._update_amounts(split_receivables_cash[payment], {'amount': amount}, date)
                        elif not is_split_payment and payment_type == 'cash':
                            combine_receivables_cash[payment_method] = self._update_amounts(combine_receivables_cash[payment_method], {'amount': amount}, date)
                        elif is_split_payment and payment_type == 'bank':
                            split_receivables_bank[payment] = self._update_amounts(split_receivables_bank[payment], {'amount': amount}, date)
                        elif not is_split_payment and payment_type == 'bank':
                            combine_receivables_bank[payment_method] = self._update_amounts(combine_receivables_bank[payment_method], {'amount': amount}, date)
                        elif payment_type == 'online':
                            split_receivables_online[payment] = self._update_amounts(split_receivables_online[payment], {'amount': amount}, date)
                        # Create the vals to create the pos receivables that will balance the pos receivables from invoice payment moves.
                        if order_is_invoiced:
                            if is_split_payment:
                                split_inv_payment_receivable_lines[payment] |= payment.account_move_id.line_ids.filtered(lambda line: line.account_id == pos_receivable_account)
                                split_invoice_receivables[payment] = self._update_amounts(split_invoice_receivables[payment], {'amount': payment.amount}, order.date_order)
                            else:
                                combine_inv_payment_receivable_lines[payment_method] |= payment.account_move_id.line_ids.filtered(lambda line: line.account_id == pos_receivable_account)
                                combine_invoice_receivables[payment_method] = self._update_amounts(combine_invoice_receivables[payment_method], {'amount': payment.amount}, order.date_order)

                    # If pay_later, we create the receivable lines.
                    #   if split, with partner
                    #   Otherwise, it's aggregated (combined)
                    # But only do if order is *not* invoiced because no account move is created for pay later invoice payments.
                    if payment_type == 'pay_later' and not order_is_invoiced:
                        if is_split_payment:
                            split_receivables_pay_later[payment] = self._update_amounts(split_receivables_pay_later[payment], {'amount': amount}, date)
                        elif not is_split_payment:
                            combine_receivables_pay_later[payment_method] = self._update_amounts(combine_receivables_pay_later[payment_method], {'amount': amount}, date)

                if not order_is_invoiced:
                    base_lines = order.with_context(linked_to_pos=True)._prepare_tax_base_line_values()
                    AccountTax._add_tax_details_in_base_lines(base_lines, order.company_id)
                    AccountTax._round_base_lines_tax_details(base_lines, order.company_id)
                    AccountTax._add_accounting_data_in_base_lines_tax_details(base_lines, order.company_id, include_caba_tags=True)
                    tax_results = AccountTax._prepare_tax_lines(base_lines, order.company_id)


                    total_amount_currency = 0.0
                    for base_line, to_update in tax_results['base_lines_to_update']:
                        # Combine sales/refund lines
                        sale_key = (
                            # account
                            base_line['account_id'].id,
                            # sign
                            -1 if base_line['is_refund'] else 1,
                            # for taxes
                            tuple(base_line['record'].tax_ids_after_fiscal_position.flatten_taxes_hierarchy().ids),
                            tuple(base_line['tax_tag_ids'].ids),
                            base_line['product_id'].id if self.config_id.is_closing_entry_by_product else False,
                        )
                        total_amount_currency += to_update['amount_currency']
                        sales[sale_key] = self._update_amounts(
                            sales[sale_key],
                            {
                                'amount': to_update['amount_currency'] - order.igtf_amount,
                                'amount_converted': to_update['balance'] - order.igtf_amount,
                            },
                            order.date_order,
                        )
                        if self.config_id.is_closing_entry_by_product:
                            sales[sale_key] = self._update_quantities(sales[sale_key], base_line['quantity'])
                    # Combine tax lines
                    for tax_line in tax_results['tax_lines_to_add']:
                        tax_key = (
                            tax_line['account_id'],
                            tax_line['tax_repartition_line_id'],
                            tuple(tax_line['tax_tag_ids'][0][2]),
                        )
                        total_amount_currency += tax_line['amount_currency']
                        taxes[tax_key] = self._update_amounts(
                            taxes[tax_key],
                            {
                                'amount': tax_line['amount_currency'],
                                'amount_converted': tax_line['balance'],
                                'base_amount': tax_line['tax_base_amount']
                            },
                            order.date_order,
                        )

                    if self.config_id.cash_rounding:
                        diff = order.amount_paid + total_amount_currency
                        rounding_difference = self._update_amounts(rounding_difference, {'amount': diff}, order.date_order)

                    # Increasing current partner's customer_rank
                    partners = (order.partner_id | order.partner_id.commercial_partner_id)
                    partners._increase_rank('customer_rank')

            if self.company_id.anglo_saxon_accounting:
                all_picking_ids = self.order_ids.filtered(lambda p: not p.is_invoiced and not p.shipping_date).picking_ids.ids + self.picking_ids.filtered(lambda p: not p.pos_order_id).ids
                if all_picking_ids:
                    # Combine stock lines
                    stock_move_sudo = self.env['stock.move'].sudo()
                    stock_moves = stock_move_sudo.search([
                        ('picking_id', 'in', all_picking_ids),
                        ('company_id.anglo_saxon_accounting', '=', True),
                        ('product_id.categ_id.property_valuation', '=', 'real_time'),
                        ('product_id.is_storable', '=', True),
                    ])
                    for stock_moves_split in self.env.cr.split_for_in_conditions(stock_moves.ids):
                        stock_moves_batch = stock_move_sudo.browse(stock_moves_split)
                        candidates = stock_moves_batch\
                            .filtered(lambda m: not bool(m.origin_returned_move_id and sum(m.stock_valuation_layer_ids.mapped('quantity')) >= 0))\
                            .mapped('stock_valuation_layer_ids')
                        for move in stock_moves_batch.with_context(candidates_prefetch_ids=candidates._prefetch_ids):
                            exp_key = move.product_id._get_product_accounts()['expense']
                            out_key = move.product_id.categ_id.property_stock_account_output_categ_id
                            signed_product_qty = move.product_qty
                            if move._is_in():
                                signed_product_qty *= -1
                            amount = signed_product_qty * move.product_id._compute_average_price(0, move.quantity, move)
                            stock_expense[exp_key] = self._update_amounts(stock_expense[exp_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
                            if move._is_in():
                                stock_return[out_key] = self._update_amounts(stock_return[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
                            else:
                                stock_output[out_key] = self._update_amounts(stock_output[out_key], {'amount': amount}, move.picking_id.date, force_company_currency=True)
            MoveLine = self.env['account.move.line'].with_context(check_move_validity=False, skip_invoice_sync=True)

            data.update({
                'taxes':                               taxes,
                'sales':                               sales,
                'stock_expense':                       stock_expense,
                'split_receivables_bank':              split_receivables_bank,
                'combine_receivables_bank':            combine_receivables_bank,
                'split_receivables_cash':              split_receivables_cash,
                'combine_receivables_cash':            combine_receivables_cash,
                'combine_invoice_receivables':         combine_invoice_receivables,
                'split_receivables_pay_later':         split_receivables_pay_later,
                'combine_receivables_pay_later':       combine_receivables_pay_later,
                'stock_return':                        stock_return,
                'stock_output':                        stock_output,
                'combine_inv_payment_receivable_lines': combine_inv_payment_receivable_lines,
                'rounding_difference':                 rounding_difference,
                'MoveLine':                            MoveLine,
                'split_invoice_receivables': split_invoice_receivables,
                'split_inv_payment_receivable_lines': split_inv_payment_receivable_lines,
                'split_receivables_online':split_receivables_online
            })
            return data
        else:
            return super(POSSession, self)._accumulate_amounts(data)


    

    