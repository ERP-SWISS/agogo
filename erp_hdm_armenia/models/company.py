import json
import struct
import logging

from odoo import fields, models, _
from odoo.exceptions import ValidationError, AccessError

from ..utils.utils import *
from ..utils.hdm_socket import HDM

_logger = logging.getLogger(__name__)


class HDMCompany(models.Model):
    _inherit = 'res.company'

    default_hdm_connection_id = fields.Many2one('hdm.connection', string='Default HDM Connection',
                                                domain="[('company_id','=',id)]")
    host = fields.Char(string='HOST', related='default_hdm_connection_id.host')
    port = fields.Integer(string='PORT', related='default_hdm_connection_id.port')
    cashier = fields.Char(string='Cashier', related='default_hdm_connection_id.cashier')
    hdm_password = fields.Char(string='Password', related='default_hdm_connection_id.hdm_password')
    hdm_pin = fields.Char(string='Pin', related='default_hdm_connection_id.hdm_pin')
    hdm_key = fields.Char(string='Connection key', readonly=False, related='default_hdm_connection_id.hdm_key',
                          store=True)

    hdm_payment = fields.Integer('PaymentSystem', related='default_hdm_connection_id.hdm_payment')
    hdm_seq = fields.Integer(string='sequence', related='default_hdm_connection_id.hdm_seq', store=True)

    @property
    def hdm_login_data(self):
        self.ensure_one()
        hdm_connection = self.env['hdm.connection'].search([('company_id', '=', self.env.company.id)], limit=1)
        if hdm_connection:
            return {
                "password": hdm_connection.hdm_password,
                "cashier": int(hdm_connection.cashier),
                "pin": hdm_connection.hdm_pin
            }

    @property
    def hdm_host(self):
        self.ensure_one()
        return (self.host, self.port)

    def hdm_connection(self):
        company = self
        _logger.info(f'Initiating HDM connection... {company} {company.hdm_login_data}')

        host_address = (company.host, company.port)
        try:
            HDM.close(id=company.id)
        except ConnectionError:
            _logger.info('No existing HDM connection to close.')
        connection = HDM.connect(host=host_address, id=company.id)
        if connection is None:
            raise ValidationError(_("Unable to connect to HDM. Please check the HOST and PORT settings."))
        response = HDM.send(id=company.id, data=company.hdm_login_data, code=2, connection=company)
        response_status = struct.unpack('>H', response[5:7])[0]
        _logger.info(f'HDM Connection Response Status: {response_status} {response}')
        notif_text, notif_type = 'Failed to connect to HDM. Please check your settings.', 'warning'
        if response_status == 200:
            notif_text, notif_type = 'Connection to HDM established successfully.', 'success'
            unpack_key = json.loads(unpack_hdm_key(company.hdm_password, response[11:])).get('key')
            if unpack_key:
                _logger.info(f'HDM Connection Key received and stored. {unpack_key}')
                company.write({'hdm_key': unpack_key})
        HDM.close(id=company.id, connection=company)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'context': dict(self._context, active_ids=self.ids),
            'target': 'new',
            'params': {
                'message': _(notif_text),
                'type': notif_type,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def hdm_disconnection(self):
        company = self
        company.hdm_seq += 1
        data = {
            "seq": company.hdm_seq
        }
        host_address = (company.host, company.port)
        connection = HDM.connect(host=host_address, id=company.id)
        if connection is None:
            raise ValidationError(_("Unable to connect to HDM. Please check the HOST and PORT settings."))
        response = HDM.send(id=company.id, data=data, code=3, company=company)
        if response:
            response_status = struct.unpack('>H', response[5:7])[0]
            _logger.info(f'HDM Connection Response Status: {response_status} {response}')
        try:
            HDM.close(id=company.id)
        except ConnectionError:
            _logger.info('No existing HDM connection to close.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'context': dict(self._context, active_ids=self.ids),
            'target': 'new',
            'params': {
                'message': _('Disconnecting...'),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


    def sync_hdm_time(self):
        self.ensure_one()
        if self.default_hdm_connection_id:
            return self.default_hdm_connection_id.sync_hdm_time()

