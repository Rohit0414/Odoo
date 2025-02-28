from odoo import fields, models

class RealEstate(models.Model):
    _name ='real.estate.property'
    _description = 'Real Estate Advertising'
    
    name=fields.Char(string="Name", required=True)
    description=fields.Char(string="Description")
    
