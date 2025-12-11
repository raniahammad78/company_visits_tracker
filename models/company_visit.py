# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
import base64
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


# ========================================================================
# MODEL: CompanyVisit
# ========================================================================

class CompanyVisit(models.Model):
    _name = 'company.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
        help="Auto-generated reference: Company - Year/Month - Sequence"
    )
    visit_number = fields.Integer(
        string='Visit Number',
        readonly=True,
        copy=False,
        help="Sequential number of the visit for the specific month."
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
    # OVERRIDE: CREATE (Robust Monthly Sequence)
    # --------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        Custom create method:
         - Generates a reference name that RESETS every month (Partner - YYYY/MM - 1).
         - Uses the HIGHEST existing number + 1 to prevent duplicates if records are deleted.
         - Automatically generates a visit report PDF.
        """
        # Cache to correctly handle batch creation (e.g., creating 8 visits at once)
        # Key: (partner_id, year, month) -> current_max_sequence
        sequence_cache = {}

        for vals in vals_list:
            # 1. Determine Partner
            contract = False
            partner = False

            if vals.get('contract_id'):
                contract = self.env['visit.contract'].browse(vals.get('contract_id'))
                partner = contract.partner_id
            elif vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals.get('partner_id'))

            # 2. Determine Visit Date
            visit_date_val = vals.get('visit_date') or fields.Date.today()
            if isinstance(visit_date_val, str):
                visit_date = fields.Date.from_string(visit_date_val)
            else:
                visit_date = visit_date_val

            # If we have a partner, we can generate the custom sequence
            if partner:
                # 3. Determine the count for this specific Month & Partner
                key = (partner.id, visit_date.year, visit_date.month)

                if key not in sequence_cache:
                    # Fetch existing HIGHEST number from DB for this month
                    start_of_month = visit_date.replace(day=1)
                    end_of_month = (start_of_month + relativedelta(months=1)) - relativedelta(days=1)

                    domain = [
                        ('partner_id', '=', partner.id),
                        ('visit_date', '>=', start_of_month),
                        ('visit_date', '<=', end_of_month)
                    ]

                    # Search for the record with the highest visit_number
                    last_visit = self.search(domain, order='visit_number desc', limit=1)
                    current_max = last_visit.visit_number if last_visit else 0

                    # Store current max in cache
                    sequence_cache[key] = current_max

                # 4. Increment count for the new record
                sequence_cache[key] += 1
                new_seq = sequence_cache[key]

                # 5. Assign Values
                vals['visit_number'] = new_seq

                # Format: "Solmax - 2025/12 - 1"
                date_label = visit_date.strftime('%Y/%m')
                vals['name'] = f"{partner.name} - {date_label} - {new_seq}"

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

            # Use the new monthly name format for the PDF filename too
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
            _logger.warning(f"Failed to generate report document for visit {self.name}: {str(e)}")

    # --------------------------------------------------------------------
    # SIGNATURE MANAGEMENT
    # --------------------------------------------------------------------
    def _save_signed_report_to_folder(self, signed_pdf_data):
        """
        Saves the signed PDF into a new company-specific folder under 'Signed Reports'.
        """
        self.ensure_one()

        if not signed_pdf_data:
            _logger.warning(f"Save report called for visit {self.name} but no PDF data was provided.")
            return

        if not self.partner_id:
            _logger.warning(f"Cannot save signed report for visit {self.name}: No partner assigned")
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

            # 3. Create the new visit.document record
            report_name = f'Signed Visit Report - {self.name}.pdf'

            self.env['visit.document'].create({
                'name': report_name,
                'folder_id': partner_folder.id,
                'datas': signed_pdf_data,
                'visit_id': self.id,
            })
            _logger.info(f"Successfully saved signed report for visit {self.name} to folder {partner_folder.name}.")

        except Exception as e:
            _logger.warning(f"Failed to save signed report for visit {self.name}: {str(e)}")

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

        if not self.partner_id.email:
            raise UserError(_t("The client company does not have an email address set."))

        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        if not report:
            raise UserError(_t("The visit report definition could not be found. Please contact your administrator."))

        report_name = f'Service Call Report - {self.name}'
        pdf_report, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)

        if not pdf_report:
            raise UserError(_t("Failed to generate the visit report PDF."))

        attachment = self.env['ir.attachment'].create({
            'name': report_name + '.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_report),
            'res_model': 'sign.template',
            'res_id': 0,
            'mimetype': 'application/pdf',
        })

        ClientRole = self.env.ref('sign.sign_item_role_customer', raise_if_not_found=False) or \
                     self.env['sign.item.role'].search([('name', '=', 'Customer')], limit=1)
        if not ClientRole:
            raise UserError(_t("Customer role not found. Please ensure the Sign module is fully set up."))

        template = self.env['sign.template'].create({
            'name': report_name,
            'attachment_id': attachment.id,
        })
        attachment.write({'res_model': 'sign.template', 'res_id': template.id})

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
# ========================================================================

class SignRequest(models.Model):
    _inherit = 'sign.request'

    company_visit_id = fields.Many2one(
        'company.visit',
        string='Company Visit',
        ondelete='cascade',
        help="The visit record linked to this signature request."
    )

    not_contracted_visit_id = fields.Many2one(
        'not.contracted.visit',
        string='Related Non-Contracted Visit',
        ondelete='set null',
        help="Links this signature request to a non-contracted visit record."
    )

    def write(self, vals):
        result = super(SignRequest, self).write(vals)

        if vals.get('completed_document'):
            _logger.info(f"SignRequest write trigger: 'completed_document' was added for records {self.ids}")
            for record in self:
                signed_document = record.completed_document

                if record.company_visit_id:
                    _logger.info(f"Processing signed report for Contracted Visit: {record.company_visit_id.name}...")
                    record.company_visit_id._save_signed_report_to_folder(signed_document)
                    if record.company_visit_id.state == 'pending':
                        record.company_visit_id.action_mark_done()

                if record.not_contracted_visit_id:
                    _logger.info(
                        f"Processing signed report for Non-Contracted Visit: {record.not_contracted_visit_id.name}...")
                    record.not_contracted_visit_id._save_signed_report_to_folder(signed_document)
                    if record.not_contracted_visit_id.state == 'pending':
                        record.not_contracted_visit_id.action_mark_done()

        return result
