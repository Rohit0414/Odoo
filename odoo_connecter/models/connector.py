import requests
from odoo import models, fields, api

class ExternalAPIConnector(models.Model):
    _name = "external.api.connector"
    _description = "External API Connector"

    name = fields.Char(string="Connector Name", required=True)
    api_url = fields.Char(string="API URL", required=True)
    api_key = fields.Char(string="API Key", required=True)
    
    def fetch_data(self):
        """Fetch data from the external API"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = requests.get(self.api_url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "Failed to fetch data"}
