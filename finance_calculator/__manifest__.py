{
    'name': 'Advanced Financial Calculator',
    'version': '1.0',
    'summary': 'Loan EMI, Compound Interest, Inflation, and Retirement Planning Calculators',
    'category': 'Finance',
    'author': 'jarvis',
    'website': 'https://yourwebsite.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/loan_calculator_view.xml',
        'views/compound_interest_view.xml',
        'views/inflation_calculator_view.xml',
        'views/retirement_planner_view.xml',
    ],
    'installable': True,
    'application': True,
}
