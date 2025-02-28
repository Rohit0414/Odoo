from odoo import fields, models, api

class Project(models.Model):
    _name='pm.project'
    _description='Project'
    
    
    name=fields.Char(string="Project Name", required=True)
    description=fields.Text()
    start_date=fields.Date(string="Start Date")
    end_date=fields.Date(string="End Date")
    task_ids=fields.One2many('pm.task', 'project_id',string="Task")