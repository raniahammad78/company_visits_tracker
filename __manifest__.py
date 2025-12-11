# -*- coding: utf-8 -*-
{
    'name': "Company Visit Tracker",
    'summary': """
        Manage and track contracted company visits, automatically organizing 
        reports into a custom folder structure for each client.""",
    'description': """
        This module provides a complete solution for service companies that perform regular visits to their clients based on contracts.

        Features:
        - Modern Kanban UI for folder navigation, similar to the Documents App.
        - Define visit contracts with start/end dates and visit frequency.
        - Automatically creates a dedicated folder for each contracted company.
        - Automatically generates sub-folders for each month of the contract's duration.
        - A scheduled action runs daily to create visit records based on the contract terms.
        - For each visit created, a placeholder PDF report is generated and placed in the correct company/month folder.
        - Provides a clean, document-app-like interface to browse visit reports.
    """,
    'author': "RANIA HAMMAD",
    'category': 'Services/Project',
    'version': '18.0.2.0.0',
    'sequence': 1,
    'depends': ['base', 'mail', 'portal', 'web', 'sign', 'account', 'web_gantt'],
    'data': [
        "views/dashboard_action.xml",
        "reports/not_contracted_report_template.xml",
        "data/folder_data.xml",
        "reports/not_contracted_report.xml",
        "views/not_contracted_visit_views.xml",
        "wizards/extra_visit_wizard_views.xml",
        "security/security.xml",
        "views/menus.xml",
        "views/visit_folder_views.xml",
        "views/company_visit_views.xml",
        "views/ visit_contract_views.xml",
        "data/ ir_sequence_data.xml",
        "data/ir_cron_data.xml",
        "reports/visit_report_template.xml",
        "reports/visit_report.xml",
        "security/ir.model.access.csv",
    ],
    'assets': {
        'web.assets_backend': [
            'company_visit_tracker/static/src/dashboard/visit_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
