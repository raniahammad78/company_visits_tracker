# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
import base64
from odoo.exceptions import UserError
import logging
from odoo.fields import Date
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class CompanyVisit(models.Model):
    _name = 'company.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Company Visit Record'

    name = fields.Char(string='Visit Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _t('New'))
    visit_number = fields.Integer(string='Visit Number', readonly=True, copy=False)
    is_extra_visit = fields.Boolean(string="Extra Visit", default=False)
    state = fields.Selection([('pending', 'Pending'), ('done', 'Done'), ('cancelled', 'Cancelled')], string='Status',
                             default='pending', tracking=True)

    contract_id = fields.Many2one('visit.contract', string='Contract', required=True, ondelete='cascade')
    partner_id = fields.Many2one(related='contract_id.partner_id', string='Company', store=True, readonly=True)
    folder_id = fields.Many2one('visit.folder', string='Month Folder', ondelete='set null')

    visit_date = fields.Date(string='Visit Date', default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    assign_engineer_id = fields.Many2one('res.users', string='Assigned Engineer', default=lambda self: self.env.user)
    reason = fields.Char(string="Type of Problem")
    description = fields.Text(string="Engineer Comments")
    partner_address = fields.Char(string="Visit Address")

    # Signatures
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")

    # Documents
    report_document_id = fields.Many2one('visit.document', string="Generated Report", readonly=True)
    sign_request_ids = fields.One2many('sign.request', 'company_visit_id', string='Signature Requests', readonly=True)

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id and self.contract_id.partner_id:
            self.partner_address = self.contract_id.partner_id.contact_address_complete

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('contract_id'):
                contract = self.env['visit.contract'].browse(vals.get('contract_id'))
                if contract.partner_id:
                    sequence_code = f'company.visit.{contract.partner_id.id}'
                    sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)

                    # Define the prefix with Year and Month placeholders
                    prefix_format = f'{contract.partner_id.name}-VST-%(y)s%(month)s-'

                    if not sequence:
                        # Create sequence with monthly reset capability
                        sequence = self.env['ir.sequence'].create({
                            'name': f'{contract.partner_id.name} Visit Sequence',
                            'code': sequence_code,
                            'prefix': prefix_format,
                            'padding': 3,
                            'use_date_range': True,  # Tells Odoo to reset the number monthly/yearly!
                            'company_id': False
                        })
                    elif not sequence.use_date_range:
                        # sequences to use the monthly reset format
                        sequence.write({
                            'use_date_range': True,
                            'prefix': prefix_format
                        })

                    vals['name'] = sequence.next_by_id()

                # Reset the internal 'visit_number' integer field monthly
                v_date_str = vals.get('visit_date') or Date.context_today(self)
                v_date = Date.to_date(v_date_str)

                start_of_month = v_date.replace(day=1)
                next_month = start_of_month + relativedelta(months=1)

                count = self.search_count([
                    ('contract_id', '=', contract.id),
                    ('visit_date', '>=', start_of_month),
                    ('visit_date', '<', next_month)
                ])
                vals['visit_number'] = count + 1

        visits = super().create(vals_list)
        for visit in visits:
            visit._action_generate_report_document()
        return visits

    def _action_generate_report_document(self):
        self.ensure_one()
        if self.report_document_id or not self.folder_id:
            return
        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        if not report:
            return
        try:
            pdf_content, _ = report._render_qweb_pdf(report_ref=report.report_name, res_ids=self.ids)
            report_name = f'Visit Report - {self.name}.pdf'
            if self.report_document_id:
                self.report_document_id.write({'datas': base64.b64encode(pdf_content), 'name': report_name})
            else:
                doc = self.env['visit.document'].create({
                    'name': report_name, 'folder_id': self.folder_id.id,
                    'datas': base64.b64encode(pdf_content), 'visit_id': self.id
                })
                self.write({'report_document_id': doc.id})
        except Exception as e:
            _logger.warning(f"Failed to generate report document: {str(e)}")

    def _save_signed_report_to_folder(self):
        self.ensure_one()
        _logger.info(f"=== STARTING SAVE PROCESS FOR VISIT: {self.name} ===")

        if not self.folder_id:
            _logger.warning("=== NO FOLDER FOUND ===")
            return

        # 1. Find completed request
        completed_sign_request = self.env['sign.request'].sudo().search([
            ('company_visit_id', '=', self.id),
            ('state', '=', 'signed')
        ], limit=1, order='id desc')

        if not completed_sign_request:
            _logger.warning("=== NO SIGNED REQUEST FOUND ===")
            return

        # 2. Extract Signature
        signed_item = self.env['sign.request.item'].sudo().search([
            ('sign_request_id', '=', completed_sign_request.id),
            ('signature', '!=', False)
        ], limit=1)

        if signed_item:
            _logger.info("=== SUCCESS: SIGNATURE FOUND. SAVING TO RECORD... ===")
            self.sudo().write({'client_signature': signed_item.signature})
        else:
            _logger.warning("=== ERROR: REQUEST IS SIGNED BUT NO SIGNATURE IMAGE FOUND ===")

        # 3. Update Document
        if completed_sign_request.completed_document:
            _logger.info("=== REPLACING PDF DOCUMENT ===")
            existing_docs = self.env['visit.document'].sudo().search([('visit_id', '=', self.id)])
            existing_docs.unlink()

            signed_pdf = completed_sign_request.completed_document
            report_name = f'Signed Visit Report - {self.name}.pdf'

            doc = self.env['visit.document'].sudo().create({
                'name': report_name,
                'folder_id': self.folder_id.id,
                'datas': signed_pdf,
                'visit_id': self.id,
            })
            self.sudo().write({'report_document_id': doc.id})

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def action_print_report(self):
        report = self.env.ref('company_visit_tracker.action_report_company_visit', raise_if_not_found=False)
        return report.report_action(self)

    def action_send_report_by_email(self):
        """
        Generates the visit report, creates a Sign Template with a signature field,
        and uses the standard Odoo wizard in the background to send the correct signature link.
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

        # 1. Create the Attachment
        attachment = self.env['ir.attachment'].create({
            'name': report_name + '.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_report),
            'res_model': 'sign.template',
            'res_id': 0,
            'mimetype': 'application/pdf',
        })

        # 2. Get Customer Role
        ClientRole = self.env.ref('sign.sign_item_role_customer', raise_if_not_found=False) or \
                     self.env['sign.item.role'].search([('name', '=', 'Customer')], limit=1)
        if not ClientRole:
            raise UserError(_t("Customer role not found. Please ensure the Sign module is fully set up."))

        # 3. Create the Sign Template & Attach Signature Field AT THE SAME TIME
        template = self.env['sign.template'].create({
            'name': report_name,
            'attachment_id': attachment.id,
            'num_pages': 1,
            'sign_item_ids': [(0, 0, {
                'type_id': self.env.ref('sign.sign_item_type_signature').id,
                'name': 'Signature',
                'required': True,
                'responsible_id': ClientRole.id,
                'page': 1,
                'posX': 0.60,
                'posY': 0.85,  # Placed towards the bottom right
                'width': 0.25,
                'height': 0.08,
            })]
        })

        # Link attachment back to template to prevent viewer crashes
        attachment.write({'res_model': 'sign.template', 'res_id': template.id})

        # Get Engineer role
        EngineerRole = self.env.ref('sign.sign_item_role_employee', raise_if_not_found=False) or \
                       self.env['sign.item.role'].search([('name', '=', 'Employee')], limit=1)
        if not EngineerRole:
            raise UserError(_t("Employee role not found."))

        # Add Engineer signature field to template
        self.env['sign.item'].create({
            'template_id': template.id,
            'type_id': self.env.ref('sign.sign_item_type_signature').id,
            'name': 'Engineer Signature',
            'required': True,
            'responsible_id': EngineerRole.id,
            'page': 1,
            'posX': 0.12,
            'posY': 0.85,
            'width': 0.25,
            'height': 0.08,
        })

        # Build signer list with both Customer and Engineer
        signer_ids = [(0, 0, {
            'role_id': ClientRole.id,
            'partner_id': self.partner_id.id,
        })]
        if self.assign_engineer_id and self.assign_engineer_id.partner_id:
            signer_ids.append((0, 0, {
                'role_id': EngineerRole.id,
                'partner_id': self.assign_engineer_id.partner_id.id,
            }))

        # 4. Open Sign Wizard for review before sending
        return {
            'name': _t('Send Signature Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'sign.send.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': template.id,
                'default_subject': _t("Signature Request for Visit Report: %s") % self.name,
                'default_filename': report_name + '.pdf',
                'default_company_visit_id': self.id,
                'default_signer_ids': signer_ids,
            }
        }

    def action_open_visit_form(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'current'}

    @api.model
    def get_dashboard_stats(self, date_filter='all'):
        """Upgraded Fetcher: Now supports Date Filtering and SLA Calculations"""
        from odoo.fields import Date

        v_model = self.env['company.visit'].sudo()
        nc_model = self.env['not.contracted.visit'].sudo()

        # 1. APPLY DYNAMIC DATE FILTER
        domain = []
        today = Date.context_today(self)
        if date_filter == 'month':
            start_of_month = today.replace(day=1)
            domain = [('create_date', '>=', start_of_month)]
        elif date_filter == 'year':
            start_of_year = today.replace(month=1, day=1)
            domain = [('create_date', '>=', start_of_year)]

        # 2. KPI CALCULATIONS (Filtered by Domain)
        total_count = v_model.search_count(domain) + nc_model.search_count(domain)
        pending_count = v_model.search_count(domain + [('state', '=', 'pending')]) + nc_model.search_count(
            domain + [('state', '=', 'pending')])
        done_count = v_model.search_count(domain + [('state', '=', 'done')]) + nc_model.search_count(
            domain + [('state', '=', 'done')])
        cancelled_count = v_model.search_count(domain + [('state', '=', 'cancelled')]) + nc_model.search_count(
            domain + [('state', '=', 'cancelled')])

        # 3. ENGINEER WORKLOAD (Filtered by Domain)
        engineers_data = {}
        all_v = v_model.search(domain + [('assign_engineer_id', '!=', False)])
        all_nc = nc_model.search(domain + [('assign_engineer_id', '!=', False)])

        def process_engineer_stats(records, model_type):
            for rec in records:
                eng_id = rec.assign_engineer_id.id
                if eng_id not in engineers_data:
                    engineers_data[eng_id] = {
                        'id': eng_id, 'name': rec.assign_engineer_id.name,
                        'pending': 0, 'done': 0, 'total': 0, 'v_total': 0, 'nc_total': 0
                    }
                engineers_data[eng_id]['total'] += 1
                if model_type == 'v':
                    engineers_data[eng_id]['v_total'] += 1
                else:
                    engineers_data[eng_id]['nc_total'] += 1
                if rec.state == 'pending':
                    engineers_data[eng_id]['pending'] += 1
                elif rec.state == 'done':
                    engineers_data[eng_id]['done'] += 1

        process_engineer_stats(all_v, 'v')
        process_engineer_stats(all_nc, 'nc')

        # 4. ACTION NEEDED & SLA LOGIC
        recent_v = v_model.search(domain + [('state', '=', 'pending')], order='create_date desc', limit=5)
        recent_nc = nc_model.search(domain + [('state', '=', 'pending')], order='create_date desc', limit=5)

        combined_recent = []
        for r in list(recent_v) + list(recent_nc):
            # Calculate how many days it has been pending
            days_pending = (today - r.create_date.date()).days if r.create_date else 0

            # SLA Rules: Over 3 days is Overdue (Red), otherwise On Time (Green)
            sla_status = 'Overdue' if days_pending > 3 else 'On Time'
            sla_color = 'danger' if days_pending > 3 else 'success'

            # ... (previous code)
            combined_recent = []
            for r in list(recent_v) + list(recent_nc):
                days_pending = (today - r.create_date.date()).days if r.create_date else 0
                sla_status = 'Overdue' if days_pending > 3 else 'On Time'
                sla_color = 'danger' if days_pending > 3 else 'success'

                combined_recent.append({
                    'id': r.id,
                    'model': r._name,
                    'name': r.name,
                    'partner': r.partner_id.name,
                    'date': r.create_date.strftime('%Y-%m-%d') if r.create_date else '',
                    'days_pending': days_pending,
                    'sla_status': sla_status,
                    'sla_color': sla_color
                })

            # ---> UNINDENT THE CODE BELOW THIS LINE <---
            all_users = self.env['res.users'].sudo().search([('share', '=', False)])  # Get internal users
            available_engineers = [{'id': u.id, 'name': u.name} for u in all_users]

            return {
                'user_name': self.env.user.name,
                'kpi': {'total': total_count, 'pending': pending_count, 'done': done_count,
                        'cancelled': cancelled_count,
                        'extra': v_model.search_count(domain + [('is_extra_visit', '=', True)])},
                'engineers': list(engineers_data.values()),
                'recent_extras': sorted(combined_recent, key=lambda x: x['date'], reverse=True)[:5],
                'available_engineers': available_engineers,
            }
