{
    'name': "Inventory & Warehouse Management Improvements",
    'version': '1.0',
    'author': "jarvis",
    'category': 'Warehouse',
    'summary': "Enhancements for custom replenishment rules, multi-warehouse support, and inventory dashboards.",
    'depends': ['stock', 'web', 'stock_barcode'],
    'data': [
         'security/ir.model.access.csv',
         'views/stock_replenishment_views.xml',
         'views/stock_dashboard_views.xml',
    ],
    'installable': True,
    'application': True,
    
}
