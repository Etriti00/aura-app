"""
Aura — Sidebar Navigation Component
Premium navigation rail with gradient logo, glow indicators, and smooth visual hierarchy.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QSpacerItem,
    QGraphicsDropShadowEffect
)
from PySide6.QtCore import Signal, Qt, QSize
from PySide6.QtGui import QFont, QColor

from config import Geometry, APP_NAME
from ui.icons import get_icon, get_pixmap, SIDEBAR_ICON_KEYS


class Sidebar(QWidget):
    """Navigation sidebar with icon-labeled buttons for each page."""

    page_changed = Signal(int)

    # Page definitions: (label, icon_key, tooltip)
    PAGES = [
        ("Dashboard",    "sidebar_dashboard",    "View campaign statistics"),
        ("Hunter",       "sidebar_hunter",       "Find and scrape leads"),
        ("Forge",        "sidebar_forge",        "Create AI personas"),
        ("Outreach",     "sidebar_outreach",     "Generate and send emails"),
        ("Fleet",        "sidebar_fleet",        "Multi-agent command center"),
        ("Kanban",       "sidebar_kanban",       "Ticket board & task management"),
        ("History",      "sidebar_history",      "Command history & activity log"),
        ("Trends",       "sidebar_trends",       "Google Trends intelligence"),
        ("Budget",       "sidebar_budget",       "Cost pacing & budget monitoring"),
        ("Integrations", "sidebar_integrations", "External chat & platform connections"),
        ("Settings",     "sidebar_settings",     "Configure API keys and preferences"),
        ("Suppression",  "sidebar_suppression",  "Manage global suppression list"),
        ("Research",     "sidebar_research",     "Pre-outreach lead intelligence"),
        ("Calls",        "sidebar_calls",        "Voice calls & cold calling"),
    ]

    def __init__(self, parent=None, theme: str = "dark"):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(Geometry.SIDEBAR_WIDTH)
        self.buttons = []
        self._current_index = 0
        self._theme = theme
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo area with glow effect
        logo_container = QWidget()
        logo_container.setFixedHeight(55)
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(20, 14, 20, 14)
        self._logo_container = logo_container
        self._logo_layout = logo_layout

        self._logo_icon = QLabel()
        self._logo_icon.setPixmap(get_pixmap("logo_mark", self._theme, "accent", 18))
        self._logo_icon.setFixedSize(22, 22)
        logo_icon = self._logo_icon

        logo_text = QLabel(APP_NAME)
        logo_text.setObjectName("logoText")

        logo_row = QWidget()
        logo_row_layout = QHBoxLayout(logo_row)
        logo_row_layout.setContentsMargins(0, 0, 0, 0)
        logo_row_layout.setSpacing(8)
        # Explicit VCenter: icon and wordmark must share one baseline row —
        # under seamless macOS chrome any drift reads as a broken header.
        logo_row_layout.addWidget(logo_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row_layout.addWidget(logo_text, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row_layout.addStretch()

        # Keep logo_label reference for glow effect
        logo_label = logo_text
        logo_label.setObjectName("logoText")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        logo_layout.addWidget(logo_row)

        layout.addWidget(logo_container)

        # Separator
        separator = QWidget()
        separator.setObjectName("separator")
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        # Navigation section label
        nav_header = QLabel("  NAVIGATION")
        nav_header.setObjectName("navSectionLabel")
        layout.addWidget(nav_header)

        # Navigation buttons
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 4, 0, 12)
        nav_layout.setSpacing(2)

        for i, (label, icon_key, tooltip) in enumerate(self.PAGES):
            btn = QPushButton(f"  {label}")
            btn.setIcon(get_icon(icon_key, self._theme))
            btn.setIconSize(QSize(18, 18))
            btn.setObjectName("sidebarButton")
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            font = btn.font()
            font.setPointSize(10)
            btn.setFont(font)

            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            nav_layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addWidget(nav_container)

        # Spacer to push version info to bottom
        layout.addSpacerItem(QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        ))

        # Version info at bottom. No accent line above it: the version row's
        # own top border continues the status bar's line across the sidebar,
        # and a second line here reads as a broken double ribbon.
        from config import APP_VERSION
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("versionLabel")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Same height as the status bar so their top borders form one
        # continuous line across the window's bottom ribbon.
        version_label.setFixedHeight(32)
        layout.addWidget(version_label)

        # Set initial active state
        self._update_active_state(0)

    def align_logo_with_toolbar(self, height: int, left_inset: int):
        """One-line header under seamless macOS chrome: the logo container
        matches the unified-toolbar height and shifts right so the traffic
        lights (at the container's left edge) share its row.

        Height is one pixel short: the separator widget below then occupies
        the same pixel row as the top bar's bottom border, so the header
        underline reads as one continuous line across the whole window.
        """
        self._logo_container.setFixedHeight(height - 1)
        self._logo_layout.setContentsMargins(left_inset, 0, 20, 0)

    def drag_handle(self):
        """The widget that doubles as a window drag region under seamless
        chrome — the logo strip, which sits where a titlebar would."""
        return self._logo_container

    def _on_button_clicked(self, index: int):
        """Handle navigation button click."""
        if index != self._current_index:
            self._current_index = index
            self._update_active_state(index)
            self.page_changed.emit(index)

    def _update_active_state(self, active_index: int):
        """Update button visual states."""
        for i, btn in enumerate(self.buttons):
            btn.setProperty("active", "true" if i == active_index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def set_page(self, index: int):
        """Programmatically set the active page."""
        if 0 <= index < len(self.buttons):
            self._current_index = index
            self._update_active_state(index)

    def update_icons(self, theme: str):
        """Rebuild all icons for a new theme."""
        self._theme = theme
        if hasattr(self, "_logo_icon"):
            self._logo_icon.setPixmap(get_pixmap("logo_mark", theme, "accent", 18))
        for i, (label, icon_key, tooltip) in enumerate(self.PAGES):
            if i < len(self.buttons):
                self.buttons[i].setIcon(get_icon(icon_key, theme))
