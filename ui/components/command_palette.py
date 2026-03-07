"""
Aura — Command Palette (Ctrl+K)
Fuzzy-search command palette for quick navigation across pages,
agents, campaigns, and actions.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QHBoxLayout, QFrame,
)
from utils.logger import get_logger

logger = get_logger("command_palette")


def _fuzzy_match(query: str, text: str) -> float:
    """
    Simple fuzzy matching score (0.0-1.0).
    Scores based on substring match position and coverage.
    """
    if not query:
        return 1.0
    query_lower = query.lower()
    text_lower = text.lower()

    # Exact match
    if query_lower == text_lower:
        return 1.0

    # Starts with
    if text_lower.startswith(query_lower):
        return 0.9

    # Contains
    if query_lower in text_lower:
        # Earlier position = higher score
        pos = text_lower.index(query_lower)
        return 0.7 - (pos / max(len(text_lower), 1)) * 0.2

    # Word-start matching (e.g., "hk" matches "Hunter" + "Kanban")
    words = text_lower.split()
    qi = 0
    for word in words:
        if qi < len(query_lower) and word.startswith(query_lower[qi]):
            qi += 1
    if qi == len(query_lower):
        return 0.5

    # Character-by-character fuzzy
    qi = 0
    for char in text_lower:
        if qi < len(query_lower) and char == query_lower[qi]:
            qi += 1
    if qi == len(query_lower):
        return 0.3

    return 0.0


class CommandPalette(QFrame):
    """
    Modal command palette overlay for quick navigation.
    Shows a search input and list of matching commands.
    """

    command_selected = Signal(dict)  # emits the selected command dict
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: list = []
        self._filtered: list = []

        self.setObjectName("commandPalette")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setFixedWidth(500)
        self.setMaximumHeight(400)

        self._setup_ui()
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(100)
        self._debounce_timer.timeout.connect(self._do_filter)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Search input
        self._input = QLineEdit()
        self._input.setObjectName("commandPaletteInput")
        self._input.setPlaceholderText("Type a command or page name...")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._on_enter)
        layout.addWidget(self._input)

        # Results list
        self._list = QListWidget()
        self._list.setObjectName("commandPaletteList")
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setMaximumHeight(320)
        layout.addWidget(self._list)

        # Hint label
        self._hint = QLabel("Navigate with \u2191\u2193, select with Enter, close with Esc")
        self._hint.setObjectName("commandPaletteHint")
        self._hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint)

    def set_commands(self, commands: list):
        """Set the full list of available commands."""
        self._commands = commands
        self._filtered = commands[:]
        self._populate_list()

    def add_commands(self, commands: list):
        """Add additional commands to the palette."""
        self._commands.extend(commands)

    def show_palette(self):
        """Show the palette centered in the parent widget."""
        if self.parent():
            parent_rect = self.parent().rect()
            x = (parent_rect.width() - self.width()) // 2
            y = max(parent_rect.height() // 5, 50)
            self.move(x, y)

        self._input.clear()
        self._filtered = self._commands[:]
        self._populate_list()
        self.show()
        self._input.setFocus()

    def hide_palette(self):
        """Hide the palette."""
        self.hide()
        self.closed.emit()

    def _on_text_changed(self, text: str):
        self._debounce_timer.start()

    def _do_filter(self):
        query = self._input.text().strip()
        if not query:
            self._filtered = self._commands[:]
        else:
            scored = []
            for cmd in self._commands:
                label = cmd.get("label", "")
                score = _fuzzy_match(query, label)

                # Also search by page name, action name, etc.
                for key in ("page_name", "action_name", "agent_name", "campaign_name"):
                    if key in cmd:
                        alt_score = _fuzzy_match(query, cmd[key])
                        score = max(score, alt_score)

                if score > 0.1:
                    scored.append((score, cmd))

            scored.sort(key=lambda x: x[0], reverse=True)
            self._filtered = [cmd for _, cmd in scored[:20]]

        self._populate_list()

    def _populate_list(self):
        self._list.clear()
        for cmd in self._filtered:
            item = QListWidgetItem()
            label = cmd.get("label", "")
            cmd_type = cmd.get("type", "")

            # Add type badge
            if cmd_type == "navigate":
                display = f"\u2192  {label}"
            elif cmd_type == "action":
                display = f"\u26A1  {label}"
            elif cmd_type == "agent":
                display = f"\U0001F916  {label}"
            elif cmd_type == "campaign":
                display = f"\U0001F4CB  {label}"
            else:
                display = label

            item.setText(display)
            item.setData(Qt.UserRole, cmd)
            self._list.addItem(item)

        # Auto-select first item
        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_item_clicked(self, item: QListWidgetItem):
        cmd = item.data(Qt.UserRole)
        if cmd:
            self.command_selected.emit(cmd)
            self.hide_palette()

    def _on_enter(self):
        current = self._list.currentItem()
        if current:
            cmd = current.data(Qt.UserRole)
            if cmd:
                self.command_selected.emit(cmd)
                self.hide_palette()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide_palette()
        elif key == Qt.Key_Down:
            row = self._list.currentRow()
            if row < self._list.count() - 1:
                self._list.setCurrentRow(row + 1)
        elif key == Qt.Key_Up:
            row = self._list.currentRow()
            if row > 0:
                self._list.setCurrentRow(row - 1)
        else:
            super().keyPressEvent(event)
