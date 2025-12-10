# -*- coding: utf-8 -*-
{
    'name': "Armenian HDM POS Integration",
    'version': '1.0.1',
    'category': 'Sales/Point of Sale',
    'summary': "Integration module for Armenian HDM POS system",
    'author': "ERP SWISS",
    'website': "https://www.erpswiss.com",
    'depends': ['point_of_sale', 'pos_self_order', 'pos_sale', 'erp_hdm_armenia'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/pos_payment_method_views.xml',
    ],
    'assets': {
        'pos_self_order.assets': [
            'erp_hdm_armenia_pos/static/src/kiosk/**/*',
        ],
        'point_of_sale._assets_pos': [
            'erp_hdm_armenia_pos/static/src/pos/**/*',
        ],
    },

}
