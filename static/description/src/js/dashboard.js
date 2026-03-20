/** @odoo-module **/
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {Component, onWillStart, useState, useRef, onMounted, onPatched} from "@odoo/owl";
import {ConfirmationDialog} from "@web/core/confirmation_dialog/confirmation_dialog";
import {loadJS} from "@web/core/assets"; // FIXED: Correct import path for Odoo 18

export class VisitDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.dialog = useService("dialog");

        // NEW: Chart variables
        this.chartRef = useRef("statusChart");
        this.chartInstance = null;

        this.state = useState({
            date_filter: 'all',
            // NEW: State for the Quick Assign Modal
            assignModal: {open: false, reqId: null, model: null, reqName: '', engId: ''},
            data: {
                user_name: '',
                kpi: {total: 0, pending: 0, done: 0, cancelled: 0, extra: 0},
                engineers: [],
                recent_extras: [],
                available_engineers: []
            }
        });

        onWillStart(async () => {
            try {
                await loadJS("/web/static/lib/Chart/Chart.js"); // Load Odoo's charting library
            } catch (e) {
                console.error("Error loading Chart.js:", e);
            }
            await this.loadData();
        });

        // NEW: Draw the chart when page loads, and update it when data changes
        onMounted(() => this.renderChart());
        onPatched(() => this.renderChart());
    }

    async loadData() {
        try {
            const result = await this.orm.call("company.visit", "get_dashboard_stats", [this.state.date_filter]);
            if (result) {
                // THE FIX: Use Object.assign so we don't accidentally delete the OWL Proxy
                Object.assign(this.state.data, result);
            }
        } catch (error) {
            console.error("Backend failed to load data:", error);
        }
    }

    async setDateFilter(filter) {
        this.state.date_filter = filter;
        await this.loadData();
    }

    // === CHART.JS LOGIC ===
    renderChart() {
        if (!this.chartRef.el) return;
        const kpi = this.state.data.kpi;

        if (this.chartInstance) {
            this.chartInstance.destroy(); // Destroy old chart before drawing new one
        }

        this.chartInstance = new Chart(this.chartRef.el, {
            type: 'doughnut',
            data: {
                labels: ['Pending', 'Completed', 'Cancelled'],
                datasets: [{
                    data: [kpi.pending, kpi.done, kpi.cancelled],
                    backgroundColor: ['#f59e0b', '#22c55e', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {legend: {display: false}}
            }
        });
    }

    // === QUICK ASSIGN MODAL LOGIC ===
    openAssignModal(req) {
        this.state.assignModal = {
            open: true,
            reqId: req.id,
            model: req.model,
            reqName: req.name,
            engId: this.state.data.available_engineers.length > 0 ? this.state.data.available_engineers[0].id.toString() : ''
        };
    }

    closeModal() {
        this.state.assignModal.open = false;
    }

    async confirmAssign() {
        const modal = this.state.assignModal;
        if (!modal.engId) return;

        // Write directly to the database from the dashboard!
        await this.orm.write(modal.model, [modal.reqId], {
            assign_engineer_id: parseInt(modal.engId)
        });

        this.closeModal();
        await this.loadData(); // Instantly refresh the dashboard numbers
    }

    // === NAVIGATION LOGIC ===
    onSearchClick(domain, title) {
        this.dialog.add(ConfirmationDialog, {
            body: `Which visits would you like to view for "${title}"?`,
            confirmLabel: "Contracted", cancelLabel: "Non-Contracted",
            confirm: () => this.openVisits(domain, title + " (Contracted)", "company.visit"),
            cancel: () => this.openVisits(domain, title + " (Non-Contracted)", "not.contracted.visit"),
        });
    }

    openVisits(domain, title, model = "company.visit") {
        this.action.doAction({
            type: "ir.actions.act_window", name: title, res_model: model,
            views: [[false, "list"], [false, "form"]], domain: domain, target: "current",
        });
    }

    createNewVisit() {
        this.action.doAction({
            type: "ir.actions.act_window", name: "New Visit", res_model: "company.visit",
            views: [[false, "form"]], target: "current",
        });
    }

    openContracts() {
        this.action.doAction({
            type: "ir.actions.act_window", name: "Contracts", res_model: "visit.contract",
            views: [[false, "list"], [false, "form"]], target: "current",
        });
    }
}

VisitDashboard.template = "company_visit_tracker.VisitDashboard";
registry.category("actions").add("visit_dashboard_action", VisitDashboard);
