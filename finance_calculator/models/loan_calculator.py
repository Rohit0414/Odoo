from odoo import models, fields, api

class LoanCalculator(models.Model):
    _name = 'finance.loan_calculator'
    _description = 'Loan EMI Calculator'

    loan_amount = fields.Float(string="Loan Amount", required=True)
    interest_rate = fields.Float(string="Annual Interest Rate (%)", required=True)
    tenure_years = fields.Integer(string="Loan Tenure (Years)", required=True)
    emi = fields.Float(string="EMI Amount", compute="_compute_emi", store=True)

    @api.depends('loan_amount', 'interest_rate', 'tenure_years')
    def _compute_emi(self):
        for record in self:
            if record.loan_amount and record.interest_rate and record.tenure_years:
                r = (record.interest_rate / 12) / 100
                n = record.tenure_years * 12
                if r > 0:
                    emi = (record.loan_amount * r * (1 + r) ** n) / ((1 + r) ** n - 1)
                else:
                    emi = record.loan_amount / n
                record.emi = emi
