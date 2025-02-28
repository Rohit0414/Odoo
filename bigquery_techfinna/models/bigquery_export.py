from odoo import models, api, fields
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account
import json
import logging
from itertools import groupby
from google.cloud.exceptions import NotFound

_logger = logging.getLogger(__name__)


class BigQueryExport(models.Model):
    _name = 'bigquery.techfinna.export'
    _description = 'BigQuery Data Export'

    table_to_export = fields.Selection(selection='_get_table_options', string="Choose a Table")

    @api.model
    def _get_table_options(self):
        self.env.cr.execute("SELECT relname AS table FROM pg_stat_user_tables ORDER BY relname")
        tables = self.env.cr.fetchall()
        # ICP = self.env['ir.config_parameter'].sudo()
        # project_id = ICP.get_param('bigquery.project_id')
        # dataset_id = ICP.get_param('bigquery.dataset_id')
        # tabl = get_tables_in_dataset(project_id, dataset_id)
        # print(tabl)
        return [(table[0], table[0].replace('_', '.')) for table in tables]

    def action_export_data(self):
        
        """ Exports data of the selected table to BigQuery. """
        if not self.table_to_export:
            _logger.error("No table selected for export.")
            return

        # Convert the selected table name to the model name (if required)
        model_name = self.table_to_export.replace('_', '.')
        _logger.info("Total records:")
         # _logger.info(self.env[model_name].search_count([]))
        # Obtain the reference to the BigQuery export model
        bigquery_exporter = self.env['bigquery.techfinna.export']

        # Call the export function from the BigQuery export model
        try:
            bigquery_exporter.export_data_to_bigquery(model=model_name)
            _logger.info(f"Data export to BigQuery initiated for table: {model_name}")
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

    
    def get_schema_bq(self, table_name):
        key_func = lambda v: v['table_name']
        res = dict()
        schemas = self.env.cr.execute(f'''
                                                        SELECT 
                                                        column_name,data_type AS column_type,table_name 
                                                        FROM 
                                                        information_schema.columns 
                                                        WHERE 
                                                        table_schema = 'public' 
                                                        ORDER BY table_name
                                                        ''')
        schemas = self.env.cr.dictfetchall()
        for key, value in groupby(schemas, key_func):
            value = list(value)
            res[key.replace('_', '.')] = [{"column_name": obj["column_name"], "column_type": obj["column_type"]}
                                          for obj in value]
        schema = []
        print(len(res[table_name]))

        typeMapping = {
            'integer': bigquery.enums.SqlTypeNames.INTEGER,
            'timestamp without time zone':bigquery.enums.SqlTypeNames.DATETIME,
            'jsonb': bigquery.enums.SqlTypeNames.STRING,
            'double precision':bigquery.enums.SqlTypeNames. FLOAT,
            'character varying': bigquery.enums.SqlTypeNames.STRING,
            'boolean': bigquery.enums.SqlTypeNames.BOOLEAN,
            'date': bigquery.enums.SqlTypeNames.DATE,
            'numeric':bigquery.enums.SqlTypeNames.FLOAT,
            'text': bigquery.enums.SqlTypeNames.STRING,
            'bytea': bigquery.enums.SqlTypeNames.STRING
        }
        jsonColumns = []
        for i in res[table_name]:
            if i["column_type"] in typeMapping.keys():
                if i["column_type"] == 'jsonb':
                    jsonColumns.append(i["column_name"])
                schema.append(
                    bigquery.SchemaField(str(i["column_name"]), typeMapping[i["column_type"]]))

            else:
                schema.append(
                    bigquery.SchemaField(str(i["column_name"]), bigquery.enums.SqlTypeNames.STRING))
            # print(typeMapping[i["column_type"]])

            # schema.append(f'bigquery.SchemaField("{i["column_name"]}", bigquery.enums.SqlTypeNames.{i["column_type"]})')

        # print(schema)

        return schema,jsonColumns


    @api.model
    def export_data_to_bigquery(self, model, batch_size=60000):
        model_schema,jsonColumns=self.get_schema_bq(model)
        client = self.get_bigquery_client()
        dataset_id = self.env['ir.config_parameter'].sudo().get_param('bigquery.dataset_id')

        if not dataset_id:
            _logger.error("BigQuery dataset ID is not set.")
            raise ValueError("BigQuery dataset ID is not set in the system parameters.")

        # Construct the full table ID
        table_id = f"{dataset_id}.{model.replace('.', '_')}"

        # Check if the table exists in BigQuery
        try:
            existing_table = client.get_table(table_id)
            _logger.info(f"Table {table_id} already exists in BigQuery. Deleting the existing table.")
            client.delete_table(existing_table)  # Delete the existing table
        except NotFound:
            _logger.info(f"Table {table_id} does not exist in BigQuery. Proceeding with export.")

        # Example: Exporting a simple Odoo model data

        query = f'''
            SELECT *
            FROM {model.replace('.', '_')}
        '''
        self.env.cr.execute(query)
        
        # Fetching data in batches
        rows_fetched = 0
        while True:
            values = self.env.cr.dictfetchmany(size=batch_size)
            if not values:
                _logger.info('operation complete... no more values!')
                break  # No more rows to fetch
            rows_fetched += len(values)
            dataframe = pd.DataFrame(values)
            for n in jsonColumns:
                dataframe[n] = dataframe[n].apply(json.dumps)
            try:

                job_config = bigquery.LoadJobConfig(
                    schema=model_schema,
                )
                job = client.load_table_from_dataframe(dataframe, table_id, job_config=job_config)
                job.result()  # Wait for the job to complete
                _logger.info(f"Loaded {job.output_rows} rows into {table_id}.")
            except Exception as e:
                _logger.error(f"Error loading data to BigQuery: {e}")
                raise

        _logger.info(f"Total {rows_fetched} rows loaded into {table_id}.")
