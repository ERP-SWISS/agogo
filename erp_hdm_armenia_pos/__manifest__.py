# -*- coding: utf-8 -*-
{
    'name': "Armenian HDM POS Integration",
    'version': '1.0.1',
    'summary': "Integration module for Armenian HDM POS system",
    'author': "ERP SWISS",
    'website': "https://www.erpswiss.com",
    'depends': ['erp_hdm_armenia', 'point_of_sale', 'pos_self_order'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml'
    ],
    'assets': {
        'pos_self_order.assets': [
            'erp_hdm_armenia_pos/static/src/**/*',
        ],
    },

}
