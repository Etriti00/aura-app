"""
Aura — Dashboard Page (Premium Design)
Stats overview, pipeline funnel, A/B results, recent campaigns.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPushButton, QFrame, QScrollArea, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor

from ui.components.glass_card import GlassCard, StatCard
from ui.components.empty_state import EmptyState
from ui.icons import get_icon, get_pixmap


class DashboardPage(QWidget):
    """Dashboard page — campaign overview and analytics."""

    export_requested = Signal(str)  # "pdf" or "csv"
    triage_requested = Signal()     # run morning triage

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # Main layout for the page (contains the scroll area)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setObjectName("dashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Content Widget
        content = QWidget()
        content.setObjectName("centralWidget")  # Ensure it picks up background theme
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Header
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        title = QLabel("Dashboard")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Your campaign performance at a glance")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, stretch=1)

        # Export buttons
        export_pdf_btn = QPushButton("Export PDF")
        export_pdf_btn.setIcon(get_icon("export_pdf", "dark"))
        export_pdf_btn.setIconSize(QSize(16, 16))
        export_pdf_btn.setObjectName("exportButton")
        export_pdf_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_pdf_btn.clicked.connect(lambda: self.export_requested.emit("pdf"))
        header.addWidget(export_pdf_btn)

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.setIcon(get_icon("export_csv", "dark"))
        export_csv_btn.setIconSize(QSize(16, 16))
        export_csv_btn.setObjectName("exportButtonSuccess")
        export_csv_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_csv_btn.clicked.connect(lambda: self.export_requested.emit("csv"))
        header.addWidget(export_csv_btn)

        layout.addLayout(header)

        # Stat cards grid — 3 columns x 2 rows for responsive layout
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.total_campaigns_card = StatCard("0", "CAMPAIGNS", accent="blue", variant="default")
        stats_grid.addWidget(self.total_campaigns_card, 0, 0)

        self.total_leads_card = StatCard("0", "TOTAL LEADS", accent="blue", variant="solid")
        stats_grid.addWidget(self.total_leads_card, 0, 1)

        self.qualified_card = StatCard("0", "QUALIFIED", accent="purple", variant="solid")
        stats_grid.addWidget(self.qualified_card, 0, 2)

        self.emailed_card = StatCard("0", "EMAILED", accent="pink", variant="solid")
        stats_grid.addWidget(self.emailed_card, 1, 0)

        self.replied_card = StatCard("0", "REPLIED", accent="orange", variant="default")
        stats_grid.addWidget(self.replied_card, 1, 1)

        self.conversion_card = StatCard("0%", "CONVERSION", accent="cyan", variant="default")
        stats_grid.addWidget(self.conversion_card, 1, 2)

        layout.addLayout(stats_grid)

        # Pipeline funnel card
        funnel_card = GlassCard()
        funnel_layout = funnel_card.get_layout()

        funnel_header = QLabel("Pipeline Funnel")
        funnel_header.setObjectName("cardHeader")
        funnel_layout.addWidget(funnel_header)

        self.funnel_bars = {}
        stages = ["Scraped", "New", "Qualified", "Emailed"]
        for stage_name in stages:
            row = QHBoxLayout()
            row.setSpacing(12)

            label = QLabel(stage_name)
            label.setFixedWidth(80)
            label.setObjectName("formLabel")
            row.addWidget(label)

            bar_bg = QWidget()
            bar_bg.setObjectName("funnelBarBg")
            bar_bg.setFixedHeight(28)
            bar_inner = QWidget(bar_bg)
            bar_inner.setObjectName("funnelBar")
            bar_inner.setFixedHeight(28)
            bar_inner.setGeometry(0, 0, 4, 28)
            row.addWidget(bar_bg, stretch=1)

            count_label = QLabel("0")
            count_label.setFixedWidth(50)
            count_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(count_label)

            funnel_layout.addLayout(row)
            self.funnel_bars[stage_name.lower()] = (bar_bg, bar_inner, count_label)

        layout.addWidget(funnel_card)

        # ─── A/B Testing Results ───────────────────────────────────────
        ab_card = GlassCard()
        ab_layout = ab_card.get_layout()
        ab_header = QHBoxLayout()
        ab_icon = QLabel()
        ab_icon.setPixmap(get_pixmap("ab_test", "dark", "accent", 16))
        ab_icon.setFixedSize(20, 20)
        ab_title = QLabel("A/B Test Results")
        ab_title.setObjectName("cardHeader")
        ab_header.addWidget(ab_icon)
        ab_header.addWidget(ab_title, stretch=1)
        ab_layout.addLayout(ab_header)

        ab_row = QHBoxLayout()
        ab_row.setSpacing(14)

        # Variant A card
        self.ab_a_card = QFrame()
        self.ab_a_card.setObjectName("abCardA")
        a_layout = QVBoxLayout(self.ab_a_card)
        a_layout.setSpacing(6)
        a_layout.setContentsMargins(14, 14, 14, 14)
        ab_a_row = QHBoxLayout()
        ab_a_dot = QLabel()
        ab_a_dot.setPixmap(get_pixmap("variant_marker", "dark", "accent", 10))
        ab_a_dot.setFixedSize(14, 14)
        self.ab_a_label = QLabel("Variant A")
        self.ab_a_label.setObjectName("abVariantA")
        ab_a_row.addWidget(ab_a_dot)
        ab_a_row.addWidget(self.ab_a_label)
        ab_a_row.addStretch()
        a_layout.addLayout(ab_a_row)
        self.ab_a_stats = QLabel("Sends: 0  ·  Opens: 0  ·  Replies: 0")
        self.ab_a_stats.setObjectName("abStats")
        a_layout.addWidget(self.ab_a_stats)
        ab_row.addWidget(self.ab_a_card)

        # Variant B card
        self.ab_b_card = QFrame()
        self.ab_b_card.setObjectName("abCardB")
        b_layout = QVBoxLayout(self.ab_b_card)
        b_layout.setSpacing(6)
        b_layout.setContentsMargins(14, 14, 14, 14)
        ab_b_row = QHBoxLayout()
        ab_b_dot = QLabel()
        ab_b_dot.setPixmap(get_pixmap("variant_marker", "dark", "accent", 10))
        ab_b_dot.setFixedSize(14, 14)
        self.ab_b_label = QLabel("Variant B")
        self.ab_b_label.setObjectName("abVariantB")
        ab_b_row.addWidget(ab_b_dot)
        ab_b_row.addWidget(self.ab_b_label)
        ab_b_row.addStretch()
        b_layout.addLayout(ab_b_row)
        self.ab_b_stats = QLabel("Sends: 0  ·  Opens: 0  ·  Replies: 0")
        self.ab_b_stats.setObjectName("abStats")
        b_layout.addWidget(self.ab_b_stats)
        ab_row.addWidget(self.ab_b_card)

        ab_layout.addLayout(ab_row)
        layout.addWidget(ab_card)

        # ─── Model Usage Card ───────────────────────────────────────
        usage_card = GlassCard()
        usage_layout = usage_card.get_layout()
        usage_header = QLabel("Model Usage (This Month)")
        usage_header.setObjectName("cardHeader")
        usage_layout.addWidget(usage_header)

        # Tier rows: local, ollama, haiku, sonnet, plus external APIs
        self.usage_rows = {}
        for tier_name in ["Local", "Ollama", "Haiku", "Sonnet", "Apollo", "Hunter"]:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl = QLabel(tier_name)
            lbl.setFixedWidth(70)
            lbl.setObjectName("formLabel")
            row.addWidget(lbl)

            calls_lbl = QLabel("0 calls")
            calls_lbl.setFixedWidth(80)
            calls_lbl.setObjectName("mutedText")
            row.addWidget(calls_lbl)

            cost_lbl = QLabel("$0.00")
            cost_lbl.setFixedWidth(70)
            cost_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(cost_lbl)

            row.addStretch()
            usage_layout.addLayout(row)
            self.usage_rows[tier_name.lower()] = (calls_lbl, cost_lbl)

        # Total cost summary
        total_row = QHBoxLayout()
        total_row.setSpacing(12)
        total_label = QLabel("Total")
        total_label.setObjectName("formLabel")
        total_label.setFixedWidth(70)
        total_row.addWidget(total_label)
        self.usage_total_calls = QLabel("0 calls")
        self.usage_total_calls.setFixedWidth(80)
        total_row.addWidget(self.usage_total_calls)
        self.usage_total_cost = QLabel("$0.00")
        self.usage_total_cost.setFixedWidth(70)
        self.usage_total_cost.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_row.addWidget(self.usage_total_cost)
        total_row.addStretch()
        usage_layout.addLayout(total_row)

        layout.addWidget(usage_card)

        # ─── Morning Triage Card ──────────────────────────────────
        triage_card = GlassCard()
        triage_layout = triage_card.get_layout()

        triage_header_row = QHBoxLayout()
        triage_header = QLabel("This Morning")
        triage_header.setObjectName("cardHeader")
        triage_header_row.addWidget(triage_header, stretch=1)

        self.triage_run_btn = QPushButton("Run Triage Now")
        self.triage_run_btn.setObjectName("primaryButton")
        self.triage_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.triage_run_btn.setFixedHeight(32)
        self.triage_run_btn.clicked.connect(self.triage_requested.emit)
        triage_header_row.addWidget(self.triage_run_btn)
        triage_layout.addLayout(triage_header_row)

        # Triage stats row
        triage_stats_row = QHBoxLayout()
        triage_stats_row.setSpacing(20)

        self.triage_total_lbl = QLabel("Emails: --")
        self.triage_total_lbl.setObjectName("formLabel")
        triage_stats_row.addWidget(self.triage_total_lbl)

        self.triage_replies_lbl = QLabel("Replies: --")
        self.triage_replies_lbl.setObjectName("formLabel")
        triage_stats_row.addWidget(self.triage_replies_lbl)

        self.triage_bounces_lbl = QLabel("Bounces: --")
        self.triage_bounces_lbl.setObjectName("formLabel")
        triage_stats_row.addWidget(self.triage_bounces_lbl)

        self.triage_unsubs_lbl = QLabel("Unsubs: --")
        self.triage_unsubs_lbl.setObjectName("formLabel")
        triage_stats_row.addWidget(self.triage_unsubs_lbl)

        triage_stats_row.addStretch()
        triage_layout.addLayout(triage_stats_row)

        # Triage summary text
        self.triage_summary_lbl = QLabel("Run triage to see your morning briefing.")
        self.triage_summary_lbl.setObjectName("mutedText")
        self.triage_summary_lbl.setWordWrap(True)
        triage_layout.addWidget(self.triage_summary_lbl)

        layout.addWidget(triage_card)

        # ─── Fleet Health Widget ──────────────────────────────────
        fleet_card = GlassCard()
        fleet_layout = fleet_card.get_layout()

        fleet_header = QLabel("Fleet Health")
        fleet_header.setObjectName("cardHeader")
        fleet_layout.addWidget(fleet_header)

        fleet_stats_row = QHBoxLayout()
        fleet_stats_row.setSpacing(20)

        self.fleet_health_lbl = QLabel("Health: --")
        self.fleet_health_lbl.setObjectName("formLabel")
        fleet_stats_row.addWidget(self.fleet_health_lbl)

        self.fleet_agents_lbl = QLabel("Agents: --")
        self.fleet_agents_lbl.setObjectName("formLabel")
        fleet_stats_row.addWidget(self.fleet_agents_lbl)

        self.fleet_tasks_lbl = QLabel("Tasks: --")
        self.fleet_tasks_lbl.setObjectName("formLabel")
        fleet_stats_row.addWidget(self.fleet_tasks_lbl)

        self.fleet_cost_lbl = QLabel("Cost: --")
        self.fleet_cost_lbl.setObjectName("formLabel")
        fleet_stats_row.addWidget(self.fleet_cost_lbl)

        fleet_stats_row.addStretch()
        fleet_layout.addLayout(fleet_stats_row)

        self.fleet_summary_lbl = QLabel("Navigate to Fleet Command to boot the agent fleet.")
        self.fleet_summary_lbl.setObjectName("mutedText")
        self.fleet_summary_lbl.setWordWrap(True)
        fleet_layout.addWidget(self.fleet_summary_lbl)

        layout.addWidget(fleet_card)

        # ─── Trending Opportunities Widget ────────────────────────
        trends_card = GlassCard()
        trends_layout = trends_card.get_layout()

        trends_header = QLabel("Trending Opportunities")
        trends_header.setObjectName("cardHeader")
        trends_layout.addWidget(trends_header)

        self.trends_summary_lbl = QLabel("Navigate to Trends to discover rising niches.")
        self.trends_summary_lbl.setObjectName("mutedText")
        self.trends_summary_lbl.setWordWrap(True)
        trends_layout.addWidget(self.trends_summary_lbl)

        self.trends_alerts_lbl = QLabel("")
        self.trends_alerts_lbl.setObjectName("warningText")
        self.trends_alerts_lbl.setWordWrap(True)
        self.trends_alerts_lbl.hide()
        trends_layout.addWidget(self.trends_alerts_lbl)

        layout.addWidget(trends_card)

        # ─── Ticket Pipeline Widget ─────────────────────────────
        ticket_card = GlassCard()
        ticket_layout = ticket_card.get_layout()

        ticket_header = QLabel("Ticket Pipeline")
        ticket_header.setObjectName("cardHeader")
        ticket_layout.addWidget(ticket_header)

        ticket_stats_row = QHBoxLayout()
        ticket_stats_row.setSpacing(20)

        self.ticket_total_lbl = QLabel("Total: --")
        self.ticket_total_lbl.setObjectName("formLabel")
        ticket_stats_row.addWidget(self.ticket_total_lbl)

        self.ticket_progress_lbl = QLabel("In Progress: --")
        self.ticket_progress_lbl.setObjectName("formLabel")
        ticket_stats_row.addWidget(self.ticket_progress_lbl)

        self.ticket_overdue_lbl = QLabel("Overdue: --")
        self.ticket_overdue_lbl.setObjectName("warningText")
        ticket_stats_row.addWidget(self.ticket_overdue_lbl)

        self.ticket_done_lbl = QLabel("Done: --")
        self.ticket_done_lbl.setObjectName("formLabel")
        ticket_stats_row.addWidget(self.ticket_done_lbl)

        ticket_stats_row.addStretch()
        ticket_layout.addLayout(ticket_stats_row)

        self.ticket_summary_lbl = QLabel("Navigate to Kanban to manage tickets.")
        self.ticket_summary_lbl.setObjectName("mutedText")
        self.ticket_summary_lbl.setWordWrap(True)
        ticket_layout.addWidget(self.ticket_summary_lbl)

        layout.addWidget(ticket_card)

        # Recent campaigns table
        recent_card = GlassCard()
        recent_layout = recent_card.get_layout()

        recent_header = QLabel("Recent Campaigns")
        recent_header.setObjectName("cardHeader")
        recent_layout.addWidget(recent_header)

        self.campaigns_table = QTableWidget()
        self.campaigns_table.setColumnCount(4)
        self.campaigns_table.setHorizontalHeaderLabels(
            ["Campaign", "Leads", "Qualified", "Status"]
        )
        self.campaigns_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.campaigns_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.campaigns_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.campaigns_table.verticalHeader().setVisible(False)
        self.campaigns_table.setShowGrid(False)
        self.campaigns_table.setAlternatingRowColors(True)
        recent_layout.addWidget(self.campaigns_table)
        
        # Empty State for Campaigns
        self.empty_campaigns = EmptyState(
            icon_key="empty_dashboard",
            title="No campaigns yet",
            subtitle="Start your first hunt to see campaign performance here.",
            action_text=None
        )
        self.empty_campaigns.hide()
        recent_layout.addWidget(self.empty_campaigns)

        layout.addWidget(recent_card, stretch=1)
        
        # Set the content widget to the scroll area
        scroll.setWidget(content)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll)

    def update_stats(self, stats: dict):
        """Update all dashboard widgets with fresh data."""
        self.total_campaigns_card.set_value(str(stats.get("total_campaigns", 0)))
        self.total_leads_card.set_value(str(stats.get("total_leads", 0)))
        self.qualified_card.set_value(str(stats.get("qualified_leads", 0)))
        self.emailed_card.set_value(str(stats.get("emailed_leads", 0)))
        self.replied_card.set_value(str(stats.get("replied_leads", 0)))
        self.conversion_card.set_value(f"{stats.get('conversion_rate', 0)}%")

        # Update funnel bars
        total = max(stats.get("total_leads", 0), 1)  # Avoid div by zero
        funnel_data = {
            "scraped": stats.get("total_leads", 0),
            "new": stats.get("new_leads", 0),
            "qualified": stats.get("qualified_leads", 0),
            "emailed": stats.get("emailed_leads", 0),
        }
        for key, (bar_bg, bar_inner, count_label) in self.funnel_bars.items():
            count = funnel_data.get(key, 0)
            count_label.setText(str(count))
            # Scale bar width using percentage (clamp between 4 and available width)
            bg_width = bar_bg.width() if bar_bg.width() > 0 else 300
            pct = count / total
            bar_width = max(4, int(pct * bg_width))
            bar_inner.setFixedWidth(bar_width)

        # Update recent campaigns table
        self.campaigns_table.setRowCount(0)
        recent = stats.get("recent_campaigns", [])
        if not recent:
            # Show empty state widget instead of table row
            self.campaigns_table.hide()
            self.empty_campaigns.show()
            return
        
        self.campaigns_table.show()
        self.empty_campaigns.hide()

        for camp in recent:
            row = self.campaigns_table.rowCount()
            self.campaigns_table.insertRow(row)
            self.campaigns_table.setItem(row, 0, QTableWidgetItem(camp["name"]))
            self.campaigns_table.setItem(row, 1, QTableWidgetItem(str(camp["total_leads"])))
            self.campaigns_table.setItem(row, 2, QTableWidgetItem(str(camp["qualified_leads"])))

            status = camp.get("status", "unknown")
            status_item = QTableWidgetItem(status.upper())
            colors = {"active": "#34D399", "paused": "#FBBF24", "completed": "#818CF8"}
            status_item.setForeground(QColor(colors.get(status, "#6B6B80")))
            self.campaigns_table.setItem(row, 3, status_item)

        # Update model usage card
        api_usage = stats.get("api_usage", {})
        breakdown = api_usage.get("breakdown", {})
        # Map service names to display rows
        tier_map = {
            "router_local": "local", "router_ollama": "ollama",
            "router_haiku": "haiku", "router_sonnet": "sonnet",
            "apollo": "apollo", "hunter": "hunter",
        }
        # Reset all rows
        for key in self.usage_rows:
            calls_lbl, cost_lbl = self.usage_rows[key]
            calls_lbl.setText("0 calls")
            cost_lbl.setText("$0.00")
        # Fill from breakdown
        for service, data in breakdown.items():
            display_key = tier_map.get(service, service)
            if display_key in self.usage_rows:
                calls_lbl, cost_lbl = self.usage_rows[display_key]
                calls_lbl.setText(f"{data.get('calls', 0)} calls")
                cost_lbl.setText(f"${data.get('cost_usd', 0.0):.2f}")
        self.usage_total_calls.setText(f"{api_usage.get('total_calls', 0)} calls")
        self.usage_total_cost.setText(f"${api_usage.get('total_cost_usd', 0.0):.2f}")

        # Update triage stats if available
        triage = stats.get("triage", {})
        if triage:
            self.show_triage_results(triage)

        # Update A/B test results if available
        ab_data = stats.get("ab_results", {})
        if ab_data:
            a = ab_data.get("variant_a", {})
            b = ab_data.get("variant_b", {})
            self.ab_a_stats.setText(
                f"Sends: {a.get('sends', 0)}  ·  Opens: {a.get('opens', 0)}  ·  Replies: {a.get('replies', 0)}"
            )
            self.ab_b_stats.setText(
                f"Sends: {b.get('sends', 0)}  ·  Opens: {b.get('opens', 0)}  ·  Replies: {b.get('replies', 0)}"
            )

    def show_triage_results(self, result: dict):
        """Display triage results in the morning briefing card."""
        self.triage_total_lbl.setText(f"Emails: {result.get('total_emails', 0)}")
        self.triage_replies_lbl.setText(f"Replies: {result.get('replies', 0)}")
        self.triage_bounces_lbl.setText(f"Bounces: {result.get('bounces', 0)}")
        self.triage_unsubs_lbl.setText(f"Unsubs: {result.get('unsubscribes', 0)}")
        self.triage_summary_lbl.setText(result.get("summary", "No summary available."))

    def update_fleet_widget(self, data: dict):
        """Update the fleet health dashboard widget."""
        if not data.get("success"):
            return
        info = data.get("data", {})
        self.fleet_health_lbl.setText(f"Health: {info.get('health_pct', 0)}%")
        self.fleet_agents_lbl.setText(f"Agents: {info.get('total_agents', 0)}")
        self.fleet_tasks_lbl.setText(f"Tasks: {info.get('total_tasks_today', 0)}")
        self.fleet_cost_lbl.setText(f"Cost: ${info.get('total_cost_today', 0):.2f}")

        running = info.get("running", 0)
        errors = info.get("error", 0)
        if errors > 0:
            self.fleet_summary_lbl.setText(
                f"{running} agents running, {errors} in error state"
            )
        elif running > 0:
            self.fleet_summary_lbl.setText(f"{running} agents actively running")
        else:
            self.fleet_summary_lbl.setText("Fleet idle — all agents standing by")

    def update_ticket_widget(self, data: dict):
        """Update the ticket pipeline dashboard widget."""
        if not data.get("success"):
            return
        stats = data.get("data", {})
        by_status = stats.get("by_status", {})
        total = sum(by_status.values()) if by_status else 0
        in_progress = by_status.get("in_progress", 0)
        done = by_status.get("done", 0)
        overdue = stats.get("overdue", 0)

        self.ticket_total_lbl.setText(f"Total: {total}")
        self.ticket_progress_lbl.setText(f"In Progress: {in_progress}")
        self.ticket_overdue_lbl.setText(f"Overdue: {overdue}")
        self.ticket_done_lbl.setText(f"Done: {done}")

        if total == 0:
            self.ticket_summary_lbl.setText("No tickets yet — create one in Kanban")
        elif overdue > 0:
            self.ticket_summary_lbl.setText(
                f"{overdue} ticket(s) overdue! {in_progress} in progress"
            )
        else:
            self.ticket_summary_lbl.setText(
                f"{in_progress} in progress, {done} completed"
            )

    def update_trends_widget(self, alerts: dict):
        """Update the trending opportunities dashboard widget."""
        if not alerts.get("success"):
            return
        data = alerts.get("data", [])
        if data:
            self.trends_summary_lbl.setText(f"{len(data)} unread trend alerts")
            # Show first few alerts
            lines = []
            for a in data[:3]:
                lines.append(f"[{a.get('alert_type', '')}] {a.get('message', '')}")
            if lines:
                self.trends_alerts_lbl.setText("\n".join(lines))
                self.trends_alerts_lbl.show()
        else:
            self.trends_summary_lbl.setText("No active trend alerts")
            self.trends_alerts_lbl.hide()

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
