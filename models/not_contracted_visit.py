# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import base64


class NotContractedVisit(models.Model):
    _name = 'not.contracted.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Visit for Not Contracted Companies'

    name = fields.Char(string='Visit Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    partner_id = fields.Many2one('res.partner', string='Company', required=True)
    state = fields.Selection([('pending', 'Pending'), ('done', 'Done'), ('cancelled', 'Cancelled')], string='Status',
                             default='pending', tracking=True)
    visit_date = fields.Date(string='Visit Date', default=fields.Date.context_today)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    assign_engineer_id = fields.Many2one('res.users', string='Assigned Engineer', default=lambda self: self.env.user)
    reason = fields.Char(string="Type of Problem")
    description = fields.Text(string="Engineer Comments")
    partner_address = fields.Char(string="Visit Address")
    engineer_signature = fields.Binary(string="Engineer Signature")
    client_signature = fields.Binary(string="Client Signature")
    report_document_id = fields.Many2one('visit.document', string="Generated Report", readonly=True, copy=False)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_address = self.partner_id.contact_address_complete

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
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

    def _action_generate_report_document(self):
        self.ensure_one()
        if self.report_document_id:
            return

        # Get main folder
        main_folder = self.env.ref('company_visit_tracker.folder_not_contracted_visits')

        # Determine and format the month folder name
        visit_date = self.visit_date or fields.Date.today()
        folder_name = visit_date.strftime('%Y-%m (%B)')

        # Search for existing month folder
        month_folder = self.env['visit.folder'].search([
            ('name', '=', folder_name),
            ('parent_id', '=', main_folder.id)
        ], limit=1)

        # If not found, create it
        if not month_folder:
            month_folder = self.env['visit.folder'].create({
                'name': folder_name,
                'parent_id': main_folder.id,
            })

        report = self.env.ref('company_visit_tracker.action_report_not_contracted_visit')
        pdf_content, _ = report._render_qweb_pdf(report.report_name, self.ids)
        report_name = f'Visit Report - {self.partner_id.name} - {self.visit_date}.pdf'

        doc = self.env['visit.document'].create({
            'name': report_name,
            'folder_id': month_folder.id,  # Use the month_folder's ID
            'datas': base64.b64encode(pdf_content),
            'not_contracted_visit_id': self.id,
        })
        self.write({'report_document_id': doc.id})

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('company_visit_tracker.action_report_not_contracted_visit').report_action(self)

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})