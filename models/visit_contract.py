# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _ as _t
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class VisitContract(models.Model):
    """
    The VisitContract model represents a service agreement between a company and a client.
    Each contract defines:
        - A client (partner)
        - A date range (start to end)
        - A specific number of scheduled visits per month

    When a contract is activated, a folder structure is automatically created under `visit.folder`,
    containing one subfolder per month for organizing visit reports and documents.
    The system can then generate visits automatically every month or manually on demand.
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
        """
        Counts how many company visits are linked to this contract.
        """
        for contract in self:
            contract.visits_count = self.env['company.visit'].search_count([('contract_id', '=', contract.id)])

    @api.depends('start_date', 'end_date', 'visits_per_month')
    def _compute_total_contract_visits(self):
        """
        Calculates the total expected number of visits during the contract period.
        Formula:
            number of months * visits per month
        """
        for contract in self:
            if contract.start_date and contract.end_date:
                delta = relativedelta(contract.end_date, contract.start_date)
                months_count = delta.years * 12 + delta.months + 1
                contract.total_contract_visits = months_count * contract.visits_per_month
            else:
                contract.total_contract_visits = 0

    # ---------------------------------------------------------
    # Contract Workflow Actions
    # ---------------------------------------------------------

    def action_start_contract(self):
        """
        Starts the contract:
            - Only allowed from 'draft' state.
            - Automatically creates a folder structure for each month
              between start_date and end_date under 'visit.folder'.
            - Sets the state to 'in_progress'.
        """
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_t("The contract must be in a draft state to start it."))

        # Create the main folder with subfolders for each contract month
        if not self.folder_id:
            child_folders_vals = []
            delta = relativedelta(self.end_date, self.start_date)
            total_months = delta.years * 12 + delta.months

            # Generate monthly folder names (e.g., "2025-03 (March)")
            for i in range(total_months + 1):
                current_date = self.start_date + relativedelta(months=i)
                if current_date > self.end_date:
                    break
                folder_name = current_date.strftime('%Y-%m (%B)')
                child_folders_vals.append((0, 0, {'name': folder_name}))

            # Create main folder with child folders
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
        """
        Manually triggers visit generation for the current month only.
        Uses the same logic as the scheduled cron method.
        Returns a visual notification indicating whether visits were created or not.
        """
        visits_created_count = self._cron_generate_monthly_visits(specific_contracts=self)

        if visits_created_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _t('Success'),
                    'message': _t(f'{visits_created_count} visits have been generated for the current month.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _t('Info'),
                    'message': _t('Visits for the current month have already been generated.'),
                    'type': 'info',
                    'sticky': False,
                }
            }

    @api.model
    def _cron_generate_monthly_visits(self, specific_contracts=None):
        """
        Scheduled task (cron) or manual call to generate visits automatically each month.

        Logic:
            - Finds all 'in_progress' contracts (or the given ones if specified)
            - Finds the current month's folder under each contract's main folder
            - If no visits exist for this month, creates the number of visits defined
              in 'visits_per_month'
            - Generates a visit report document for each created visit

        Returns:
            int: The total number of visits created
        """
        if specific_contracts:
            contracts = specific_contracts
        else:
            contracts = self.search([('state', '=', 'in_progress')])

        today = fields.Date.today()
        current_month_str = today.strftime('%Y-%m')
        visits_created_total = 0

        for contract in contracts:
            # Skip if no folder was created for this contract
            if not contract.folder_id:
                continue

            # Find the folder for the current month
            month_folder = self.env['visit.folder'].search([
                ('parent_id', '=', contract.folder_id.id),
                ('name', 'like', f'{current_month_str}%')
            ], limit=1)

            if not month_folder:
                continue

            # Check if visits for this month already exist
            existing_visits = self.env['company.visit'].search_count([
                ('contract_id', '=', contract.id),
                ('folder_id', '=', month_folder.id)
            ])

            # If no visits exist, generate new ones
            if existing_visits == 0:
                for i in range(contract.visits_per_month):
                    visit = self.env['company.visit'].create({
                        'contract_id': contract.id,
                        'visit_date': today,
                        'folder_id': month_folder.id,
                    })

                    # Generate the report document for the new visit
                    if visit and visit.folder_id:
                        visit._action_generate_report_document()
                    else:
                        _logger.warning(f"Failed to create visit with folder link for contract {contract.name}")

                visits_created_total += contract.visits_per_month

        return visits_created_total

    # ---------------------------------------------------------
    # Navigation & UI Actions
    # ---------------------------------------------------------

    def action_open_visits(self):
        """
        Opens a window showing all visits related to this contract.
        Includes multiple view modes (list, form, calendar, graph, pivot).
        """
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
        """
        Opens a pop-up (wizard) to manually add extra visits to the contract.
        """
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
