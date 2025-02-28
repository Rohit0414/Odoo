from odoo import fields, models, api


class StudentPerformance(models.Model):
    _name='student.performance'
    _description="Student Academic Performance"
    
    student_id=fields.Many2many('student.management', string="Student", required=True)
    subject=fields.Char(string="Subject", required=True)
    score=fields.Float(string="score", required=True)
    max_score=fields.Float(string="Max Score", required=True)
    grade=fields.Char(string="Grade")