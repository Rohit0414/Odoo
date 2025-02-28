from odoo import fields, models

class WebPortals(models.Model):
    _name='web.portals'
    _description='that serve as gateways to a range of services or resources (often requiring login) and provide a variety of information in one place.'
    
    
    name=fields.Char(string="Name", required=True)
    description=fields.Char(string="Description")