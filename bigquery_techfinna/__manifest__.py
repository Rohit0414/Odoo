{
    'name': 'BigQuery Connector | Cloud Data Warehouse for Odoo',
    'version': '2.1.2',
    'summary': 'BigQuery integration with query builder for Odoo',
    'author': 'TechFinna',
    'website': 'https://techfinna.com/odoo-bigquery-connector/',
    'maintainer': 'Techfinna',
    'category': 'Connector',
    'support': "info@techfinna.com",
    'license': 'LGPL-3',
    'price': 399,
    'currency': 'USD',
    'depends': ['base'],
    'images': ['static/description/banner.gif'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_auto_sync.xml',
        'views/res_config_settings_view.xml',
        'views/bigquery_connector_menu.xml',
        'views/bigquery_export_wizard_view.xml',
        'views/bigquery_query_menu.xml',   # ✅ NEW Query Menu XML
        'views/bigquery_query_view.xml',   # ✅ NEW Query Form XML
    ],
    'external_dependencies': {
        'python': ['google-cloud-bigquery', 'pandas', 'pyarrow'],
    },
    'application': True,
    'installable': True,
}
