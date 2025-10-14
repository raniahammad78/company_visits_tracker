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

    document_count = fields.Integer(
        string='Report Count',
        compute='_compute_document_count',
        store=True
    )
    is_company_folder = fields.Boolean(
        string="Is Company Folder",
        compute='_compute_is_company_folder'
    )
    is_not_contracted_folder = fields.Boolean(
        string="Is for Not Contracted Visits"
    )

    # CORRECTED FIELD DEFINITION: This must be Many2many for a computed list of records
    all_child_document_ids = fields.Many2many(
        'visit.document',
        string="All Child Documents",
        compute='_compute_all_child_document_ids'
    )

    @api.depends('parent_id')
    def _compute_is_company_folder(self):
        for folder in self:
            folder.is_company_folder = not bool(folder.parent_id)

    @api.depends('document_ids', 'child_folder_ids.document_count')
    def _compute_document_count(self):
        for folder in self:
            count = len(folder.document_ids)
            count += sum(child.document_count for child in folder.child_folder_ids)
            folder.document_count = count

    def _compute_all_child_document_ids(self):
        """
        This method gathers all documents from this folder and its sub-folders.
        """
        for folder in self:
            all_child_folders = self.env['visit.folder'].search([('id', 'child_of', folder.id)])
            docs = self.env['visit.document'].search([('folder_id', 'in', all_child_folders.ids)])
            folder.all_child_document_ids = docs
