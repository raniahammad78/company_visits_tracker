# -*- coding: utf-8 -*-
from odoo import models, fields, api

class VisitDocument(models.Model):
    _name = 'visit.document'
    _description = 'Visit Document'

    name = fields.Char(string='Name', required=True)
    folder_id = fields.Many2one('visit.folder', string='Folder', ondelete='cascade')
    datas = fields.Binary(string='File', attachment=True)
    mimetype = fields.Char(string='Mime Type')
    visit_id = fields.Many2one('company.visit', string='Related Visit')