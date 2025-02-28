{
    'name': 'Project Management',
    'version': '1.0',
    'summary': 'Manage projects, tasks, and team collaborations',
    'description': """
        This module allows you to create and manage projects, tasks,
        view tasks on calendar and Gantt charts, and allocate resources.
    """,
    'author': 'Jarvis',
    'depends': ['base', 'calendar'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/project_views.xml',
        'views/task_views.xml',
        
    ],
    'installable': True,
    'application': True,
}
