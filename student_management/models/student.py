from odoo import fields, models, api

class Students(models.Model):
    _name='student.management'
    _description='student information'
    
    name=fields.Char(string="Student Name", required=True)
    enrollment_date=fields.Date(string="Enrollment Date", required=True)
    contact_email=fields.Char(string="Email")
    course_ids=fields.Many2many('course.management', string="Courses")
    
    