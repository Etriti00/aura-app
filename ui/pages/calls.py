"""
Aura — Calls Page
Voice call management: active calls, call log, transcript viewer, config.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QTextEdit, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard, StatCard
from ui.components.modern_button import ModernButton
from ui.components.empty_state import EmptyState


class CallsPage(QWidget):
    """Calls page — voice call log, active calls, transcript viewer."""

    call_requested = Signal(int)         # lead_id
    end_call_requested = Signal(int)     # call_id
    refresh_requested = Signal()
    view_transcript_requested = Signal(int)  # call_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("callsPage")
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
        title = QLabel("Voice Calls")
        title.setObjectName("sectionHeader")
        header.addWidget(title)
        subtitle = QLabel("AI-powered cold calling — outbound & inbound voice conversations")
        subtitle.setObjectName("sectionSubheader")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # ─── Stats Row ────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.stat_total = StatCard("0", "TOTAL CALLS", accent="blue")
        self.stat_active = StatCard("0", "ACTIVE", accent="green")
        self.stat_interested = StatCard("0", "INTERESTED", accent="purple")
        self.stat_meetings = StatCard("0", "MEETINGS", accent="orange")

        for card in [self.stat_total, self.stat_active, self.stat_interested, self.stat_meetings]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # ─── Provider Status ──────────────────────────────────────
        provider_card = GlassCard()
        provider_layout = provider_card.get_layout()
        provider_hdr = QLabel("Voice Providers")
        provider_hdr.setObjectName("cardHeader")
        provider_layout.addWidget(provider_hdr)

        self.provider_row = QHBoxLayout()
        self.provider_row.setSpacing(12)
        self.twilio_badge = QLabel("Twilio")
        self.twilio_badge.setObjectName("badgeDanger")
        self.tts_badge = QLabel("TTS")
        self.tts_badge.setObjectName("badgeDanger")
        self.stt_badge = QLabel("STT")
        self.stt_badge.setObjectName("badgeDanger")
        self.ws_badge = QLabel("WS Server")
        self.ws_badge.setObjectName("badgeDanger")

        for badge in [self.twilio_badge, self.tts_badge, self.stt_badge, self.ws_badge]:
            self.provider_row.addWidget(badge)
        self.provider_row.addStretch()

        provider_layout.addLayout(self.provider_row)
        provider_card.setObjectName("callConfigPanel")
        layout.addWidget(provider_card)

        # ─── Active Calls ─────────────────────────────────────────
        active_card = GlassCard()
        active_layout = active_card.get_layout()
        active_hdr = QLabel("Active Calls")
        active_hdr.setObjectName("cardHeader")
        active_layout.addWidget(active_hdr)

        self.active_table = QTableWidget()
        self.active_table.setObjectName("activeCallCard")
        self.active_table.setColumnCount(4)
        self.active_table.setHorizontalHeaderLabels([
            "Lead", "Duration", "Transcript Lines", "Actions",
        ])
        self.active_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.active_table.verticalHeader().setVisible(False)
        self.active_table.setMaximumHeight(150)
        active_layout.addWidget(self.active_table)
        layout.addWidget(active_card)

        # ─── Call Log Table ────────────────────────────────────────
        log_card = GlassCard()
        log_layout = log_card.get_layout()
        log_hdr_row = QHBoxLayout()
        log_hdr = QLabel("Call History")
        log_hdr.setObjectName("cardHeader")
        log_hdr_row.addWidget(log_hdr)
        log_hdr_row.addStretch()

        self.refresh_btn = ModernButton("Refresh")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())
        log_hdr_row.addWidget(self.refresh_btn)
        log_layout.addLayout(log_hdr_row)

        self.log_table = QTableWidget()
        self.log_table.setObjectName("callLogTable")
        self.log_table.setColumnCount(7)
        self.log_table.setHorizontalHeaderLabels([
            "Lead", "Direction", "Status", "Duration", "Outcome", "Date", "Actions",
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setMinimumHeight(200)
        log_layout.addWidget(self.log_table)

        self.empty_state = EmptyState(
            icon_key="sidebar_calls",
            title="No Calls Yet",
            subtitle="Configure Twilio and a TTS provider in Settings to start making calls.",
        )
        self.empty_state.setVisible(False)
        log_layout.addWidget(self.empty_state)

        layout.addWidget(log_card)

        # ─── Transcript Viewer ─────────────────────────────────────
        transcript_card = GlassCard()
        transcript_layout = transcript_card.get_layout()
        transcript_hdr = QLabel("Call Transcript")
        transcript_hdr.setObjectName("cardHeader")
        transcript_layout.addWidget(transcript_hdr)

        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setObjectName("callTranscriptPanel")
        self.transcript_viewer.setReadOnly(True)
        self.transcript_viewer.setMinimumHeight(200)
        self.transcript_viewer.setPlaceholderText("Select a call from the history to view its transcript...")
        transcript_layout.addWidget(self.transcript_viewer)

        layout.addWidget(transcript_card)
        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def update_call_history(self, calls: list):
        """Populate the call log table."""
        self.log_table.setRowCount(len(calls))
        total = len(calls)
        interested = sum(1 for c in calls if c.get("outcome") == "interested")
        meetings = sum(1 for c in calls if c.get("outcome") == "meeting_booked")

        self.stat_total.set_value(str(total))
        self.stat_interested.set_value(str(interested))
        self.stat_meetings.set_value(str(meetings))

        self.empty_state.setVisible(total == 0)
        self.log_table.setVisible(total > 0)

        for row, call in enumerate(calls):
            self.log_table.setItem(row, 0, QTableWidgetItem(call.get("lead_name", "")))
            self.log_table.setItem(row, 1, QTableWidgetItem(call.get("direction", "")))
            self.log_table.setItem(row, 2, QTableWidgetItem(call.get("status", "")))

            duration = call.get("duration", 0) or 0
            dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "-"
            self.log_table.setItem(row, 3, QTableWidgetItem(dur_str))

            outcome = call.get("outcome") or "-"
            outcome_item = QTableWidgetItem(outcome)
            self.log_table.setItem(row, 4, outcome_item)

            self.log_table.setItem(row, 5, QTableWidgetItem(call.get("started_at", "")[:16]))

            view_btn = QPushButton("View")
            view_btn.setObjectName("tableActionButton")
            view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            call_id = call.get("id", 0)
            view_btn.clicked.connect(lambda checked, cid=call_id: self._on_view_transcript(cid))
            cell = QWidget()
            cell_lyt = QHBoxLayout(cell)
            cell_lyt.setContentsMargins(4, 3, 4, 3)
            cell_lyt.addStretch()
            cell_lyt.addWidget(view_btn)
            cell_lyt.addStretch()
            self.log_table.setCellWidget(row, 6, cell)

    def _on_view_transcript(self, call_id: int):
        """Request to load a call transcript — wired by controller."""
        self.view_transcript_requested.emit(call_id)

    def update_active_calls(self, calls: list):
        """Update the active calls panel."""
        self.active_table.setRowCount(len(calls))
        self.stat_active.set_value(str(len(calls)))

        for row, call in enumerate(calls):
            self.active_table.setItem(row, 0, QTableWidgetItem(call.get("lead_name", "")))
            self.active_table.setItem(row, 1, QTableWidgetItem(call.get("started_at", "")))
            self.active_table.setItem(row, 2, QTableWidgetItem(str(call.get("transcript_count", 0))))

            end_btn = QPushButton("End Call")
            end_btn.setObjectName("tableActionDanger")
            end_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            call_id = call.get("call_id", 0)
            end_btn.clicked.connect(lambda checked, cid=call_id: self.end_call_requested.emit(cid))
            cell = QWidget()
            cell_lyt = QHBoxLayout(cell)
            cell_lyt.setContentsMargins(4, 3, 4, 3)
            cell_lyt.addStretch()
            cell_lyt.addWidget(end_btn)
            cell_lyt.addStretch()
            self.active_table.setCellWidget(row, 3, cell)

    def update_call_detail(self, data: dict):
        """Display a full call transcript."""
        transcript = data.get("transcript", [])
        if not transcript:
            self.transcript_viewer.setPlainText("No transcript available for this call.")
            return

        lines = [f"Call #{data.get('call_id', '?')}"]
        if data.get("outcome"):
            lines.append(f"Outcome: {data['outcome']} | Sentiment: {data.get('sentiment', '?')}")
        if data.get("notes"):
            lines.append(f"Notes: {data['notes']}")
        lines.append("─" * 60)

        for entry in transcript:
            speaker = entry.get("speaker", "?").upper()
            text = entry.get("text", "")
            ts = entry.get("ts", "")[:19]
            lines.append(f"[{ts}] {speaker}: {text}")

        self.transcript_viewer.setPlainText("\n".join(lines))

    def update_provider_status(self, status: dict):
        """Update provider badge colors."""
        def _set_badge(badge, key, label):
            active = status.get(key, False)
            badge.setObjectName("badgeSuccess" if active else "badgeDanger")
            extra = f" ({status.get(key + '_provider', '')})" if active and status.get(key + "_provider") else ""
            badge.setText(f"{label} Ready{extra}" if active else f"{label} Off")
            badge.style().unpolish(badge)
            badge.style().polish(badge)

        _set_badge(self.twilio_badge, "twilio", "Twilio")
        _set_badge(self.tts_badge, "tts", "TTS")
        _set_badge(self.stt_badge, "stt", "STT")

        ws_active = status.get("ws_server", False)
        self.ws_badge.setObjectName("badgeSuccess" if ws_active else "badgeWarning")
        self.ws_badge.setText("WS Server Active" if ws_active else "WS Server Off")
        self.ws_badge.style().unpolish(self.ws_badge)
        self.ws_badge.style().polish(self.ws_badge)

    def receive_context(self, context: dict):
        """Handle cross-page navigation context."""
        lead_id = context.get("lead_id")
        if lead_id:
            self.call_requested.emit(lead_id)
