"""
Aura — Hunter Page (Full Implementation)
Two-tab layout: Search (scraping form) and Campaigns (browse + enrich).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QComboBox, QCheckBox, QSpinBox, QFrame, QScrollArea,
    QAbstractItemView, QFileDialog, QTabWidget, QStackedWidget,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QColor

from ui.icons import get_icon, get_pixmap

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.toast_notification import show_toast
from ui.components.empty_state import EmptyState
from config import SCRAPER_SOURCES, LEAD_SOURCES, LEAD_SOURCE_LABELS


# ─── Campaign Detail View ─────────────────────────────────────────────────
class CampaignDetailView(QWidget):
    """Shows all leads for a single campaign in a rich table with enrichment columns."""

    back_requested = Signal()
    enrich_lead_requested = Signal(int)       # lead_id
    enrich_all_requested = Signal(int)        # campaign_id

    DETAIL_COLUMNS = [
        "Business Name", "Email", "Phone", "City", "Category",
        "Status", "Score", "Rating", "Reviews", "Domain Age",
        "Decision Maker", "FB", "IG", "LI", "Source",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._campaign_id = None
        self._leads_data = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header row: back button + campaign name + enrich all button
        header = QHBoxLayout()
        header.setSpacing(12)

        self.back_btn = QPushButton()
        self.back_btn.setObjectName("secondaryButton")
        self.back_btn.setIcon(get_icon("chevron_left", "dark"))
        self.back_btn.setIconSize(QSize(16, 16))
        self.back_btn.setText("Campaigns")
        self.back_btn.setFixedHeight(36)
        self.back_btn.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_btn)

        self.campaign_title = QLabel("")
        self.campaign_title.setObjectName("sectionHeader")
        header.addWidget(self.campaign_title, stretch=1)

        self.enrich_selected_btn = ModernButton("Enrich Selected", "secondary")
        self.enrich_selected_btn.setIcon(get_icon("generate", "dark", "accent"))
        self.enrich_selected_btn.setIconSize(QSize(14, 14))
        self.enrich_selected_btn.setFixedHeight(36)
        self.enrich_selected_btn.clicked.connect(self._on_enrich_selected)
        header.addWidget(self.enrich_selected_btn)

        self.enrich_all_btn = ModernButton("Enrich All Leads", "primary")
        self.enrich_all_btn.setIcon(get_icon("generate", "dark"))
        self.enrich_all_btn.setIconSize(QSize(14, 14))
        self.enrich_all_btn.setFixedHeight(36)
        self.enrich_all_btn.clicked.connect(self._on_enrich_all)
        header.addWidget(self.enrich_all_btn)

        self.export_csv_btn = ModernButton("Export CSV", "secondary")
        self.export_csv_btn.setIcon(get_icon("export", "dark", "accent"))
        self.export_csv_btn.setIconSize(QSize(14, 14))
        self.export_csv_btn.setFixedHeight(36)
        self.export_csv_btn.clicked.connect(self._on_export_csv)
        header.addWidget(self.export_csv_btn)

        self.lead_count_label = QLabel("0 leads")
        self.lead_count_label.setObjectName("badgeInfo")
        self.lead_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lead_count_label.setFixedHeight(28)
        header.addWidget(self.lead_count_label)

        layout.addLayout(header)

        # Stats row
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(16)
        self.stat_qualified = QLabel("")
        self.stat_qualified.setObjectName("badgeSuccess")
        self.stat_enriched = QLabel("")
        self.stat_enriched.setObjectName("badgeInfo")
        self.stats_row.addWidget(self.stat_qualified)
        self.stats_row.addWidget(self.stat_enriched)
        self.stats_row.addStretch()
        layout.addLayout(self.stats_row)

        # Leads table
        self.table = QTableWidget()
        self.table.setObjectName("campaignDetailTable")
        self.table.setColumnCount(len(self.DETAIL_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.DETAIL_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 200)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

    def load_campaign(self, campaign_id: int, campaign_name: str, leads: list):
        """Populate the detail view with leads data."""
        self._campaign_id = campaign_id
        self._leads_data = leads
        self.campaign_title.setText(campaign_name)
        self.lead_count_label.setText(f"{len(leads)} leads")

        qualified = sum(1 for l in leads if l.get("status") == "qualified")
        enriched = sum(1 for l in leads if l.get("data_completeness_score", 0) > 0)
        self.stat_qualified.setText(f" {qualified} qualified ")
        self.stat_enriched.setText(f" {enriched} enriched ")

        self.table.setRowCount(0)
        status_colors = {
            "new": "#6366F1", "qualifying": "#FBBF24",
            "qualified": "#34D399", "disqualified": "#F87171",
        }

        for lead in leads:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Store lead_id in first column's data role
            name_item = QTableWidgetItem(lead.get("business_name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, lead.get("id"))
            self.table.setItem(row, 0, name_item)

            self.table.setItem(row, 1, QTableWidgetItem(lead.get("email", "")))
            self.table.setItem(row, 2, QTableWidgetItem(lead.get("phone", "")))
            self.table.setItem(row, 3, QTableWidgetItem(lead.get("city", "")))
            self.table.setItem(row, 4, QTableWidgetItem(lead.get("category", "")))

            # Status with color
            status = lead.get("status", "new")
            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QColor(status_colors.get(status, "#6B6B80")))
            self.table.setItem(row, 5, status_item)

            # Completeness score
            score = lead.get("data_completeness_score", 0)
            score_item = QTableWidgetItem(f"{score}%" if score else "—")
            if score >= 60:
                score_item.setForeground(QColor("#34D399"))
            elif score >= 30:
                score_item.setForeground(QColor("#FBBF24"))
            else:
                score_item.setForeground(QColor("#6B6B80"))
            self.table.setItem(row, 6, score_item)

            # Google Maps rating
            rating = lead.get("google_maps_rating")
            self.table.setItem(row, 7, QTableWidgetItem(f"{rating}" if rating else "—"))

            # Review count
            reviews = lead.get("review_count")
            self.table.setItem(row, 8, QTableWidgetItem(f"{reviews}" if reviews else "—"))

            # Domain age
            age = lead.get("domain_age")
            self.table.setItem(row, 9, QTableWidgetItem(f"{age}y" if age else "—"))

            # Decision maker
            self.table.setItem(row, 10, QTableWidgetItem(lead.get("decision_maker", "") or "—"))

            # Social presence indicators
            for col_idx, key in [(11, "has_facebook"), (12, "has_instagram"), (13, "has_linkedin")]:
                val = lead.get(key, False)
                item = QTableWidgetItem("Yes" if val else "—")
                if val:
                    item.setForeground(QColor("#34D399"))
                else:
                    item.setForeground(QColor("#6B6B80"))
                self.table.setItem(row, col_idx, item)

            # Source
            self.table.setItem(row, 14, QTableWidgetItem(lead.get("source_platform", "")))

    def _on_enrich_selected(self):
        """Enrich only selected leads."""
        selected_rows = set(idx.row() for idx in self.table.selectedIndexes())
        if not selected_rows:
            show_toast(self.window(), "Select one or more leads to enrich.", "warning")
            return
        self._pending_enrich_count = len(selected_rows)
        self._enrich_done_count = 0
        self.enrich_selected_btn.set_loading(True)
        self.enrich_selected_btn.setText("Enriching...")
        self.enrich_all_btn.setEnabled(False)
        for row in selected_rows:
            item = self.table.item(row, 0)
            if item:
                lead_id = item.data(Qt.ItemDataRole.UserRole)
                if lead_id:
                    self.enrich_lead_requested.emit(lead_id)
        show_toast(self.window(), f"Enriching {len(selected_rows)} lead(s)...", "info")

    def _on_enrich_all(self):
        """Enrich all leads in the campaign."""
        if self._campaign_id:
            self.enrich_all_requested.emit(self._campaign_id)
            self.enrich_all_btn.set_loading(True)
            self.enrich_all_btn.setText("Enriching...")
            self.enrich_selected_btn.setEnabled(False)
            self.back_btn.setEnabled(False)
            show_toast(self.window(), "Starting full campaign enrichment...", "info")

    def _on_export_csv(self):
        """Export all leads in this campaign to a detailed CSV file."""
        if not self._leads_data:
            show_toast(self.window(), "No leads to export.", "warning")
            return

        campaign_name = self.campaign_title.text().replace(" ", "_") or "campaign"
        default_name = f"{campaign_name}_leads.csv"

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Leads as CSV", default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        import csv

        # All fields to include in the CSV (superset of display columns)
        fieldnames = [
            "id", "business_name", "email", "phone", "website",
            "city", "address", "category", "status", "qualification_score",
            "rating", "review_count", "domain_age_years",
            "decision_maker_name", "facebook_url", "instagram_url", "linkedin_url",
            "source", "data_completeness_score",
            "pain_points", "tech_stack", "employees", "revenue",
            "company_description", "qualification_reason",
        ]

        self.export_csv_btn.set_loading(True)
        self.export_csv_btn.setText("Exporting...")
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=fieldnames, extrasaction="ignore"
                )
                writer.writeheader()
                for lead in self._leads_data:
                    writer.writerow({k: lead.get(k, "") for k in fieldnames})

            show_toast(
                self.window(),
                f"Exported {len(self._leads_data)} leads to {path.split('/')[-1]}",
                "success",
            )
        except Exception as e:
            show_toast(self.window(), f"Export failed: {e}", "error")
        finally:
            self.export_csv_btn.set_loading(False)

    def on_enrich_finished(self):
        """Reset all button states after campaign enrichment completion."""
        self.enrich_all_btn.set_loading(False)
        self.enrich_all_btn.setText("Enrich All Leads")
        self.enrich_selected_btn.setEnabled(True)
        self.enrich_selected_btn.set_loading(False)
        self.enrich_selected_btn.setText("Enrich Selected")
        self.enrich_all_btn.setEnabled(True)
        self.back_btn.setEnabled(True)

    def on_single_enrich_done(self):
        """Track individual lead enrichment completion for selected-enrich mode."""
        self._enrich_done_count = getattr(self, "_enrich_done_count", 0) + 1
        pending = getattr(self, "_pending_enrich_count", 0)
        if pending and self._enrich_done_count >= pending:
            self.enrich_selected_btn.set_loading(False)
            self.enrich_selected_btn.setText("Enrich Selected")
            self.enrich_all_btn.setEnabled(True)
            self._pending_enrich_count = 0
            self._enrich_done_count = 0


# ─── Campaign List View ───────────────────────────────────────────────────
class CampaignListView(QWidget):
    """Lists all campaigns with summary stats. Click to open detail."""

    campaign_selected = Signal(int, str)  # campaign_id, campaign_name
    refresh_requested = Signal()

    CAMPAIGN_COLUMNS = [
        "Campaign Name", "Niche", "City", "Status",
        "Total Leads", "Qualified", "Enriched", "Created",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Campaigns")
        title.setObjectName("sectionHeader")
        header.addWidget(title, stretch=1)

        self.refresh_btn = ModernButton("Refresh", "secondary")
        self.refresh_btn.setIcon(get_icon("refresh", "dark"))
        self.refresh_btn.setIconSize(QSize(14, 14))
        self.refresh_btn.setFixedHeight(36)
        self.refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(self.refresh_btn)

        self.campaign_count = QLabel("0 campaigns")
        self.campaign_count.setObjectName("badgeInfo")
        self.campaign_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.campaign_count.setFixedHeight(28)
        header.addWidget(self.campaign_count)

        layout.addLayout(header)

        subtitle = QLabel("Click a campaign to view its leads and enrichment data")
        subtitle.setObjectName("sectionSubheader")
        layout.addWidget(subtitle)

        # Campaigns table
        self.table = QTableWidget()
        self.table.setObjectName("campaignListTable")
        self.table.setColumnCount(len(self.CAMPAIGN_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.CAMPAIGN_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 250)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        # Empty state
        self.empty_state = EmptyState(
            icon_key="empty_hunter",
            title="No Campaigns Yet",
            subtitle="Run a hunt from the Search tab to create your first campaign.",
        )
        self.empty_state.setMinimumHeight(200)
        layout.addWidget(self.empty_state)
        self.empty_state.hide()

    def _on_refresh(self):
        """Handle refresh button click with loading state."""
        self.refresh_btn.set_loading(True)
        self.refresh_btn.setText("Loading...")
        self.refresh_requested.emit()

    def load_campaigns(self, campaigns: list):
        """Populate the campaign list."""
        self.refresh_btn.set_loading(False)
        self.refresh_btn.setText("Refresh")
        self.table.setRowCount(0)
        self.campaign_count.setText(f"{len(campaigns)} campaigns")

        if not campaigns:
            self.table.hide()
            self.empty_state.show()
            return

        self.table.show()
        self.empty_state.hide()

        status_colors = {
            "active": "#FBBF24", "completed": "#34D399",
            "paused": "#6B6B80", "draft": "#6366F1",
        }

        for c in campaigns:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Store campaign_id in first column
            name_item = QTableWidgetItem(c.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, c.get("id"))
            self.table.setItem(row, 0, name_item)

            self.table.setItem(row, 1, QTableWidgetItem(c.get("target_niche", "")))
            self.table.setItem(row, 2, QTableWidgetItem(c.get("target_city", "")))

            status = c.get("status", "completed")
            status_item = QTableWidgetItem(status.upper())
            status_item.setForeground(QColor(status_colors.get(status, "#6B6B80")))
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(str(c.get("total_leads", 0))))
            self.table.setItem(row, 5, QTableWidgetItem(str(c.get("qualified_leads", 0))))
            self.table.setItem(row, 6, QTableWidgetItem(str(c.get("enriched_leads", 0))))
            self.table.setItem(row, 7, QTableWidgetItem(c.get("created_at", "")))

    def _on_row_double_clicked(self, index):
        """Handle double-click on a campaign row."""
        row = index.row()
        item = self.table.item(row, 0)
        if item:
            campaign_id = item.data(Qt.ItemDataRole.UserRole)
            campaign_name = item.text()
            if campaign_id:
                self.campaign_selected.emit(campaign_id, campaign_name)


# ─── Main Hunter Page ─────────────────────────────────────────────────────
class HunterPage(QWidget):
    """Hunter page — two tabs: Search (scraping) and Campaigns (browse + enrich)."""

    # Signals to controller
    start_requested = Signal(str, str, str, str, int, list)
    stop_requested = Signal()
    batch_import_requested = Signal(str)
    apollo_search_requested = Signal(str, str, list, int)
    hubspot_search_requested = Signal(str, str, str, int)
    linkedin_import_requested = Signal(str)
    enrich_lead_requested = Signal(int)          # lead_id
    enrich_campaign_requested = Signal(int)      # campaign_id
    load_campaigns_requested = Signal()

    # Navigation
    navigate_requested = Signal(int, dict)

    # Search tab table columns
    COLUMNS = [
        "Business Name", "Category", "City", "Phone",
        "Email", "Source", "Website", "Status"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._lead_count = 0

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ─── Tab Widget ───────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setObjectName("hunterTabs")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # ══════════════════════════════════════════════════════════════
        # TAB 1: SEARCH
        # ══════════════════════════════════════════════════════════════
        search_widget = QWidget()
        search_scroll = QScrollArea()
        search_scroll.setWidgetResizable(True)
        search_scroll.setFrameShape(QFrame.Shape.NoFrame)
        search_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header Row
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Hunter")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Search and discover business leads across the web")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, stretch=1)

        self.lead_counter = QLabel("0 leads")
        self.lead_counter.setObjectName("badgeInfo")
        self.lead_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lead_counter.setFixedHeight(28)
        header_row.addWidget(self.lead_counter, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(header_row)

        # Search Form Card
        search_card = GlassCard()
        form = search_card.get_layout()
        form.setSpacing(8)

        # Row 1: Campaign name + Niche
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        name_col = QVBoxLayout()
        name_col.setSpacing(8)
        name_label = QLabel("Campaign Name")
        name_label.setObjectName("formLabel")
        name_col.addWidget(name_label)
        self.campaign_name_input = QLineEdit()
        self.campaign_name_input.setPlaceholderText("e.g., Dentists Berlin July 2025")
        self.campaign_name_input.setClearButtonEnabled(True)
        name_col.addWidget(self.campaign_name_input)
        row1.addLayout(name_col, stretch=1)

        niche_col = QVBoxLayout()
        niche_col.setSpacing(8)
        niche_label = QLabel("Business Niche")
        niche_label.setObjectName("formLabel")
        niche_col.addWidget(niche_label)
        self.niche_input = QLineEdit()
        self.niche_input.setPlaceholderText("e.g., Dentist, Plumber, Restaurant")
        self.niche_input.setClearButtonEnabled(True)
        niche_col.addWidget(self.niche_input)
        row1.addLayout(niche_col, stretch=1)
        form.addLayout(row1)

        # Row 2: City + Search Query
        row2 = QHBoxLayout()
        row2.setSpacing(16)
        city_col = QVBoxLayout()
        city_col.setSpacing(8)
        city_label = QLabel("Target City")
        city_label.setObjectName("formLabel")
        city_col.addWidget(city_label)
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("e.g., Berlin, New York, London")
        self.city_input.setClearButtonEnabled(True)
        city_col.addWidget(self.city_input)
        row2.addLayout(city_col, stretch=1)

        query_col = QVBoxLayout()
        query_col.setSpacing(8)
        query_label = QLabel("Custom Search Query (optional)")
        query_label.setObjectName("formLabel")
        query_col.addWidget(query_label)
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Override with custom query...")
        self.query_input.setClearButtonEnabled(True)
        query_col.addWidget(self.query_input)
        row2.addLayout(query_col, stretch=1)
        form.addLayout(row2)

        # Row 3: Unified Sources
        src_row = QVBoxLayout()
        src_row.setSpacing(8)
        src_label = QLabel("Lead Sources")
        src_label.setObjectName("formLabel")
        src_row.addWidget(src_label)
        self.source_checks = {}

        scraper_row = QHBoxLayout()
        scraper_row.setSpacing(10)
        scraper_tag = QLabel("Web")
        scraper_tag.setObjectName("badgeInfo")
        scraper_tag.setMinimumWidth(60)
        scraper_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scraper_row.addWidget(scraper_tag)
        for source in LEAD_SOURCES.get("scraper", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.source_checks[source] = cb
            scraper_row.addWidget(cb)
        scraper_row.addStretch()
        src_row.addLayout(scraper_row)

        api_row = QHBoxLayout()
        api_row.setSpacing(10)
        api_tag = QLabel("API")
        api_tag.setObjectName("badgeSuccess")
        api_tag.setMinimumWidth(60)
        api_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        api_row.addWidget(api_tag)
        for source in LEAD_SOURCES.get("api", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(False)
            self.source_checks[source] = cb
            api_row.addWidget(cb)
        api_row.addStretch()
        src_row.addLayout(api_row)

        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        import_tag = QLabel("Import")
        import_tag.setObjectName("badgeWarning")
        import_tag.setMinimumWidth(60)
        import_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        import_row.addWidget(import_tag)
        for source in LEAD_SOURCES.get("import", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(False)
            self.source_checks[source] = cb
            import_row.addWidget(cb)
        import_row.addStretch()
        src_row.addLayout(import_row)
        form.addLayout(src_row)

        # Row 4: Limit + action buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        limit_label = QLabel("Max Leads")
        limit_label.setObjectName("formLabel")
        action_row.addWidget(limit_label)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(5, 200)
        self.limit_spin.setValue(50)
        self.limit_spin.setSingleStep(5)
        self.limit_spin.setMinimumWidth(70)
        action_row.addWidget(self.limit_spin)
        action_row.addStretch()

        self.start_btn = ModernButton("Start Hunting", "primary")
        self.start_btn.setIcon(get_icon("sidebar_hunter", "dark"))
        self.start_btn.setIconSize(QSize(16, 16))
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setFixedHeight(42)
        action_row.addWidget(self.start_btn)

        self.stop_btn = ModernButton("Stop", "danger")
        self.stop_btn.setIcon(get_icon("chat_close", "dark", "danger"))
        self.stop_btn.setIconSize(QSize(14, 14))
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setFixedHeight(42)
        self.stop_btn.setEnabled(False)
        action_row.addWidget(self.stop_btn)
        form.addLayout(action_row)
        layout.addWidget(search_card)

        # Kill Switch Warning
        self.kill_warning = QFrame()
        self.kill_warning.setObjectName("toastWarning")
        self.kill_warning.setVisible(False)
        kw_layout = QHBoxLayout(self.kill_warning)
        kw_layout.setContentsMargins(16, 10, 16, 10)
        kw_icon = QLabel()
        kw_icon.setPixmap(get_pixmap("warning", "dark", "warning", 16))
        kw_icon.setFixedSize(20, 20)
        kw_layout.addWidget(kw_icon)
        self.kill_warning_label = QLabel("Detection risk is high. Scraping paused for safety.")
        self.kill_warning_label.setObjectName("warningText")
        kw_layout.addWidget(self.kill_warning_label, stretch=1)
        self.kill_timer_label = QLabel("")
        self.kill_timer_label.setObjectName("warningText")
        kw_layout.addWidget(self.kill_timer_label)
        layout.addWidget(self.kill_warning)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        # Status bar
        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready to hunt")
        self.status_label.setObjectName("sectionSubheader")
        status_row.addWidget(self.status_label, stretch=1)
        self.export_btn = ModernButton("Export CSV", "secondary")
        self.export_btn.clicked.connect(self._on_export)
        self.export_btn.setFixedHeight(40)
        self.export_btn.setEnabled(False)
        status_row.addWidget(self.export_btn)
        layout.addLayout(status_row)

        # Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(350)
        layout.addWidget(self.table)

        self.empty_state = EmptyState(
            icon_key="empty_hunter",
            title="Ready to Hunt?",
            subtitle="Enter a niche and city above to start discovering leads.",
            action_text="Start Hunting"
        )
        self.empty_state.action_clicked.connect(self._on_start)
        self.empty_state.setMinimumHeight(250)
        layout.addWidget(self.empty_state)
        self.table.hide()

        # Batch Import Section
        import_card = GlassCard()
        import_layout_c = import_card.get_layout()
        import_hdr_row = QHBoxLayout()
        import_hdr_icon = QLabel()
        import_hdr_icon.setPixmap(get_pixmap("batch_import", "dark", "default", 16))
        import_hdr_icon.setFixedSize(20, 20)
        import_header = QLabel("Batch Import")
        import_header.setObjectName("cardHeader")
        import_hdr_row.addWidget(import_hdr_icon)
        import_hdr_row.addWidget(import_header, stretch=1)
        import_layout_c.addLayout(import_hdr_row)

        import_row_w = QHBoxLayout()
        self.import_path_label = QLabel("No file selected")
        self.import_path_label.setObjectName("mutedText")
        import_row_w.addWidget(self.import_path_label, stretch=1)
        browse_btn = ModernButton("Browse CSV", "primary")
        browse_btn.setFixedHeight(40)
        browse_btn.clicked.connect(self._on_browse_csv)
        import_row_w.addWidget(browse_btn)
        self.import_btn = ModernButton("Import", "primary")
        self.import_btn.setFixedHeight(40)
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_import_csv)
        import_row_w.addWidget(self.import_btn)
        import_layout_c.addLayout(import_row_w)
        layout.addWidget(import_card)

        # API Source Options Card
        api_card = GlassCard()
        api_layout_c = api_card.get_layout()
        api_layout_c.setSpacing(8)
        api_hdr_row = QHBoxLayout()
        api_hdr_icon = QLabel()
        api_hdr_icon.setPixmap(get_pixmap("apollo_search", "dark", "default", 16))
        api_hdr_icon.setFixedSize(20, 20)
        api_header = QLabel("API Source Options")
        api_header.setObjectName("cardHeader")
        api_hdr_row.addWidget(api_hdr_icon)
        api_hdr_row.addWidget(api_header, stretch=1)
        api_layout_c.addLayout(api_hdr_row)

        api_info = QLabel("Configure search parameters for Apollo, Hunter.io, and HubSpot.")
        api_info.setObjectName("mutedText")
        api_layout_c.addWidget(api_info)

        title_row = QVBoxLayout()
        title_row.setSpacing(8)
        title_label_a = QLabel("Apollo — Title Keywords")
        title_label_a.setObjectName("formLabel")
        title_row.addWidget(title_label_a)
        self.apollo_title_input = QLineEdit()
        self.apollo_title_input.setPlaceholderText("CEO, Founder, Owner")
        self.apollo_title_input.setClearButtonEnabled(True)
        title_row.addWidget(self.apollo_title_input)
        api_layout_c.addLayout(title_row)

        hs_row = QVBoxLayout()
        hs_row.setSpacing(8)
        hs_label = QLabel("HubSpot — Company Name Filter")
        hs_label.setObjectName("formLabel")
        hs_row.addWidget(hs_label)
        self.hubspot_company_input = QLineEdit()
        self.hubspot_company_input.setPlaceholderText("Filter by company name (optional)")
        self.hubspot_company_input.setClearButtonEnabled(True)
        hs_row.addWidget(self.hubspot_company_input)
        api_layout_c.addLayout(hs_row)

        api_opts = QHBoxLayout()
        api_opts.setSpacing(12)
        emp_label = QLabel("Max Employees")
        emp_label.setObjectName("formLabel")
        api_opts.addWidget(emp_label)
        self.apollo_emp_spin = QSpinBox()
        self.apollo_emp_spin.setRange(1, 10000)
        self.apollo_emp_spin.setValue(50)
        self.apollo_emp_spin.setMinimumWidth(70)
        api_opts.addWidget(self.apollo_emp_spin)
        api_opts.addSpacing(8)
        alimit_label = QLabel("Max Results")
        alimit_label.setObjectName("formLabel")
        api_opts.addWidget(alimit_label)
        self.apollo_limit_spin = QSpinBox()
        self.apollo_limit_spin.setRange(5, 100)
        self.apollo_limit_spin.setValue(50)
        self.apollo_limit_spin.setSingleStep(5)
        self.apollo_limit_spin.setMinimumWidth(70)
        api_opts.addWidget(self.apollo_limit_spin)
        api_opts.addStretch()
        self.apollo_search_btn = ModernButton("Search Apollo", "primary")
        self.apollo_search_btn.setFixedHeight(42)
        self.apollo_search_btn.clicked.connect(self._on_apollo_search)
        api_opts.addWidget(self.apollo_search_btn)
        api_layout_c.addLayout(api_opts)

        linkedin_row = QHBoxLayout()
        linkedin_row.setSpacing(8)
        linkedin_label = QLabel("LinkedIn — Sales Navigator CSV")
        linkedin_label.setObjectName("formLabel")
        linkedin_row.addWidget(linkedin_label)
        linkedin_row.addStretch()
        self.linkedin_path_label = QLabel("No file selected")
        self.linkedin_path_label.setObjectName("mutedText")
        linkedin_row.addWidget(self.linkedin_path_label)
        self.linkedin_browse_btn = ModernButton("Browse", "secondary")
        self.linkedin_browse_btn.setFixedHeight(40)
        self.linkedin_browse_btn.clicked.connect(self._on_browse_linkedin_csv)
        linkedin_row.addWidget(self.linkedin_browse_btn)
        self.linkedin_import_btn = ModernButton("Import LinkedIn", "primary")
        self.linkedin_import_btn.setFixedHeight(40)
        self.linkedin_import_btn.setEnabled(False)
        self.linkedin_import_btn.clicked.connect(self._on_import_linkedin_csv)
        linkedin_row.addWidget(self.linkedin_import_btn)
        api_layout_c.addLayout(linkedin_row)
        layout.addWidget(api_card)

        search_scroll.setWidget(content)
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(search_scroll)

        self.tabs.addTab(search_widget, get_icon("sidebar_hunter", "dark"), "Search")

        # ══════════════════════════════════════════════════════════════
        # TAB 2: CAMPAIGNS
        # ══════════════════════════════════════════════════════════════
        campaigns_widget = QWidget()
        campaigns_outer = QVBoxLayout(campaigns_widget)
        campaigns_outer.setContentsMargins(32, 24, 32, 24)
        campaigns_outer.setSpacing(0)

        self._campaigns_stack = QStackedWidget()

        # Page 0: Campaign list
        self.campaign_list = CampaignListView()
        self.campaign_list.campaign_selected.connect(self._on_campaign_selected)
        self.campaign_list.refresh_requested.connect(self._on_refresh_campaigns)
        self._campaigns_stack.addWidget(self.campaign_list)

        # Page 1: Campaign detail
        self.campaign_detail = CampaignDetailView()
        self.campaign_detail.back_requested.connect(self._on_back_to_list)
        self.campaign_detail.enrich_lead_requested.connect(self.enrich_lead_requested.emit)
        self.campaign_detail.enrich_all_requested.connect(self.enrich_campaign_requested.emit)
        self._campaigns_stack.addWidget(self.campaign_detail)

        campaigns_outer.addWidget(self._campaigns_stack)

        self.tabs.addTab(campaigns_widget, get_icon("sidebar_fleet", "dark"), "Campaigns")

        main_layout.addWidget(self.tabs)

        # Kill switch cooldown timer
        self._kill_timer = QTimer(self)
        self._kill_timer.timeout.connect(self._update_kill_timer)
        self._kill_cooldown_remaining = 0

    # ─── Tab change handler ──────────────────────────────────────────
    def _on_tab_changed(self, index: int):
        """When switching to Campaigns tab, request a refresh."""
        if index == 1:
            self.load_campaigns_requested.emit()

    # ─── Campaign navigation ─────────────────────────────────────────
    def _on_campaign_selected(self, campaign_id: int, campaign_name: str):
        """User double-clicked a campaign — load detail view."""
        self._pending_campaign = (campaign_id, campaign_name)
        # Signal to controller to get leads
        self.load_campaigns_requested.emit()

    def show_campaign_detail(self, campaign_id: int, campaign_name: str, leads: list):
        """Called by controller to populate and show the detail view."""
        self.campaign_detail.load_campaign(campaign_id, campaign_name, leads)
        self._campaigns_stack.setCurrentIndex(1)

    def _on_back_to_list(self):
        """Return from detail view to campaign list."""
        self._campaigns_stack.setCurrentIndex(0)
        self.load_campaigns_requested.emit()

    def _on_refresh_campaigns(self):
        """Refresh campaign list."""
        self.load_campaigns_requested.emit()

    def on_campaigns_loaded(self, campaigns: list):
        """Receive campaign list from controller."""
        self.campaign_list.load_campaigns(campaigns)
        # If there's a pending detail request, load it
        pending = getattr(self, "_pending_campaign", None)
        if pending:
            cid, cname = pending
            self._pending_campaign = None
            # Emit signal for controller to load leads — handled by main_window
            self._load_campaign_detail(cid, cname)

    def _load_campaign_detail(self, campaign_id: int, campaign_name: str):
        """Internal: request leads for campaign detail view.
        This is picked up by the controller via the stored pending state."""
        # Store for main_window to handle
        self._detail_request = (campaign_id, campaign_name)

    def on_enrich_campaign_finished(self, campaign_id: int, result: dict):
        """Handle campaign enrichment completion — refresh detail view."""
        self.campaign_detail.on_enrich_finished()
        enriched = result.get("enriched", 0)
        emails = result.get("emails_found", 0)
        error = result.get("error", "")
        if error:
            show_toast(self.window(), f"Enrichment error: {error[:100]}", "error")
        else:
            show_toast(
                self.window(),
                f"Enrichment complete: {enriched} leads enriched, {emails} emails found.",
                "success",
            )

    def on_enrich_lead_finished(self, lead_id: int, result: dict):
        """Handle single lead enrichment completion."""
        self.campaign_detail.on_single_enrich_done()
        if result.get("success"):
            show_toast(self.window(), f"Lead #{lead_id} enriched successfully.", "success")
        else:
            error = result.get("error", "unknown error")
            show_toast(self.window(), f"Enrichment failed for lead #{lead_id}: {error[:80]}", "error")

    # ─── Signal Handlers (from Controller) — Search tab ──────────────

    def add_lead_row(self, lead_data: dict):
        """Add a new lead row to the results table."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(lead_data.get("business_name", "")))
        self.table.setItem(row, 1, QTableWidgetItem(lead_data.get("category", "")))
        self.table.setItem(row, 2, QTableWidgetItem(lead_data.get("city", "")))
        self.table.setItem(row, 3, QTableWidgetItem(lead_data.get("phone", "")))
        self.table.setItem(row, 4, QTableWidgetItem(lead_data.get("email", "")))
        self.table.setItem(row, 5, QTableWidgetItem(lead_data.get("source_platform", "")))

        has_site = lead_data.get("has_website", False)
        website_item = QTableWidgetItem("Yes" if has_site else "No")
        website_item.setForeground(QColor("#34D399") if has_site else QColor("#F87171"))
        self.table.setItem(row, 6, website_item)

        status = lead_data.get("status", "new")
        status_item = QTableWidgetItem(status.upper())
        status_colors = {
            "new": "#6366F1", "qualifying": "#FBBF24",
            "qualified": "#34D399", "disqualified": "#F87171",
        }
        status_item.setForeground(QColor(status_colors.get(status, "#6B6B80")))
        self.table.setItem(row, 7, status_item)

        self.table.scrollToBottom()
        self._lead_count += 1
        self.lead_counter.setText(f"{self._lead_count} leads")

        if self.table.isHidden():
            self.table.show()
            self.empty_state.hide()

    def set_progress(self, value: int):
        self.progress_bar.setVisible(value < 100)
        self.progress_bar.setValue(value)

    def set_status(self, message: str):
        self.status_label.setText(message)

    def on_scrape_finished(self, total: int):
        self.start_btn.setEnabled(True)
        self.start_btn.set_loading(False)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(total > 0)
        self.progress_bar.setVisible(False)
        self.set_status(f"Complete — {total} leads found")
        show_toast(self.window(), f"Scraping complete! Found {total} leads.", "success")

    def on_scrape_error(self, error: str):
        self.start_btn.setEnabled(True)
        self.start_btn.set_loading(False)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.set_status("Error occurred")
        show_toast(self.window(), f"Scraping error: {error[:100]}", "error", duration_ms=6000)

    def on_kill_switch(self, cooldown_seconds: int):
        self._kill_cooldown_remaining = cooldown_seconds
        self.kill_warning.setVisible(True)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._kill_timer.start(1000)
        self._update_kill_timer()
        show_toast(
            self.window(),
            "Detection risk is high. Scraping paused for 30 minutes for your safety.",
            "warning", duration_ms=10000,
        )

    # ─── Internal Methods ────────────────────────────────────────────

    def _on_start(self):
        niche = self.niche_input.text().strip()
        city = self.city_input.text().strip()
        if not niche or not city:
            show_toast(self.window(), "Please enter both a business niche and target city.", "warning")
            return

        query = self.query_input.text().strip()
        campaign_name = self.campaign_name_input.text().strip()
        limit = self.limit_spin.value()
        sources = [src for src, cb in self.source_checks.items() if cb.isChecked()]
        if not sources:
            show_toast(self.window(), "Please select at least one data source.", "warning")
            return

        self.table.setRowCount(0)
        self._lead_count = 0
        self.lead_counter.setText("0 leads")
        self.table.show()
        self.empty_state.hide()
        self.start_btn.set_loading(True)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.start_requested.emit(query, city, niche, campaign_name, limit, sources)

    def _on_stop(self):
        self.stop_btn.setEnabled(False)
        self.stop_requested.emit()
        self.set_status("Stopping...")

    def _update_kill_timer(self):
        if self._kill_cooldown_remaining <= 0:
            self.kill_warning.setVisible(False)
            self._kill_timer.stop()
            self.start_btn.setEnabled(True)
            self.start_btn.set_loading(False)
            self.set_status("Kill switch cooldown expired. Ready to scrape.")
            return
        minutes = self._kill_cooldown_remaining // 60
        seconds = self._kill_cooldown_remaining % 60
        self.kill_timer_label.setText(f"Resuming in {minutes}:{seconds:02d}")
        self._kill_cooldown_remaining -= 1

    def _on_export(self):
        if self.table.rowCount() == 0:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Leads", "leads.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        try:
            import csv
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.COLUMNS)
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            show_toast(self.window(), f"Exported {self.table.rowCount()} leads to CSV.", "success")
        except Exception as e:
            show_toast(self.window(), f"Export failed: {str(e)}", "error")

    # ─── Batch Import Handlers ───────────────────────────────────────

    def _on_browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV File", "", "CSV Files (*.csv)")
        if path:
            self._import_path = path
            from pathlib import Path
            self.import_path_label.setText(Path(path).name)
            self.import_btn.setEnabled(True)

    def _on_import_csv(self):
        path = getattr(self, "_import_path", "")
        if path:
            self.batch_import_requested.emit(path)
            show_toast(self.window(), "Batch import started...", "info")
            self.import_btn.setEnabled(False)
            self.import_path_label.setText("Importing...")

    def _on_apollo_search(self):
        niche = self.niche_input.text().strip()
        city = self.city_input.text().strip()
        if not niche or not city:
            show_toast(self.window(), "Please enter a niche and city above first.", "warning")
            return
        titles_raw = self.apollo_title_input.text().strip()
        title_keywords = [t.strip() for t in titles_raw.split(",") if t.strip()] if titles_raw else []
        limit = self.apollo_limit_spin.value()
        self.apollo_search_btn.set_loading(True)
        self.table.show()
        self.empty_state.hide()
        self.apollo_search_requested.emit(niche, city, title_keywords, limit)

    def on_apollo_search_finished(self, total: int):
        self.apollo_search_btn.set_loading(False)
        if total > 0:
            show_toast(self.window(), f"Apollo found {total} leads.", "success")
        else:
            show_toast(self.window(), "Apollo returned no results.", "info")

    # ─── LinkedIn CSV Handlers ───────────────────────────────────────

    def _on_browse_linkedin_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select LinkedIn CSV", "", "CSV Files (*.csv)")
        if path:
            self._linkedin_path = path
            from pathlib import Path
            self.linkedin_path_label.setText(Path(path).name)
            self.linkedin_import_btn.setEnabled(True)

    def _on_import_linkedin_csv(self):
        path = getattr(self, "_linkedin_path", "")
        if path:
            self.linkedin_import_requested.emit(path)
            show_toast(self.window(), "LinkedIn import started...", "info")
            self.linkedin_import_btn.setEnabled(False)
            self.linkedin_path_label.setText("Importing...")

    def on_linkedin_import_finished(self, total: int, skipped: int):
        self.linkedin_import_btn.setEnabled(True)
        self.linkedin_path_label.setText("No file selected")
        if total > 0:
            msg = f"LinkedIn import: {total} leads imported"
            if skipped > 0:
                msg += f", {skipped} skipped"
            show_toast(self.window(), msg, "success")
        else:
            show_toast(self.window(), f"LinkedIn import: no valid leads found ({skipped} skipped).", "warning")

    def on_hubspot_search_finished(self, total: int):
        if total > 0:
            show_toast(self.window(), f"HubSpot found {total} contacts.", "success")
        else:
            show_toast(self.window(), "HubSpot returned no results.", "info")

    def receive_context(self, context: dict):
        if not context:
            return
        if "prefill_niche" in context:
            self.niche_input.setText(context["prefill_niche"])
        if "prefill_city" in context:
            self.city_input.setText(context["prefill_city"])
        if "prefill_query" in context:
            self.query_input.setText(context["prefill_query"])
        # Allow switching to campaigns tab with a specific campaign
        if "show_campaign" in context:
            self.tabs.setCurrentIndex(1)
