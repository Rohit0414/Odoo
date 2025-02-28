{
    'name': "Real Estate Advertising",
    'version': '18.0',
    'depends': ['base'],
    'author': "Jarvis",
    'category': 'Advertising',
    'description': """
     Real Estate Advertising Description
    """,
   
    'data': [
        'security/ir.model.access.csv',
        'views/property.xml',
        'views/menu.xml'
    ],
   
    'demo': [
        
    ],
    
    'installable':True,
    'application':True,
    'autoinstall':False,
    
}