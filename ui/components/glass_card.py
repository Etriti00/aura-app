"""
Aura — Glass Card Component
Premium glassmorphism cards with glow shadows and accent bars.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QLabel
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QPen, QBrush
from PySide6.QtCore import Qt, QRectF


class GlassCard(QFrame):
    """A rounded card container with glassmorphism glow — the building block of the layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(22, 22, 22, 22)
        self._layout.setSpacing(14)
        
        # Prevent default QFrame 3D borders (ghost lines)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setLineWidth(0)
        
        self._apply_shadow()

    def _apply_shadow(self):
        # Disabled shadow effect per user request "get rid of shadow behind text"
        # Using QSS borders for definition instead.
        pass
        # shadow = QGraphicsDropShadowEffect(self)
        # shadow.setBlurRadius(40)  # Increased blur for smoother glow
        # shadow.setOffset(0, 8)
        # shadow.setColor(QColor(0, 0, 0, 60))  # Darker, richer shadow
        # self.setGraphicsEffect(shadow)

    def get_layout(self) -> QVBoxLayout:
        """Return the card's internal layout for adding child widgets."""
        return self._layout


# ─── Accent color presets for stat cards ───────────────────────────────
ACCENT_PRESETS = {
    "blue":   ("#0A84FF", "#409CFF"),  # System Blue
    "green":  ("#30D158", "#66E08B"),  # System Green
    "purple": ("#BF5AF2", "#DA8FFF"),  # System Purple
    "orange": ("#FF9F0A", "#FFB340"),  # System Orange
    "red":    ("#FF453A", "#FF6961"),  # System Red
    "cyan":   ("#64D2FF", "#8FDFFF"),  # System Cyan
    "pink":   ("#FF375F", "#FF6482"),  # System Pink
    "yellow": ("#FFD60A", "#FDE047"),  # Neon Yellow
}


class StatCard(QFrame):
    """
    A compact stat display card.
    Variants:
      - 'default': Glass background with top accent bar.
      - 'solid': Solid accent color background with white text (High Emphasis).
    """

    def __init__(self, value: str = "0", label: str = "Label", accent: str = "blue", variant: str = "default", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setMinimumHeight(120)  # Taller for modern look
        self._accent = accent
        self._variant = variant

        # Get accent colors
        colors = ACCENT_PRESETS.get(accent, ACCENT_PRESETS["blue"])
        self._accent_start = QColor(colors[0])
        self._accent_end = QColor(colors[1])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)  # Increased from 4 to 12 for distinct separation

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.text_label = QLabel(label)
        self.text_label.setObjectName("statLabel")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.value_label)
        layout.addWidget(self.text_label)

        # Both variants keep a white value for a clean, uniform read; each
        # card's identity comes from its top accent bar, not a tinted number.

    def paintEvent(self, event):
        """Draw the small accent bar along the top edge."""
        super().paintEvent(event)
        if True:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Draw gradient accent bar at top
            bar_height = 4
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0, self._accent_start)
            gradient.setColorAt(1, self._accent_end)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(
                QRectF(16, 0, 40, bar_height),  # Short separate bar like reference
                2, 2
            )
            painter.end()

    def set_value(self, value: str):
        self.value_label.setText(value)

    def set_label(self, label: str):
        self.text_label.setText(label)
