# -*- coding: utf-8 -*-
from odoo import models, fields, api


class VisitFolder(models.Model):
    _name = 'visit.folder'
    _description = 'Visit Document Folder'

    name = fields.Char(string='Folder Name', required=True)
    parent_id = fields.Many2one('visit.folder', string='Parent Folder', ondelete='cascade')

    child_folder_ids = fields.One2many('visit.folder', 'parent_id', string='Sub-folders')
    document_ids = fields.One2many('visit.document', 'folder_id', string='Documents')

    # --- NEW FIELD TO FIX THE ERROR ---
    # This directly links the folder to the visit records inside it.
    visit_ids = fields.One2many('company.visit', 'folder_id', string='Visits')

    document_count = fields.Integer(string='Report Count', compute='_compute_document_count')
    is_company_folder = fields.Boolean(string="Is Company Folder", compute='_compute_is_company_folder')

    @api.depends('parent_id')
    def _compute_is_company_folder(self):
        for folder in self:
            folder.is_company_folder = not bool(folder.parent_id)

    def _compute_document_count(self):
        for folder in self:
            # Recursively count documents in this folder and all sub-folders
            count = len(folder.document_ids)
            for child in folder.child_folder_ids:
                count += child.document_count
            folder.document_count = count

    def action_open_subfolder_wizard(self):
        # This action is now handled by the form view's notebook structure
        # and is kept for potential future use or alternative UI designs.
        pass

