# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import base64


class CompanyVisit(models.Model):
    _name = 'company.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Company Visit Record'

    name = fields.Char(string='Visit Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
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
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")
    report_document_id = fields.Many2one('visit.document', string="Generated Report", readonly=True)

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
                    # Logic to create a new sequence for each company if it doesn't exist
                    sequence_code = f'company.visit.{contract.partner_id.id}'
                    sequence = self.env['ir.sequence'].search([('code', '=', sequence_code)], limit=1)
                    if not sequence:
                        sequence = self.env['ir.sequence'].create({
                            'name': f'{contract.partner_id.name} Visit Sequence',
                            'code': sequence_code,
                            'prefix': f'{contract.partner_id.name}-VST-',
                            'padding': 3,
                            'company_id': False,
                        })

                    # Assign the name from the company-specific sequence
                    vals['name'] = sequence.next_by_id()

                # Calculate and set the visit number (counts visits per contract)
                count = self.search_count([('contract_id', '=', contract.id)])
                vals['visit_number'] = count + 1

        visits = super().create(vals_list)
        for visit in visits:
            visit._action_generate_report_document()
        return visits

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def _action_generate_report_document(self):
        self.ensure_one()
        if self.report_document_id or not self.folder_id:
            return

        report = self.env.ref('company_visit_tracker.action_report_company_visit')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)
        report_name = f'Visit Report - {self.name}.pdf'

        doc = self.env['visit.document'].create({
            'name': report_name,
            'folder_id': self.folder_id.id,
            'datas': base64.b64encode(pdf_content),
            'visit_id': self.id,
        })
        self.write({'report_document_id': doc.id})

    def action_print_report(self):
        return self.env.ref('company_visit_tracker.action_report_company_visit').report_action(self)

    def action_send_report_by_email(self):
        return {}

    def action_open_visit_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
