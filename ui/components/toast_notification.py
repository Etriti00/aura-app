"""
Aura — Toast Notification Component
Non-blocking corner notification with auto-dismiss, slide animation,
and premium glassmorphism styling.
"""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtGui import QColor
from ui.icons import get_icon, get_pixmap


class ToastNotification(QFrame):
    """
    A slide-in notification that appears in the bottom-right corner.

    Variants: success, error, warning, info
    """

    _active_toasts = []  # Class-level list to stack toasts

    def __init__(
        self,
        message: str,
        variant: str = "info",
        duration_ms: int = 4000,
        action_text: str = None,
        action_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.duration_ms = duration_ms
        self.action_callback = action_callback

        # Set object name for QSS styling
        variant_names = {
            "success": "toastSuccess",
            "error": "toastError",
            "warning": "toastWarning",
            "info": "toastInfo",
        }
        self.setObjectName(variant_names.get(variant, "toastInfo"))

        # Fixed width, dynamic height — stays inside parent as a child overlay
        self.setFixedWidth(360)

        # Shadow with variant-tinted color
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow_colors = {
            "success": QColor(16, 185, 129, 30),
            "error": QColor(239, 68, 68, 30),
            "warning": QColor(251, 191, 36, 30),
            "info": QColor(99, 102, 241, 30),
        }
        shadow.setColor(shadow_colors.get(variant, QColor(0, 0, 0, 30)))
        self.setGraphicsEffect(shadow)

        self._setup_ui(message, variant, action_text)

    def _setup_ui(self, message: str, variant: str, action_text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Icon
        icon_keys = {
            "success": "toast_success",
            "error": "toast_error",
            "warning": "toast_warning",
            "info": "toast_info",
        }
        icon_color_keys = {
            "success": "success",
            "error": "danger",
            "warning": "warning",
            "info": "info",
        }

        theme = "dark"
        try:
            if self.parent() and hasattr(self.parent(), '_current_theme'):
                theme = self.parent()._current_theme
        except Exception:
            pass

        icon_label = QLabel()
        icon_label.setPixmap(get_pixmap(
            icon_keys.get(variant, "toast_info"), theme,
            icon_color_keys.get(variant, "info"), 20,
        ))
        icon_label.setFixedSize(24, 24)
        icon_obj_names = {
            "success": "toastIconSuccess",
            "error": "toastIconError",
            "warning": "toastIconWarning",
            "info": "toastIconInfo",
        }
        icon_label.setObjectName(icon_obj_names.get(variant, "toastIconInfo"))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(icon_label)

        # Content area
        content_layout = QVBoxLayout()
        content_layout.setSpacing(4)

        msg_label = QLabel(message)
        msg_label.setObjectName("toastMessage")
        msg_label.setWordWrap(True)
        content_layout.addWidget(msg_label)

        if action_text and self.action_callback:
            action_btn = QPushButton(action_text)
            action_btn.setObjectName("secondaryButton")
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.clicked.connect(self._on_action)
            content_layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addLayout(content_layout, stretch=1)

        # Close button
        close_btn = QPushButton()
        close_btn.setIcon(get_icon("toast_close", theme))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setObjectName("toastCloseButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Dismiss")
        close_btn.clicked.connect(self.dismiss)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)

    def show_toast(self):
        """Show the toast with slide-in animation inside the parent widget."""
        if self.parent():
            parent = self.parent()
            self.adjustSize()

            # Calculate position — stack from bottom right within parent
            toast_index = len(ToastNotification._active_toasts)
            toast_h = self.sizeHint().height()
            x = parent.width() - self.width() - 24
            y = parent.height() - (toast_index + 1) * (toast_h + 12) - 24

            self.move(parent.width(), y)  # Start off-screen right
            self.show()
            self.raise_()

            # Slide in animation
            self._anim = QPropertyAnimation(self, b"pos")
            self._anim.setDuration(300)
            self._anim.setStartValue(QPoint(parent.width(), y))
            self._anim.setEndValue(QPoint(x, y))
            self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._anim.start()

            ToastNotification._active_toasts.append(self)

            # Auto-dismiss timer
            if self.duration_ms > 0:
                QTimer.singleShot(self.duration_ms, self.dismiss)

    def dismiss(self):
        """Dismiss the toast with slide-out animation."""
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)

        if self.parent():
            self._dismiss_anim = QPropertyAnimation(self, b"pos")
            self._dismiss_anim.setDuration(200)
            self._dismiss_anim.setStartValue(self.pos())
            self._dismiss_anim.setEndValue(QPoint(self.parent().width(), self.pos().y()))
            self._dismiss_anim.setEasingCurve(QEasingCurve.Type.InCubic)
            self._dismiss_anim.finished.connect(self._on_dismissed)
            self._dismiss_anim.start()
        else:
            self.close()
            self.deleteLater()

    def _on_dismissed(self):
        self.close()
        self.deleteLater()

    def _on_action(self):
        if self.action_callback:
            self.action_callback()
        self.dismiss()


def show_toast(parent, message: str, variant: str = "info", duration_ms: int = 4000,
               action_text: str = None, action_callback=None):
    """Convenience function to show a toast notification."""
    toast = ToastNotification(
        message=message,
        variant=variant,
        duration_ms=duration_ms,
        action_text=action_text,
        action_callback=action_callback,
        parent=parent,
    )
    toast.show_toast()
    return toast
