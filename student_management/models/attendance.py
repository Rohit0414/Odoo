from odoo import fields, models, api


class StudentAttendance(models.Model):
    _name='student.attendance'
    _description='Student Attendance Record'
    
    student_id=fields.Many2many('student.management', string="Student", required=True)
    date=fields.Date(string="Date", required=True)
    status=fields.Selection([
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('excused', 'Excused')
    ], string="Status", default='present')
    notes=fields.Text(string="Notes")