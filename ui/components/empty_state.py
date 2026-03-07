"""
Aura — Empty State Component
A reusable placeholder widget to display when data is missing (e.g., empty tables).
Fully QSS-themed via objectNames — no hardcoded colors.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from ui.components.modern_button import ModernButton
from ui.icons import get_pixmap


class EmptyState(QWidget):
    """
    A centered widget with an icon, title, subtitle, and optional action button.
    Styled via QSS objectNames: emptyStateIcon, emptyStateTitle, emptyStateSubtitle.
    """

    action_clicked = Signal()

    def __init__(
        self,
        icon_key: str = "empty_default",
        title: str = "Nothing here yet",
        subtitle: str = "Get started by taking an action above.",
        action_text: str | None = None,
        parent=None,
        theme: str = "dark",
    ):
        super().__init__(parent)
        self.setObjectName("emptyState")
        self._icon_key = icon_key
        self._theme = theme

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setPixmap(get_pixmap(icon_key, theme, "muted", 48))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setObjectName("emptyStateIcon")
        layout.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setObjectName("emptyStateTitle")
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setMaximumWidth(380)
        self.subtitle_label.setObjectName("emptyStateSubtitle")
        layout.addWidget(self.subtitle_label)

        if action_text:
            layout.addSpacing(8)
            self.action_btn = ModernButton(action_text, "primary")
            self.action_btn.setFixedHeight(38)
            self.action_btn.setFixedWidth(160)
            self.action_btn.clicked.connect(self.action_clicked.emit)
            layout.addWidget(self.action_btn, alignment=Qt.AlignmentFlag.AlignCenter)
