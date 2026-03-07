"""
Aura — Outreach Page (Full Implementation)
Campaign/lead selector, email draft generation, preview, send controls.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView,
    QLineEdit, QTextEdit, QSplitter, QHeaderView, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.toast_notification import show_toast
from ui.components.empty_state import EmptyState
from ui.icons import get_icon, get_pixmap


class OutreachPage(QWidget):
    """Outreach page — generate AI emails and send to qualified leads."""

    # Signals to controller
    generate_requested = Signal(int, int)        # lead_id, skill_id
    send_requested = Signal(int, str, str, str)  # lead_id, to_email, subject, body
    generate_channels_requested = Signal(int, int)  # lead_id, skill_id
    crm_sync_requested = Signal(int)             # campaign_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 24, 32, 24)
        main_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Outreach")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Generate personalized emails and reach out to qualified leads")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, stretch=1)
        main_layout.addLayout(header)

        # Tab widget
        self.tabs = QTabWidget()

        # ─── Tab 0: Compose (existing content) ─────────────────
        compose_tab = QWidget()
        layout = QVBoxLayout(compose_tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        # Selector: Campaign + Skill + CRM sync
        selector_card = GlassCard()
        sel_layout = selector_card.get_layout()

        sel_row = QHBoxLayout()
        sel_row.setSpacing(10)

        campaign_lbl = QLabel("Campaign:")
        sel_row.addWidget(campaign_lbl)
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumWidth(140)
        self.campaign_combo.currentIndexChanged.connect(self._on_campaign_changed)
        sel_row.addWidget(self.campaign_combo, stretch=1)

        skill_lbl = QLabel("Skill:")
        sel_row.addWidget(skill_lbl)
        self.skill_combo = QComboBox()
        self.skill_combo.setMinimumWidth(140)
        sel_row.addWidget(self.skill_combo, stretch=1)

        self.crm_sync_btn = ModernButton("Sync to CRM", "secondary")
        self.crm_sync_btn.setFixedHeight(36)
        self.crm_sync_btn.clicked.connect(self._on_crm_sync)
        sel_row.addWidget(self.crm_sync_btn)

        sel_layout.addLayout(sel_row)
        layout.addWidget(selector_card)

        # Splitter: Lead table | Email editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Lead table card
        table_card = GlassCard()
        lead_layout = table_card.get_layout()

        table_header = QHBoxLayout()
        table_label = QLabel("Qualified Leads")
        table_label.setObjectName("cardHeader")
        table_header.addWidget(table_label, stretch=1)

        self.status_label = QLabel("Select a campaign to load leads")
        self.status_label.setObjectName("mutedText")
        table_header.addWidget(self.status_label)
        lead_layout.addLayout(table_header)

        self.lead_table = QTableWidget()
        self.lead_table.setColumnCount(4)
        self.lead_table.setHorizontalHeaderLabels(["Business", "City", "Email", "Status"])
        self.lead_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lead_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lead_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lead_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lead_table.verticalHeader().setVisible(False)
        self.lead_table.setShowGrid(False)
        self.lead_table.setAlternatingRowColors(True)
        self.lead_table.currentCellChanged.connect(lambda r, c, pr, pc: self._on_lead_selected(r))
        lead_layout.addWidget(self.lead_table)

        self.empty_leads = EmptyState(
            icon_key="empty_outreach", 
            title="No leads loaded",
            subtitle="Select a campaign above to load qualified leads."
        )
        lead_layout.addWidget(self.empty_leads)
        self.lead_table.hide() # Initially hidden until leads loaded

        splitter.addWidget(table_card)

        # Right: Email preview/editor
        email_card = GlassCard()
        email_layout = email_card.get_layout()

        email_header = QLabel("Email Preview")
        email_header.setObjectName("cardHeader")
        email_layout.addWidget(email_header)

        # To field
        to_row = QHBoxLayout()
        to_label = QLabel("To:")
        to_label.setObjectName("formLabel")
        to_label.setMinimumWidth(60)
        to_row.addWidget(to_label)
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("recipient@email.com")
        self.to_input.setClearButtonEnabled(True)
        to_row.addWidget(self.to_input)
        email_layout.addLayout(to_row)

        # Subject
        subj_row = QHBoxLayout()
        subj_label = QLabel("Subject:")
        subj_label.setObjectName("formLabel")
        subj_label.setMinimumWidth(60)
        subj_row.addWidget(subj_label)
        self.subject_input = QLineEdit()
        self.subject_input.setPlaceholderText("Email subject...")
        self.subject_input.setClearButtonEnabled(True)
        subj_row.addWidget(self.subject_input)
        email_layout.addLayout(subj_row)

        # Body
        self.body_editor = QTextEdit()
        self.body_editor.setPlaceholderText("Generate an email or write your own...")
        email_layout.addWidget(self.body_editor, stretch=1)

        # Tone indicator
        self.tone_label = QLabel("")
        self.tone_label.setObjectName("mutedText")
        email_layout.addWidget(self.tone_label)

        # Action buttons
        btn_row = QHBoxLayout()

        self.generate_btn = ModernButton("Generate Email", "primary")
        self.generate_btn.setIcon(get_icon("generate", "dark", "default"))
        self.generate_btn.setIconSize(QSize(16, 16))
        self.generate_btn.setFixedHeight(38)
        self.generate_btn.clicked.connect(self._on_generate)
        btn_row.addWidget(self.generate_btn)

        self.send_btn = ModernButton("Send Email", "primary")
        self.send_btn.setIcon(get_icon("send_email", "dark", "default"))
        self.send_btn.setIconSize(QSize(16, 16))
        self.send_btn.setFixedHeight(38)
        self.send_btn.clicked.connect(self._on_send)
        self.send_btn.setEnabled(False)
        btn_row.addWidget(self.send_btn)

        email_layout.addLayout(btn_row)

        splitter.addWidget(email_card)
        splitter.setSizes([400, 500])

        layout.addWidget(splitter, stretch=1)
        self.tabs.addTab(compose_tab, get_icon("tab_compose", "dark"), "Compose")

        # ─── Tab 1: Sequences ──────────────────────────────────
        seq_tab = QWidget()
        seq_layout = QVBoxLayout(seq_tab)
        seq_layout.setContentsMargins(0, 12, 0, 0)
        seq_layout.setSpacing(12)

        seq_card = GlassCard()
        sl = seq_card.get_layout()
        _seq_header = QLabel("Follow-Up Sequences")
        _seq_header.setObjectName("cardHeader")
        sl.addWidget(_seq_header)

        self.seq_table = QTableWidget()
        self.seq_table.setColumnCount(4)
        self.seq_table.setHorizontalHeaderLabels(["Sequence", "Steps", "Active Leads", "Status"])
        self.seq_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.seq_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.seq_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        sl.addWidget(self.seq_table, stretch=1)

        seq_status = QLabel("Sequences run automatically every 30 minutes")
        seq_status.setObjectName("mutedText")
        sl.addWidget(seq_status)

        seq_layout.addWidget(seq_card, stretch=1)
        self.tabs.addTab(seq_tab, get_icon("tab_sequences", "dark"), "Sequences")

        # ─── Tab 2: Replies ────────────────────────────────────
        rep_tab = QWidget()
        rep_layout = QVBoxLayout(rep_tab)
        rep_layout.setContentsMargins(0, 12, 0, 0)
        rep_layout.setSpacing(12)

        rep_card = GlassCard()
        rl = rep_card.get_layout()
        _rep_header = QLabel("Detected Replies")
        _rep_header.setObjectName("cardHeader")
        rl.addWidget(_rep_header)

        self.reply_table = QTableWidget()
        self.reply_table.setColumnCount(4)
        self.reply_table.setHorizontalHeaderLabels(["Lead", "Subject", "Received", "Sentiment"])
        self.reply_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.reply_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.reply_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        rl.addWidget(self.reply_table, stretch=1)

        rep_status = QLabel("Reply detection checks IMAP every 2 hours")
        rep_status.setObjectName("mutedText")
        rl.addWidget(rep_status)

        rep_layout.addWidget(rep_card, stretch=1)
        self.tabs.addTab(rep_tab, get_icon("tab_replies", "dark"), "Replies")

        # ─── Tab 3: Scheduled ──────────────────────────────────
        sched_tab = QWidget()
        sched_layout = QVBoxLayout(sched_tab)
        sched_layout.setContentsMargins(0, 12, 0, 0)
        sched_layout.setSpacing(12)

        sched_card = GlassCard()
        scl = sched_card.get_layout()
        _sched_header = QLabel("Scheduled Sends")
        _sched_header.setObjectName("cardHeader")
        scl.addWidget(_sched_header)

        self.sched_table = QTableWidget()
        self.sched_table.setColumnCount(4)
        self.sched_table.setHorizontalHeaderLabels(["Lead", "Subject", "Scheduled For", "Status"])
        self.sched_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sched_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sched_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        scl.addWidget(self.sched_table, stretch=1)

        sched_status = QLabel("Scheduled queue drains every 5 minutes")
        sched_status.setObjectName("mutedText")
        scl.addWidget(sched_status)

        sched_layout.addWidget(sched_card, stretch=1)
        self.tabs.addTab(sched_tab, get_icon("tab_scheduled", "dark"), "Scheduled")

        # ─── Tab 4: Channels ─────────────────────────────────
        chan_tab = QWidget()
        chan_layout = QVBoxLayout(chan_tab)
        chan_layout.setContentsMargins(0, 12, 0, 0)
        chan_layout.setSpacing(12)

        chan_card = GlassCard()
        cl = chan_card.get_layout()

        chan_header_row = QHBoxLayout()
        _chan_header = QLabel("Multi-Channel Drafts")
        _chan_header.setObjectName("cardHeader")
        chan_header_row.addWidget(_chan_header, stretch=1)

        self.chan_generate_btn = ModernButton("Generate All Channels", "primary")
        self.chan_generate_btn.setFixedHeight(36)
        self.chan_generate_btn.clicked.connect(self._on_generate_channels)
        chan_header_row.addWidget(self.chan_generate_btn)
        cl.addLayout(chan_header_row)

        # Channel sub-tabs: Email / LinkedIn / Twitter
        self.channel_tabs = QTabWidget()

        email_sub = QWidget()
        esl = QVBoxLayout(email_sub)
        self.chan_email_subject = QLineEdit()
        self.chan_email_subject.setPlaceholderText("Email subject...")
        esl.addWidget(self.chan_email_subject)
        self.chan_email_body = QTextEdit()
        self.chan_email_body.setPlaceholderText("Email body will appear here...")
        esl.addWidget(self.chan_email_body, stretch=1)
        self.channel_tabs.addTab(email_sub, "Email")

        li_sub = QWidget()
        lsl = QVBoxLayout(li_sub)
        self.chan_linkedin_body = QTextEdit()
        self.chan_linkedin_body.setPlaceholderText("LinkedIn connection request will appear here...")
        lsl.addWidget(self.chan_linkedin_body, stretch=1)
        li_copy_btn = ModernButton("Copy to Clipboard", "secondary")
        li_copy_btn.setFixedHeight(36)
        li_copy_btn.clicked.connect(lambda: self._copy_to_clipboard(self.chan_linkedin_body.toPlainText()))
        lsl.addWidget(li_copy_btn)
        li_note = QLabel("Paste into LinkedIn manually after copying")
        li_note.setObjectName("mutedText")
        lsl.addWidget(li_note)
        self.channel_tabs.addTab(li_sub, "LinkedIn")

        tw_sub = QWidget()
        tsl = QVBoxLayout(tw_sub)
        self.chan_twitter_body = QTextEdit()
        self.chan_twitter_body.setPlaceholderText("Twitter DM will appear here...")
        tsl.addWidget(self.chan_twitter_body, stretch=1)
        tw_copy_btn = ModernButton("Copy to Clipboard", "secondary")
        tw_copy_btn.setFixedHeight(36)
        tw_copy_btn.clicked.connect(lambda: self._copy_to_clipboard(self.chan_twitter_body.toPlainText()))
        tsl.addWidget(tw_copy_btn)
        tw_note = QLabel("Paste into Twitter/X DMs manually after copying")
        tw_note.setObjectName("mutedText")
        tsl.addWidget(tw_note)
        self.channel_tabs.addTab(tw_sub, "Twitter")

        cl.addWidget(self.channel_tabs, stretch=1)
        chan_layout.addWidget(chan_card, stretch=1)
        self.tabs.addTab(chan_tab, get_icon("tab_channels", "dark"), "Channels")

        main_layout.addWidget(self.tabs, stretch=1)

    # ─── Public methods (called by controller) ─────────────────────────

    def load_campaigns(self, campaigns: list):
        """Populate campaign selector."""
        self.campaign_combo.clear()
        for camp in campaigns:
            display = f"{camp['name']} ({camp['total_leads']} leads)"
            self.campaign_combo.addItem(display, camp["id"])

    def load_skills(self, skills: list):
        """Populate skill selector."""
        self.skill_combo.clear()
        for skill in skills:
            self.skill_combo.addItem(skill["name"], skill["id"])

    def load_leads(self, leads: list):
        """Populate lead table."""
        self.lead_table.setRowCount(0)
        for lead in leads:
            row = self.lead_table.rowCount()
            self.lead_table.insertRow(row)
            self.lead_table.setItem(row, 0, QTableWidgetItem(lead.get("business_name", "")))
            self.lead_table.setItem(row, 1, QTableWidgetItem(lead.get("city", "")))
            self.lead_table.setItem(row, 2, QTableWidgetItem(lead.get("email", "")))

            status = lead.get("status", "qualified")
            status_item = QTableWidgetItem(status.upper())
            colors = {"qualified": "#34D399", "emailed": "#6366F1", "replied": "#A78BFA"}
            status_item.setForeground(QColor(colors.get(status, "#6B6B80")))
            self.lead_table.setItem(row, 3, status_item)

            # Store full lead data in first column
            self.lead_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, lead)

        self.status_label.setText(f"{len(leads)} leads")
        
        if len(leads) > 0:
            self.lead_table.show()
            self.empty_leads.hide()
        else:
            self.lead_table.hide()
            self.empty_leads.show()
            self.empty_leads.title_label.setText("No qualified leads")
            self.empty_leads.subtitle_label.setText("This campaign has no leads ready for outreach.")

    def show_draft(self, draft: dict):
        """Display a generated email draft."""
        self.subject_input.setText(draft.get("subject", ""))
        body = draft.get("body", "").replace("\\n", "\n")
        self.body_editor.setPlainText(body)
        tone = draft.get("tone", "")
        self.tone_label.setText(f"Tone: {tone}" if tone else "")
        self.send_btn.setEnabled(True)
        self.generate_btn.set_loading(False)

    def on_email_sent(self, lead_id: int, result: dict):
        """Handle send result."""
        self.send_btn.set_loading(False)
        if result.get("success"):
            show_toast(self.window(), "Email sent successfully!", "success")
            # Update status in table
            for row in range(self.lead_table.rowCount()):
                item = self.lead_table.item(row, 0)
                if item:
                    lead = item.data(Qt.ItemDataRole.UserRole)
                    if lead and lead.get("id") == lead_id:
                        status_item = QTableWidgetItem("EMAILED")
                        status_item.setForeground(QColor("#6366F1"))
                        self.lead_table.setItem(row, 3, status_item)
                        break
        else:
            error_msg = result.get("error", "Unknown error")
            show_toast(self.window(), f"Send failed: {error_msg}", "error", duration_ms=6000)

    # ─── Internal ──────────────────────────────────────────────────────

    def _on_campaign_changed(self, index: int):
        """Signal that campaign selection changed."""
        pass  # Controller will wire this

    def _on_lead_selected(self, row: int):
        """Load selected lead's email into the To field."""
        if row < 0:
            return
        item = self.lead_table.item(row, 0)
        if item:
            lead = item.data(Qt.ItemDataRole.UserRole)
            if lead:
                self.to_input.setText(lead.get("email", ""))

    def _on_generate(self):
        """Request email generation for selected lead."""
        row = self.lead_table.currentRow()
        if row < 0:
            show_toast(self.window(), "Select a lead first.", "warning")
            return

        item = self.lead_table.item(row, 0)
        if not item:
            return

        lead = item.data(Qt.ItemDataRole.UserRole)
        skill_id = self.skill_combo.currentData()

        if not lead or not skill_id:
            show_toast(self.window(), "Select a lead and skill.", "warning")
            return

        self.generate_btn.set_loading(True)
        self.generate_requested.emit(lead["id"], skill_id)

    def _on_send(self):
        """Send the current email."""
        row = self.lead_table.currentRow()
        if row < 0:
            return

        item = self.lead_table.item(row, 0)
        if not item:
            return

        lead = item.data(Qt.ItemDataRole.UserRole)
        to_email = self.to_input.text().strip()
        subject = self.subject_input.text().strip()
        body = self.body_editor.toPlainText().strip()

        if not to_email or not subject or not body:
            show_toast(self.window(), "To, subject, and body are all required.", "warning")
            return

        self.send_btn.set_loading(True)
        self.send_requested.emit(lead["id"], to_email, subject, body)

    def _on_generate_channels(self):
        """Request multi-channel draft generation."""
        row = self.lead_table.currentRow()
        if row < 0:
            show_toast(self.window(), "Select a lead first.", "warning")
            return
        item = self.lead_table.item(row, 0)
        if not item:
            return
        lead = item.data(Qt.ItemDataRole.UserRole)
        skill_id = self.skill_combo.currentData()
        if not lead or not skill_id:
            show_toast(self.window(), "Select a lead and skill.", "warning")
            return
        self.chan_generate_btn.set_loading(True)
        self.generate_channels_requested.emit(lead["id"], skill_id)

    def show_channel_drafts(self, lead_id: int, drafts: dict):
        """Display multi-channel drafts."""
        self.chan_generate_btn.set_loading(False)
        email = drafts.get("email", {})
        self.chan_email_subject.setText(email.get("subject", ""))
        self.chan_email_body.setPlainText(email.get("body", "").replace("\\n", "\n"))

        linkedin = drafts.get("linkedin", {})
        self.chan_linkedin_body.setPlainText(linkedin.get("body", ""))

        twitter = drafts.get("twitter", {})
        self.chan_twitter_body.setPlainText(twitter.get("body", ""))

        # Switch to channels tab
        self.tabs.setCurrentIndex(4)

    def _on_crm_sync(self):
        """Request CRM sync for the selected campaign."""
        campaign_id = self.campaign_combo.currentData()
        if not campaign_id:
            show_toast(self.window(), "Select a campaign first.", "warning")
            return
        self.crm_sync_btn.set_loading(True)
        self.crm_sync_requested.emit(campaign_id)

    def on_crm_sync_done(self):
        """Reset button state after CRM sync completes."""
        self.crm_sync_btn.set_loading(False)

    def _copy_to_clipboard(self, text: str):
        """Copy text to system clipboard."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            show_toast(self.window(), "Copied to clipboard!", "success")

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
