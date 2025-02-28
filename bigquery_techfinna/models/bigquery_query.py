from odoo import models, fields, api
import json
from google.cloud import bigquery
from google.oauth2 import service_account
import logging

_logger = logging.getLogger(__name__)

class BigQueryQuery(models.Model):
    _name = 'bigquery.techfinna.query'
    _description = 'BigQuery Query Builder'

    name = fields.Char(string="Query Name", required=True)
    table_name = fields.Selection(selection='_get_table_options', string="Table", required=True)
    selected_columns = fields.Char(string="Selected Columns")
    condition_column = fields.Char(string="Condition Column")
    condition_value = fields.Char(string="Condition")

    @api.model
    def _get_table_options(self):
        """Fetch available tables from BigQuery"""
        client = self.get_bigquery_client()
        dataset_id = self.env['ir.config_parameter'].sudo().get_param('bigquery.dataset_id')
        tables = client.list_tables(dataset_id)
        return [(table.table_id, table.table_id) for table in tables]

    def get_bigquery_client(self):
        """Authenticate with BigQuery"""
        ICP = self.env['ir.config_parameter'].sudo()
        credentials_json = ICP.get_param('bigquery.credentials_json')
        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        project_id = ICP.get_param('bigquery.project_id')
        return bigquery.Client(project=project_id, credentials=credentials)

    def run_query(self):
        """Execute the query and return results"""
        client = self.get_bigquery_client()
        dataset_id = self.env['ir.config_parameter'].sudo().get_param('bigquery.dataset_id')
        table_id = f"{dataset_id}.{self.table_name}"

        # Construct the SQL query
        query = f"SELECT {self.selected_columns} FROM `{table_id}`"
        if self.condition_column and self.condition_value:
            query += f" WHERE {self.condition_column} = '{self.condition_value}'"

        _logger.info(f"Running BigQuery: {query}")
        job = client.query(query)
        result = job.result().to_dataframe()
        return result.to_dict(orient='records')  # Convert to Odoo-compatible format
