# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64


class CompanyVisit(models.Model):
    _name = 'company.visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Company Visit Record'

    name = fields.Char(string='Visit Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'))
    state = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', tracking=True)

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
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('company.visit') or _('New')
        visits = super().create(vals_list)
        return visits

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def _action_generate_report_document(self):
        self.ensure_one()
        if self.report_document_id:
            return

        report_action = self.env.ref('company_visit_tracker.action_report_company_visit')
        pdf_content, _ = report_action._render_qweb_pdf(report_ref='company_visit_tracker.action_report_company_visit',
                                                        res_ids=self.ids)

        report_name = f'Visit Report - {self.name}.pdf'

        # Ensure folder_id exists before creating document
        if not self.folder_id:
            return

        doc = self.env['visit.document'].create({
            'name': report_name,
            'folder_id': self.folder_id.id,
            'datas': base64.b64encode(pdf_content),
            'visit_id': self.id,
        })
        self.report_document_id = doc.id

    def action_print_report(self):
        self.ensure_one()
        if not self.report_document_id:
            self._action_generate_report_document()
        return self.env.ref('company_visit_tracker.action_report_company_visit').report_action(self)

    def action_send_report_by_email(self):
        """
        This opens a wizard to compose an email, with the visit report template message loaded.
        """
        self.ensure_one()
        if not self.report_document_id:
            self._action_generate_report_document()

        template_id = self.env.ref('company_visit_tracker.email_template_visit_report').id

        ctx = {
            'default_model': 'company.visit',
            'default_res_ids': self.ids,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'force_email': True,
            'lang': self.partner_id.lang or self.env.user.lang,
        }
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }

