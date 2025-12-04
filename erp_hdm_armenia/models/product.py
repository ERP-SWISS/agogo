from odoo import fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    hdm_product_name = fields.Char(string='HDM Name', tranlate=False)
    hdm_dep = fields.Integer(string='HDM Department', default=1)
    hs_code = fields.Char(string='HS Code', help='Harmonized System Code for international trade')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    hdm_dep = fields.Integer(string='HDM Department', related='product_tmpl_id.hdm_dep')