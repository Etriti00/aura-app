"""
Aura — Hunter Page (Full Implementation)
Search form, live-updating results table, Start/Stop controls,
progress bar, kill switch warning, and export functionality.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QComboBox, QCheckBox, QSpinBox, QFrame, QScrollArea,
    QAbstractItemView, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QColor

from ui.icons import get_icon, get_pixmap

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.toast_notification import show_toast
from ui.components.empty_state import EmptyState
from config import SCRAPER_SOURCES, LEAD_SOURCES, LEAD_SOURCE_LABELS


class HunterPage(QWidget):
    """Hunter page — lead scraping interface with live results table."""

    # Signals to controller
    start_requested = Signal(str, str, str, str, int, list)  # query, city, niche, name, limit, sources
    stop_requested = Signal()
    batch_import_requested = Signal(str)  # CSV file path
    apollo_search_requested = Signal(str, str, list, int)     # niche, city, title_keywords, limit
    hubspot_search_requested = Signal(str, str, str, int)     # niche, city, company_name, limit
    linkedin_import_requested = Signal(str)                    # CSV file path

    # Navigation signal (emitted when user wants to navigate to another page with context)
    navigate_requested = Signal(int, dict)  # page_index, context

    # Table column definitions
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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # ─── Header Row ────────────────────────────────────────────────
        header_row = QHBoxLayout()

        header_text = QVBoxLayout()
        title = QLabel("Hunter")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)

        subtitle = QLabel("Search and discover business leads across the web")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        header_row.addLayout(header_text, stretch=1)

        # Lead counter badge
        self.lead_counter = QLabel("0 leads")
        self.lead_counter.setObjectName("badgeInfo")
        self.lead_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lead_counter.setFixedHeight(28)
        header_row.addWidget(self.lead_counter, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addLayout(header_row)

        # ─── Search Form Card ──────────────────────────────────────────
        search_card = GlassCard()
        form = search_card.get_layout()
        form.setSpacing(8)

        # Row 1: Campaign name + Niche
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        # Campaign name
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

        # Niche
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

        # Row 3: Unified Sources (categorized)
        src_row = QVBoxLayout()
        src_row.setSpacing(8)
        src_label = QLabel("Lead Sources")
        src_label.setObjectName("formLabel")
        src_row.addWidget(src_label)

        self.source_checks = {}

        # Web Scrapers
        scraper_row = QHBoxLayout()
        scraper_row.setSpacing(10)
        scraper_tag = QLabel("Web")
        scraper_tag.setObjectName("badgeInfo")
        scraper_tag.setFixedWidth(52)
        scraper_row.addWidget(scraper_tag)
        for source in LEAD_SOURCES.get("scraper", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(True)
            self.source_checks[source] = cb
            scraper_row.addWidget(cb)
        scraper_row.addStretch()
        src_row.addLayout(scraper_row)

        # API Sources
        api_row = QHBoxLayout()
        api_row.setSpacing(10)
        api_tag = QLabel("API")
        api_tag.setObjectName("badgeSuccess")
        api_tag.setFixedWidth(52)
        api_row.addWidget(api_tag)
        for source in LEAD_SOURCES.get("api", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(False)  # API sources unchecked by default (require keys)
            self.source_checks[source] = cb
            api_row.addWidget(cb)
        api_row.addStretch()
        src_row.addLayout(api_row)

        # Import Sources
        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        import_tag = QLabel("Import")
        import_tag.setObjectName("badgeWarning")
        import_tag.setFixedWidth(52)
        import_row.addWidget(import_tag)
        for source in LEAD_SOURCES.get("import", []):
            label = LEAD_SOURCE_LABELS.get(source, source)
            cb = QCheckBox(label)
            cb.setChecked(False)  # Import sources unchecked by default
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

        # ─── Kill Switch Warning ───────────────────────────────────────
        self.kill_warning = QFrame()
        self.kill_warning.setObjectName("toastWarning")
        self.kill_warning.setVisible(False)
        kw_layout = QHBoxLayout(self.kill_warning)
        kw_layout.setContentsMargins(16, 10, 16, 10)

        kw_icon = QLabel()
        kw_icon.setPixmap(get_pixmap("warning", "dark", "warning", 16))
        kw_icon.setFixedSize(20, 20)
        kw_layout.addWidget(kw_icon)

        self.kill_warning_label = QLabel(
            "Detection risk is high. Scraping paused for safety."
        )
        self.kill_warning_label.setObjectName("warningText")
        kw_layout.addWidget(self.kill_warning_label, stretch=1)

        self.kill_timer_label = QLabel("")
        self.kill_timer_label.setObjectName("warningText")
        kw_layout.addWidget(self.kill_timer_label)

        layout.addWidget(self.kill_warning)

        # ─── Progress Bar ──────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        # ─── Status bar ───────────────────────────────────────────────
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

        # ─── Results Table ─────────────────────────────────────────────
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

        # Empty State Overlay
        self.empty_state = EmptyState(
            icon_key="empty_hunter",
            title="Ready to Hunt?",
            subtitle="Enter a niche and city above to start discovering leads.",
            action_text="Start Hunting"
        )
        self.empty_state.action_clicked.connect(self._on_start)
        self.empty_state.setMinimumHeight(250)
        layout.addWidget(self.empty_state)
        self.table.hide() # Hide table initially

        # ─── Batch Import Section ───────────────────────────────────────
        import_card = GlassCard()
        import_layout = import_card.get_layout()

        import_hdr_row = QHBoxLayout()
        import_hdr_icon = QLabel()
        import_hdr_icon.setPixmap(get_pixmap("batch_import", "dark", "default", 16))
        import_hdr_icon.setFixedSize(20, 20)
        import_header = QLabel("Batch Import")
        import_header.setObjectName("cardHeader")
        import_hdr_row.addWidget(import_hdr_icon)
        import_hdr_row.addWidget(import_header, stretch=1)
        import_layout.addLayout(import_hdr_row)

        import_row = QHBoxLayout()
        self.import_path_label = QLabel("No file selected")
        self.import_path_label.setObjectName("mutedText")
        import_row.addWidget(self.import_path_label, stretch=1)

        browse_btn = ModernButton("Browse CSV", "primary")
        browse_btn.setFixedHeight(40) # Standardized height
        browse_btn.clicked.connect(self._on_browse_csv)
        import_row.addWidget(browse_btn)

        self.import_btn = ModernButton("Import", "primary")
        self.import_btn.setFixedHeight(40) # Standardized height
        self.import_btn.setEnabled(False)
        self.import_btn.clicked.connect(self._on_import_csv)
        import_row.addWidget(self.import_btn)

        import_layout.addLayout(import_row)
        layout.addWidget(import_card)

        # ─── API Source Options Card ────────────────────────────────────
        api_card = GlassCard()
        api_layout = api_card.get_layout()
        api_layout.setSpacing(8)

        api_hdr_row = QHBoxLayout()
        api_hdr_icon = QLabel()
        api_hdr_icon.setPixmap(get_pixmap("apollo_search", "dark", "default", 16))
        api_hdr_icon.setFixedSize(20, 20)
        api_header = QLabel("API Source Options")
        api_header.setObjectName("cardHeader")
        api_hdr_row.addWidget(api_hdr_icon)
        api_hdr_row.addWidget(api_header, stretch=1)
        api_layout.addLayout(api_hdr_row)

        api_info = QLabel("Configure search parameters for Apollo, Hunter.io, and HubSpot.")
        api_info.setObjectName("mutedText")
        api_layout.addWidget(api_info)

        # Apollo: Title keywords
        title_row = QVBoxLayout()
        title_row.setSpacing(8)
        title_label = QLabel("Apollo — Title Keywords")
        title_label.setObjectName("formLabel")
        title_row.addWidget(title_label)
        self.apollo_title_input = QLineEdit()
        self.apollo_title_input.setPlaceholderText("CEO, Founder, Owner")
        self.apollo_title_input.setClearButtonEnabled(True)
        title_row.addWidget(self.apollo_title_input)
        api_layout.addLayout(title_row)

        # HubSpot: Company name filter
        hs_row = QVBoxLayout()
        hs_row.setSpacing(8)
        hs_label = QLabel("HubSpot — Company Name Filter")
        hs_label.setObjectName("formLabel")
        hs_row.addWidget(hs_label)
        self.hubspot_company_input = QLineEdit()
        self.hubspot_company_input.setPlaceholderText("Filter by company name (optional)")
        self.hubspot_company_input.setClearButtonEnabled(True)
        hs_row.addWidget(self.hubspot_company_input)
        api_layout.addLayout(hs_row)

        # Options row: Max employees + max results
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

        api_layout.addLayout(api_opts)

        # LinkedIn CSV import row
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

        api_layout.addLayout(linkedin_row)
        layout.addWidget(api_card)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Kill switch cooldown timer
        self._kill_timer = QTimer(self)
        self._kill_timer.timeout.connect(self._update_kill_timer)
        self._kill_cooldown_remaining = 0

    # ─── Signal Handlers (from Controller) ─────────────────────────────

    def add_lead_row(self, lead_data: dict):
        """Add a new lead row to the results table (called from controller signal)."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(lead_data.get("business_name", "")))
        self.table.setItem(row, 1, QTableWidgetItem(lead_data.get("category", "")))
        self.table.setItem(row, 2, QTableWidgetItem(lead_data.get("city", "")))
        self.table.setItem(row, 3, QTableWidgetItem(lead_data.get("phone", "")))
        self.table.setItem(row, 4, QTableWidgetItem(lead_data.get("email", "")))
        self.table.setItem(row, 5, QTableWidgetItem(lead_data.get("source_platform", "")))

        # Website indicator
        has_site = lead_data.get("has_website", False)
        website_item = QTableWidgetItem("Yes" if has_site else "No")
        website_item.setForeground(
            QColor("#34D399") if has_site else QColor("#F87171")
        )
        self.table.setItem(row, 6, website_item)

        # Status badge
        status = lead_data.get("status", "new")
        status_item = QTableWidgetItem(status.upper())
        status_colors = {
            "new": "#6366F1",
            "qualifying": "#FBBF24",
            "qualified": "#34D399",
            "disqualified": "#F87171",
        }
        status_item.setForeground(QColor(status_colors.get(status, "#6B6B80")))
        self.table.setItem(row, 7, status_item)

        # Auto-scroll to latest
        self.table.scrollToBottom()

        # Update counter
        self._lead_count += 1
        self.lead_counter.setText(f"{self._lead_count} leads")
        
        # Show table if hidden
        if self.table.isHidden():
            self.table.show()
            self.empty_state.hide()

    def set_progress(self, value: int):
        """Update progress bar."""
        self.progress_bar.setVisible(value < 100)
        self.progress_bar.setValue(value)

    def set_status(self, message: str):
        """Update status text."""
        self.status_label.setText(message)

    def on_scrape_finished(self, total: int):
        """Handle scrape completion."""
        self.start_btn.setEnabled(True)
        self.start_btn.set_loading(False)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(total > 0)
        self.progress_bar.setVisible(False)
        self.set_status(f"Complete — {total} leads found")
        show_toast(self.window(), f"Scraping complete! Found {total} leads.", "success")

    def on_scrape_error(self, error: str):
        """Handle scrape error."""
        self.start_btn.setEnabled(True)
        self.start_btn.set_loading(False)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.set_status("Error occurred")
        show_toast(self.window(), f"Scraping error: {error[:100]}", "error", duration_ms=6000)

    def on_kill_switch(self, cooldown_seconds: int):
        """Show kill switch warning with countdown."""
        self._kill_cooldown_remaining = cooldown_seconds
        self.kill_warning.setVisible(True)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self._kill_timer.start(1000)  # Update every second
        self._update_kill_timer()
        show_toast(
            self.window(),
            "Detection risk is high. Scraping paused for 30 minutes for your safety.",
            "warning",
            duration_ms=10000,
        )

    # ─── Internal Methods ──────────────────────────────────────────────

    def _on_start(self):
        """Handle Start button click."""
        niche = self.niche_input.text().strip()
        city = self.city_input.text().strip()

        if not niche or not city:
            show_toast(self.window(), "Please enter both a business niche and target city.", "warning")
            return

        query = self.query_input.text().strip()
        campaign_name = self.campaign_name_input.text().strip()
        limit = self.limit_spin.value()

        sources = [
            src for src, cb in self.source_checks.items()
            if cb.isChecked()
        ]
        if not sources:
            show_toast(self.window(), "Please select at least one data source.", "warning")
            return

        # Reset table
        self.table.setRowCount(0)
        self._lead_count = 0
        self.lead_counter.setText("0 leads")
        
        # Toggle views
        self.table.show()
        self.empty_state.hide()

        # Update UI state
        self.start_btn.set_loading(True)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Emit signal to controller
        self.start_requested.emit(query, city, niche, campaign_name, limit, sources)

    def _on_stop(self):
        """Handle Stop button click."""
        self.stop_btn.setEnabled(False)
        self.stop_requested.emit()
        self.set_status("Stopping...")

    def _update_kill_timer(self):
        """Update the kill switch countdown display."""
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
        """Export results to CSV."""
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

            show_toast(
                self.window(),
                f"Exported {self.table.rowCount()} leads to CSV.",
                "success",
            )
        except Exception as e:
            show_toast(self.window(), f"Export failed: {str(e)}", "error")

    # ─── Batch Import Handlers ─────────────────────────────────────────

    def _on_browse_csv(self):
        """Open file dialog to select a CSV file for batch import."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if path:
            self._import_path = path
            # Show just the filename
            from pathlib import Path
            self.import_path_label.setText(Path(path).name)
            self.import_btn.setEnabled(True)

    def _on_import_csv(self):
        """Emit signal to import the selected CSV file."""
        path = getattr(self, "_import_path", "")
        if path:
            self.batch_import_requested.emit(path)
            show_toast(self.window(), "Batch import started...", "info")
            self.import_btn.setEnabled(False)
            self.import_path_label.setText("Importing...")

    def _on_apollo_search(self):
        """Handle Apollo Search button click."""
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
        """Handle Apollo search completion."""
        self.apollo_search_btn.set_loading(False)
        if total > 0:
            show_toast(self.window(), f"Apollo found {total} leads.", "success")
        else:
            show_toast(self.window(), "Apollo returned no results.", "info")

    # ─── LinkedIn CSV Handlers ────────────────────────────────────────

    def _on_browse_linkedin_csv(self):
        """Open file dialog to select a LinkedIn Sales Navigator CSV."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select LinkedIn CSV", "", "CSV Files (*.csv)"
        )
        if path:
            self._linkedin_path = path
            from pathlib import Path
            self.linkedin_path_label.setText(Path(path).name)
            self.linkedin_import_btn.setEnabled(True)

    def _on_import_linkedin_csv(self):
        """Emit signal to import the LinkedIn CSV file."""
        path = getattr(self, "_linkedin_path", "")
        if path:
            self.linkedin_import_requested.emit(path)
            show_toast(self.window(), "LinkedIn import started...", "info")
            self.linkedin_import_btn.setEnabled(False)
            self.linkedin_path_label.setText("Importing...")

    def on_linkedin_import_finished(self, total: int, skipped: int):
        """Handle LinkedIn import completion."""
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
        """Handle HubSpot search completion."""
        if total > 0:
            show_toast(self.window(), f"HubSpot found {total} contacts.", "success")
        else:
            show_toast(self.window(), "HubSpot returned no results.", "info")

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        if not context:
            return
        if "prefill_niche" in context:
            self.niche_input.setText(context["prefill_niche"])
        if "prefill_city" in context:
            self.city_input.setText(context["prefill_city"])
        if "prefill_query" in context:
            self.query_input.setText(context["prefill_query"])

