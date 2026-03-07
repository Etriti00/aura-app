"""
Aura — Modern Button Component
Premium styled QPushButton with gradient variants and hover animations.
"""

from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor


class ModernButton(QPushButton):
    """Styled button with variant support: primary, secondary, danger, ghost."""

    def __init__(self, text: str, variant: str = "primary", parent=None):
        super().__init__(text, parent)
        self._variant = variant
        self._apply_variant()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_variant(self):
        variant_map = {
            "primary": "primaryButton",
            "secondary": "secondaryButton",
            "danger": "dangerButton",
            "ghost": "secondaryButton",
        }
        object_name = variant_map.get(self._variant, "primaryButton")
        self.setObjectName(object_name)

        # Disabled shadow for clean flat look
        # if self._variant == "primary":
        #     shadow = QGraphicsDropShadowEffect(self)
        #     shadow.setBlurRadius(20)
        #     shadow.setOffset(0, 4)
        #     shadow.setColor(QColor(99, 102, 241, 50))
        #     self.setGraphicsEffect(shadow)
        # elif self._variant == "danger":
        #     shadow = QGraphicsDropShadowEffect(self)
        #     shadow.setBlurRadius(20)
        #     shadow.setOffset(0, 4)
        #     shadow.setColor(QColor(239, 68, 68, 40))
        #     self.setGraphicsEffect(shadow)

    def set_variant(self, variant: str):
        """Change button variant dynamically."""
        self._variant = variant
        self._apply_variant()
        self.style().unpolish(self)
        self.style().polish(self)

    def set_loading(self, loading: bool):
        """Toggle loading state — disables button and shows spinner text."""
        if loading:
            self._original_text = self.text()
            self.setText("Processing...")
            self.setEnabled(False)
        else:
            if hasattr(self, "_original_text"):
                self.setText(self._original_text)
            self.setEnabled(True)
