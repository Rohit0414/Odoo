from odoo import fields, models

class OdooModule(models.Model):
    _name = 'odoo.module'
    _description = 'Odoo Module Description'

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Module Description", required=True)
    date = fields.Date(string="Date Created", required=True)
    quantity = fields.Integer(string="Module Count", required=True)

   
