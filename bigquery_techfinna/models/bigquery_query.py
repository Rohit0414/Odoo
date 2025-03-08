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
        Exports data from the selected Odoo table (with selected columns and condition filtering)
        to a BigQuery table named after self.name.
        
        Behavior:
         - Full Sync (first run, when last_sync is not set): exports all records and performs deletions in BigQuery for rows not in source.
         - Incremental Sync (subsequent runs): queries records with write_date or create_date greater than last_sync
           and omits the deletion clause in the MERGE operation.
        
        After a successful run, the last_sync timestamp is updated.
        """
        self = obj
        client = self.get_bigquery_client()
        project_id = client.project
        
        # Build the list of columns to export (ensure 'id' is included as primary key)
        selected_columns = self.column_ids.mapped('name')
        if 'id' not in selected_columns:
            selected_columns = ['id'] + selected_columns

        base_query = f"SELECT {', '.join(selected_columns)} FROM {self.table_name}"
        params = []
        conditions = []

        # For incremental sync: filter records changed since last_sync.
        if self.last_sync:
            conditions.append("(write_date > %s OR create_date > %s)")
            params.extend([self.last_sync, self.last_sync])
        
        _logger.info(self.last_sync)
        # Process domain_filter if provided
        if self.domain_filter:
            try:
                domain_expr = ast.literal_eval(self.domain_filter)
                _logger.info("Domain filter: %s", domain_expr)
                # Try to get the model from table_name (convert table name to model name format)
                model = self.env[self.table_name.replace('_','.')]
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
            
        _logger.info("Executing query: %s with params: %s", base_query, params)
        self.env.cr.execute(base_query, tuple(params))
        data = self.env.cr.dictfetchall()
        if not data:
            _logger.info("No data found for export after applying filters.")
            return
        
        df = pd.DataFrame(data)
    
        datetime_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
        for col in datetime_cols:
            df[col] = df[col].apply(lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.%f") if pd.notnull(x) else None)
        
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
        
        _logger.info(f"Selected columns: {selected_columns}")
        _logger.info(f"DataFrame dtypes: {df.dtypes}")
       
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

        schema = [
            bigquery.SchemaField(col, infer_bq_field_type(df[col].dtype, col))
            for col in selected_columns
        ]

        ICP = self.env['ir.config_parameter'].sudo()
        dataset_id = ICP.get_param('bigquery.dataset_id')
        if not dataset_id:
            _logger.error("BigQuery dataset ID is not set.")
            raise ValueError("BigQuery dataset ID is not set in the system parameters.")
        
        target_table_id = f"{project_id}.{dataset_id}.{self.name}"
        temp_table_id = f"{project_id}.{dataset_id}._temp_{self.name}"
        try:
            client.delete_table(temp_table_id, not_found_ok=True)
        except Exception as e:
            _logger.error(f"Error deleting temporary table {temp_table_id}: {e}")
            raise

        load_job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        load_job = client.load_table_from_dataframe(df, temp_table_id, job_config=load_job_config)
        load_job.result()

        try:
            target_table = client.get_table(target_table_id)
        except NotFound:
            table = bigquery.Table(target_table_id, schema=schema)
            target_table = client.create_table(table)
            _logger.info(f"Created new table {target_table_id} in BigQuery.")

        on_clause = "T.id = S.id"
        non_key_columns = [col for col in selected_columns if col != 'id']
        set_clause = ", ".join([f"T.{col} = S.{col}" for col in non_key_columns])
        insert_columns = ", ".join(selected_columns)
        insert_values = ", ".join([f"S.{col}" for col in selected_columns])

        # Build the MERGE SQL:
        # For full sync (when last_sync is not set) include deletion clause.
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
        
        query_job = client.query(merge_sql)
        query_job.result()
        _logger.info(f"Data sync completed for table {target_table_id}.")

        client.delete_table(temp_table_id, not_found_ok=True)

        # Update sync marker after successful sync
        self.write({'last_sync': fields.Datetime.now()})
        _logger.info(f"Sync marker updated for query '{self.name}'.")

    @api.model
    def auto_sync_queries(self):
        """
        Finds all queries with auto_sync enabled and runs their export.
        This method is intended to be called from an ir.cron scheduled action.
        """
        auto_sync_queries = self.search([('auto_sync', '=', True)])
        for query in auto_sync_queries:
            try:
                query.run_query()
            except Exception as e:
                _logger.error(f"Auto-sync error for query '{query.name}': {e}")

    @api.model
    def debug_auto_sync(self, *args, **kwargs):
        if not self.id:
            _logger.error("Record is not saved; please save the record first.")
            return False
        _logger.info("DEBUG: debug_auto_sync() called for query: %s, table_name: %s", self.name, self.table_name)
        if not self.table_name:
            _logger.error("No table selected for export.")
            return False
        self.run_query()
        return True
