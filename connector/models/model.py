from odoo import models, fields

class Connector(models.Model):
    _name='connector.module'
    _description='Connector Description'
    
    
    name=fields.Char(string="Name", required=True)
    description=fields.Char(string="Connector Description", required=True)
    date_time = fields.Datetime(string="Date & Time", required=True)
    quantity=fields.Integer(string="Quantity", required=True)
    data=fields.Float(string="Data", required=True)
    
    
