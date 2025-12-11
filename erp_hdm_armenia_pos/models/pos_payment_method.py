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

    def _construct_hdm_connection(self, pos_config, hdm_dep=False, hdm_type=False):
        pos_id = f'pos_{pos_config.id}'
        pos_connection = pos_config.hdm_connection_id
        hdm_dep = hdm_dep or pos_config.hdm_dep
        hdm_type = hdm_type or pos_config.hdm_type
        return pos_connection, pos_id, int(hdm_dep), int(hdm_type)

    def _payment_request_from_kiosk(self, order):
        if self.use_payment_terminal != 'hdm':
            return super()._payment_request_from_kiosk(order)
        else:
            return self.hdm_kiosk_payment_request(order)

    def _prepare_hdm_item_data(self, lines, hdm_dep=False):
        items = []
        for line in lines:
            product_id = self.env['product.product'].browse(line.get('product_id'))
            item = {
                "dep": product_id.hdm_dep or hdm_dep,
                "adgCode": product_id.hs_code or product_id.product_tmpl_id and product_id.product_tmpl_id.hs_code,
                "productCode": product_id.id,
                "productName": product_id.hdm_product_name,
                "qty": line.get('qty', 1),
                "unit": product_id.uom_id.name,
                "price": round(line.get('price_unit', 1) * line.get('discount') / 100 if line.get('discount', 0) else line.get('price_unit', 1), 2),
            }
            if line.get('discount', 0):
                item.update({
                    'discountType': 1,
                    'discount': line['discount']
                })
            if hdm_dep:
                item['dep'] = 1
            items.append(item)
        return items

    def init_hdm_start_data(self, seq, hdm_type, hdm_dep=False, lines=False):
        data = {
            "items": None,
            "paidAmount": 0,
            "paidAmountCard": 0,
            "partialAmount": 0,
            "prePaymentAmount": 0,
            "useExtPOS": True if self.use_ext_pos else False,
            'eMarks': [],
            "mode": int(hdm_type),
            "partnerTin": None,
            "seq": seq,
        }
        if hdm_type == 1:
            data['dep'] = hdm_dep
        print(hdm_type, lines, 'CHECK THIS')
        if hdm_type == 2 and lines:
            data['items'] = self._prepare_hdm_item_data(lines, hdm_dep)
        return data

    def hdm_pos_payment_request(self, config_id, amount, lines=False, hdm_dep=False, hdm_type=False, *args, **kwargs):
        print("HDM POS PAYMENT REQUEST CALLED", lines)
        pos_config = self.env['pos.config'].browse(config_id)
        pos_connection, pos_id, hdm_dep, hdm_type = self._construct_hdm_connection(pos_config, hdm_dep, hdm_type)

        data = self.init_hdm_start_data(seq=pos_config.hdm_connection_id.hdm_seq, hdm_type=hdm_type, hdm_dep=hdm_dep, lines=lines)
        if self.fiscal_payment_type == 'cash':
            updated_data = {
                "paidAmount": abs(round(amount, 2)),
            }
        else:
            updated_data = {
                "paidAmountCard": abs(round(amount, 2)),
            }
            if self.use_ext_pos:
                updated_data["useExtPOS"] = True
        data.update({**kwargs, **updated_data})
        print("HDM PAYMENT REQUEST DATA:", data)
        response = pos_connection.send_request_to_hdm(id=pos_id, code=4, data=data)
        if response.get('hdm_error'):
            return response
        if response:
            receipt = response.get('fiscal', '')
            receipt_id = self.env['hdm.receipt'].sudo().create({
                'rseq': response.get('rseq', ''),
                'name': receipt,
                'crn': response.get('crn', ''),
                'hdm_type': str(hdm_type),
                'total': response.get('total', 0.0),
            })
            return {
                'success': True,
                'fiscal_receipt_id': receipt_id.id,
                'fiscal_uuid': receipt,
            }

    def hdm_pos_payment_refund(self, config_id, amount, refunded_line_id, lines=False, hdm_dep=False, hdm_type=False,
                               *args,
                               **kwargs):
        print(lines)
        pos_config = self.env['pos.config'].browse(config_id)
        pos_connection, pos_id, _, _ = self._construct_hdm_connection(pos_config)

        order = self.env['pos.order.line'].browse(refunded_line_id[0]).order_id
        if not order.fiscal_receipt_id:
            return {'hdm_error': 'Original fiscal receipt not found for refund.'}

        hdm_data = {
            'crn': str(order.fiscal_receipt_id.crn),
            'returnTicketId': str(order.fiscal_receipt_id.rseq),
            'seq': pos_connection.hdm_seq,
        }

        if self.fiscal_payment_type == 'cash':
            updated_data = {
                "cashAmountForReturn": abs(round(amount, 2)),
            }
        else:
            updated_data = {
                "cardAmountForReturn": abs(round(amount, 2)),
            }
        hdm_data.update({**kwargs, **updated_data})
        response = pos_connection.send_request_to_hdm(id=pos_id, code=6, data=hdm_data)
        if response.get('hdm_error'):
            return response
        receipt_id = self.env['hdm.receipt'].sudo().create({
            'rseq': response.get('rseq', ''),
            'name': response.get('fiscal', ''),
            'crn': response.get('crn', ''),
            'hdm_type': str(4),
            'total': response.get('total', 0.0),
            'related_hdm_receipt_id': order.fiscal_receipt_id.id,
        })
        return {
            'success': True,
            'fiscal_receipt_id': receipt_id.id,
            'fiscal_uuid': response.get('fiscal', ''),
        }

    def hdm_kiosk_payment_request(self, order):
        self.ensure_one()
        hdm_response = order.hdm_receipt_send(False, False, self)
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
