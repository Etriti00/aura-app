"""
Aura — Research Page
Pre-outreach lead intelligence: research queue, report viewer, provider status.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QTextEdit, QPushButton, QComboBox,
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard, StatCard
from ui.components.modern_button import ModernButton
from ui.components.empty_state import EmptyState


class ResearchPage(QWidget):
    """Research page — lead intelligence queue, report viewer, config."""

    research_requested = Signal(int, str)   # lead_id, depth
    refresh_requested = Signal()
    view_report_requested = Signal(int)      # lead_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("researchPage")
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(26)

        # ─── Header ───────────────────────────────────────────────
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Lead Research")
        title.setObjectName("sectionHeader")
        header.addWidget(title)
        subtitle = QLabel("Pre-outreach intelligence — know your leads before reaching out")
        subtitle.setObjectName("sectionSubheader")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # ─── Stats Row ────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.stat_total = StatCard("0", "TOTAL REPORTS", accent="blue")
        self.stat_completed = StatCard("0", "COMPLETED", accent="green")
        self.stat_running = StatCard("0", "RUNNING", accent="purple")
        self.stat_providers = StatCard("0/3", "PROVIDERS", accent="orange")

        for card in [self.stat_total, self.stat_completed, self.stat_running, self.stat_providers]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # ─── Provider Status ──────────────────────────────────────
        provider_card = GlassCard()
        provider_layout = provider_card.get_layout()
        provider_hdr = QLabel("Research Providers")
        provider_hdr.setObjectName("cardHeader")
        provider_layout.addWidget(provider_hdr)

        self.provider_row = QHBoxLayout()
        self.provider_row.setSpacing(12)
        self.tavily_badge = QLabel("Tavily")
        self.tavily_badge.setObjectName("badgeDanger")
        self.firecrawl_badge = QLabel("Firecrawl")
        self.firecrawl_badge.setObjectName("badgeDanger")
        self.apify_badge = QLabel("Apify")
        self.apify_badge.setObjectName("badgeDanger")

        for badge in [self.tavily_badge, self.firecrawl_badge, self.apify_badge]:
            self.provider_row.addWidget(badge)
        self.provider_row.addStretch()

        provider_layout.addLayout(self.provider_row)
        self.provider_card = provider_card
        self.provider_card.setObjectName("researchConfigPanel")
        layout.addWidget(provider_card)

        # ─── Research Queue Table ──────────────────────────────────
        queue_card = GlassCard()
        queue_layout = queue_card.get_layout()
        queue_hdr_row = QHBoxLayout()
        queue_hdr = QLabel("Research Reports")
        queue_hdr.setObjectName("cardHeader")
        queue_hdr_row.addWidget(queue_hdr)
        queue_hdr_row.addStretch()

        self.refresh_btn = ModernButton("Refresh")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        queue_hdr_row.addWidget(self.refresh_btn)
        queue_layout.addLayout(queue_hdr_row)

        self.queue_table = QTableWidget()
        self.queue_table.setObjectName("researchQueue")
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels([
            "Lead", "Depth", "Status", "Sources", "Date", "Actions",
        ])
        self.queue_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.queue_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setMinimumHeight(200)
        queue_layout.addWidget(self.queue_table)

        self.empty_state = EmptyState(
            icon_key="sidebar_research",
            title="No Research Reports Yet",
            subtitle="Research will run automatically when leads are qualified, or you can trigger it manually.",
        )
        self.empty_state.setVisible(False)
        queue_layout.addWidget(self.empty_state)

        layout.addWidget(queue_card)

        # ─── Report Detail Viewer ──────────────────────────────────
        detail_card = GlassCard()
        detail_layout = detail_card.get_layout()
        detail_hdr = QLabel("Report Detail")
        detail_hdr.setObjectName("cardHeader")
        detail_layout.addWidget(detail_hdr)

        self.report_viewer = QTextEdit()
        self.report_viewer.setObjectName("researchReportCard")
        self.report_viewer.setReadOnly(True)
        self.report_viewer.setMinimumHeight(250)
        self.report_viewer.setPlaceholderText("Select a report from the table above to view details...")
        detail_layout.addWidget(self.report_viewer)

        layout.addWidget(detail_card)
        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def update_reports(self, reports: list):
        """Populate the research reports table."""
        self.queue_table.setRowCount(len(reports))
        total = len(reports)
        completed = sum(1 for r in reports if r.get("status") == "completed")
        running = sum(1 for r in reports if r.get("status") in ("running", "pending"))

        self.stat_total.set_value(str(total))
        self.stat_completed.set_value(str(completed))
        self.stat_running.set_value(str(running))

        self.empty_state.setVisible(total == 0)
        self.queue_table.setVisible(total > 0)

        for row, report in enumerate(reports):
            self.queue_table.setItem(row, 0, QTableWidgetItem(report.get("lead_name", "")))
            self.queue_table.setItem(row, 1, QTableWidgetItem(report.get("depth", "")))

            status = report.get("status", "")
            status_item = QTableWidgetItem(status)
            self.queue_table.setItem(row, 2, status_item)

            sources = ", ".join(report.get("sources_used", []))
            self.queue_table.setItem(row, 3, QTableWidgetItem(sources))
            self.queue_table.setItem(row, 4, QTableWidgetItem(report.get("created_at", "")[:16]))

            # View button — compact capsule centered in the cell
            view_btn = QPushButton("View")
            view_btn.setObjectName("tableActionButton")
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            lead_id = report.get("lead_id", 0)
            view_btn.clicked.connect(lambda checked, lid=lead_id: self._on_view_report(lid))
            cell = QWidget()
            cell_lyt = QHBoxLayout(cell)
            cell_lyt.setContentsMargins(4, 3, 4, 3)
            cell_lyt.addStretch()
            cell_lyt.addWidget(view_btn)
            cell_lyt.addStretch()
            self.queue_table.setCellWidget(row, 5, cell)

    def _on_view_report(self, lead_id: int):
        """Ask the controller for this lead's full report."""
        self.view_report_requested.emit(lead_id)

    def update_report_detail(self, data: dict):
        """Display a full research report."""
        sections = []
        if data.get("company_overview"):
            sections.append(f"**Company Overview**\n{data['company_overview']}")
        if data.get("services_offered"):
            sections.append(f"**Services Offered**\n{data['services_offered']}")
        if data.get("pain_points"):
            sections.append(f"**Pain Points**\n{data['pain_points']}")
        if data.get("competitors"):
            sections.append(f"**Competitors**\n{data['competitors']}")
        if data.get("tech_stack"):
            sections.append(f"**Tech Stack**\n{data['tech_stack']}")
        if data.get("recent_news"):
            sections.append(f"**Recent News**\n{data['recent_news']}")
        if data.get("gaps_opportunities"):
            sections.append(f"**Gaps & Opportunities**\n{data['gaps_opportunities']}")
        if data.get("llm_summary"):
            sections.append(f"**Executive Summary**\n{data['llm_summary']}")

        if not sections:
            self.report_viewer.setPlainText("No data available for this report.")
            return

        header = f"Research Report — Lead #{data.get('lead_id', '?')} ({data.get('depth', 'quick')})\n"
        header += f"Status: {data.get('status', '')} | Sources: {', '.join(data.get('sources_used', []))}\n"
        header += f"Created: {data.get('created_at', '')}\n"
        header += "─" * 60 + "\n\n"

        self.report_viewer.setPlainText(header + "\n\n".join(sections))

    def update_provider_status(self, status: dict):
        """Update provider badge colors."""
        active_count = sum(1 for v in status.values() if v)
        self.stat_providers.set_value(f"{active_count}/3")

        self.tavily_badge.setObjectName("badgeSuccess" if status.get("tavily") else "badgeDanger")
        self.tavily_badge.setText("Tavily Ready" if status.get("tavily") else "Tavily Off")
        self.tavily_badge.style().unpolish(self.tavily_badge)
        self.tavily_badge.style().polish(self.tavily_badge)

        self.firecrawl_badge.setObjectName("badgeSuccess" if status.get("firecrawl") else "badgeDanger")
        self.firecrawl_badge.setText("Firecrawl Ready" if status.get("firecrawl") else "Firecrawl Off")
        self.firecrawl_badge.style().unpolish(self.firecrawl_badge)
        self.firecrawl_badge.style().polish(self.firecrawl_badge)

        self.apify_badge.setObjectName("badgeSuccess" if status.get("apify") else "badgeDanger")
        self.apify_badge.setText("Apify Ready" if status.get("apify") else "Apify Off")
        self.apify_badge.style().unpolish(self.apify_badge)
        self.apify_badge.style().polish(self.apify_badge)

    def receive_context(self, context: dict):
        """Handle cross-page navigation context."""
        lead_id = context.get("lead_id")
        if lead_id:
            self._on_view_report(lead_id)
