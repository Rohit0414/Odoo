import logging
import math
import json
import pandas as pd
import ast

from odoo import models, fields, api
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
    auto_sync=fields.Boolean(string="Auto Sync")

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
        """
        Row-level action to export data for the current record to BigQuery.
        """
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

    def export_data_to_bigquery(self, batch_size=1):
        """
        Exports data from the specified Odoo table to BigQuery in batches.
        If no records are found, an empty table is created/overwritten in BigQuery.
        
        -----------------------------------------------------------------------------
        Why Some People Use SELECT COUNT(*)
          - Progress Tracking:
              If you want to show a progress bar or calculate how many batches you'll have in total,
              you need the row count so you can compute how many times you'll loop.
          - Preemptive Stopping/Resource Planning:
              Sometimes you might want to stop after a certain number of batches or estimate
              how long the job will run. A row count helps with that.
          - Validation or Logging:
              In some cases, it's helpful to log, "We're about to export 10,000 rows,
              in batches of 500," just for clarity.
        
        When You Don't Need It
          - If you're happy to keep fetching until empty (i.e., the query returns no more rows),
            and not worry about total batch counts or progress bars,
            then you can skip the SELECT COUNT(*) step. Your loop will stop automatically
            when there's no more data to fetch.
        -----------------------------------------------------------------------------
        """
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
            # If no columns are specified, export all columns.
            select_clause = '*'

        # Build base query using selected columns.
        base_query = f"SELECT {select_clause} FROM {self.table_name}"
        params = []
        conditions = []

        if self.last_sync:
            conditions.append("(write_date > %s OR create_date > %s)")
            params.extend([self.last_sync, self.last_sync])

        if self.domain_filter:
            try:
                domain_expr = ast.literal_eval(self.domain_filter)
                # Adjust model name if necessary
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

        # If no records are found, create an empty table in BigQuery.
        if total_records == 0:
            self._create_empty_table_in_bigquery(client, project_id, dataset_id)
            _logger.info("No records to export. Created/overwrote an empty table in BigQuery.")
            return

        target_table_id = f"{project_id}.{dataset_id}.{self.name}"

        # Process records in batches.
        offset = self.export_offset or 0
        total_rows_processed = 0
        batch_index = 0
        first_chunk = True

        while True:
            paginated_query = f"{base_query} LIMIT {batch_size} OFFSET {offset}"
            _logger.info("Executing paginated query: %s", paginated_query)
            self.env.cr.execute(paginated_query, tuple(params))
            data_chunk = self.env.cr.dictfetchall()

            if not data_chunk:
                _logger.info("No more data to export at offset %s.", offset)
                break

            df = pd.DataFrame(data_chunk)
            rows_fetched = len(df)
            total_rows_processed += rows_fetched
            batch_index += 1
            _logger.info("Fetched %s rows in batch %s (offset %s)", rows_fetched, batch_index, offset)

            self._transform_dataframe(df)

            # Set write disposition: first batch overwrites, subsequent batches append.
            if first_chunk:
                write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
                first_chunk = False
            else:
                write_disposition = bigquery.WriteDisposition.WRITE_APPEND

            load_job_config = bigquery.LoadJobConfig(write_disposition=write_disposition)

            _logger.info("Loading batch %s into %s (rows: %s)", batch_index, target_table_id, rows_fetched)
            load_job = client.load_table_from_dataframe(df, target_table_id, job_config=load_job_config)
            load_job.result()

            offset += batch_size

        self.write({'export_offset': offset})
        _logger.info("Export finished. Processed %s rows total. Table: %s", total_rows_processed, target_table_id)

    def _transform_dataframe(self, df):
        """
        Transforms DataFrame columns for BigQuery.
          - Converts datetime columns to ISO format.
          - Converts dictionary or list columns to JSON strings.
        """
        datetime_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
        for col in datetime_cols:
            df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.%f") if pd.notnull(x) else None)

        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

    def _create_empty_table_in_bigquery(self, client, project_id, dataset_id):
        """
        Creates or overwrites the target BigQuery table with an empty table if no records exist.
        An explicit schema is provided so that even an empty DataFrame can define the table structure.
        """
        target_table_id = f"{project_id}.{dataset_id}.{self.name}"
        
        # Build the schema based on self.column_ids
        selected_columns = self.column_ids.mapped('name')
        if not selected_columns:
            # If no columns in column_ids, retrieve column names from the table in PostgreSQL.
            self.env.cr.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (self.table_name,))
            columns_data = self.env.cr.fetchall()
            selected_columns = [col[0] for col in columns_data]
        
        # Ensure 'id' is included
        if 'id' not in selected_columns:
            selected_columns = ['id'] + selected_columns

        # Build explicit schema: defaulting all types to STRING (adjust types as needed)
        schema = [bigquery.SchemaField(col, "STRING") for col in selected_columns]

        # Create an empty DataFrame with the proper columns
        empty_df = pd.DataFrame(columns=selected_columns)
        
        load_job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            schema=schema
        )
        load_job = client.load_table_from_dataframe(empty_df, target_table_id, job_config=load_job_config)
        load_job.result()
        _logger.info("Created/overwrote an empty BigQuery table: %s", target_table_id)
