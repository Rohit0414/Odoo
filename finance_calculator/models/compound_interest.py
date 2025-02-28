from odoo import models, fields, api

class CompoundInterestCalculator(models.Model):
    _name = 'finance.compound.interest'
    _description = 'Compound Interest & SIP Calculator'

    principal = fields.Float(string="Principal Amount", required=True)
    rate = fields.Float(string="Annual Interest Rate (%)", required=True)
    years = fields.Integer(string="Number of Years", required=True)
    times_compounded = fields.Integer(string="Times Compounded per Year", required=True, default=1)
    maturity_amount = fields.Float(string="Maturity Amount", compute="_compute_maturity", store=True)

    @api.depends('principal', 'rate', 'years', 'times_compounded')
    def _compute_maturity(self):
        for record in self:
            r = record.rate / 100
            n = record.times_compounded
            t = record.years
            record.maturity_amount = record.principal * (1 + (r / n)) ** (n * t)
