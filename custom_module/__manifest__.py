# custom_module/__manifest__.py
{
    'name': 'first module',
    'summery': 'First Odoo 18 module',
    'description': 'testing purpuses',
    'version': '1.0',
    'category': 'Productivity',
    'author': 'Jarvis',
    'depends': [],
    'data': [
    'security/ir.model.access.csv',
    'views/invoice_view.xml',  ],
    'installable': True,
    'application': True,
}
