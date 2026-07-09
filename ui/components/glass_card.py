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
        self._layout.setSpacing(12)
        
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
    "blue":   ("#4E5BF2", "#6D79F6"),  # Neon Indigo
    "green":  ("#10B981", "#34D399"),  # Emerald
    "purple": ("#8B5CF6", "#A78BFA"),  # Violet
    "orange": ("#F59E0B", "#FBBF24"),  # Amber
    "red":    ("#EF4444", "#F87171"),  # Rose
    "cyan":   ("#06B6D4", "#22D3EE"),  # Cyan
    "pink":   ("#EC4899", "#F472B6"),  # Fuschia
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

        # Apply Variant Styling
        if variant == "solid":
            # Solid color background
            self.setStyleSheet(f"""
                QFrame#statCard {{
                    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {colors[0]}, stop:1 {colors[1]});
                    border: none;
                }}
                QLabel#statValue {{ color: #FFFFFF; font-size: 38px; }}
                QLabel#statLabel {{ color: rgba(255, 255, 255, 0.8); }}
            """)
            
            # Disabled glow shadow per user request
            # shadow = QGraphicsDropShadowEffect(self)
            # shadow.setBlurRadius(30)
            # shadow.setOffset(0, 8)
            # glow_color = QColor(self._accent_start)
            # glow_color.setAlpha(80) 
            # shadow.setColor(glow_color)
            # self.setGraphicsEffect(shadow)

        else:
            # Default Glass Style
            # Disabled shadow
            pass
            # shadow = QGraphicsDropShadowEffect(self)
            # shadow.setBlurRadius(24)
            # shadow.setOffset(0, 4)
            # shadow.setColor(QColor(0, 0, 0, 40))
            # self.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        """Draw a gradient accent bar only for 'default' variant."""
        super().paintEvent(event)
        if self._variant == "default":
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
