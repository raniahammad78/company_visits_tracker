# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t
from odoo.exceptions import UserError


class ExtraVisitWizard(models.TransientModel):
    """
    Wizard model to allow users to create extra visits manually for a given contract.
    This is a transient model, meaning records are temporary and automatically cleared.
    """
    _name = 'extra.visit.wizard'
    _description = 'Wizard to Create Extra Visits'

    # -----------------------------------------------------------
    # FIELDS
    # -----------------------------------------------------------

    contract_id = fields.Many2one(
        'visit.contract',
        string='Contract',
        required=True,
        help="Select the contract for which extra visits will be generated."
    )

    partner_id = fields.Many2one(
        related='contract_id.partner_id',
        string='Company',
        readonly=True,
        help="The company associated with the selected contract."
    )

    contract_folder_id = fields.Many2one(
        related='contract_id.folder_id',
        string='Contract Main Folder',
        readonly=True,
        help="The main folder of the contract where monthly subfolders reside."
    )

    month_folder_id = fields.Many2one(
        'visit.folder',
        string='Month Folder',
        required=True,
        domain="[('parent_id', '=', contract_folder_id)]",
        help="Select the specific month folder where the extra visits will be stored."
    )

    number_of_visits = fields.Integer(
        string='Number of Extra Visits',
        default=1,
        required=True,
        help="Enter the number of extra visits you want to create."
    )

    reason = fields.Text(
        string='Reason for Extra Visits',
        required=True,
        help="Provide a reason explaining why these extra visits are needed."
    )

    # -----------------------------------------------------------
    # METHODS
    # -----------------------------------------------------------

    def action_create_extra_visits(self):
        """
        Creates extra visit records for the selected contract and month folder.
        Each visit is linked to the contract, assigned to the chosen folder,
        and marked as an extra visit. Generates the corresponding PDF report.
        """
        self.ensure_one()  # Ensure only one wizard record is processed

        # Validation: Number of visits must be positive
        if self.number_of_visits <= 0:
            raise UserError(_t("The number of visits must be greater than zero."))

        visit_env = self.env['company.visit']

        # Loop to create the specified number of extra visits
        for i in range(self.number_of_visits):
            new_visit = visit_env.create({
                'contract_id': self.contract_id.id,
                'folder_id': self.month_folder_id.id,
                'visit_date': fields.Date.today(),
                'reason': self.reason,
                'is_extra_visit': True,  # Flag to indicate this visit is an extra one
            })

            # Generate the PDF report for the newly created visit
            if new_visit:
                new_visit._action_generate_report_document()

        # Close the wizard after creating visits
        return {'type': 'ir.actions.act_window_close'}
