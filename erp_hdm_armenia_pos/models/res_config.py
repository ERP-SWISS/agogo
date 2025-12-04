from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hdm_connection_id = fields.Many2one(related='pos_config_id.hdm_connection_id', string='HDM Connection',
                                        readonly=False)
    hdm_dep = fields.Selection(related='pos_config_id.hdm_dep', string='Department', readonly=False)
    use_dep = fields.Boolean(related='pos_config_id.use_dep', string='Use Department', readonly=False)
    hdm_type = fields.Selection(related='pos_config_id.hdm_type', string='Mode', readonly=False)
    use_hdm_type = fields.Boolean(related='pos_config_id.use_hdm_type', string='Use Mode', readonly=False)
