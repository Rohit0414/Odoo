from odoo import fields, models, api

class Task(models.Model):
    _name='pm.task'
    _description='Task'
    
    name=fields.Char(string="Task Name", required=True)
    project_id=fields.Many2one('pm.project', string="Project", ondelete="cascade", required=True)
    assigned_to=fields.Many2many('res.users', string="Assigned To")
    start_date=fields.Datetime(string="Start Date")
    end_date=fields.Datetime(string="End date")
    description=fields.Text()
    progress=fields.Float(string="Progress (%)", default=0.0)
    