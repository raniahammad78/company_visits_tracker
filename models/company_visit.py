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
        return super().create(vals_list)

    def action_mark_done(self):
        return self.write({'state': 'done'})

    def action_cancel(self):
        return self.write({'state': 'cancelled'})

    def _action_generate_report_document(self):
        return

    def action_print_report(self):
        return {}

    def action_send_report_by_email(self):
        return {}

    def action_open_visit_form(self):
        return {}