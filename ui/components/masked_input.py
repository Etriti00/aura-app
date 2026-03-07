"""
Aura — Masked Input Component
API key input field that displays in sk-proj-****2345 format
with a toggle-reveal button.
"""

from PySide6.QtWidgets import QLineEdit, QPushButton, QHBoxLayout, QWidget
from PySide6.QtCore import Qt, QSize
from ui.icons import get_icon


class MaskedInput(QWidget):
    """
    A text input that masks sensitive values (like API keys) by default,
    with a toggle button to reveal/hide the full value.
    """

    def __init__(self, placeholder: str = "Enter API key...", parent=None,
                 theme: str = "dark"):
        super().__init__(parent)
        self._raw_value = ""
        self._is_revealed = False
        self._theme = theme
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setProperty("masked", True)
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input, stretch=1)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(get_icon("eye_visible", self._theme))
        self.toggle_btn.setIconSize(QSize(18, 18))
        self.toggle_btn.setFixedSize(36, 36)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setObjectName("maskToggle")
        self.toggle_btn.clicked.connect(self._toggle_reveal)
        layout.addWidget(self.toggle_btn)

    def _on_text_changed(self, text: str):
        """When the user types, capture the raw value."""
        if self._is_revealed:
            self._raw_value = text

    def _toggle_reveal(self):
        """Toggle between showing masked and full value."""
        self._is_revealed = not self._is_revealed
        if self._is_revealed:
            self.toggle_btn.setIcon(get_icon("eye_hidden", self._theme))
            self.input.blockSignals(True)
            self.input.setText(self._raw_value)
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.input.setReadOnly(False)
            self.input.blockSignals(False)
        else:
            self.toggle_btn.setIcon(get_icon("eye_visible", self._theme))
            self.input.blockSignals(True)
            self.input.setText(self._get_masked_display())
            self.input.setReadOnly(True)
            self.input.blockSignals(False)

    def _get_masked_display(self) -> str:
        """Return masked version of the raw value."""
        if not self._raw_value:
            return ""
        from core.key_vault import KeyVault
        return KeyVault.mask(self._raw_value)

    def set_value(self, value: str):
        """Set the input value programmatically (e.g., from decrypted settings)."""
        self._raw_value = value
        self._is_revealed = False
        self.toggle_btn.setIcon(get_icon("eye_visible", self._theme))
        self.input.blockSignals(True)
        self.input.setText(self._get_masked_display())
        self.input.setReadOnly(True)
        self.input.blockSignals(False)

    def get_value(self) -> str:
        """Get the raw (unmasked) value."""
        return self._raw_value

    def set_raw_and_show(self, value: str):
        """Set value and immediately show it for editing (used in wizard)."""
        self._raw_value = value
        self._is_revealed = True
        self.toggle_btn.setIcon(get_icon("eye_hidden", self._theme))
        self.input.blockSignals(True)
        self.input.setText(value)
        self.input.setReadOnly(False)
        self.input.blockSignals(False)

    def clear(self):
        """Clear the input."""
        self._raw_value = ""
        self._is_revealed = False
        self.toggle_btn.setIcon(get_icon("eye_visible", self._theme))
        self.input.blockSignals(True)
        self.input.clear()
        self.input.setReadOnly(False)
        self.input.blockSignals(False)
