import logging
from odoo import models, fields, api
from google.cloud.exceptions import NotFound
import json
from google.cloud import bigquery
import pandas as pd
from itertools import groupby
from google.oauth2 import service_account
import ast

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

    
    auto_sync = fields.Boolean(string="Auto Sync", default=False)

   
    last_sync = fields.Datetime(string="Last Sync Timestamp")

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
        """ Exports data of the selected table to BigQuery. """
        model_name = self.table_name
        if not model_name:
            _logger.error("No table selected for export.")
            return

        try:
            self.export_data_to_bigquery(obj=self)
            _logger.info(f"Data export to BigQuery initiated for query: {self.name}")
        except Exception as e:
            _logger.error(f"Error during export to BigQuery: {str(e)}")
            raise
        pass
         
    def get_bigquery_client(self):
        ICP = self.env['ir.config_parameter'].sudo()
        credentials_json = ICP.get_param('bigquery.credentials_json')
        if not credentials_json:
            _logger.error("BigQuery credentials are not set.")
            raise ValueError("BigQuery credentials are not set in the system parameters.")

        try:
            credentials_info = json.loads(credentials_json)
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON format for BigQuery credentials: {e}")
            raise

        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        project_id = ICP.get_param('bigquery.project_id')
        return bigquery.Client(project=project_id, credentials=credentials)

    @api.model
    def export_data_to_bigquery(self, obj, batch_size=60000):
        """
        Exports data from the selected Odoo table to BigQuery in batches.
        It loads the data in chunks into a temporary table and then merges it with
        the target table. For full sync (when last_sync is not set), rows in the
        target table that are not in the export will be deleted.
        """
        self = obj
        client = self.get_bigquery_client()
        project_id = client.project

        # Build the list of columns to export (ensure 'id' is included as primary key)
        selected_columns = self.column_ids.mapped('name')
        if 'id' not in selected_columns:
            selected_columns = ['id'] + selected_columns

        # Build the base query with optional filtering.
        base_query = f"SELECT {', '.join(selected_columns)} FROM {self.table_name}"
        params = []
        conditions = []

        # Incremental sync: only export records changed since last_sync.
        if self.last_sync:
            conditions.append("(write_date > %s OR create_date > %s)")
            params.extend([self.last_sync, self.last_sync])

        # Process domain_filter if provided.
        if self.domain_filter:
            try:
                domain_expr = ast.literal_eval(self.domain_filter)
                model = self.env[self.table_name.replace('_', '.')]
                matching_ids = model.search(domain_expr).ids
                if matching_ids:
                    conditions.append("id IN %s")
                    params.append(tuple(matching_ids))
                else:
                    _logger.info("No matching records found for the domain filter.")
                    return
            except Exception as e:
                _logger.error(f"Error parsing domain filter: {e}")
                return

        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        _logger.info("Base query: %s with params: %s", base_query, params)

        # Prepare BigQuery schema based on DataFrame dtypes.
        def infer_bq_field_type(dtype, col_name):
            if col_name == "id":
                return "INTEGER"
            elif pd.api.types.is_integer_dtype(dtype):
                return "INTEGER"
            elif pd.api.types.is_float_dtype(dtype):
                return "FLOAT"
            elif pd.api.types.is_bool_dtype(dtype):
                return "BOOLEAN"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                return "TIMESTAMP"
            else:
                return "STRING"

        # Retrieve dataset and target table IDs from system parameters.
        ICP = self.env['ir.config_parameter'].sudo()
        dataset_id = ICP.get_param('bigquery.dataset_id')
        if not dataset_id:
            _logger.error("BigQuery dataset ID is not set.")
            raise ValueError("BigQuery dataset ID is not set in the system parameters.")

        target_table_id = f"{project_id}.{dataset_id}.{self.name}"
        temp_table_id = f"{project_id}.{dataset_id}._temp_{self.name}"

        # Ensure the temporary table does not exist.
        try:
            client.delete_table(temp_table_id, not_found_ok=True)
        except Exception as e:
            _logger.error(f"Error deleting temporary table {temp_table_id}: {e}")
            raise

        offset = 0
        first_chunk = True
        total_rows = 0
        schema = None  # Will be set after processing the first chunk.

        while True:
            # Append pagination clause.
            paginated_query = f"{base_query} LIMIT {batch_size} OFFSET {offset}"
            _logger.info("Executing paginated query: %s", paginated_query)
            self.env.cr.execute(paginated_query, tuple(params))
            data_chunk = self.env.cr.dictfetchall()
            if not data_chunk:
                break

            df = pd.DataFrame(data_chunk)
            total_rows += len(df)
            _logger.info("Fetched %s rows (offset %s)", len(df), offset)

            # Process datetime columns.
            datetime_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
            for col in datetime_cols:
                df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.%f") if pd.notnull(x) else None)

            # Convert dict or list columns to JSON strings.
            for col in df.columns:
                if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                    df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

            # Set up schema on the first chunk.
            if schema is None:
                schema = [
                    bigquery.SchemaField(col, infer_bq_field_type(df[col].dtype, col))
                    for col in selected_columns
                ]

            # Determine the write disposition: first chunk truncates, others append.
            write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE if first_chunk else bigquery.WriteDisposition.WRITE_APPEND
            first_chunk = False

            load_job_config = bigquery.LoadJobConfig(
                schema=schema,
                write_disposition=write_disposition
            )

            _logger.info("Loading chunk into temporary table %s (rows: %s)", temp_table_id, len(df))
            load_job = client.load_table_from_dataframe(df, temp_table_id, job_config=load_job_config)
            load_job.result()  # Wait for the job to complete.
            offset += batch_size

        if total_rows == 0:
            _logger.info("No data found for export after applying filters.")
            return

        # Ensure target table exists; create it if not.
        try:
            target_table = client.get_table(target_table_id)
        except NotFound:
            table = bigquery.Table(target_table_id, schema=schema)
            target_table = client.create_table(table)
            _logger.info(f"Created new table {target_table_id} in BigQuery.")

        # Build the MERGE SQL.
        on_clause = "T.id = S.id"
        non_key_columns = [col for col in selected_columns if col != 'id']
        set_clause = ", ".join([f"T.{col} = S.{col}" for col in non_key_columns])
        insert_columns = ", ".join(selected_columns)
        insert_values = ", ".join([f"S.{col}" for col in selected_columns])

        merge_sql = f"""
            MERGE `{target_table_id}` T
            USING `{temp_table_id}` S
            ON {on_clause}
            WHEN MATCHED THEN 
            UPDATE SET {set_clause}
            WHEN NOT MATCHED THEN 
            INSERT ({insert_columns}) VALUES ({insert_values})
        """
        if not self.last_sync:
            merge_sql += """                        
            WHEN NOT MATCHED BY SOURCE THEN 
            DELETE
            """
        else:
            _logger.info("Incremental sync in effect; deletion clause skipped (deletions are not processed).")

        _logger.info("Executing MERGE operation on target table %s", target_table_id)
        query_job = client.query(merge_sql)
        query_job.result()
        _logger.info(f"Data sync completed for table {target_table_id} (total rows processed: {total_rows}).")

        # Clean up the temporary table.
        client.delete_table(temp_table_id, not_found_ok=True)

        # Update sync marker after successful sync.
        self.write({'last_sync': fields.Datetime.now()})
        _logger.info(f"Sync marker updated for query '{self.name}'.")

