import logging
import math
import json
import pandas as pd
import ast
import sqlalchemy

from odoo import models, fields, api, tools
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2 import service_account

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
    domain_filter = fields.Text(
        string="Domain Filter",
        help="Enter a valid Odoo domain expression, e.g., [('state','=','done'), ('amount_total','>',1000)]"
    )
    last_sync = fields.Datetime(string="Last Sync Timestamp")
    export_offset = fields.Integer(string="Export Offset", default=0)
    auto_sync = fields.Boolean(string="Auto Sync")

    @api.model
    def _get_table_options(self):
        self.env.cr.execute("SELECT relname AS table FROM pg_stat_user_tables ORDER BY relname")
        tables = self.env.cr.fetchall()
        return [(table[0], table[0]) for table in tables]

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
        if not self.table_name:
            _logger.error("No table selected for export for record %s.", self.id)
            return
        try:
            self.export_data_to_bigquery()
            self.write({'last_sync': fields.Datetime.now()})
            _logger.info("Data export completed for record: %s", self.name)
        except Exception as e:
            _logger.error("Error during export for record %s: %s", self.name, str(e))
            raise

    def get_bigquery_client(self):
        ICP = self.env['ir.config_parameter'].sudo()
        credentials_json = ICP.get_param('bigquery.credentials_json')
        if not credentials_json:
            _logger.error("BigQuery credentials are not set.")
            raise ValueError("BigQuery credentials are not set in system parameters.")

        try:
            credentials_info = json.loads(credentials_json)
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON format for BigQuery credentials: {e}")
            raise

        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        project_id = ICP.get_param('bigquery.project_id')
        return bigquery.Client(project=project_id, credentials=credentials)

    def export_data_to_bigquery(self, batch_size=10):
        client = self.get_bigquery_client()
        project_id = client.project
        ICP = self.env['ir.config_parameter'].sudo()
        dataset_id = ICP.get_param('bigquery.dataset_id')
        if not dataset_id:
            _logger.error("BigQuery dataset ID is not set.")
            raise ValueError("BigQuery dataset ID is not set in system parameters.")

        # Build the list of columns to export using column_ids.
        selected_columns = self.column_ids.mapped('name')
        if selected_columns:
            if 'id' not in selected_columns:
                selected_columns = ['id'] + selected_columns
            select_clause = ', '.join(selected_columns)
        else:
            select_clause = '*'

        base_query = f"SELECT {select_clause} FROM {self.table_name}"
        params = []
        conditions = []

        if self.last_sync:
            conditions.append("(write_date > %s OR create_date > %s)")
            params.extend([self.last_sync, self.last_sync])

        if self.domain_filter:
            try:
                domain_expr = ast.literal_eval(self.domain_filter)
                model_name = self.table_name.replace('_', '.')
                model = self.env[model_name]
                matching_ids = model.search(domain_expr).ids
                if matching_ids:
                    conditions.append("id IN %s")
                    params.append(tuple(matching_ids))
                else:
                    _logger.info("No matching records found for the domain filter.")
                    self._create_empty_table_in_bigquery(client, project_id, dataset_id)
                    return
            except Exception as e:
                _logger.error(f"Error parsing domain filter: {e}")
                return

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        # Count total records for logging/progress.
        count_query = f"SELECT COUNT(*) FROM ({base_query}) AS subquery"
        self.env.cr.execute(count_query, tuple(params))
        total_records = self.env.cr.fetchone()[0]
        _logger.info("Total records to export: %s", total_records)

        if total_records == 0:
            self._create_empty_table_in_bigquery(client, project_id, dataset_id)
            _logger.info("No records to export. Created/overwrote an empty table in BigQuery.")
            return

        # Create SQLAlchemy engine using Odoo configuration parameters.
        db_name = self.env.cr.dbname
        db_user = tools.config.get('dhimanrohit070@gmail.com')
        db_password = tools.config.get('odoo18', '')
        db_host = tools.config.get('db_host', 'localhost')
        db_port = tools.config.get('db_port', '5432')
        dsn = f"postgresql://{'dhimanrohit070@gmail.com'}:{'odoo18'}@{'localhost'}:{'8018'}/{'odoo'}"
        engine = sqlalchemy.create_engine(dsn)

        _logger.info("Fetching data using SQLAlchemy engine with chunksize=%s", batch_size)
        # Use pd.read_sql_query with chunksize; Pandas will internally loop over chunks
        df = pd.concat(
            pd.read_sql_query(base_query, engine, params=tuple(params), chunksize=batch_size)
        )
        rows_fetched = len(df)
        _logger.info("Fetched %s rows by concatenating chunks.", rows_fetched)

        self._transform_dataframe(df)

        target_table_id = f"{project_id}.{dataset_id}.{self.name}"
        load_job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE)
        _logger.info("Loading data into %s (rows: %s)", target_table_id, rows_fetched)
        load_job = client.load_table_from_dataframe(df, target_table_id, job_config=load_job_config)
        load_job.result()

        self.write({'export_offset': rows_fetched})
        _logger.info("Export finished. Processed %s rows total. Table: %s", rows_fetched, target_table_id)

    def _transform_dataframe(self, df):
        # Transform datetime columns to ISO format and convert dicts/lists to JSON strings.
        datetime_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
        for col in datetime_cols:
            df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.%f") if pd.notnull(x) else None)
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

    def _create_empty_table_in_bigquery(self, client, project_id, dataset_id):
        target_table_id = f"{project_id}.{dataset_id}.{self.name}"
        # Build the schema based on self.column_ids.
        selected_columns = self.column_ids.mapped('name')
        if not selected_columns:
            self.env.cr.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (self.table_name,))
            columns_data = self.env.cr.fetchall()
            selected_columns = [col[0] for col in columns_data]
        if 'id' not in selected_columns:
            selected_columns = ['id'] + selected_columns

        # Build explicit schema: defaulting all types to STRING (adjust types as needed)
        schema = [bigquery.SchemaField(col, "STRING") for col in selected_columns]
        empty_df = pd.DataFrame(columns=selected_columns)
        load_job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=schema
        )
        load_job = client.load_table_from_dataframe(empty_df, target_table_id, job_config=load_job_config)
        load_job.result()
        _logger.info("Created/overwrote an empty BigQuery table: %s", target_table_id)
