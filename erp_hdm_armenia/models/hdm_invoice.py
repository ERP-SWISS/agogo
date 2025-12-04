import logging

from odoo import fields, models, _
from odoo.exceptions import ValidationError, AccessError

_logger = logging.getLogger(__name__)


class HdmInvoiceLines(models.Model):
    _inherit = 'account.move.line'

    fiscal_receipt_id = fields.Many2one('hdm.receipt', related='move_id.fiscal_receipt_id', string='Fiscal Receipt', help='HDM Կտրոն')

    def _prepare_hdm_item_data(self) -> dict:
        self.ensure_one()
        hs_code = self.product_id.hs_code or self.product_id.product_tmpl_id and self.product_id.product_tmpl_id.hs_code
        item = {
            "dep": self.product_id.hdm_dep or 1,
            "adgCode": hs_code,
            "productCode": self.product_id.id,
            "productName": self.product_id.hdm_product_name,
            "qty": self.qty,
            "unit": self.product_uom_id.name,
            "price": self.price_total / self.qty,
        }
        if self.discount:
            item.update({
                'discountType': 1,
                'discount': self.discount,
            })
        return item


class HdmInvoice(models.Model):
    _inherit = 'account.move'

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

    def get_lines_without_downpayment(self):
        return self.invoice_line_ids.filtered(
            lambda l: l.product_id.id != self.company_id.sale_down_payment_product_id.id).sorted(
            'id')

    def get_downpayment_lines(self):
        return self.invoice_line_ids.filtered(
            lambda l: l.product_id.id == self.company_id.sale_down_payment_product_id.id).sorted(
            'id')

    # sale_down_payment_product_id
    def _prepare_invoice_hdm_data(self, hdm_dep, hdm_type) -> dict:
        self.ensure_one()

        cash_amount, bank_amount, prepayment_amount = 0, 0, 0
        account_payments = self._get_reconciled_payments()
        payments = account_payments.filtered(lambda p: p.journal_id.type in ['cash', 'bank'])
        prepayment_amount = abs(sum(self.get_downpayment_lines().mapped('price_total')))
        for payment in payments:
            if payment.journal_id.type == 'cash':
                cash_amount += payment.amount
            elif payment.journal_id.type == 'bank':
                bank_amount += payment.amount
        data = {
            "items": None,
            "paidAmount": round(cash_amount, 1),
            "paidAmountCard": round(bank_amount, 1),
            "partialAmount": 0,
            "prePaymentAmount": round(prepayment_amount),
            "useExtPOS": True if bool(bank_amount) else False,
            'eMarks': [],
            "mode": hdm_type,
            "partnerTin": None,
            "seq": self.config_id.hdm_connection_id.hdm_seq,
        }
        if hdm_type == 1:
            data['dep'] = hdm_dep
        if hdm_type == 2:
            data['items'] = [line._prepare_hdm_item_data() for line in self.get_lines_without_downpayment()]
        return data
