import logging
import struct
import json

from odoo import fields, models, _
from odoo.exceptions import ValidationError, AccessError

from odoo.addons.erp_hdm_armenia.utils.hdm_socket import HDM
from odoo.addons.erp_hdm_armenia.utils.utils import unpack_hdm_key, unpack_hdm_response, hdm_error_codes

_logger = logging.getLogger(__name__)


class HdmReceipt(models.Model):
    _name = 'hdm.receipt'
    _description = 'HDM Receipt'

    name = fields.Char(string='Ֆիսկալ կոդ', help='HDM-ի կողմից տրված Ֆիսկալ կոդ')
    hdm_type = fields.Selection([
        ('1', 'Պարզ կտրոն'),
        ('2', 'Ապրանքներ ռեժիմ'),
        ('3', 'Կանխավճար'),
        ('4', 'Վերադարձի կտրոն'),
    ], string='Mode', help='HDM Կտրոնի ռեժիմը')
    crn = fields.Char(string='CRN', help='Կտրոնի ռեգիստրացիոն համարը')
    rseq = fields.Char(string='Rseq', help='Կտրոնի հերթական համար')
    returned_rseq = fields.Char(string='Returned Rseq', help='Վերադարձված կտրոնի հերթական համար')
    returned_time = fields.Datetime(string='Returned Time', help='Վերադարձված կտրոնի ժամանակը')
    returned_cash = fields.Float(string='Returned Cash', help='Վերադարձված կանխիկ գումարը')
    returned_card = fields.Float(string='Returned Card', help='Վերադարձված քարտով գումարը')
    related_hdm_receipt_id = fields.Many2one('hdm.receipt', string='Related HDM Receipt')
    total = fields.Float(string='Total Amount', help='Կտրոնի ընդհանուր գումարը')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    related_model_name = fields.Char(string='Related Model Name')
    related_model_id = fields.Integer(string='Related Model ID')

    def action_open_related_record(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record'),
            'res_model': self.related_model_name,
            'res_id': self.related_model_id,
            'view_mode': 'form',
            'target': 'current',
        }


class HDMConnection(models.Model):
    _name = 'hdm.connection'
    _description = 'HDM Connection Settings'
    _code_with_responses = [2, 4, 6]

    name = fields.Char(string='Terminal ID')
    host = fields.Char(string='HOST')
    port = fields.Integer(string='PORT')
    cashier = fields.Char(string='Cashier')
    hdm_password = fields.Char(string='Password')
    hdm_pin = fields.Char(string='Pin')
    hdm_key = fields.Char(string='Connection key', readonly=True)
    hdm_payment = fields.Integer('PaymentSystem')
    hdm_seq = fields.Integer(string='sequence', default=1)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    use_ext_pos = fields.Boolean(string='Use External POS', default=False)
    active = fields.Boolean(string='Active', default=True)

    @property
    def hdm_login_data(self):
        self.ensure_one()
        return {
            "password": self.hdm_password,
            "cashier": int(self.cashier),
            "pin": self.hdm_pin
        }

    @property
    def hdm_host(self):
        self.ensure_one()
        return (self.host, self.port)

    def check_waiting_for_response(self, code):
        if code in self._code_with_responses:
            return True
        return False

    def get_response_status_code(self, response):
        try:
            response_status = struct.unpack('>H', response[5:7])[0]
            if response_status != 200:
                error_message = hdm_error_codes.get(response_status, 'Unknown Error')
                return {'hdm_error': f'{response_status}: {error_message}'}
        except Exception as E:
            _logger.error(f'Error unpack response status from HDM: {E}')
            return {'hdm_error': 'Failed to unpack response status from HDM.'}

    def send_request_to_hdm(self, id, code, data):
        self.ensure_one()
        pos_connection = self
        try:
            HDM.close(id=id, connection=pos_connection)
        except ConnectionError:
            _logger.info('No existing HDM connection to close.')
        connection = HDM.connect(host=pos_connection.hdm_host, id=id)
        if connection is None:
            raise ValidationError(_("Unable to connect to HDM. Please check the HOST and PORT settings."))
        response = HDM.send(id=id, data=pos_connection.hdm_login_data, code=2, connection=pos_connection)
        if self.check_waiting_for_response(code):
            try:
                response_status = struct.unpack('>H', response[5:7])[0]
            except Exception as E:
                _logger.error(f'Error unpack response status from HDM: {E}')
                raise ValidationError(_("Failed to receive a valid response from HDM. Please try again."))
            else:
                if response_status == 200:
                    unpack_key = json.loads(unpack_hdm_key(pos_connection.hdm_password, response[11:])).get('key')
                    if unpack_key:
                        pos_connection.write({'hdm_key': unpack_key})
        try:
            response = HDM.send(id=id, data=data, code=code, connection=pos_connection)
            if self.check_waiting_for_response(code):
                error_code = self.get_response_status_code(response)
                if error_code:
                    return error_code
            unpack_data = json.loads(unpack_hdm_response(pos_connection.hdm_key, response[11:]))
            return unpack_data
        except Exception as E:
            _logger.error(f'Error recv data to HDM: {E}')
            return False
        finally:
            HDM.close(id=id, connection=pos_connection)

    def sync_hdm_time(self):
        self.ensure_one()
        hdm_time_data = {
            "seq": self.hdm_seq,
        }
        self.send_request_to_hdm(id=f'sync_{self.id}', code=10, data=hdm_time_data)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'context': dict(self._context, active_ids=self.ids),
            'target': 'new',
            'params': {
                'message': _("HDM time synchronized successfully."),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
