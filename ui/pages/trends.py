"""
Aura — Trends Page (Google Trends Intelligence)
Keyword interest analysis, opportunity discovery, campaign monitoring, and alerts.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QScrollArea, QPushButton, QLineEdit, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard, StatCard
from ui.components.empty_state import EmptyState
from config import TRENDS_TIMEFRAMES


class TrendsPage(QWidget):
    """Google Trends intelligence — keyword analysis, opportunities, alerts."""

    search_requested = Signal(list, str, str)  # keywords, region, timeframe
    related_requested = Signal(str, str)  # keyword, region
    opportunities_requested = Signal(list, str)  # seed_keywords, region
    monitor_requested = Signal(int)  # campaign_id
    alert_acknowledged = Signal(int)  # alert_id
    refresh_alerts_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
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
        layout.setSpacing(20)

        # ─── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        title = QLabel("Google Trends")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)

        subtitle = QLabel("Real-time trend intelligence for your campaigns")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)

        header.addLayout(header_text, stretch=1)

        self.refresh_btn = QPushButton("Refresh Alerts")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_alerts_requested.emit)
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        # ─── Search Bar ──────────────────────────────────────────
        search_card = GlassCard()
        s_layout = search_card.get_layout()

        search_header = QLabel("Keyword Analysis")
        search_header.setObjectName("cardHeader")
        s_layout.addWidget(search_header)

        search_row = QHBoxLayout()
        search_row.setSpacing(10)

        self.keyword_input = QLineEdit()
        self.keyword_input.setObjectName("chatInput")
        self.keyword_input.setPlaceholderText("Enter keywords (comma-separated, max 5)...")
        self.keyword_input.setMinimumHeight(38)
        search_row.addWidget(self.keyword_input, stretch=3)

        self.region_combo = QComboBox()
        self.region_combo.setObjectName("secondaryButton")
        self.region_combo.addItems(["US", "GB", "DE", "FR", "CA", "AU", "IN", "BR", "JP", ""])
        self.region_combo.setCurrentText("US")
        self.region_combo.setMinimumHeight(38)
        search_row.addWidget(self.region_combo)

        self.timeframe_combo = QComboBox()
        self.timeframe_combo.setObjectName("secondaryButton")
        for code, label in TRENDS_TIMEFRAMES:
            self.timeframe_combo.addItem(label, code)
        self.timeframe_combo.setCurrentIndex(5)  # "Last 3 months"
        self.timeframe_combo.setMinimumHeight(38)
        search_row.addWidget(self.timeframe_combo)

        search_btn = QPushButton("Analyze")
        search_btn.setObjectName("primaryButton")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setMinimumHeight(38)
        search_btn.clicked.connect(self._on_search)
        search_row.addWidget(search_btn)

        related_btn = QPushButton("Related")
        related_btn.setObjectName("secondaryButton")
        related_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        related_btn.setMinimumHeight(38)
        related_btn.clicked.connect(self._on_related)
        search_row.addWidget(related_btn)

        s_layout.addLayout(search_row)
        layout.addWidget(search_card)

        # ─── Results Stats ────────────────────────────────────────
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.score_card = StatCard("—", "CURRENT SCORE", accent="blue", variant="solid")
        stats_grid.addWidget(self.score_card, 0, 0)

        self.direction_card = StatCard("—", "DIRECTION", accent="green")
        stats_grid.addWidget(self.direction_card, 0, 1)

        self.peak_card = StatCard("—", "PEAK DATE", accent="purple")
        stats_grid.addWidget(self.peak_card, 0, 2)

        self.alerts_count_card = StatCard("0", "ALERTS", accent="orange")
        stats_grid.addWidget(self.alerts_count_card, 0, 3)

        layout.addLayout(stats_grid)

        # ─── Interest Over Time ───────────────────────────────────
        interest_card = GlassCard()
        i_layout = interest_card.get_layout()

        interest_header = QLabel("Interest Over Time")
        interest_header.setObjectName("cardHeader")
        i_layout.addWidget(interest_header)

        self.interest_table = QTableWidget()
        self.interest_table.setColumnCount(3)
        self.interest_table.setHorizontalHeaderLabels(["Date", "Keyword", "Score"])
        self.interest_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.interest_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.interest_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.interest_table.setMinimumHeight(200)
        i_layout.addWidget(self.interest_table)

        layout.addWidget(interest_card)

        # ─── Related Queries ──────────────────────────────────────
        related_card = GlassCard()
        r_layout = related_card.get_layout()

        related_header = QLabel("Related & Rising Queries")
        related_header.setObjectName("cardHeader")
        r_layout.addWidget(related_header)

        self.related_table = QTableWidget()
        self.related_table.setColumnCount(3)
        self.related_table.setHorizontalHeaderLabels(["Query", "Type", "Value"])
        self.related_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.related_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.related_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.related_table.setMinimumHeight(180)
        r_layout.addWidget(self.related_table)

        layout.addWidget(related_card)

        # ─── Opportunity Discovery ────────────────────────────────
        opp_card = GlassCard()
        o_layout = opp_card.get_layout()

        opp_header_row = QHBoxLayout()
        opp_title = QLabel("Opportunity Discovery")
        opp_title.setObjectName("cardHeader")
        opp_header_row.addWidget(opp_title, stretch=1)

        self.opp_seed_input = QLineEdit()
        self.opp_seed_input.setObjectName("chatInput")
        self.opp_seed_input.setPlaceholderText("Seed keywords...")
        self.opp_seed_input.setMinimumHeight(34)
        self.opp_seed_input.setMaximumWidth(250)
        opp_header_row.addWidget(self.opp_seed_input)

        opp_btn = QPushButton("Find Niches")
        opp_btn.setObjectName("primaryButton")
        opp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        opp_btn.clicked.connect(self._on_find_opportunities)
        opp_header_row.addWidget(opp_btn)

        o_layout.addLayout(opp_header_row)

        self.opp_table = QTableWidget()
        self.opp_table.setColumnCount(4)
        self.opp_table.setHorizontalHeaderLabels(["Niche", "Direction", "Score", "Source"])
        self.opp_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.opp_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.opp_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.opp_table.setMinimumHeight(180)
        o_layout.addWidget(self.opp_table)

        layout.addWidget(opp_card)

        # ─── Alerts ───────────────────────────────────────────────
        alerts_card = GlassCard()
        a_layout = alerts_card.get_layout()

        alerts_header = QLabel("Trend Alerts")
        alerts_header.setObjectName("cardHeader")
        a_layout.addWidget(alerts_header)

        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(4)
        self.alerts_table.setHorizontalHeaderLabels(["Keyword", "Type", "Message", "Time"])
        self.alerts_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.alerts_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.alerts_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.alerts_table.setMinimumHeight(150)
        a_layout.addWidget(self.alerts_table)

        layout.addWidget(alerts_card)

        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── Slot handlers ────────────────────────────────────────────────

    def _on_search(self):
        text = self.keyword_input.text().strip()
        if not text:
            return
        keywords = [k.strip() for k in text.split(",") if k.strip()][:5]
        region = self.region_combo.currentText()
        timeframe = self.timeframe_combo.currentData()
        self.search_requested.emit(keywords, region, timeframe)

    def _on_related(self):
        text = self.keyword_input.text().strip()
        if not text:
            return
        keyword = text.split(",")[0].strip()
        region = self.region_combo.currentText()
        self.related_requested.emit(keyword, region)

    def _on_find_opportunities(self):
        text = self.opp_seed_input.text().strip()
        if not text:
            text = self.keyword_input.text().strip()
        if not text:
            return
        seeds = [k.strip() for k in text.split(",") if k.strip()][:3]
        region = self.region_combo.currentText()
        self.opportunities_requested.emit(seeds, region)

    # ─── Data update methods ──────────────────────────────────────────

    def update_interest(self, data: dict):
        """Update interest-over-time stats and table."""
        if not data.get("success"):
            return

        info = data.get("data", {})
        self.score_card.set_value(str(info.get("current_score", "—")))
        self.direction_card.set_value(info.get("trend_direction", "—").capitalize())
        self.peak_card.set_value(info.get("peak_date", "—") or "—")

        # Fill table
        scores = info.get("scores", {})
        rows = []
        for kw, entries in scores.items():
            if isinstance(entries, list):
                for entry in entries:
                    rows.append((entry.get("date", ""), kw, str(entry.get("value", 0))))

        self.interest_table.setRowCount(len(rows))
        for i, (date, kw, val) in enumerate(rows):
            self.interest_table.setItem(i, 0, QTableWidgetItem(date))
            self.interest_table.setItem(i, 1, QTableWidgetItem(kw))
            self.interest_table.setItem(i, 2, QTableWidgetItem(val))

    def update_related(self, data: dict):
        """Update the related queries table."""
        if not data.get("success"):
            return

        info = data.get("data", {})
        rows = []
        for item in info.get("top", []):
            query = item.get("query", "")
            val = str(item.get("value", ""))
            rows.append((query, "Top", val))
        for item in info.get("rising", []):
            query = item.get("query", "")
            val = str(item.get("value", ""))
            rows.append((query, "Rising", val))
        for item in info.get("breakouts", []):
            query = item.get("query", "")
            rows.append((query, "Breakout", "Breakout"))

        self.related_table.setRowCount(len(rows))
        for i, (query, qtype, val) in enumerate(rows):
            self.related_table.setItem(i, 0, QTableWidgetItem(query))
            self.related_table.setItem(i, 1, QTableWidgetItem(qtype))
            self.related_table.setItem(i, 2, QTableWidgetItem(val))

    def update_opportunities(self, data: dict):
        """Update the opportunity discovery table."""
        if not data.get("success"):
            return

        opps = data.get("data", {}).get("opportunities", [])
        self.opp_table.setRowCount(len(opps))
        for i, opp in enumerate(opps):
            self.opp_table.setItem(i, 0, QTableWidgetItem(opp.get("niche", "")))
            self.opp_table.setItem(i, 1, QTableWidgetItem(opp.get("direction", "")))
            self.opp_table.setItem(i, 2, QTableWidgetItem(str(opp.get("trend_score", 0))))
            self.opp_table.setItem(i, 3, QTableWidgetItem(opp.get("source_keyword", "")))

    def update_alerts(self, data: dict):
        """Update the alerts table."""
        if not data.get("success"):
            return

        alerts = data.get("data", [])
        self.alerts_count_card.set_value(str(len(alerts)))

        self.alerts_table.setRowCount(len(alerts))
        for i, alert in enumerate(alerts):
            self.alerts_table.setItem(i, 0, QTableWidgetItem(alert.get("keyword", "")))
            self.alerts_table.setItem(i, 1, QTableWidgetItem(alert.get("alert_type", "")))
            self.alerts_table.setItem(i, 2, QTableWidgetItem(alert.get("message", "")))
            self.alerts_table.setItem(i, 3, QTableWidgetItem(alert.get("triggered_at", "")))

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
