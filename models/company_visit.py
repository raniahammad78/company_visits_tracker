# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
import base64
from odoo.exceptions import UserError


# ========================================================================
# MODEL: CompanyVisit
# ------------------------------------------------------------------------
# This model manages company visit records linked to a service contract.
# Each record represents one maintenance or inspection visit.
# The model integrates:
#   - Contract & Partner details (auto-fetched)
#   - Report generation (PDF)
#   - Digital signature workflow via Odoo Sign
#   - State management (Pending → Done → Cancelled)
#   - Automatic numbering and folder organization
# ========================================================================

class CompanyVisit(models.Model):
    _name = 'company.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Enables chatter & activities
    _description = 'Company Visit Record'

    # ------------------------------
    # Basic Record Information
    # ------------------------------
    name = fields.Char(
        string='Visit Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _t('New'),
        help="Auto-generated reference for the visit (unique per company)."
    )
    visit_number = fields.Integer(
        string='Visit Number',
        readonly=True,
        copy=False,
        help="Sequential number of the visit under the same contract."
    )
    is_extra_visit = fields.Boolean(
        string="Extra Visit",
        default=False,
        help="Mark if this visit was outside the regular contract schedule."
    )

    # ------------------------------
    # Workflow / Status Fields
    # ------------------------------
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', tracking=True)

    # ------------------------------
    # Relational Fields
    # ------------------------------
    contract_id = fields.Many2one(
        'visit.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        help="The service contract that this visit is associated with."
    )
    partner_id = fields.Many2one(
        related='contract_id.partner_id',
        string='Company',
        store=True,
        readonly=True,
        help="The company associated with this visit (auto-filled from contract)."
    )
    folder_id = fields.Many2one(
        'visit.folder',
        string='Month Folder',
        ondelete='set null',
        help="Folder used to group visits and store generated reports."
    )

    # ------------------------------
    # Visit Details
    # ------------------------------
    visit_date = fields.Date(
        string='Visit Date',
        default=fields.Date.context_today,
        help="The actual date of the visit."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="The internal company managing this visit record."
    )
    assign_engineer_id = fields.Many2one(
        'res.users',
        string='Assigned Engineer',
        default=lambda self: self.env.user,
        help="The engineer responsible for performing this visit."
    )
    reason = fields.Char(string="Type of Problem")
    description = fields.Text(string="Engineer Comments")
    partner_address = fields.Char(string="Visit Address")
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")

    # Stores the generated report (PDF) in the document management system
    report_document_id = fields.Many2one('visit.document', string="Generated Report", readonly=True)

    # Linked sign requests for this visit (Odoo Sign integration)
    sign_request_ids = fields.One2many('sign.request', 'company_visit_id', string='Signature Requests', readonly=True)

    # --------------------------------------------------------------------
    # ONCHANGE METHODS
    # --------------------------------------------------------------------
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """
        Auto-fill partner address when a contract is selected.
        """
        if self.contract_id and self.contract_id.partner_id:
            self.partner_address = self.contract_id.partner_id.contact_address_complete

    # --------------------------------------------------------------------
    # OVERRIDE: CREATE
    # --------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Custom create method:
         - Assigns a sequence number (per partner/company)
         - Increments visit count within contract
         - Automatically generates a visit report PDF
        """
        for vals in vals_list:
            if vals.get('contract_id'):
                contract = self.env['visit.contract'].browse(vals.get('contract_id'))

                # ------------------------------
                # Sequence Generation per Partner
                # ------------------------------
                if contract.partner_id:
                    sequence_code = f'company.visit.{contract.partner_id.id}'
                    sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)

                    # Create partner-specific sequence if it doesn't exist
                    if not sequence:
                        sequence = self.env['ir.sequence'].create({
                            'name': f'{contract.partner_id.name} Visit Sequence',
                            'code': sequence_code,
                            'prefix': f'{contract.partner_id.name}-VST-',
                            'padding': 3,
                            'company_id': False,
                        })
                    vals['name'] = sequence.next_by_id()

                # ------------------------------
                # Increment Visit Counter
                # ------------------------------
                count = self.search_count([('contract_id', '=', contract.id)])
                vals['visit_number'] = count + 1

        # Call super to actually create the records
        visits = super().create(vals_list)

        # Automatically generate report document after creation
        for visit in visits:
            visit._action_generate_report_document()

        return visits

    # --------------------------------------------------------------------
    # STATE ACTIONS
    # --------------------------------------------------------------------
    def action_mark_done(self):
        """Set visit state to 'Done'."""
        return self.write({'state': 'done'})

    def action_cancel(self):
        """Cancel the visit record."""
        return self.write({'state': 'cancelled'})

    # --------------------------------------------------------------------
    # REPORT GENERATION METHODS
    # --------------------------------------------------------------------
    def _action_generate_report_document(self):
        """
        Generate a PDF report for the visit and save it into the document folder.
        Automatically called after record creation.
        """
        self.ensure_one()

        # Skip if already generated or no folder assigned
        if self.report_document_id or not self.folder_id:
            return

        # Retrieve QWeb report definition
        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        if not report:
            return

        try:
            # Render the report as PDF
            pdf_content, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)
            report_name = f'Visit Report - {self.name}.pdf'

            # Create a new visit.document record (stores the PDF)
            doc = self.env['visit.document'].create({
                'name': report_name,
                'folder_id': self.folder_id.id,
                'datas': base64.b64encode(pdf_content),
                'visit_id': self.id,
            })
            self.write({'report_document_id': doc.id})

        except Exception as e:
            # Log any errors without blocking creation
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Failed to generate report document for visit {self.name}: {str(e)}")

    # --------------------------------------------------------------------
    # SIGNATURE MANAGEMENT
    # --------------------------------------------------------------------
    def _save_signed_report_to_folder(self):
        """
        Once a sign request is completed, this method saves the signed PDF
        to the same document folder, replacing or adding the signed version.
        """
        self.ensure_one()

        if not self.folder_id:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Cannot save signed report for visit {self.name}: No folder assigned")
            return

        # Get the latest completed (signed) sign request
        completed_sign_request = self.env['sign.request'].search([
            ('company_visit_id', '=', self.id),
            ('state', '=', 'signed')
        ], limit=1, order='id desc')

        if not completed_sign_request:
            return

        # Extract the signed PDF
        if completed_sign_request.completed_document:
            signed_pdf = completed_sign_request.completed_document
            report_name = f'Signed Visit Report - {self.name}.pdf'

            # Update existing document or create a new one
            if self.report_document_id:
                self.report_document_id.write({
                    'name': report_name,
                    'datas': signed_pdf,
                })
            else:
                doc = self.env['visit.document'].create({
                    'name': report_name,
                    'folder_id': self.folder_id.id,
                    'datas': signed_pdf,
                    'visit_id': self.id,
                })
                self.write({'report_document_id': doc.id})

    # --------------------------------------------------------------------
    # ACTIONS (Report Printing / Sending / Opening)
    # --------------------------------------------------------------------
    def action_print_report(self):
        """Prints the visit report (PDF) through the report action."""
        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        if not report:
            raise UserError(_t("The visit report could not be found."))
        return report.report_action(self)

    def action_send_report_by_email(self):
        """
        Generates the visit report, creates a Sign Request for the client,
        and sends it via email for digital signature.
        """
        self.ensure_one()

        # Ensure the client has an email
        if not self.partner_id.email:
            raise UserError(_t("The client company does not have an email address set."))

        # Re-render the report with current data
        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        if not report:
            raise UserError(_t("The visit report definition could not be found. Please contact your administrator."))

        report_name = f'Service Call Report - {self.name}'
        pdf_report, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)

        if not pdf_report:
            raise UserError(_t("Failed to generate the visit report PDF."))

        # Step 1: Create attachment from report
        attachment = self.env['ir.attachment'].create({
            'name': report_name + '.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_report),
            'res_model': 'sign.template',
            'res_id': 0,
            'mimetype': 'application/pdf',
        })

        # Step 2: Retrieve or fallback to Customer Role
        ClientRole = self.env.ref('sign.sign_item_role_customer', raise_if_not_found=False) or \
                     self.env['sign.item.role'].search([('name', '=', 'Customer')], limit=1)
        if not ClientRole:
            raise UserError(_t("Customer role not found. Please ensure the Sign module is fully set up."))

        # Step 3: Create sign template from attachment
        template = self.env['sign.template'].create({
            'name': report_name,
            'attachment_id': attachment.id,
        })
        attachment.write({'res_model': 'sign.template', 'res_id': template.id})

        # Step 4: Add client signature field
        self.env['sign.item'].create({
            'template_id': template.id,
            'type_id': self.env.ref('sign.sign_item_type_signature').id,
            'required': True,
            'responsible_id': ClientRole.id,
            'page': 1,
            # Adjust X and Y positions to move it inside the frame
            'posX': 0.62,  
            'posY': 0.58,
            # Adjust width/height to fit inside frame
            'width': 0.24,
            'height': 0.06,
        })

        # Step 5: Create and send the sign request
        sign_request = self.env['sign.request'].create({
            'template_id': template.id,
            'reference': report_name,
            'subject': _t("Signature Request for Visit Report: %s") % self.name,
            'company_visit_id': self.id,
            'request_item_ids': [(0, 0, {
                'partner_id': self.partner_id.id,
                'role_id': ClientRole.id,
            })],
        })

        # Step 6: Send the sign request using available methods
        try:
            if hasattr(sign_request, 'action_send'):
                sign_request.action_send()
            elif hasattr(sign_request, 'send_signature_accesses'):
                sign_request.send_signature_accesses()
            elif hasattr(sign_request, 'action_sent'):
                sign_request.action_sent()
            else:
                sign_request.write({'state': 'sent'})
                for item in sign_request.request_item_ids:
                    if item.partner_id.email and hasattr(item, 'send_signature_accesses'):
                        item.send_signature_accesses()
        except Exception as e:
            raise UserError(_t("Failed to send signature request: %s") % str(e))

        # Step 7: Notify user of success
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

    def action_open_visit_form(self):
        """Utility method to reopen the visit form view."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


# ========================================================================
# MODEL EXTENSION: SignRequest
# ------------------------------------------------------------------------
# Extends Odoo's sign.request model to link sign requests directly
# to specific Company Visits. Automatically syncs status updates
# and triggers report saving when a signature is completed.
# ========================================================================

class SignRequest(models.Model):
    _inherit = 'sign.request'

    company_visit_id = fields.Many2one(
        'company.visit',
        string='Company Visit',
        ondelete='cascade',
        help="The visit record linked to this signature request."
    )

    def write(self, vals):
        """
        Override: detects when a sign request is marked 'signed' and
        automatically saves the signed document to the visit folder
        and updates the visit status.
        """
        result = super(SignRequest, self).write(vals)

        # If the sign request was just completed
        if vals.get('state') == 'signed':
            for record in self:
                if record.company_visit_id:
                    record.company_visit_id._save_signed_report_to_folder()

                    # Optionally mark visit as done
                    if record.company_visit_id.state == 'pending':
                        record.company_visit_id.action_mark_done()

        return result
