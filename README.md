Company Visit Tracker Odoo Module
Overview

The Company Visit Tracker is an Odoo 18 module designed to manage, automate, and track company service visits. It supports both contracted visits (based on agreements) and non-contracted ad-hoc visits, ensuring all customer interactions are recorded and properly documented.

The module automates contract creation, folder structures, visit records, and professional reporting—while providing managers and engineers with clear views and status tracking.

This is ideal for service-based businesses that need recurring contract visits and the ability to log extra or ad-hoc visits with ease.

Key Features
🔹 Core Functionality

Automated Folder Structure

Creates a main folder per company contract.

Generates monthly sub-folders for the contract’s duration.

Stores visit reports inside the correct monthly folder.

Automated Visit & Report Generation

Creates visits per contract terms (e.g., 8 visits per month).

Generates placeholder PDF reports for each visit.

Auto-links visits to their monthly folder.

Professional PDF Reports

Standardized reports for each visit.

Includes engineer notes, reason, and digital signatures.

Intuitive Navigation (Kanban Folders)

Two-level Kanban view: Contract folders → Monthly sub-folders.

Quick access to all visit documents.

Status Tracking

Visits marked as Pending, Done, or Cancelled.

Status shown with color-coded badges.

Advanced Views

Supports List, Calendar, Kanban, Pivot, and Graph views for easy planning and analysis.

🔹 Extended Functionality

Not Contracted Visits

Log ad-hoc visits outside a contract.

Capture client, reason, visit date, engineer, and signatures.

Store documents in dedicated non-contracted folders.

Extra Visit Wizard

Add extra visits in addition to contracted ones.

User-friendly wizard to select month folder, number of visits, and reason.

Reports automatically generated and stored correctly.

Signature Support

Both engineer and client can digitally sign visit reports.

Stored securely inside the visit report.

Direct Emailing (planned)

Reports can be sent directly to the client by email.

Role-Based Security

Access rights defined for managing contracts, visits, and reports.

Installation

Place the company_visit_tracker folder into your Odoo addons directory.

Restart your Odoo server.

Navigate to Apps, click Update Apps List, and remove the Apps filter.

Search for Company Visit Tracker and click Install.

Configuration & Usage

Set Company Logo

Navigate to: Settings > Companies > Your Company

Upload logo for branded reports.

Create a Contract

Go to: Visit Tracker > Contracts.

Add client, contract period, and visits per month.

Start the Contract

Click Start Contract → Auto-creates company folder + monthly sub-folders.

Generate Visits

Click Generate Current Month’s Visits → Creates visits and placeholder reports.

Manage Visits

Navigate to: Visit Tracker > Document Folders to browse reports.

Or: Visit Tracker > All Visits to see them in the Calendar or List view.

Add Extra Visits

Use "Add Extra Visits" wizard to log additional visits beyond contract limits.

Handle Not-Contracted Visits

Go to Visit Tracker > Not Contracted Company

Log details and generate standalone reports.