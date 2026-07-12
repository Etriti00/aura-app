"""
Aura — Integrations Page
Manage external messaging platform connections (Telegram, Discord),
authorized users, and notification preferences.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QLineEdit,
    QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.masked_input import MaskedInput
from ui.icons import get_pixmap


class IntegrationsPage(QWidget):
    """Integrations page — external chat platforms and access control."""

    platform_connect_requested = Signal(str, str)      # platform, bot_token
    platform_disconnect_requested = Signal(str)         # platform
    user_add_requested = Signal(str, str, str)          # platform, user_id, display_name
    user_remove_requested = Signal(str, str)            # platform, user_id
    save_notification_prefs = Signal(dict)              # notification toggle states

    def __init__(self, parent=None):
        super().__init__(parent)
        self._platform_connected = {"telegram": False, "discord": False}
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("integrationsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(26)

        # ─── Header ───────────────────────────────────────────────
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        title = QLabel("Integrations & Access")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Connect Aura to Telegram and Discord for remote control")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        layout.addLayout(header_text)

        # ─── Section 1: Platform Configuration ────────────────────
        platforms_card = GlassCard()
        platforms_card_layout = platforms_card.get_layout()
        platforms_hdr = QLabel("Platform Connections")
        platforms_hdr.setObjectName("cardHeader")
        platforms_card_layout.addWidget(platforms_hdr)
        platforms_layout = QVBoxLayout()
        platforms_layout.setSpacing(16)

        # Telegram row
        self.telegram_widgets = self._build_platform_row(
            "telegram", "Telegram Bot", "Enter your Telegram Bot token..."
        )
        platforms_layout.addLayout(self.telegram_widgets["layout"])

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        platforms_layout.addWidget(sep)

        # Discord row
        self.discord_widgets = self._build_platform_row(
            "discord", "Discord Bot", "Enter your Discord Bot token..."
        )
        platforms_layout.addLayout(self.discord_widgets["layout"])

        platforms_card_layout.addLayout(platforms_layout)
        layout.addWidget(platforms_card)

        # ─── Section 2: Authorized Users ──────────────────────────
        users_card = GlassCard()
        users_card_layout = users_card.get_layout()
        users_hdr = QLabel("Access Control")
        users_hdr.setObjectName("cardHeader")
        users_card_layout.addWidget(users_hdr)
        users_layout = QVBoxLayout()
        users_layout.setSpacing(12)

        desc = QLabel("Only authorized users can control Aura via external chat. "
                       "Unauthorized messages are dropped at the Gateway level.")
        desc.setObjectName("mutedText")
        desc.setWordWrap(True)
        users_layout.addWidget(desc)

        # Add user form
        add_row = QHBoxLayout()
        add_row.setSpacing(8)

        self.user_platform_combo = QComboBox()
        self.user_platform_combo.addItems(["Telegram", "Discord"])
        self.user_platform_combo.setMinimumWidth(90)
        add_row.addWidget(self.user_platform_combo)

        self.user_id_input = QLineEdit()
        self.user_id_input.setPlaceholderText("User/Chat ID")
        add_row.addWidget(self.user_id_input, stretch=1)

        self.user_name_input = QLineEdit()
        self.user_name_input.setPlaceholderText("Display Name (optional)")
        add_row.addWidget(self.user_name_input, stretch=1)

        add_btn = ModernButton("Add User", "secondary")
        add_btn.clicked.connect(self._on_add_user)
        add_row.addWidget(add_btn)

        add_row.addStretch()
        users_layout.addLayout(add_row)

        # Users table
        self.users_table = QTableWidget()
        self.users_table.setColumnCount(4)
        self.users_table.setHorizontalHeaderLabels(
            ["Platform", "User ID", "Name", ""]
        )
        self.users_table.horizontalHeader().setStretchLastSection(False)
        self.users_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.users_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.users_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.users_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self.users_table.verticalHeader().setVisible(False)
        self.users_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.users_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.users_table.setMaximumHeight(200)
        users_layout.addWidget(self.users_table)

        users_card_layout.addLayout(users_layout)
        layout.addWidget(users_card)

        # ─── Section 3: Notification Preferences ──────────────────
        notif_card = GlassCard()
        notif_card_layout = notif_card.get_layout()
        notif_hdr = QLabel("Proactive Notifications")
        notif_hdr.setObjectName("cardHeader")
        notif_card_layout.addWidget(notif_hdr)
        notif_layout = QVBoxLayout()
        notif_layout.setSpacing(10)

        notif_desc = QLabel("Aura can send alerts to your connected platforms.")
        notif_desc.setObjectName("mutedText")
        notif_layout.addWidget(notif_desc)

        self.notif_budget = QCheckBox("Send budget pacing alerts")
        self.notif_budget.setChecked(True)
        notif_layout.addWidget(self.notif_budget)

        self.notif_triage = QCheckBox("Send inbox triage summaries")
        self.notif_triage.setChecked(True)
        notif_layout.addWidget(self.notif_triage)

        self.notif_campaign = QCheckBox("Send campaign completion alerts")
        self.notif_campaign.setChecked(True)
        notif_layout.addWidget(self.notif_campaign)

        save_notif_btn = ModernButton("Save Preferences", "secondary")
        save_notif_btn.clicked.connect(self._on_save_notifications)
        notif_layout.addWidget(save_notif_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        notif_card_layout.addLayout(notif_layout)
        layout.addWidget(notif_card)

        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── Platform row builder ──────────────────────────────────────

    def _build_platform_row(self, platform: str, display_name: str,
                            placeholder: str) -> dict:
        """Build a row for configuring a platform connection."""
        row = QVBoxLayout()
        row.setSpacing(8)

        # Header row: icon + name + status
        header = QHBoxLayout()
        header.setSpacing(10)

        icon_key = "telegram" if platform == "telegram" else "discord"
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap(icon_key, "dark", "default", 22))
        icon_lbl.setObjectName("integrationPlatformIcon")
        icon_lbl.setFixedSize(28, 28)
        header.addWidget(icon_lbl)

        name_lbl = QLabel(display_name)
        name_lbl.setObjectName("cardHeader")
        header.addWidget(name_lbl)

        status_lbl = QLabel("Disconnected")
        status_lbl.setObjectName("badgeInfo")
        header.addWidget(status_lbl)

        header.addStretch()
        row.addLayout(header)

        # Token input + buttons
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        token_input = MaskedInput(placeholder)
        input_row.addWidget(token_input, stretch=1)

        connect_btn = ModernButton("Connect", "primary")
        connect_btn.clicked.connect(
            lambda: self._on_toggle_platform(platform)
        )
        input_row.addWidget(connect_btn)

        row.addLayout(input_row)

        return {
            "layout": row,
            "token_input": token_input,
            "connect_btn": connect_btn,
            "status_lbl": status_lbl,
            "platform": platform,
        }

    # ─── Event handlers ────────────────────────────────────────────

    def _on_toggle_platform(self, platform: str):
        """Toggle platform connection."""
        widgets = (
            self.telegram_widgets if platform == "telegram"
            else self.discord_widgets
        )

        if self._platform_connected.get(platform, False):
            self.platform_disconnect_requested.emit(platform)
        else:
            token = widgets["token_input"].get_value()
            if not token:
                return
            # Show connecting state immediately
            widgets["status_lbl"].setText("Connecting...")
            widgets["status_lbl"].setObjectName("badgeWarning")
            widgets["status_lbl"].style().unpolish(widgets["status_lbl"])
            widgets["status_lbl"].style().polish(widgets["status_lbl"])
            widgets["connect_btn"].setEnabled(False)
            self.platform_connect_requested.emit(platform, token)

    def _on_add_user(self):
        """Add authorized user."""
        platform = self.user_platform_combo.currentText().lower()
        user_id = self.user_id_input.text().strip()
        name = self.user_name_input.text().strip()

        if not user_id:
            return

        self.user_add_requested.emit(platform, user_id, name)

        # Add to table
        self._add_user_row(platform, user_id, name)

        # Clear inputs
        self.user_id_input.clear()
        self.user_name_input.clear()

    def _add_user_row(self, platform: str, user_id: str, name: str):
        """Add a row to the users table."""
        row = self.users_table.rowCount()
        self.users_table.insertRow(row)
        self.users_table.setItem(row, 0, QTableWidgetItem(platform.title()))
        self.users_table.setItem(row, 1, QTableWidgetItem(user_id))
        self.users_table.setItem(row, 2, QTableWidgetItem(name))

        remove_btn = QPushButton("Remove")
        remove_btn.setObjectName("dangerButton")
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(
            lambda: self._on_remove_user(platform, user_id, row)
        )
        self.users_table.setCellWidget(row, 3, remove_btn)

    def _on_remove_user(self, platform: str, user_id: str, row: int):
        """Remove authorized user."""
        self.user_remove_requested.emit(platform, user_id)
        self.users_table.removeRow(row)

    def _on_save_notifications(self):
        """Save notification preferences."""
        self.save_notification_prefs.emit({
            "budget_alerts": self.notif_budget.isChecked(),
            "triage_summaries": self.notif_triage.isChecked(),
            "campaign_alerts": self.notif_campaign.isChecked(),
        })

    # ─── Public slots ──────────────────────────────────────────────

    def update_connection_status(self, platform: str, connected: bool):
        """Update the UI to reflect connection status."""
        self._platform_connected[platform] = connected
        widgets = (
            self.telegram_widgets if platform == "telegram"
            else self.discord_widgets
        )

        if connected:
            widgets["status_lbl"].setText("Connected")
            widgets["status_lbl"].setObjectName("badgeSuccess")
            widgets["connect_btn"].setText("Disconnect")
        else:
            widgets["status_lbl"].setText("Disconnected")
            widgets["status_lbl"].setObjectName("badgeInfo")
            widgets["connect_btn"].setText("Connect")

        widgets["connect_btn"].setEnabled(True)
        widgets["status_lbl"].style().unpolish(widgets["status_lbl"])
        widgets["status_lbl"].style().polish(widgets["status_lbl"])

    def load_authorized_users(self, users: list):
        """Load authorized users into the table."""
        self.users_table.setRowCount(0)
        for u in users:
            self._add_user_row(
                u.get("platform", ""),
                u.get("user_id", ""),
                u.get("display_name", ""),
            )

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
