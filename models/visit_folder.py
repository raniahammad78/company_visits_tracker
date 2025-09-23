# -*- coding: utf-8 -*-
from odoo import models, fields, api

class VisitFolder(models.Model):
    _name = 'visit.folder'
    _description = 'Visit Document Folder'

    name = fields.Char(string='Folder Name', required=True)
    parent_id = fields.Many2one('visit.folder', string='Parent Folder', ondelete='cascade')
    child_folder_ids = fields.One2many('visit.folder', 'parent_id', string='Sub-folders')
    document_ids = fields.One2many('visit.document', 'folder_id', string='Documents')
    visit_ids = fields.One2many('company.visit', 'folder_id', string='Visits')
    document_count = fields.Integer(string='Report Count', compute='_compute_document_count')
    is_company_folder = fields.Boolean(string="Is Company Folder", compute='_compute_is_company_folder')
    is_not_contracted_folder = fields.Boolean(string="Is for Not Contracted Visits")

    @api.depends('parent_id')
    def _compute_is_company_folder(self):
        for folder in self:
            folder.is_company_folder = not bool(folder.parent_id)

    def _compute_document_count(self):
        for folder in self:
            count = len(folder.document_ids)
            for child in folder.child_folder_ids:
                count += child.document_count
            folder.document_count = count