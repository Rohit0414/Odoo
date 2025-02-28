from odoo import fields, models

class ProductBundling(models.Model):
    _name = 'product.bundling'
    _description = 'A user-friendly interface for sales teams to build and price custom bundles quickly'
    
    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
