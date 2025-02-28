{
    'name': 'BigQuery Connector | Cloud Data Warehouse for Odoo',
    'version': '2.1.1',
    'summary': '',
    'author': 'TechFinna',
    'website': 'https://techfinna.com/odoo-bigquery-connector/',
    'maintainer': 'Techfinna',
    'category': 'Connector',
    'support': "info@techfinna.com",
    'live_test_url': 'https://youtu.be/fRtjMXTZSwA',
    'license': 'LGPL-3',
    'price': 399,
    # 'module_type': 'official',
    'currency': 'USD',
    'depends': ['base'],
    'images': ['static/description/banner.gif'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_view.xml',
        'views/bigquery_connector_menu.xml',
        'views/bigquery_export_wizard_view.xml',
    ],

    'external_dependencies': {
        'python': ['google-cloud-bigquery', 'pandas', 'pyarrow'],
    },
    'application': True,
    'installable': True,
}
