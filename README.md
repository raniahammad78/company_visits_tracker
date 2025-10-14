
Company Visit Tracker (Odoo Module)

Overview

The Company Visit Tracker is a powerful Odoo module designed for service-based businesses that manage recurring client visits under contract. It automates the entire service lifecycle, from contract setup and scheduled visit generation to report documentation and client sign-off. This module introduces a novel, document-app-like folder structure for organizing all client reports, ensuring no visit detail is lost and making document retrieval instantaneous.


Key Features

This module provides a seamless, automated workflow for managing contracted services.

1. Automated Contract Lifecycle
   
Contract Definition: Define service contracts specifying the client, duration (start/end dates), and the required Visits Per Month. The system automatically calculates the total expected visits for the contract duration.

Scheduled Generation: A daily scheduled action (ir.cron) automatically runs to generate the required company.visit records for all active contracts for the current month.

Extra Visits: A dedicated wizard allows users to manually add non-scheduled, Extra Visits for a specific month and contract, which are clearly flagged in the system.

2. Document Management & Reporting
   
Automated Folder Structure: Upon activating a contract, the system automatically creates a main folder for the client and generates monthly sub-folders (e.g., "2025-03 (March)") spanning the contract duration.

Report Archiving: For every visit created, a "Service Call" PDF report is automatically generated and saved as a visit.document record, instantly linked to the correct monthly folder.

Intuitive Navigation: Navigate through reports using a clean, two-level Kanban interface (visit.folder) to go from Company Folder to Monthly Sub-folders.

3. Digital Signatures & Workflow Automation
   
Odoo Sign Integration: Users can send the visit report directly to the client via email for a digital signature using the integrated Odoo Sign module.

Status Sync: Once the client completes the digital signing process, the related visit record is automatically updated to the 'Done' status.

Signed Document Storage: The final, signed PDF document is saved back into the correct monthly document folder.

Status Tracking: Visits are tracked with clear workflow states: Pending, Done (completed), and Cancelled.

4. Non-Contracted Visits
   
The module supports tracking visits for companies that do not have an active service contract via a separate model (not.contracted.visit).

These one-off visits are organized under a distinct, shared root folder named "Not Contracted Visits," with monthly sub-folders also generated automatically.

5. Analytics and Visualization
   
All visit data is accessible through advanced Odoo views, including Calendar, Graph, and Pivot tables for detailed analysis of workload, schedules, and completion rates.


Company Visit Tracker (Odoo Module)
Overview
The Company Visit Tracker is a powerful Odoo module designed for service-based businesses that manage recurring client visits under contract. It automates the entire service lifecycle, from contract setup and scheduled visit generation to report documentation and client sign-off. This module introduces a novel, document-app-like folder structure for organizing all client reports, ensuring no visit detail is lost and making document retrieval instantaneous.

Module Metadata
Field	Value	Source
Odoo Version	18.0	
Module Version	18.0.2.0.0	
Author	RANIA HAMMAD	
Category	Services/Project	
License	LGPL-3	

Export to Sheets
Key Features
This module provides a seamless, automated workflow for managing contracted services.

1. Automated Contract Lifecycle
Contract Definition: Define service contracts specifying the client, duration (start/end dates), and the required Visits Per Month. The system automatically calculates the total expected visits for the contract duration.

Scheduled Generation: A daily scheduled action (ir.cron) automatically runs to generate the required company.visit records for all active contracts for the current month.

Extra Visits: A dedicated wizard allows users to manually add non-scheduled, Extra Visits for a specific month and contract, which are clearly flagged in the system.

2. Document Management & Reporting
Automated Folder Structure: Upon activating a contract, the system automatically creates a main folder for the client and generates monthly sub-folders (e.g., "2025-03 (March)") spanning the contract duration.

Report Archiving: For every visit created, a "Service Call" PDF report is automatically generated and saved as a visit.document record, instantly linked to the correct monthly folder.

Intuitive Navigation: Navigate through reports using a clean, two-level Kanban interface (visit.folder) to go from Company Folder to Monthly Sub-folders.

3. Digital Signatures & Workflow Automation
Odoo Sign Integration: Users can send the visit report directly to the client via email for a digital signature using the integrated Odoo Sign module.

Status Sync: Once the client completes the digital signing process, the related visit record is automatically updated to the 'Done' status.

Signed Document Storage: The final, signed PDF document is saved back into the correct monthly document folder.

Status Tracking: Visits are tracked with clear workflow states: Pending, Done (completed), and Cancelled.

4. Non-Contracted Visits
The module supports tracking visits for companies that do not have an active service contract via a separate model (not.contracted.visit).

These one-off visits are organized under a distinct, shared root folder named "Not Contracted Visits," with monthly sub-folders also generated automatically.

5. Analytics and Visualization
All visit data is accessible through advanced Odoo views, including Calendar, Graph, and Pivot tables for detailed analysis of workload, schedules, and completion rates.

Usage and Configuration

Create a Contract: Navigate to Visit Tracker > Contracts and create a new Visit Contract. Define the Company, Start Date, End Date, and Visits Per Month.

Start Contract: Click the Start Contract button to move the state from Draft to In Progress. This action automatically creates the root folder and all monthly sub-folders for the duration of the contract.

Visit Generation:

Automatic: The system will automatically create the scheduled number of visits and their PDF reports daily.

Manual: You can manually generate the current month's visits at any time by clicking Generate Current Month's Visits on the contract form.

Extra Visits: Use the Add Extra Visits button to launch a wizard for creating one-off visits for a specific month.

Process a Visit:

Find the visit under Visit Tracker > Document Folders (Kanban view) or Visit Tracker > All Visits (List/Calendar view).

Fill in the Type of Problem and Engineer Comments.

Click Request Signature to send the PDF report to the client's email for digital sign-off.

Once signed, the visit status will automatically change to Done.
