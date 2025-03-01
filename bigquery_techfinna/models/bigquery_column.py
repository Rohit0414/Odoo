# bigquery_column.py
from odoo import models, fields

class BigQueryColumn(models.Model):
    _name = 'bigquery.techfinna.column'
    _description = 'BigQuery Table Column'

    name = fields.Char(string="Column Name", required=True)
