{
    'name': "Student Management",
    'version': '1.0',
    'author': "Your Name",
    'category': 'Education',
    'summary': "Manage student registrations, academic performance, attendance, and schedules",
    'depends': ['base', 'mail'],  # Add additional dependencies if needed
    'data': [
         'security/ir.model.access.csv',
         'views/student_views.xml',
         'views/performance_views.xml',
         'views/attendance_views.xml',
         'views/schedule_views.xml',
    ],
    'installable': True,
    'application': True,
}
