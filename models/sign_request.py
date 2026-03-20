# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class SignSendRequest(models.TransientModel):
    """
    Inherit the Odoo Sign Wizard to catch the visit IDs
    and pass them to the final sign.request.
    """
    _inherit = 'sign.send.request'

    company_visit_id = fields.Many2one('company.visit', string='Company Visit')
    not_contracted_visit_id = fields.Many2one('not.contracted.visit', string='Non-Contracted Visit')

    def create_request(self):
        # 1. Let Odoo create the sign.request record(s) normally
        sign_requests = super(SignSendRequest, self).create_request()

        # 2. Attach our custom visit IDs to the newly created request
        for wizard in self:
            if wizard.company_visit_id:
                sign_requests.write({'company_visit_id': wizard.company_visit_id.id})
            if wizard.not_contracted_visit_id:
                sign_requests.write({'not_contracted_visit_id': wizard.not_contracted_visit_id.id})

        return sign_requests


class SignRequest(models.Model):
    """
    Inherit the actual Signature Request to trigger automation
    when the document is fully signed.
    """
    _inherit = 'sign.request'

    company_visit_id = fields.Many2one(
        'company.visit',
        string='Related Contracted Visit',
        ondelete='cascade',
        help="Links this signature request to a contracted company visit record."
    )

    not_contracted_visit_id = fields.Many2one(
        'not.contracted.visit',
        string='Related Non-Contracted Visit',
        ondelete='cascade',
        help="Links this signature request to a non-contracted visit record."
    )

    def write(self, vals):
        res = super(SignRequest, self).write(vals)
        # Automate saving the document to the folder when signed
        if vals.get('state') == 'signed':
            for request in self.sudo():
                # Logic for Contracted Visits
                if request.company_visit_id:
                    _logger.info(f"=== TRIGGERING UPDATE FOR VISIT {request.company_visit_id.name} ===")
                    request.company_visit_id._save_signed_report_to_folder()
                    if request.company_visit_id.state == 'pending':
                        request.company_visit_id.action_mark_done()

                # Logic for Not Contracted Visits
                if request.not_contracted_visit_id:
                    _logger.info(
                        f"=== TRIGGERING UPDATE FOR NOT CONTRACTED VISIT {request.not_contracted_visit_id.name} ===")
                    request.not_contracted_visit_id._save_signed_report_to_folder()
                    if request.not_contracted_visit_id.state == 'pending':
                        request.not_contracted_visit_id.action_mark_done()
        return res

    def action_done(self):
        """Fallback to ensure state is marked done when the sign action is fully finished."""
        res = super(SignRequest, self).action_done()
        for record in self:
            if record.company_visit_id and record.company_visit_id.state == 'pending':
                record.company_visit_id.write({'state': 'done'})
            if record.not_contracted_visit_id and record.not_contracted_visit_id.state == 'pending':
                record.not_contracted_visit_id.write({'state': 'done'})
        return res
