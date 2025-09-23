# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class VisitContract(models.Model):
    _name = 'visit.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Visit Contract'

    name = fields.Char(string='Contract Name', required=True)
    partner_id = fields.Many2one('res.partner', string='Company', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    visits_per_month = fields.Integer(string='Visits Per Month', default=1, required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    folder_id = fields.Many2one('visit.folder', string='Main Folder', readonly=True, copy=False)
    visits_count = fields.Integer(string='Generated Visits', compute='_compute_visits_count')
    total_contract_visits = fields.Integer(string="Total Visits in Contract", compute='_compute_total_contract_visits', store=True)

    def _compute_visits_count(self):
        for contract in self:
            contract.visits_count = self.env['company.visit'].search_count([('contract_id', '=', contract.id)])

    @api.depends('start_date', 'end_date', 'visits_per_month')
    def _compute_total_contract_visits(self):
        for contract in self:
            if contract.start_date and contract.end_date:
                delta = relativedelta(contract.end_date, contract.start_date)
                months_count = delta.years * 12 + delta.months + 1
                contract.total_contract_visits = months_count * contract.visits_per_month
            else:
                contract.total_contract_visits = 0

    def action_start_contract(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_("The contract must be in a draft state to start it."))

        if not self.folder_id:
            child_folders_vals = []
            delta = relativedelta(self.end_date, self.start_date)
            total_months = delta.years * 12 + delta.months

            for i in range(total_months + 1):
                current_date = self.start_date + relativedelta(months=i)
                if current_date > self.end_date:
                    break
                folder_name = current_date.strftime('%Y-%m (%B)')
                child_folders_vals.append((0, 0, {'name': folder_name}))

            main_folder = self.env['visit.folder'].create({
                'name': self.partner_id.name,
                'child_folder_ids': child_folders_vals,
            })
            self.folder_id = main_folder.id

        self.state = 'in_progress'

    def action_generate_current_month_visits(self):
        visits_created_count = self._cron_generate_monthly_visits(specific_contracts=self)
        if visits_created_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': f'{visits_created_count} visits have been generated for the current month.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Info'),
                    'message': _('Visits for the current month have already been generated.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

    @api.model
    def _cron_generate_monthly_visits(self, specific_contracts=None):
        if specific_contracts:
            contracts = specific_contracts
        else:
            contracts = self.search([('state', '=', 'in_progress')])

        today = fields.Date.today()
        current_month_str = today.strftime('%Y-%m')
        visits_created_total = 0

        for contract in contracts:
            if not contract.folder_id:
                continue

            month_folder = self.env['visit.folder'].search([
                ('parent_id', '=', contract.folder_id.id),
                ('name', 'like', f'{current_month_str}%')
            ], limit=1)

            if not month_folder:
                continue

            existing_visits = self.env['company.visit'].search_count([
                ('contract_id', '=', contract.id),
                ('folder_id', '=', month_folder.id)
            ])

            if existing_visits == 0:
                for i in range(contract.visits_per_month):
                    visit = self.env['company.visit'].create({
                        'contract_id': contract.id,
                        'visit_date': today,
                        'folder_id': month_folder.id,
                    })
                    if visit and visit.folder_id:
                        visit._action_generate_report_document()
                    else:
                        _logger.warning(f"Failed to create visit with folder link for contract {contract.name}")
                visits_created_total += contract.visits_per_month
        return visits_created_total

    def action_open_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generated Visits',
            'res_model': 'company.visit',
            'view_mode': 'list,form,calendar,graph,pivot',
            'domain': [('contract_id', '=', self.id)],
            'target': 'current',
        }

    def action_open_extra_visit_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Extra Visits',
            'res_model': 'extra.visit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
            }
        }