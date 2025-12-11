# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _ as _t
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import datetime

_logger = logging.getLogger(__name__)


class VisitContract(models.Model):
    """
    The VisitContract model represents a service agreement between a company and a client.
    """
    _name = 'visit.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Visit Contract'

    # ---------------------------------------------------------
    # Basic Contract Information
    # ---------------------------------------------------------
    name = fields.Char(
        string='Contract Name',
        required=True,
        help="Name of the contract, usually identifying the client or contract type."
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        required=True,
        help="The client company this contract belongs to."
    )

    # Responsible Person (Receives reminders)
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        required=True,
        help="The user responsible for this contract. They will receive expiry reminders."
    )

    start_date = fields.Date(
        string='Start Date',
        required=True,
        help="The start date of the service contract period."
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        help="The end date of the service contract period."
    )
    visits_per_month = fields.Integer(
        string='Visits Per Month',
        default=1,
        required=True,
        help="Defines how many visits should be generated automatically per month."
    )

    # Note / Description Field (Fixes the XML error)
    description = fields.Html(
        string='Terms and Notes',
        help="Internal notes or terms regarding this contract."
    )

    # Preferred Visit Days
    visit_on_mon = fields.Boolean(string='Mon', default=False)
    visit_on_tue = fields.Boolean(string='Tue', default=False)
    visit_on_wed = fields.Boolean(string='Wed', default=False)
    visit_on_thu = fields.Boolean(string='Thu', default=False)
    visit_on_fri = fields.Boolean(string='Fri', default=False)
    visit_on_sat = fields.Boolean(string='Sat', default=False)
    visit_on_sun = fields.Boolean(string='Sun', default=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ],
        string='Status',
        default='draft',
        tracking=True,
        help="Workflow state of the contract."
    )

    # ---------------------------------------------------------
    # Folder & Visit Information
    # ---------------------------------------------------------
    folder_id = fields.Many2one(
        'visit.folder',
        string='Main Folder',
        readonly=True,
        copy=False,
        help="Root folder created automatically for this contract to store monthly visit reports."
    )
    visits_count = fields.Integer(
        string='Generated Visits',
        compute='_compute_visits_count',
        help="Total number of visits already generated under this contract."
    )
    total_contract_visits = fields.Integer(
        string="Total Visits in Contract",
        compute='_compute_total_contract_visits',
        store=True,
        help="Computed total number of visits based on duration and monthly frequency."
    )

    # ---------------------------------------------------------
    # Compute Methods
    # ---------------------------------------------------------

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

    def _get_visit_dates_for_month(self, target_date, required_visits):
        """Calculates specific dates for visits based on preferred weekdays."""
        self.ensure_one()
        preferred_weekdays = []
        if self.visit_on_mon: preferred_weekdays.append(0)
        if self.visit_on_tue: preferred_weekdays.append(1)
        if self.visit_on_wed: preferred_weekdays.append(2)
        if self.visit_on_thu: preferred_weekdays.append(3)
        if self.visit_on_fri: preferred_weekdays.append(4)
        if self.visit_on_sat: preferred_weekdays.append(5)
        if self.visit_on_sun: preferred_weekdays.append(6)

        if not preferred_weekdays or required_visits <= 0:
            return [target_date] * required_visits

        potential_dates = []
        current_iter_date = target_date.replace(day=1)
        next_month = current_iter_date + relativedelta(months=1)
        last_day_of_month = next_month - relativedelta(days=1)

        while current_iter_date <= last_day_of_month:
            if current_iter_date.weekday() in preferred_weekdays:
                potential_dates.append(current_iter_date)
            current_iter_date += relativedelta(days=1)

        if not potential_dates:
            return [target_date] * required_visits

        final_dates = []
        potential_count = len(potential_dates)
        for i in range(required_visits):
            date_index = i % potential_count
            final_dates.append(potential_dates[date_index])

        final_dates.sort()
        return final_dates

    # ---------------------------------------------------------
    # Contract Workflow Actions
    # ---------------------------------------------------------

    def action_start_contract(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_t("The contract must be in a draft state to start it."))

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

    # ---------------------------------------------------------
    # Visit Generation Methods
    # ---------------------------------------------------------

    def action_generate_current_month_visits(self):
        visits_created_count = self._cron_generate_monthly_visits(specific_contracts=self)
        if visits_created_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': _t('Success'), 'message': _t(f'{visits_created_count} visits generated.'),
                           'type': 'success', 'sticky': False}
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': _t('Info'), 'message': _t('Visits already generated.'), 'type': 'info',
                           'sticky': False}
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
            if not contract.folder_id: continue

            month_folder = self.env['visit.folder'].search([
                ('parent_id', '=', contract.folder_id.id),
                ('name', 'like', f'{current_month_str}%')
            ], limit=1)

            if not month_folder: continue

            existing_visits = self.env['company.visit'].search_count([
                ('contract_id', '=', contract.id),
                ('folder_id', '=', month_folder.id)
            ])

            if existing_visits == 0:
                calculated_dates = contract._get_visit_dates_for_month(today, contract.visits_per_month)
                for visit_date in calculated_dates:
                    visit = self.env['company.visit'].create({
                        'contract_id': contract.id,
                        'visit_date': visit_date,
                        'folder_id': month_folder.id,
                    })
                    if visit and visit.folder_id:
                        visit._action_generate_report_document()
                visits_created_total += len(calculated_dates)

        return visits_created_total

    # ---------------------------------------------------------
    # Cron: Contract Expiry Reminder (Daily Check)
    # ---------------------------------------------------------
    @api.model
    def _cron_contract_expiry_reminder(self):
        """
        Runs daily. Checks for contracts expiring in exactly 1 MONTH.
        Creates a 'To Do' activity for the responsible user.
        """
        today = fields.Date.today()
        target_expiry_date = today + relativedelta(months=1)

        expiring_contracts = self.search([
            ('state', '=', 'in_progress'),
            ('end_date', '=', target_expiry_date)
        ])

        for contract in expiring_contracts:
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=contract.user_id.id,
                note=f"This contract expires on {contract.end_date}. Please contact the client for renewal.",
                summary="Contract Expiring in 1 Month"
            )
            _logger.info(f"Created expiry reminder for contract {contract.name}")

    # ---------------------------------------------------------
    # Navigation Actions
    # ---------------------------------------------------------

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
