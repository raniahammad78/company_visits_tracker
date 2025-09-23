# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ExtraVisitWizard(models.TransientModel):
    _name = 'extra.visit.wizard'
    _description = 'Wizard to Create Extra Visits'

    contract_id = fields.Many2one('visit.contract', string='Contract', required=True)
    partner_id = fields.Many2one(related='contract_id.partner_id')

    month_folder_id = fields.Many2one(
        'visit.folder',
        string='Month Folder',
        required=True,
        domain="[('parent_id', '=', contract_folder_id)]"
    )
    contract_folder_id = fields.Many2one(related='contract_id.folder_id')

    number_of_visits = fields.Integer(string='Number of Extra Visits', default=1, required=True)
    reason = fields.Text(string='Reason for Extra Visits', required=True)

    def action_create_extra_visits(self):
        self.ensure_one()
        if self.number_of_visits <= 0:
            raise UserError(_("The number of visits must be greater than zero."))

        visit_env = self.env['company.visit']
        for i in range(self.number_of_visits):
            new_visit = visit_env.create({
                'contract_id': self.contract_id.id,
                'folder_id': self.month_folder_id.id,
                'visit_date': fields.Date.today(),
                'reason': self.reason,
                'is_extra_visit': True,
            })
            if new_visit:
                new_visit._action_generate_report_document()

        return {'type': 'ir.actions.act_window_close'}