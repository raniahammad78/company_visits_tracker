# -*- coding: utf-8 -*-
from odoo import models, fields


class VisitDocument(models.Model):
    """
    Model: Visit Document
    ---------------------
    This model represents **documents related to company visits**. It serves as
    a bridge between the document management system and the visit workflows.

    Each document can be stored under a specific folder and linked to:
      - A contracted visit (`company.visit`)
      - A non-contracted visit (`not.contracted.visit`)
      - A custom signature request (`visit.signature.request`)

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
        help="Links this document to a specific contracted company visit."
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
        'visit.signature.request',
        string='Related Signature Request',
        help="Connects this document to a custom signature request record "
             "for managing signed documents or approval workflows."
    )
