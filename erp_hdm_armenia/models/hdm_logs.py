from odoo import models, api, fields


class HdmLogs(models.Model):
    _name = 'hdm.log'
    _description = 'HDM Logs'

    name = fields.Char(string='Log Entry', required=True)
    code = fields.Char(string='Request Code')
    req_data = fields.Char(string='Request Data')
    terminal_id = fields.Many2one('hdm.connection', string='HDM Device', required=True)
    company_id = fields.Many2one('res.company', string='Company')
    model_name = fields.Char(string='Model Name')
    res_id = fields.Integer(string='Record ID')
    ref = fields.Reference([('pos.order', 'POS Order'), ('pos.payment.method', 'Pos Payment Method')], 'Document ID',
                           compute='_compute_ref_id', store=True)

    @api.depends('model_name', 'res_id')
    def _compute_ref_id(self):
        for record in self:
            if record.model_name and record.res_id:
                record.ref = f"{record.model_name},{int(record.res_id)}"
            else:
                record.ref = False
