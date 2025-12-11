import logging

from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    def _prepare_hdm_item_data(self, hdm_dep) -> dict:
        self.ensure_one()
        hs_code = self.product_id.hs_code or self.product_id.product_tmpl_id and self.product_id.product_tmpl_id.hs_code
        item = {
            "dep": self.product_id.hdm_dep or hdm_dep,
            "adgCode": hs_code,
            "productCode": self.product_id.id,
            "productName": self.product_id.hdm_product_name,
            "qty": self.qty,
            "unit": self.product_uom_id.name,
            "price": round(self.price_subtotal_incl / self.qty, 2)
        }
        if self.discount:
            item.update({
                'discountType': 1,
                'discount': self.discount,
            })
        return item


class PosOrder(models.Model):
    _inherit = 'pos.order'

    fiscal_uuid = fields.Char(string='Fiscal UUID', help='HDM-ի կողմից տրված Ֆիսկալ կոդ')
    hdm_type = fields.Selection([
        ('1', 'Պարզ կտրոն'),
        ('2', 'Ապրանքներ ռեժիմ'),
        ('3', 'Կանխավճար'),
    ], string='Mode', help='HDM Կտրոնի ռեժիմը')
    fiscal_receipt_id = fields.Many2one('hdm.receipt', string='Fiscal Receipt', help='HDM Կտրոն')
    retunr_receipt_id = fields.Many2one('hdm.receipt', string='Return Receipt', help='HDM Վերադարձի Կտրոն')
    rseq = fields.Char(string='Rseq', help='Կտրոնի հերթական համար')
    returned_rseq = fields.Char(string='Returned Rseq', help='Վերադարձի Կտրոնի հերթական համար')
    hdm_success = fields.Boolean(string='HDM Success', readonly=True, help='Հաջողությամբ ուղարկված է HDM')

    @api.model
    def _order_fields(self, ui_order):
        fields = super()._order_fields(ui_order)
        if ui_order.get('hdm_type'):
            fields['hdm_type'] = ui_order.get('hdm_type')
        if ui_order.get('fiscal_uuid'):
            fields['fiscal_uuid'] = ui_order.get('fiscal_uuid')
        if ui_order.get('fiscal_receipt_id'):
            fields['fiscal_receipt_id'] = ui_order.get('fiscal_receipt_id', False)
        return fields


    def hdm_type_display(self) -> list:
        self.ensure_one()
        prepayment_line = bool(
            self.lines.filtered(lambda line: line.product_id.id == self.config_id.gift_product_id.id))
        return [{
            'id': i + 1,
            'label': label,
            'item': {'id': i + 1},
            'isSelected': (i + 1 == 2 and not prepayment_line) or (i + 1 == 3 and prepayment_line)
        } for i, label in enumerate(['Պարզ կտրոն', 'Ապրանքներ ռեժիմ', 'Կանխավճար'])]

    def get_downpayment_lines(self):
        return self.lines.filtered(lambda l: l.product_id.id == self.config_id.down_payment_product_id.id).sorted(
            'id')

    def get_lines_without_downpayment(self):
        return self.lines.filtered(lambda l: l.product_id.id != self.config_id.down_payment_product_id.id).sorted(
            'id')

    def _prepare_already_payd_hdm_data(self, hdm_dep, hdm_type, **kwargs) -> dict:
        self.ensure_one()
        cash_amount, bank_amount = 0, 0
        payments = self.payment_ids.filtered(
            lambda p: p.payment_method_id.fiscal_payment_type in ['cash',
                                                                  'bank'] and p.payment_method_id.id != self.config_id.gift_account_id.id)

        used_prepayment = sum(self.payment_ids.filtered(
            lambda p: p.payment_method_id.id == self.config_id.gift_account_id.id).mapped('amount'))
        down_payment_lines = self.get_downpayment_lines()
        if bool(down_payment_lines):
            used_prepayment += abs(sum(down_payment_lines.mapped('price_subtotal_incl')))
        prepayment_amount = used_prepayment if used_prepayment else 0.0

        for payment in payments:
            if payment.payment_method_id.fiscal_payment_type == 'cash':
                cash_amount += payment.amount
            elif payment.payment_method_id.fiscal_payment_type == 'bank':
                bank_amount += payment.amount
        data = {
            "items": None,
            "paidAmount": round(cash_amount, 2),
            "paidAmountCard": round(bank_amount, 2),
            "partialAmount": 0,
            "prePaymentAmount": round(prepayment_amount),
            "useExtPOS": True if bool(bank_amount) else False,
            'eMarks': [],
            "mode": hdm_type,
            "partnerTin": None,
            "seq": self.config_id.hdm_connection_id.hdm_seq,
        }
        data.update(kwargs)
        if hdm_type == 1:
            data['dep'] = hdm_dep
        if hdm_type == 2:
            data['items'] = [line._prepare_hdm_item_data(hdm_dep) for line in
                             self.get_lines_without_downpayment()]
        return data

    def _prepare_invoice_hdm_data(self, hdm_dep, hdm_type, payment_method_id, **kwargs) -> dict:
        self.ensure_one()
        if not payment_method_id:
            return self._prepare_already_payd_hdm_data(hdm_dep, hdm_type, **kwargs)
        data = {
            "items": None,
            "paidAmount": 0,
            "paidAmountCard": 0,
            "partialAmount": 0,
            "prePaymentAmount": 0,
            "useExtPOS": False,
            'eMarks': [],
            "mode": hdm_type,
            "partnerTin": None,
            "seq": self.config_id.hdm_connection_id.hdm_seq,
        }
        if payment_method_id.fiscal_payment_type == 'cash':
            updated_data = {
                "paidAmount": round(self.amount_total, 2),
            }
        else:
            updated_data = {
                "paidAmountCard": round(self.amount_total, 2),
            }
            if payment_method_id.use_ext_pos:
                updated_data["useExtPOS"] = True

        data.update({**kwargs, **updated_data})
        if hdm_type == 1:
            data['dep'] = hdm_dep
        if hdm_type == 2:
            data['items'] = [line._prepare_hdm_item_data(hdm_dep) for line in
                             self.get_lines_without_downpayment()]
        print(data, 'INVOICE DATA')
        return data

    def check_refund_status(self):
        for line in self.lines:
            if line.refunded_orderline_id:
                return True
        return False

    def hdm_return_order(self):
        self.ensure_one()
        pos_id = f'pos_{self.config_id.id}'
        pos_config = self.config_id
        pos_connection = pos_config.hdm_connection_id
        refunded_order = None
        for line in self.lines:
            if line.refunded_orderline_id and line.refunded_orderline_id.order_id:
                refunded_order = line.refunded_orderline_id.order_id
                break
        if not refunded_order or not refunded_order.fiscal_receipt_id:
            return
        receipt = refunded_order.fiscal_receipt_id
        hdm_data = {
            'crn': str(receipt.crn),
            'returnTicketId': str(receipt.rseq),
            'seq': pos_connection.hdm_seq,
        }
        returnItemList = []
        if abs(refunded_order.amount_total) != abs(self.amount_total):
            cash_amount = sum(
                self.payment_ids.filtered(lambda
                                              p: p.payment_method_id.fiscal_payment_type == 'cash' and p.payment_method_id.id != self.config_id.gift_account_id.id).mapped(
                    'amount'))
            bank_amount = sum(
                self.payment_ids.filtered(lambda
                                              p: p.payment_method_id.fiscal_payment_type == 'bank' and p.payment_method_id.id != self.config_id.gift_account_id.id).mapped(
                    'amount'))
            prepayment_amount = sum(self.payment_ids.filtered(
                lambda p: p.payment_method_id.id == self.config_id.gift_account_id.id).mapped('amount'))
            data = [l.id for l in refunded_order.lines.sorted('id')]
            for current_line in self.lines:
                count = 0
                for i in data:
                    if current_line.refunded_orderline_id.id == i:
                        returnItemList.append({
                            "rpid": count,
                            "quantity": abs(current_line.qty),
                        })
                    count += 1

            hdm_data.update({
                "returnItemList": returnItemList,
                "cashAmountForReturn": round(abs(cash_amount)),
                "prePaymentAmountForReturn": round(abs(prepayment_amount)),
                "cardAmountForReturn": round(abs(bank_amount)),
            })
        response = pos_connection.send_request_to_hdm(id=pos_id, code=6, data=hdm_data)
        if response.get('hdm_error'):
            return response

        receipt_id = self.env['hdm.receipt'].sudo().create({
            'rseq': response.get('rseq', ''),
            'name': response.get('fiscal', ''),
            'crn': response.get('crn', ''),
            'related_model_name': self._name,
            'related_model_id': self.id,
            'hdm_type': str(4),
            'total': response.get('total', 0.0),
            'related_hdm_receipt_id': receipt.id,
        })
        self.write({
            'hdm_success': True,
            'rseq': response.get('rseq', ''),
            'fiscal_uuid': response.get('fiscal', ''),
            'fiscal_receipt_id': receipt_id.id,
        })
        return {'success': True, 'fiscal_uuid': response.get('fiscal', '')}

    def hdm_receipt_send(self, hdm_type=False, hdm_dep=False, payment=False, *args, **kwargs):
        self.ensure_one()
        if self.check_refund_status():
            return self.hdm_return_order()
        pos_id = f'pos_{self.config_id.id}'
        pos_config = self.config_id
        pos_connection = pos_config.hdm_connection_id
        hdm_dep = int(hdm_dep) or int(pos_config.hdm_dep)
        hdm_type = int(hdm_type) or int(pos_config.hdm_type)
        self.write({'hdm_type': str(hdm_type)})
        hdm_data = self._prepare_invoice_hdm_data(hdm_dep, hdm_type, payment, **kwargs)
        response = pos_connection.send_request_to_hdm(id=pos_id, code=4, data=hdm_data)
        if response.get('hdm_error'):
            return response

        if response:
            receipt = response.get('fiscal', '')
            receipt_id = self.env['hdm.receipt'].sudo().create({
                'rseq': response.get('rseq', ''),
                'name': receipt,
                'crn': response.get('crn', ''),
                'related_model_name': self._name,
                'related_model_id': self.id,
                'hdm_type': str(hdm_type),
                'total': response.get('total', 0.0),
            })
            self.write({
                'hdm_success': True,
                'rseq': response.get('rseq', ''),
                'fiscal_uuid': receipt,
                'fiscal_receipt_id': receipt_id.id,
            })
            return {'success': True, 'fiscal_uuid': receipt}

    def get_all_payment_total(self):
        totals = {'cash_amount': 0.0, 'bank_amount': 0.0, 'prepayment_amount': 0.0}
        for order in self:
            payment_totals = order.get_current_payment_total()
            totals['cash_amount'] += payment_totals['cash_amount']
            totals['bank_amount'] += payment_totals['bank_amount']
            totals['prepayment_amount'] += payment_totals['prepayment_amount']
        return totals

    def get_current_payment_total(self):
        self.ensure_one()
        cash_amount = sum(
            self.payment_ids.filtered(lambda
                                          p: p.payment_method_id.fiscal_payment_type == 'cash' and p.payment_method_id.id != self.config_id.gift_account_id.id).mapped(
                'amount'))
        bank_amount = sum(
            self.payment_ids.filtered(lambda
                                          p: p.payment_method_id.fiscal_payment_type == 'bank' and p.payment_method_id.id != self.config_id.gift_account_id.id).mapped(
                'amount'))
        prepayment_amount = sum(self.payment_ids.filtered(
            lambda p: p.payment_method_id.id == self.config_id.gift_account_id.id).mapped('amount'))
        return {
            'cash_amount': cash_amount,
            'bank_amount': bank_amount,
            'prepayment_amount': prepayment_amount,
        }

    def get_refunded_orders_remaining_payments(self):
        self.ensure_one()
        refunded_orders = self.refunded_order_ids
        total_refunded_payments = {
            'cash_amount': 0,
            'bank_amount': 0,
            'prepayment_amount': 0,
        }
        for order in refunded_orders:

            cash_amount = sum(
                order.payment_ids.filtered(lambda
                                               p: p.payment_method_id.fiscal_payment_type == 'cash' and p.payment_method_id.id != order.config_id.gift_account_id.id).mapped(
                    'amount'))
            bank_amount = sum(
                order.payment_ids.filtered(lambda
                                               p: p.payment_method_id.fiscal_payment_type == 'bank' and p.payment_method_id.id != order.config_id.gift_account_id.id).mapped(
                    'amount'))
            prepayment_amount = sum(order.payment_ids.filtered(
                lambda p: p.payment_method_id.id == order.config_id.gift_account_id.id).mapped('amount'))
            total_refunded_payments.update({
                'cash_amount': total_refunded_payments.get('cash_amount', 0) + cash_amount,
                'bank_amount': total_refunded_payments.get('bank_amount', 0) + bank_amount,
                'prepayment_amount': total_refunded_payments.get('prepayment_amount', 0) + prepayment_amount,
            })
            another_refund = order.mapped('lines.refund_orderline_ids.order_id').ids
            if another_refund:
                refund = {i for i in another_refund if i != self.id}
                another_refund = self.env['pos.order'].browse(refund)
                another_refunds_totals = another_refund.get_all_payment_total()
                total_refunded_payments.update({
                    'cash_amount': total_refunded_payments['cash_amount'] + another_refunds_totals['cash_amount'],
                    'bank_amount': total_refunded_payments['bank_amount'] + another_refunds_totals['bank_amount'],
                    'prepayment_amount': total_refunded_payments['prepayment_amount'] + another_refunds_totals[
                        'prepayment_amount'],
                })

        return total_refunded_payments

    def check_extra_rules(self):
        super().check_extra_rules()
        for current_order in self:
            refunded_order = None
            for line in current_order.lines:
                if line.refunded_orderline_id and line.refunded_orderline_id.order_id:
                    refunded_order = line.refunded_orderline_id.order_id
                    break
            if not refunded_order:
                continue
            refunded_payments = current_order.get_refunded_orders_remaining_payments()
            _logger.info(f"{refunded_payments}, 'refunded_payments'")

            current_payments = current_order.get_current_payment_total()
            _logger.info(f"{current_payments}, 'current_payments'")
            for payment_type in ['cash_amount', 'bank_amount', 'prepayment_amount']:
                original = refunded_payments.get(payment_type, 0.0)
                refund = current_payments.get(payment_type, 0.0)

                if refund != 0 and original == 0:
                    raise ValidationError(
                        _(f'Not right payment method: {payment_type.replace("_amount", "")}. '
                          f'Refund must be make with the same payment method as the original order. '
                          f'Remaining payments: {refunded_payments.__str__().replace("_amount", "")}')
                    )

                if abs(refund) > original:
                    raise ValidationError(
                        _(f'Total payment in this payment type {payment_type.replace("_amount", "")}. '
                          f'({abs(refund)}) exceeds current ({original}).')
                    )

    def _prepare_invoice_vals(self):
        self.ensure_one()
        invoice_vals = super()._prepare_invoice_vals()
        if self.fiscal_receipt_id:
            invoice_vals.update({
                'fiscal_receipt_id': self.fiscal_receipt_id.id,
            })
        return invoice_vals

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_order_line):
        return {
            'product_id': line_values['product'].id,
            'quantity': line_values['quantity'],
            'discount': line_values['discount'],
            'price_unit': line_values['price_unit'],
            'name': line_values['name'],
            'tax_ids': [(6, 0, line_values['taxes'].ids)],
            'product_uom_id': line_values['uom'].id,
            'fiscal_receipt_id': self.fiscal_receipt_id.id if self.fiscal_receipt_id else False,
        }
