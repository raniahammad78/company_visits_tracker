# -*- coding: utf-8 -*-
from odoo import models, fields


class VisitDocument(models.Model):
    """
    Model: Visit Document
    ---------------------
    This model represents documents related to company visits.
    """

    _name = 'visit.document'
    _description = 'Visit Document'

    # ---------------------------------------------------------
    # Basic Information
    # ---------------------------------------------------------
    name = fields.Char(string='Name', required=True)

    # ---------------------------------------------------------
    # File Storage
    # ---------------------------------------------------------
    folder_id = fields.Many2one(
        'visit.folder',
        string='Folder',
        ondelete='cascade'
    )

    datas = fields.Binary(string='File', attachment=True)
    mimetype = fields.Char(string='Mime Type')

    # ---------------------------------------------------------
    # Visit Relations
    # ---------------------------------------------------------
    visit_id = fields.Many2one(
        'company.visit',
        string='Related Visit',
        ondelete='cascade'
    )

    not_contracted_visit_id = fields.Many2one(
        'not.contracted.visit',
        string='Related Non-Contracted Visit',
        ondelete='cascade'
    )

    # ---------------------------------------------------------
    # Signature Request Relation (FIXED)
    # ---------------------------------------------------------
    signature_request_id = fields.Many2one(
        'sign.request',  # <--- CHANGED FROM 'visit.signature.request' TO 'sign.request'
        string='Related Signature Request',
        help="Connects this document to the signature request."
    )
