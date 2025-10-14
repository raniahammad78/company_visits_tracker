# -*- coding: utf-8 -*-
from odoo import models, fields, api, _ as _t


class SignRequest(models.Model):
    """
    This class extends the Odoo 'sign.request' model to link digital signature
    requests with both contracted and non-contracted company visit records.
    It ensures that when a signature process is completed, the corresponding
    visit is automatically marked as 'done'.
    """
    _inherit = 'sign.request'

    # ---------------------------------------------------------
    # New Relationship Fields
    # ---------------------------------------------------------

    company_visit_id = fields.Many2one(
        'company.visit',
        string='Related Contracted Visit',
        ondelete='set null',
        help="Links this signature request to a contracted company visit record."
    )

    not_contracted_visit_id = fields.Many2one(
        'not.contracted.visit',
        string='Related Non-Contracted Visit',
        ondelete='set null',
        help="Links this signature request to a non-contracted visit record."
    )

    # ---------------------------------------------------------
    # Actions
    # ---------------------------------------------------------

    def action_sent_and_close(self):
        """
        Override the default method that sends the signature request and closes it.
        Currently, it just calls the parent implementation, but it's overridden
        here in case we want to add custom behavior (e.g., logging or state tracking)
        in the future.
        """
        res = super(SignRequest, self).action_sent_and_close()
        return res

    def action_done(self):
        """
        Override the default 'action_done' method, which is triggered when
        a signature request is fully signed by all required parties.

        This method extends the default logic by marking the related visit
        record (contracted or non-contracted) as 'done' once the signature
        process is completed.

        This ensures full automation between the digital signing process
        and the company visit lifecycle.
        """
        # Call the parent method to preserve original behavior
        res = super(SignRequest, self).action_done()

        # Loop through each completed sign request record
        for record in self:
            # If the sign request is linked to a contracted visit, mark it as done
            if record.company_visit_id:
                record.company_visit_id.write({'state': 'done'})

            # If the sign request is linked to a non-contracted visit, mark it as done
            if record.not_contracted_visit_id:
                record.not_contracted_visit_id.write({'state': 'done'})

        # Return the result of the parent action
        return res
