from odoo import api, fields, models, _, Command
from odoo.fields import Domain

import logging

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        selection = super()._get_payment_terminal_selection()
        selection.append(('hdm', 'Fiscal Printer (HDM)'))
        return selection

    fiscal_payment_type = fields.Selection(related='journal_id.type', string='Fiscal Payment Type')
    use_ext_pos = fields.Boolean('Use External POS System', default=False)

    @api.constrains('fiscal_payment_type', 'use_payment_terminal')
    def _check_fiscal_payment_type(self):
        for payment in self:
            if payment.use_payment_terminal == 'hdm' and payment.fiscal_payment_type not in ('cash', 'bank'):
                raise models.ValidationError(
                    _("The fiscal payment methods using HDM terminal must be of type 'Cash' or 'Bank'.")
                )

    @api.model
    def _load_pos_self_data_domain(self, data, config):
        domain = super()._load_pos_self_data_domain(data, config)
        if config.self_ordering_mode == 'kiosk':
            domain = Domain.OR([
                [('use_payment_terminal', '=', 'hdm'), ('id', 'in', config.payment_method_ids.ids)],
                domain
            ])
        return domain

    def _payment_request_from_kiosk(self, order):
        if self.use_payment_terminal != 'hdm':
            return super()._payment_request_from_kiosk(order)
        else:
            return self.hdm_payment_request(order)

    def pos_hdm_payment_request(self, config_id, order):
        self.ensure_one()
        hdm_response = order.hdm_receipt_send(False, False, self)
        # TODO: add expression for use extr POS <or self.use_ext_pos>
        if hdm_response.get('success') and hdm_response.get('fiscal_uuid'):
            order.add_payment({
                'amount': order.amount_total,
                'payment_method_id': self.id,
                'payment_status': 'done',
                'pos_order_id': order.id,
            })
            order.action_pos_order_paid()
            order._send_payment_result('Success')
            return 'success'
        elif hdm_response.get('hdm_error'):
            order._send_payment_result('fail')
            _logger.error(f'HDM Payment Error: {hdm_response.get("hdm_error")}')
            return 'fail'

    def hdm_payment_request(self, order):
        self.ensure_one()
        hdm_response = order.hdm_receipt_send(False, False, self)
        # TODO: add expression for use extr POS <or self.use_ext_pos>
        if hdm_response.get('success') and hdm_response.get('fiscal_uuid'):
            order.add_payment({
                'amount': order.amount_total,
                'payment_method_id': self.id,
                'payment_status': 'done',
                'pos_order_id': order.id,
            })
            order.action_pos_order_paid()
            order._send_payment_result('Success')
            return 'success'
        elif hdm_response.get('hdm_error'):
            order._send_payment_result('fail')
            _logger.error(f'HDM Payment Error: {hdm_response.get("hdm_error")}')
            return 'fail'
