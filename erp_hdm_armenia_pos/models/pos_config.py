# -*- coding: utf-8 -*-
from datetime import datetime
from uuid import uuid4
import pytz

from odoo import api, fields, models, _, Command
from odoo.http import request
from odoo.osv.expression import OR, AND
from odoo.exceptions import AccessError, ValidationError, UserError


class PosConfig(models.Model):
    _inherit = 'pos.config'

    hdm_connection_id = fields.Many2one('hdm.connection', string='HDM Armenia Connection')
    hdm_dep = fields.Selection([('1', 'հարկվող'), ('2', 'չհարկվող')], string='HDM Department', default='1')
    use_dep = fields.Boolean(string='Use HDM Department', default=False)
    hdm_type = fields.Selection([
        ('1', 'Պարզ կտրոն'),
        ('2', 'Ապրանքներ ռեժիմ'),
        ('3', 'Կանխավճար'),
    ], string='Mode', default='2')
    use_hdm_type = fields.Boolean(string='Use HDM Type', default=True)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    fiscal_payment_type = fields.Selection(related='journal_id.type', string='Fiscal Payment Type')
