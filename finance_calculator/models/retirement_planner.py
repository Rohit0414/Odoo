from odoo import models, fields, api

class RetirementPlanner(models.Model):
    _name = 'finance.retirement_planner'
    _description = 'Retirement Planning Calculator'

    current_savings = fields.Float(string="Current Savings", required=True)
    annual_contribution = fields.Float(string="Annual Contribution", required=True)
    years_to_retirement = fields.Integer(string="Years to Retirement", required=True)
    expected_return = fields.Float(string="Expected Annual Return (%)", required=True)
    final_savings = fields.Float(string="Projected Savings at Retirement", compute="_compute_final_savings", store=True)

    @api.depends('current_savings', 'annual_contribution', 'years_to_retirement', 'expected_return')
    def _compute_final_savings(self):
        for record in self:
            r = record.expected_return / 100  # Convert percentage to decimal
            n = record.years_to_retirement
            
            if r == 0:
                # If the interest rate is 0, use a simple calculation
                total = record.current_savings + (record.annual_contribution * n)
            else:
                # Compound interest calculation
                total = record.current_savings * ((1 + r) ** n) + record.annual_contribution * (((1 + r) ** n - 1) / r)
            
            # Store the calculated total
            record.final_savings = total
