# -*- coding: utf-8 -*-
{
    'name': "Armenian HDM Integration",
    'version': '1.0.1',
    'summary': "Armenian Invoice/Check Printing intergation",
    'author': "ERP SWISS",
    'website': "https://www.erpswiss.com",
    'depends': ['base', 'account', 'product'],
    'data': [
        'views/hdm.xml',
        'views/product.xml',
        'views/hdm_receipt.xml',
        'security/ir.model.access.csv'
    ],
    'external_dependencies': {'python': ['pycryptodome']}
}
