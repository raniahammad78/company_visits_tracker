# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
import base64
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class NotContractedVisit(models.Model):
    """
    Model: not.contracted.visit
    ----------------------------------
    Tracks service visits for non-contracted companies.
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
    )

    partner_id = fields.Many2one('res.partner', string='Company', required=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending', tracking=True)

    visit_date = fields.Date(string='Visit Date', default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    assign_engineer_id = fields.Many2one('res.users', string='Assigned Engineer', default=lambda self: self.env.user)

    # Details
    reason = fields.Char(string="Type of Problem")
    description = fields.Text(string="Engineer Comments")
    partner_address = fields.Char(string="Visit Address")

    # Signatures
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")

    cc_partner_ids = fields.Many2many(
        'res.partner',
        string="Contacts in Copy",
        help="Contacts who will receive a copy of the final signed report."
    )

    # Documents
    report_document_id = fields.Many2one('visit.document', string="Generated Report", readonly=True, copy=False)
    sign_request_ids = fields.One2many('sign.request', 'not_contracted_visit_id', string='Signature Requests',
                                       readonly=True)

    # === FIELD ONCHANGE METHODS ===
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_address = self.partner_id.contact_address or ''

    # === RECORD CREATION ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _t('New')) == _t('New'):
                sequence = self.env['ir.sequence'].next_by_code('not.contracted.visit') or ''
                partner_name = ''
                if vals.get('partner_id'):
                    partner = self.env['res.partner'].browse(vals.get('partner_id'))
                    if partner:
                        partner_name = partner.name
                vals['name'] = f"{partner_name} - {sequence}" if partner_name else sequence

        visits = super().create(vals_list)
        for visit in visits:
            visit._action_generate_report_document()
        return visits

    # === REPORT GENERATION ===
    def _action_generate_report_document(self):
        self.ensure_one()
        if self.report_document_id:
            return

        main_folder = self.env.ref('company_visit_tracker.folder_not_contracted_visits', raise_if_not_found=False)
        if not main_folder:
            return

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

        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
        if not report:
            return

        pdf_content, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)
        report_name = f'Visit Report - {self.partner_id.name} - {self.visit_date}.pdf'

        doc = self.env['visit.document'].create({
            'name': report_name,
            'folder_id': month_folder.id,
            'datas': base64.b64encode(pdf_content),
            'not_contracted_visit_id': self.id,
        })
        self.write({'report_document_id': doc.id})

    # === DOCUMENT REPLACEMENT LOGIC  ===
    def _save_signed_report_to_folder(self):
        """
        Deletes the unsigned report, saves the signed one, updates the signature image,
        and sends the signed report to CC contacts.
        """
        self.ensure_one()
        _logger.info(f"=== STARTING SAVE PROCESS FOR NOT CONTRACTED VISIT: {self.name} ===")

        # 1. Find the completed sign request
        completed_sign_request = self.env['sign.request'].sudo().search([
            ('not_contracted_visit_id', '=', self.id),
            ('state', '=', 'signed')
        ], limit=1, order='id desc')

        if not completed_sign_request:
            _logger.warning("=== NO SIGNED REQUEST FOUND ===")
            return

        # 2. Extract Client Signature
        signed_item = self.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', completed_sign_request.id),
            ('signature', '!=', False)
        ], limit=1)

        if signed_item:
            _logger.info("=== SUCCESS: SIGNATURE FOUND. SAVING TO RECORD... ===")
            self.sudo().write({'client_signature': signed_item.signature})
        else:
            _logger.warning("=== NO SIGNATURE IMAGE FOUND IN REQUEST ===")

        # 3. Handle Document Replacement
        signed_pdf = None
        if completed_sign_request.completed_document:
            _logger.info("=== REPLACING PDF DOCUMENT ===")
            # Delete old documents
            existing_docs = self.env['visit.document'].sudo().search([('not_contracted_visit_id', '=', self.id)])
            existing_docs.unlink()

            # Find folder
            main_folder = self.env.ref('company_visit_tracker.folder_not_contracted_visits', raise_if_not_found=False)
            folder_id = False
            if main_folder:
                visit_date = self.visit_date or fields.Date.today()
                folder_name = visit_date.strftime('%Y-%m (%B)')
                month_folder = self.env['visit.folder'].sudo().search([
                    ('name', '=', folder_name),
                    ('parent_id', '=', main_folder.id)
                ], limit=1)
                if month_folder:
                    folder_id = month_folder.id

            # Create new document
            signed_pdf = completed_sign_request.completed_document
            report_name = f'Signed Visit Report - {self.name}.pdf'

            doc = self.env['visit.document'].sudo().create({
                'name': report_name,
                'folder_id': folder_id,
                'datas': signed_pdf,
                'not_contracted_visit_id': self.id,
            })

            self.sudo().write({'report_document_id': doc.id})

        # 4. Send Email to CC Contacts
        if self.cc_partner_ids and signed_pdf:
            self._send_signed_report_to_cc_contacts(signed_pdf)

    def _send_signed_report_to_cc_contacts(self, signed_pdf):
        """
        Send the signed visit report to all contacts in copy.
        """
        self.ensure_one()
        if not self.cc_partner_ids:
            _logger.info("=== NO CC CONTACTS TO NOTIFY ===")
            return

        _logger.info(f"=== SENDING SIGNED REPORT TO {len(self.cc_partner_ids)} CC CONTACTS ===")

        # Create attachment for the signed PDF
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'Signed Visit Report - {self.name}.pdf',
            'type': 'binary',
            'datas': signed_pdf,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # Prepare email template
        mail_template = self.env.ref('company_visit_tracker.email_template_signed_visit_report',
                                     raise_if_not_found=False)

        # Send emails immediately to CC contacts
        for cc_partner in self.cc_partner_ids:
            if cc_partner.email:
                mail_values = {
                    'subject': f'Signed Visit Report - {self.name}',
                    'body_html': f"""
                        <div style="margin: 0px; padding: 0px; font-family: Arial, Helvetica, sans-serif; font-size: 13px;">
                            <p>Dear {cc_partner.name},</p>

                            <p>We are pleased to inform you that the visit report has been signed by all parties.</p>

                            <p><strong>Visit Details:</strong></p>
                            <table style="border-collapse: collapse; margin-left: 20px;">
                                <tr>
                                    <td style="padding: 5px;"><strong>Visit Reference:</strong></td>
                                    <td style="padding: 5px;">{self.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px;"><strong>Visit Date:</strong></td>
                                    <td style="padding: 5px;">{self.visit_date}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px;"><strong>Company:</strong></td>
                                    <td style="padding: 5px;">{self.partner_id.name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 5px;"><strong>Assigned Engineer:</strong></td>
                                    <td style="padding: 5px;">{self.assign_engineer_id.name if self.assign_engineer_id else 'N/A'}</td>
                                </tr>
                                {'<tr><td style="padding: 5px;"><strong>Type of Problem:</strong></td><td style="padding: 5px;">' + self.reason + '</td></tr>' if self.reason else ''}
                            </table>

                            <p>Please find the signed report attached to this email for your records.</p>

                            <p>If you have any questions or concerns, please do not hesitate to contact us.</p>

                            <p>
                                Best regards,<br/>
                                {self.company_id.name}<br/>
                                {('Phone: ' + self.company_id.phone + '<br/>') if self.company_id.phone else ''}
                                {('Email: ' + self.company_id.email) if self.company_id.email else ''}
                            </p>
                        </div>
                    """,
                    'email_to': cc_partner.email,
                    'email_from': self.env.user.email or self.company_id.email,
                    'attachment_ids': [(4, attachment.id)],
                }

                # Create and send the email
                mail = self.env['mail.mail'].sudo().create(mail_values)
                mail.sudo().send()
                _logger.info(f"=== EMAIL QUEUED FOR: {cc_partner.email} ===")

    # === ACTIONS ===
    def action_print_report(self):
        self.ensure_one()
        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
        return report.report_action(self)

    def action_send_report_for_signature(self):
        """
        Generates a fresh version of the visit report, creates a Sign Template,
        and opens the standard Odoo Sign wizard.
        """
        self.ensure_one()

        # Ensure the engineer has signed on the server first
        if not self.engineer_signature:
            raise UserError(_t("The assigned engineer must sign the visit form before sending it to the company."))

        if not self.partner_id.email:
            raise UserError(_t("The client company does not have an email address set."))

        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit', raise_if_not_found=False)
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

        # Build signer list with ONLY the Customer
        signer_ids = [(0, 0, {
            'role_id': ClientRole.id,
            'partner_id': self.partner_id.id,
        })]

        # === OPEN ODOO'S NATIVE SIGN WIZARD ===
        return {
            'name': _t('Send Signature Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'sign.send.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': template.id,
                'default_subject': _t("Signature Request for Visit Report: %s") % self.name,
                'default_not_contracted_visit_id': self.id,
                'default_signer_ids': signer_ids,
                'default_cc_partner_ids': self.cc_partner_ids.ids,
            }
        }

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    @api.model
    def get_dashboard_stats(self):
        """Universal Fetcher: Uses global environment to force-merge statistics."""
        # 1. Access models via the global env to ensure model isolation is bridged
        v_model = self.env['company.visit'].sudo().with_context(active_test=False)
        nc_model = self.env['not.contracted.visit'].sudo().with_context(active_test=False)

        # 2. Fetch ALL records
        visits = v_model.search([])
        nc_visits = nc_model.search([]) if nc_model.exists() else self.env['not.contracted.visit']

        # 3. KPI CALCULATIONS (Manual Aggregation)
        # We manually sum them to ensure no Odoo 'context' filters them out
        total_len = len(visits) + len(nc_visits)

        pending_total = (len(visits.filtered(lambda v: v.state == 'pending')) +
                         len(nc_visits.filtered(lambda v: v.state == 'pending')))

        done_total = (len(visits.filtered(lambda v: v.state == 'done')) +
                      len(nc_visits.filtered(lambda v: v.state == 'done')))

        cancelled_total = (len(visits.filtered(lambda v: v.state == 'cancelled')) +
                           len(nc_visits.filtered(lambda v: v.state == 'cancelled')))

        extra_total = len(visits.filtered(lambda v: v.is_extra_visit)) + len(nc_visits)

        # 4. ENGINEER WORKLOAD
        engineers_data = {}

        # Combined list for workload processing
        all_records = list(visits) + list(nc_visits)

        for rec in all_records:
            if rec.assign_engineer_id:
                eng_id = rec.assign_engineer_id.id
                if eng_id not in engineers_data:
                    engineers_data[eng_id] = {
                        'id': eng_id,
                        'name': rec.assign_engineer_id.name,
                        'pending': 0, 'done': 0, 'total': 0
                    }

                engineers_data[eng_id]['total'] += 1
                if rec.state == 'pending':
                    engineers_data[eng_id]['pending'] += 1
                elif rec.state == 'done':
                    engineers_data[eng_id]['done'] += 1

        # 5. ACTION NEEDED
        recent_v = v_model.search([('state', '=', 'pending')], order='create_date desc', limit=5)
        recent_nc = nc_model.search([('state', '=', 'pending')], order='create_date desc', limit=5)

        combined_recent = []
        for r in recent_v:
            combined_recent.append({
                'id': r.id, 'model': 'company.visit', 'name': r.name,
                'partner': r.partner_id.name, 'date': r.create_date.strftime('%Y-%m-%d') if r.create_date else ''
            })
        for r in recent_nc:
            combined_recent.append({
                'id': r.id, 'model': 'not.contracted.visit', 'name': r.name,
                'partner': r.partner_id.name, 'date': r.create_date.strftime('%Y-%m-%d') if r.create_date else ''
            })

        return {
            'user_name': self.env.user.name,
            'kpi': {
                'total': total_len,
                'pending': pending_total,
                'done': done_total,
                'cancelled': cancelled_total,
                'extra': extra_total,
            },
            'engineers': list(engineers_data.values()),
            'recent_extras': sorted(combined_recent, key=lambda x: x['date'], reverse=True)[:5],
        }
