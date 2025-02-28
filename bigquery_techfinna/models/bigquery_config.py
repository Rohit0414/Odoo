from odoo import fields, models, api
import logging
from google.cloud import bigquery


_logger = logging.getLogger(__name__)
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bigquery_project_id = fields.Char(string='BigQuery Project ID', config_parameter='bigquery.project_id')
    bigquery_dataset_id = fields.Char(string='BigQuery Dataset ID', config_parameter='bigquery.dataset_id')
    bigquery_credentials_json = fields.Char(string='BigQuery Credentials JSON', config_parameter='bigquery.credentials_json')

     # Field for table selection
    table_to_export = fields.Selection(selection='_get_table_options', string="Choose a Table")




    @api.model
    def _get_table_options(self):
        self.env.cr.execute("SELECT relname AS table FROM pg_stat_user_tables ORDER BY relname")
        tables = self.env.cr.fetchall()
        return [(table[0], table[0].replace('_', '.')) for table in tables]
    
    @api.onchange('table_to_export')
    def _onchange_table_to_export(self):
        # Automatically save the selected table name
        if self.table_to_export:
            self.env['ir.config_parameter'].sudo().set_param('bigquery.table_to_export', self.table_to_export)




    def action_export_data_to_bigquery(self):
        table_name = self.env['ir.config_parameter'].sudo().get_param('bigquery.table_to_export')
        if not table_name:
            _logger.error("No table selected for export.")
            return

        selected_table = table_name.replace('.', '_')
        bigquery_exporter = self.env['bigquery.techfinna.export']
        bigquery_exporter.export_data_to_bigquery(model=selected_table)

        _logger.info(f"Data export initiated for table: {self.table_to_export}")


