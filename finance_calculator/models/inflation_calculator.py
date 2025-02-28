from odoo import models, fields, api

class InflationCalculator(models.Model):
    _name = 'finance.inflation_calculator'
    _description = 'Inflation Calculator'

    initial_amount = fields.Float(string="Initial Amount", required=True)
    inflation_rate = fields.Float(string="Annual Inflation Rate (%)", required=True)
    years = fields.Integer(string="Years", required=True)
    future_value = fields.Float(string="Future Value", compute="_compute_future_value", store=True)

    @api.depends('initial_amount', 'inflation_rate', 'years')
    def _compute_future_value(self):
        for record in self:
            r = record.inflation_rate / 100
            record.future_value = record.initial_amount * ((1 + r) ** record.years)
