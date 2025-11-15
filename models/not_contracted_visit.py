# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
import base64
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class NotContractedVisit(models.Model):
    """
    Model: not.contracted.visit
    ... (rest of comments) ...
    """
    _name = 'not.contracted.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Visit for Not Contracted Companies'

    # === BASIC VISIT INFORMATION ===
    name = fields.Char(
        string='Visit Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _t('New'),
        help="Unique reference for each visit (auto-generated)."
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        required=True,
        help="Select the client company for which the visit is made."
    )

    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
        ],
        string='Status',
        default='pending',
        tracking=True,
        help="Tracks the current visit status. Used for workflow transitions."
    )

    visit_date = fields.Date(
        string='Visit Date',
        default=fields.Date.context_today,
        help="Date when the visit took place or is scheduled."
    )

    # Company info for multi-company environment support
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="Indicates the company responsible for the visit (for multi-company setups)."
    )

    # Engineer assigned to handle the visit
    assign_engineer_id = fields.Many2one(
        'res.users',
        string='Assigned Engineer',
        default=lambda self: self.env.user,
        help="Engineer or technician responsible for performing this visit."
    )

    # Additional details about the visit
    reason = fields.Char(string="Type of Problem", help="Short description of the issue or request.")
    description = fields.Text(string="Engineer Comments", help="Detailed comments added by the engineer.")
    partner_address = fields.Char(string="Visit Address", help="Client's address for the visit location.")

    # Signatures captured during or after the visit
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")

    # Link to the generated PDF report
    report_document_id = fields.Many2one(
        'visit.document',
        string="Generated Report",
        readonly=True,
        copy=False,
        help="Automatically generated visit report stored as a document record."
    )

    # Relation to electronic signature requests (Odoo Sign)
    sign_request_ids = fields.One2many(
        'sign.request',
        'not_contracted_visit_id',
        string='Signature Requests',
        readonly=True,
        help="Tracks all signature requests associated with this visit."
    )

    # === FIELD ONCHANGE METHODS ===
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Automatically fills the client address when a partner is selected."""
        if self.partner_id:
            self.partner_address = self.partner_id.contact_address_complete

    # === RECORD CREATION ===
    @api.model_create_multi
    def create(self, vals_list):
        """
        Overrides create() to:
        - Auto-generate visit reference name using partner name and sequence.
        - Automatically generate the visit report document after creation.
        """
        for vals in vals_list:
            # Generate unique reference number if not provided
            if vals.get('name', _t('New')) == _t('New'):
                sequence = self.env['ir.sequence'].next_by_code('not.contracted.visit') or ''
                partner_name = ''
                if vals.get('partner_id'):
                    partner = self.env['res.partner'].browse(vals.get('partner_id'))
                    if partner:
                        partner_name = partner.name

                # Combine partner name and sequence for clearer tracking
                vals['name'] = f"{partner_name} - {sequence}" if partner_name else sequence

        # Create the record(s)
        visits = super().create(vals_list)

        # Automatically generate a PDF report for each created visit
        for visit in visits:
            visit._action_generate_report_document()
        return visits

    # === REPORT GENERATION ===
    def _action_generate_report_document(self):
        """
        Generates a PDF report for the visit and saves it in the
        corresponding 'Not Contracted Visits' folder (grouped by month).

        This method is called automatically after creation.
        """
        self.ensure_one()

        # Skip if report already exists
        if self.report_document_id:
            return

        # Main root folder reference (must exist in XML data)
        main_folder = self.env.ref('company_visit_tracker.folder_not_contracted_visits', raise_if_not_found=False)
        if not main_folder:
            return  # Avoid crash if folder not configured

        # Create or locate month subfolder (e.g., "2025-10 (October)")
        visit_date = self.visit_date or fields.Date.today()
        folder_name = visit_date.strftime('%Y-%m (%B)')

        month_folder = self.env['visit.folder'].search([
            ('name', '=', folder_name),
            ('parent_id', '=', main_folder.id)
        ], limit=1)

        if not month_folder:
            month_folder = self.env['visit.folder'].create({
                'name': folder_name,
                'parent_id': main_folder.id,
            })

        # Load report definition
        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
        if not report:
            return

        # Render QWeb report into PDF
        pdf_content, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)
        report_name = f'Visit Report - {self.partner_id.name} - {self.visit_date}.pdf'

        # Create new visit.document record to store the generated PDF
        doc = self.env['visit.document'].create({
            'name': report_name,
            'folder_id': month_folder.id,
            'datas': base64.b64encode(pdf_content),
            'not_contracted_visit_id': self.id,
        })

        # Link generated document back to this visit
        self.write({'report_document_id': doc.id})

    # === NEW METHOD: Save Signed Report ===
    def _save_signed_report_to_folder(self, signed_pdf_data):
        """
        *** MODIFIED ***
        Once a sign request is completed, this method saves the signed PDF
        into a new company-specific folder under 'Signed Reports'.

        This method now accepts the PDF data directly from the 'write'
        trigger to avoid a database transaction timing issue.
        """
        self.ensure_one()

        if not signed_pdf_data:
            _logger.warning(f"Save report called for non-contracted visit {self.name} but no PDF data was provided.")
            return

        if not self.partner_id:
            _logger.warning(f"Cannot save signed report for non-contracted visit {self.name}: No partner assigned")
            return

        try:
            # 1. Find the main "Signed Reports" folder
            main_signed_folder = self.env.ref('company_visit_tracker.folder_signed_reports', raise_if_not_found=True)

            # 2. Find or create the company-specific sub-folder (e.g., "Signed Reports / Client A")
            partner_folder = self.env['visit.folder'].search([
                ('name', '=', self.partner_id.name),
                ('parent_id', '=', main_signed_folder.id)
            ], limit=1)

            if not partner_folder:
                partner_folder = self.env['visit.folder'].create({
                    'name': self.partner_id.name,
                    'parent_id': main_signed_folder.id,
                })

            # 3. REMOVED: Search for sign.request (we now pass the data in)

            # 4. Create the new visit.document record
            report_name = f'Signed Visit Report - {self.name}.pdf'

            self.env['visit.document'].create({
                'name': report_name,
                'folder_id': partner_folder.id,
                'datas': signed_pdf_data,  # Use the passed-in data
                'not_contracted_visit_id': self.id,
            })
            _logger.info(
                f"Successfully saved signed report for non-contracted visit {self.name} to folder {partner_folder.name}.")

        except Exception as e:
            _logger.warning(f"Failed to save signed report for non-contracted visit {self.name}: {str(e)}")

    # === ACTIONS ===
    def action_print_report(self):
        """Triggers Odoo to generate and download the visit report as PDF."""
        self.ensure_one()
        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
        if not report:
            raise UserError(_t("The non-contracted visit report could not be found."))

        return report.report_action(self)

    def action_send_report_for_signature(self):
        """
        Generates a fresh version of the visit report, creates a Sign Template,
        and sends a digital signature request directly to the client.
        ... (rest of comments) ...
        """
        self.ensure_one()

        # Ensure the client has an email address
        if not self.partner_id.email:
            raise UserError(_t("The client company does not have an email address set."))

        # Load the visit report definition
        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
        if not report:
            raise UserError(_t("The visit report definition could not be found. Please contact your administrator."))

        report_name = f'Service Call Report - {self.name}'

        # Render PDF report from QWeb template
        pdf_report, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)
        if not pdf_report:
            raise UserError(_t("Failed to generate the visit report PDF."))

        # === STEP 1: Create attachment from generated PDF ===
        attachment = self.env['ir.attachment'].create({
            'name': report_name + '.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_report),
            'res_model': 'sign.template',
            'res_id': 0,  # Temporarily unset, will be updated below
            'mimetype': 'application/pdf',
        })

        # === STEP 2: Get customer role (required by Odoo Sign) ===
        ClientRole = self.env.ref('sign.sign_item_role_customer', raise_if_not_found=False)
        if not ClientRole:
            ClientRole = self.env['sign.item.role'].search([('name', '=', 'Customer')], limit=1)

        if not ClientRole:
            raise UserError(_t("Customer role not found. Please ensure the Sign module is fully set up."))

        # === STEP 3: Create sign template from attachment ===
        template = self.env['sign.template'].create({
            'name': report_name,
            'attachment_id': attachment.id,
        })

        # Update attachment to point to the new template
        attachment.write({
            'res_model': 'sign.template',
            'res_id': template.id,
        })

        # === STEP 4: Add customer signature field to template ===
        # Coordinates may need adjusting based on actual report layout
        self.env['sign.item'].create({
            'template_id': template.id,
            'type_id': self.env.ref('sign.sign_item_type_signature').id,
            'required': True,
            'responsible_id': ClientRole.id,
            'page': 1,
            'posX': 0.62,
            'posY': 0.58,
            'width': 0.24,
            'height': 0.06,
        })

        # === STEP 5: Create the Sign Request ===
        sign_request = self.env['sign.request'].create({
            'template_id': template.id,
            'reference': report_name,
            'subject': _t("Signature Request for Visit Report: %s") % self.name,
            'not_contracted_visit_id': self.id,
            'request_item_ids': [(0, 0, {
                'partner_id': self.partner_id.id,
                'role_id': ClientRole.id,
            })],
        })

        # === STEP 6: Send signature request via email ===
        try:
            # Initialize request (for newer Odoo Sign versions)
            if hasattr(sign_request, 'initialize_new'):
                sign_request.initialize_new()

            # Send email to client
            if hasattr(sign_request, 'action_send'):
                sign_request.action_send()
            elif hasattr(sign_request, 'send_signature_accesses'):
                sign_request.send_signature_accesses()
            else:
                # Fallback for older Odoo Sign versions
                sign_request.write({'state': 'sent'})
                for item in sign_request.request_item_ids:
                    if item.partner_id and item.partner_id.email:
                        if hasattr(item, 'send_signature_accesses'):
                            item.send_signature_accesses()
        except Exception as e:
            raise UserError(_t("Failed to send signature request: %s") % str(e))

        # === STEP 7: Return confirmation popup ===
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _t('Success'),
                'message': _t('Signature request sent directly to client %s.') % self.partner_id.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_mark_done(self):
        """Marks the visit as completed."""
        return self.write({'state': 'done'})

    def action_cancel(self):
        """Cancels the visit record."""
        return self.write({'state': 'cancelled'})
