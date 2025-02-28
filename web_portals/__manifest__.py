{
    'name': "Web Portals",
    'version': '18.0',
    'depends': ['base'],
    'author': "Jarvis",
    'category': 'Website',
    'description': """
    Description text
    """,
    'that serve as gateways to a range of services or resources (often requiring login) and provide a variety of information in one place.'
    'data': [
        'security/ir.model.access.csv'
        'views/mymodule_view.xml',
        'views/menu.xml'
    ],
    # data files containing optionally loaded demonstration data
    'demo': [
        
    ],
    
    'installable':True,
    'application':True,
    'auto-install':False,
}