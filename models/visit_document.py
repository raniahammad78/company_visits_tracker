# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class VisitDocument(models.Model):
    """
    Model: Visit Document
    ---------------------
    This model represents **documents related to company visits**. It serves as
    a bridge between the document management system and the visit workflows.

    Each document can be stored under a specific folder and linked to:
      - A contracted visit `company.visit`)
      - A non-contracted visit `not.contracted.visit`)
      - A custom signature request `sign.request`)

    This model allows the system to manage, store, and access all visit-related
    files (reports, signed PDFs, etc.) in a structured way.
    """

    _name = 'visit.document'
    _description = 'Visit Document'

    # ---------------------------------------------------------
    # Basic Information
    # ---------------------------------------------------------

    name = fields.Char(
        string='Name',
        required=True,
        help="The display name of the document (e.g., 'January Visit Report.pdf')."
    )

    # ---------------------------------------------------------
    # File Storage
    # ---------------------------------------------------------

    folder_id = fields.Many2one(
        'visit.folder',
        string='Folder',
        ondelete='cascade',
        help="Specifies the folder where this document is stored. "
             "If the folder is deleted, all related documents are also removed."
    )

    datas = fields.Binary(
        string='File',
        attachment=True,
        help="Binary field that holds the actual file content in base64 format."
    )

    mimetype = fields.Char(
        string='Mime Type',
        help="Indicates the document's file type (e.g., 'application/pdf', 'image/png')."
    )

    # ---------------------------------------------------------
    # Visit Relations
    # ---------------------------------------------------------

    visit_id = fields.Many2one(
        'company.visit',
        string='Related Visit',
        help="Links this document to a specific contracted company visit.",
        ondelete='cascade'
    )

    not_contracted_visit_id = fields.Many2one(
        'not.contracted.visit',
        string='Related Non-Contracted Visit',
        help="Links this document to a non-contracted visit record."
    )

    # ---------------------------------------------------------
    # Signature Request Relation
    # ---------------------------------------------------------

    signature_request_id = fields.Many2one(
        'sign.request',
        string='Related Signature Request',
        help="Connects this document to a custom signature request record "
             "for managing signed documents or approval workflows."
    )

    # ---------------------------------------------------------
    # Auto-delete unsigned reports
    # ---------------------------------------------------------

    @api.model
    def create(self, vals):
        """Override create to delete unsigned version when signed document is created"""
        res = super(VisitDocument, self).create(vals)

        # Check if the created document is a signed version
        if res.name and 'Signed' in res.name:
            _logger.info(f"Signed document detected: {res.name}")

            # Extract the base name by removing "Signed" variations
            base_name = res.name
            base_name = base_name.replace('Signed Visit Report - ', 'Visit Report - ')
            base_name = base_name.replace('Signed ', '')
            base_name = base_name.replace(' - Signed', '')
            base_name = base_name.strip()

            _logger.info(f"Looking for unsigned document with base name: {base_name}")

            # Search for the unsigned version in the same folder
            # Try multiple search strategies
            search_domains = [
                # Exact match with base name
                [('folder_id', '=', res.folder_id.id), ('name', '=', base_name), ('id', '!=', res.id)],
                # Contains the visit reference (e.g., VST-001)
                [('folder_id', '=', res.folder_id.id),
                 ('name', 'ilike', res.name.split('-VST-')[-1].split('.')[0] if '-VST-' in res.name else ''),
                 ('name', 'not ilike', 'Signed'), ('id', '!=', res.id)],
                # Any document without "Signed" in the same folder (last resort)
                [('folder_id', '=', res.folder_id.id), ('name', 'not ilike', 'Signed'), ('id', '!=', res.id)]
            ]

            for domain in search_domains:
                unsigned_doc = self.search(domain, limit=1)
                if unsigned_doc:
                    _logger.info(f"Found and deleting unsigned document: {unsigned_doc.name} (replaced by {res.name})")
                    unsigned_doc.unlink()
                    break
            else:
                _logger.warning(f"No unsigned document found to delete for: {res.name}")

        return res

    def write(self, vals):
        """Override write to handle renaming to signed version"""
        # Store original names before update
        original_names = {doc.id: doc.name for doc in self}

        res = super(VisitDocument, self).write(vals)

        # Check if name was changed to include "Signed"
        if 'name' in vals:
            for document in self:
                original_name = original_names.get(document.id)
                # If document was renamed to signed version
                if original_name and 'Signed' not in original_name and 'Signed' in document.name:
                    _logger.info(f"Document renamed to signed version: {original_name} -> {document.name}")
                    # In this case, the unsigned version is this same document, just renamed
                    # So we don't need to delete anything

        return res

    @api.model
    def cleanup_unsigned_reports(self):
        """
        Scheduled action to clean up unsigned reports when signed version exists.
        This handles cases where unsigned reports existed before the auto-delete was implemented.
        """
        _logger.info("Starting cleanup of unsigned reports...")

        # Find all signed documents
        signed_docs = self.search([('name', 'ilike', 'Signed')])

        deleted_count = 0
        for signed_doc in signed_docs:
            # Extract visit reference (e.g., VST-001)
            if '-VST-' in signed_doc.name:
                visit_ref = signed_doc.name.split('-VST-')[1].split('.')[0]
                visit_ref = f'VST-{visit_ref}'

                # Find unsigned document with same visit reference
                unsigned_docs = self.search([
                    ('folder_id', '=', signed_doc.folder_id.id),
                    ('name', 'ilike', visit_ref),
                    ('name', 'not ilike', 'Signed'),
                    ('id', '!=', signed_doc.id)
                ])

                if unsigned_docs:
                    for unsigned_doc in unsigned_docs:
                        _logger.info(
                            f"Cleanup: Deleting unsigned document: {unsigned_doc.name} (signed version exists: {signed_doc.name})")
                        unsigned_doc.unlink()
                        deleted_count += 1

        _logger.info(f"Cleanup completed. Deleted {deleted_count} unsigned reports.")
        return deleted_count
