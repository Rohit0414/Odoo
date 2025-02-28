from odoo import fields, models, api

class StudentSchedule(models.Model):
    _name='student.schedule'
    _description='Student Class Schedule'
    
    student_id=fields.Many2many('student.management', string="student", required=True)
    class_date=fields.Date(string="Class Date", required=True)
    start_time=fields.Float(string="Start Time", required=True)
    end_time=fields.Float(string="End Time", required=True)
    subject=fields.Char(string="Subject", required=True)