"""
Aura -- Command Palette (Ctrl+K)
Fuzzy-search command palette for quick navigation across pages, agents,
campaigns, and actions -- plus a natural-language route to the assistant.
"""

from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QFrame,
)
from utils.logger import get_logger

logger = get_logger("command_palette")


def _fuzzy_match(query: str, text: str) -> float:
    """Simple fuzzy matching score (0.0-1.0)."""
    if not query:
        return 1.0
    query_lower = query.lower()
    text_lower = text.lower()
    if query_lower == text_lower:
        return 1.0
    if text_lower.startswith(query_lower):
        return 0.9
    if query_lower in text_lower:
        pos = text_lower.index(query_lower)
        return 0.7 - (pos / max(len(text_lower), 1)) * 0.2
    words = text_lower.split()
    qi = 0
    for word in words:
        if qi < len(query_lower) and word.startswith(query_lower[qi]):
            qi += 1
    if qi == len(query_lower):
        return 0.5
    qi = 0
    for char in text_lower:
        if qi < len(query_lower) and char == query_lower[qi]:
            qi += 1
    if qi == len(query_lower):
        return 0.3
    return 0.0


class CommandPalette(QFrame):
    """Modal command palette overlay for quick navigation and NL search."""

    command_selected = Signal(dict)  # emits the selected command dict
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: list = []
        self._filtered: list = []

        self.setObjectName("commandPalette")
        # Frameless translucent popup so the QSS rounded card shows cleanly
        # (no square window backing behind the rounded corners).
        self.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedWidth(560)
        self.setMaximumHeight(440)

        self._setup_ui()
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(90)
        self._debounce_timer.timeout.connect(self._do_filter)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)

        self._input = QLineEdit()
        self._input.setObjectName("commandPaletteInput")
        self._input.setPlaceholderText(
            "Search pages and actions, or ask Aura in plain English..."
        )
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._on_enter)
        layout.addWidget(self._input)

        self._list = QListWidget()
        self._list.setObjectName("commandPaletteList")
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setMaximumHeight(320)
        layout.addWidget(self._list)

        self._hint = QLabel(
            "↑↓ to navigate   ↵ to run   esc to close"
        )
        self._hint.setObjectName("commandPaletteHint")
        self._hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._hint)

    def set_commands(self, commands: list):
        self._commands = commands
        self._filtered = commands[:]
        self._populate_list()

    def add_commands(self, commands: list):
        self._commands.extend(commands)

    def show_palette(self):
        """Show the palette centered over the parent window."""
        parent = self.parent()
        if parent is not None:
            # Position relative to the parent window, then map into global
            # screen coordinates -- this is a top-level popup, so move()
            # takes screen coords, not parent-local ones.
            local_x = max((parent.width() - self.width()) // 2, 0)
            local_y = max(parent.height() // 7, 60)
            self.move(parent.mapToGlobal(QPoint(local_x, local_y)))

        self._input.clear()
        self._filtered = self._commands[:]
        self._populate_list()
        self.show()
        self._input.setFocus()

    def hide_palette(self):
        self.hide()
        self.closed.emit()

    def _on_text_changed(self, _text: str):
        self._debounce_timer.start()

    def _do_filter(self):
        query = self._input.text().strip()
        if not query:
            self._filtered = self._commands[:]
        else:
            scored = []
            for cmd in self._commands:
                score = _fuzzy_match(query, cmd.get("label", ""))
                for key in ("page_name", "action_name", "agent_name", "campaign_name"):
                    if key in cmd:
                        score = max(score, _fuzzy_match(query, cmd[key]))
                if score > 0.1:
                    scored.append((score, cmd))
            scored.sort(key=lambda x: x[0], reverse=True)
            self._filtered = [cmd for _, cmd in scored[:18]]
            # Always offer a natural-language route to the assistant. It leads
            # when nothing matched (plain-English query), and trails as a
            # fallback when commands did match.
            ask = {"type": "ask", "label": f'Ask Aura: "{query}"', "query": query}
            if not self._filtered or " " in query:
                self._filtered.insert(0, ask)
            else:
                self._filtered.append(ask)
        self._populate_list()

    def _populate_list(self):
        self._list.clear()
        for cmd in self._filtered:
            item = QListWidgetItem()
            label = cmd.get("label", "")
            cmd_type = cmd.get("type", "")
            if cmd_type == "navigate":
                display = f"→   {label}"
            elif cmd_type == "action":
                display = f"⚡   {label}"
            elif cmd_type == "agent":
                display = f"🤖   {label}"
            elif cmd_type == "campaign":
                display = f"📋   {label}"
            elif cmd_type == "ask":
                display = f"✨   {label}"
            else:
                display = label
            item.setText(display)
            item.setData(Qt.UserRole, cmd)
            self._list.addItem(item)
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
