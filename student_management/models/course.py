from odoo import models, fields

class CourseManagement(models.Model):
    _name = 'course.management'
    _description = 'Course Information'

    name = fields.Char(string="Course Name", required=True)
    description = fields.Text(string="Course Description")
