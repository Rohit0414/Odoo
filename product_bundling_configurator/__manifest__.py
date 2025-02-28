{
    'name': "Product Bundling and Configurator",
    'version': '18.0.1.0',
    'license': 'LGPL-3',
    'depends': ['base', 'sale'],
    'author': "Jarvis",
    'category': 'Sales',
    'summary': "A user-friendly interface for sales teams to build and price custom bundles quickly.",
    'description': """
        A user-friendly interface for sales teams to build and price custom bundles quickly.
    """,
    'data': [
        'security/ir.model.access.csv',
        'views/product_view.xml',
        'views/main_menu.xml',
    ],
    'demo':[
        
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
