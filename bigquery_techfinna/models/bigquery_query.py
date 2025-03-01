# bigquery_query.py
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class BigQueryQuery(models.Model):
    _name = 'bigquery.techfinna.query'
    _description = 'BigQuery Query Builder'

    name = fields.Char(string="Query Name", required=True)
    
    table_name = fields.Selection(
        selection='_get_table_options',
        string="Table",
        required=True
    )

    column_ids = fields.Many2many(
        'bigquery.techfinna.column',
        'bigquery_query_column_rel',
        'query_id',
        'column_id',
        string="Columns"
    )

    condition_column = fields.Many2one(
        'bigquery.techfinna.column',
        string="Condition Column",
        domain="[('id', 'in', column_ids)]"
    )
    condition_value = fields.Char(string="Condition Value")

    @api.model
    def _get_table_options(self):
        self.env.cr.execute("SELECT relname FROM pg_stat_user_tables ORDER BY relname")
        tables = self.env.cr.fetchall()
        return [(t[0], t[0]) for t in tables]

    @api.onchange('table_name')
    def _onchange_table_name(self):
        if self.table_name:
            self.env.cr.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (self.table_name,))
            columns_data = self.env.cr.fetchall()

            column_ids = []
            for col_tuple in columns_data:
                col_name = col_tuple[0]
                existing = self.env['bigquery.techfinna.column'].search([('name', '=', col_name)], limit=1)
                if not existing:
                    existing = self.env['bigquery.techfinna.column'].create({'name': col_name})
                column_ids.append(existing.id)

            self.column_ids = [(6, 0, column_ids)]
        else:
            self.column_ids = [(5, 0, 0)]

    def run_query(self):
        """Method triggered by the 'Run Query' button in the XML view."""
        _logger.info("Run Query button clicked for record: %s", self.name)
        # TODO: Add your logic to run the query
        # e.g., building a SQL query or calling your BigQuery client
        return True
