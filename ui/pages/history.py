"""
Aura -- Command History Page
Chronological activity log with expandable command trees, filter bar, and detail dialog.
"""

import json
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QComboBox, QLineEdit, QSizePolicy, QDialog, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QSize

from ui.components.glass_card import GlassCard, StatCard
from ui.components.modern_button import ModernButton
from ui.components.empty_state import EmptyState
from ui.icons import get_icon, get_pixmap
from config import COMMAND_HISTORY_SOURCES, COMMAND_HISTORY_TYPES


SOURCE_LABELS = {
    "telegram": "Telegram",
    "discord": "Discord",
    "chat": "Chat",
    "system": "System",
    "scheduled": "Scheduled",
}

STATUS_LABELS = {
    "pending": "Pending",
    "running": "Running",
    "completed": "Completed",
    "failed": "Failed",
}


# ─── Command Row ────────────────────────────────────────────────────

class CommandRow(QFrame):
    """Single command entry in the history list."""

    clicked = Signal(int)
    expand_requested = Signal(int)

    def __init__(self, command_data: dict, parent=None):
        super().__init__(parent)
        self._cmd_id = command_data.get("id", 0)
        self._data = command_data
        self._is_expanded = False
        self._children_container = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("historyCommandRow")
        self._setup_ui(command_data)

    def _setup_ui(self, data: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Main row
        row = QHBoxLayout()
        row.setSpacing(10)

        # Timestamp
        created = data.get("created_at", "")
        ts_text = ""
        if created:
            try:
                dt = datetime.fromisoformat(created)
                ts_text = dt.strftime("%m/%d %H:%M")
            except (ValueError, TypeError):
                ts_text = created[:16]
        ts_label = QLabel(ts_text)
        ts_label.setObjectName("historyTimestamp")
        ts_label.setFixedWidth(90)
        row.addWidget(ts_label)

        # Source badge
        source = data.get("source", "system")
        source_label = QLabel(SOURCE_LABELS.get(source, source.capitalize()))
        source_label.setObjectName(f"historySourceBadge{source.capitalize()}")
        source_label.setFixedWidth(70)
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(source_label)

        # Command text / type
        cmd_text = data.get("command_text", "") or data.get("command_type", "")
        if len(cmd_text) > 80:
            cmd_text = cmd_text[:77] + "..."
        text_label = QLabel(cmd_text)
        text_label.setObjectName("cardHeader")
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(text_label)

        # Agent
        agent_emoji = data.get("agent_emoji", "")
        agent_name = data.get("agent_name", "")
        if agent_name:
            agent_label = QLabel(f"{agent_emoji} {agent_name}")
            agent_label.setObjectName("mutedText")
            agent_label.setFixedWidth(110)
            row.addWidget(agent_label)

        # Status badge
        status = data.get("status", "pending")
        status_label = QLabel(STATUS_LABELS.get(status, status.capitalize()))
        status_label.setObjectName(f"historyStatus{status.capitalize()}")
        status_label.setFixedWidth(75)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(status_label)

        # Cost
        cost = data.get("cost_usd", 0)
        if cost and cost > 0:
            cost_label = QLabel(f"${cost:.4f}")
            cost_label.setObjectName("historyCostLabel")
            cost_label.setFixedWidth(60)
            row.addWidget(cost_label)

        # Expand button (if command has children via tree)
        expand_btn = ModernButton("", variant="secondary")
        expand_btn.setIcon(get_icon("chevron_right", "dark"))
        expand_btn.setIconSize(QSize(16, 16))
        expand_btn.setObjectName("historyExpandButton")
        expand_btn.setFixedSize(28, 28)
        expand_btn.setToolTip("Expand command tree")
        expand_btn.clicked.connect(lambda: self._toggle_expand())
        row.addWidget(expand_btn)
        self._expand_btn = expand_btn

        layout.addLayout(row)

        # Children container (hidden initially)
        self._children_container = QVBoxLayout()
        self._children_container.setContentsMargins(24, 0, 0, 0)
        layout.addLayout(self._children_container)

    def _toggle_expand(self):
        self._is_expanded = not self._is_expanded
        icon_key = "chevron_down" if self._is_expanded else "chevron_right"
        self._expand_btn.setIcon(get_icon(icon_key, "dark"))
        self.expand_requested.emit(self._cmd_id)

    def set_children(self, children_data: list):
        """Populate or clear child rows."""
        # Clear existing
        while self._children_container.count():
            item = self._children_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._is_expanded:
            return

        for child in children_data:
            child_row = CommandChildRow(child)
            self._children_container.addWidget(child_row)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._cmd_id)
        super().mousePressEvent(event)


class CommandChildRow(QFrame):
    """Indented child action row within a command tree."""

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("historyChildRow")
        self._setup_ui(data)

    def _setup_ui(self, data: dict):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Type
        cmd_type = data.get("command_type", "")
        type_label = QLabel(cmd_type.replace("_", " ").title())
        type_label.setObjectName("mutedText")
        type_label.setFixedWidth(120)
        layout.addWidget(type_label)

        # Agent
        agent_emoji = data.get("agent_emoji", "")
        agent_name = data.get("agent_name", "")
        if agent_name:
            agent_label = QLabel(f"{agent_emoji} {agent_name}")
            agent_label.setObjectName("mutedText")
            agent_label.setFixedWidth(100)
            layout.addWidget(agent_label)

        # Status
        status = data.get("status", "")
        status_label = QLabel(STATUS_LABELS.get(status, status))
        status_label.setObjectName(f"historyStatus{status.capitalize()}")
        status_label.setFixedWidth(75)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status_label)

        # Duration
        dur = data.get("duration_ms")
        if dur is not None:
            dur_text = f"{dur}ms" if dur < 1000 else f"{dur / 1000:.1f}s"
            dur_label = QLabel(dur_text)
            dur_label.setObjectName("historyCostLabel")
            layout.addWidget(dur_label)

        layout.addStretch()


# ─── Command Detail Dialog ──────────────────────────────────────────

class CommandDetailDialog(QDialog):
    """Full command tree detail view."""

    navigate_to_ticket = Signal(int)
    navigate_to_agent = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyDetailDialog")
        from ui.win_effects import apply_sheet_glass
        apply_sheet_glass(self)
        self.setWindowTitle("Command Detail")
        self.setMinimumSize(650, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self._header = QLabel("Command Detail")
        self._header.setObjectName("sectionHeader")
        layout.addWidget(self._header)

        # Tree widget for command chain
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Type", "Agent", "Status", "Duration", "Cost"])
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tree.setObjectName("historyTreeNode")
        layout.addWidget(self._tree)

        # Detail text area
        self._detail_text = QTextEdit()
        self._detail_text.setReadOnly(True)
        self._detail_text.setObjectName("formLabel")
        self._detail_text.setMaximumHeight(200)
        layout.addWidget(self._detail_text)

        # Close button
        close_btn = ModernButton("Close", variant="secondary")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def load_tree(self, tree_data: dict):
        """Populate the tree widget from command tree data."""
        self._tree.clear()
        self._header.setText(
            tree_data.get("command_text") or tree_data.get("command_type", "Command Detail")
        )

        root_item = self._add_tree_item(None, tree_data)
        for child in tree_data.get("children", []):
            self._add_tree_item_recursive(root_item, child)

        self._tree.expandAll()

        # Show detail JSON
        detail = {
            "intent": tree_data.get("intent"),
            "parameters": tree_data.get("parameters"),
            "result": tree_data.get("result"),
            "correlation_id": tree_data.get("correlation_id"),
        }
        self._detail_text.setPlainText(json.dumps(detail, indent=2, default=str))

    def _add_tree_item(self, parent, data: dict) -> QTreeWidgetItem:
        cmd_type = data.get("command_type", "")
        agent = f"{data.get('agent_emoji', '')} {data.get('agent_name', '')}".strip()
        status = data.get("status", "")
        dur = data.get("duration_ms")
        dur_text = f"{dur}ms" if dur is not None else ""
        cost = data.get("cost_usd", 0)
        cost_text = f"${cost:.4f}" if cost else ""

        item = QTreeWidgetItem([cmd_type, agent, status, dur_text, cost_text])
        if parent:
            parent.addChild(item)
        else:
            self._tree.addTopLevelItem(item)
        return item

    def _add_tree_item_recursive(self, parent_item, data: dict):
        item = self._add_tree_item(parent_item, data)
        for child in data.get("children", []):
            self._add_tree_item_recursive(item, child)


# ─── History Page ───────────────────────────────────────────────────

class HistoryPage(QWidget):
    """Command history & activity log page."""

    refresh_requested = Signal()
    filter_changed = Signal(dict)
    command_selected = Signal(int)
    page_changed = Signal(int)
    prune_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_page = 1
        self._total_pages = 1
        self._agents_list = []
        self._command_rows = {}
        self._detail_dialog = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header
        header_row = QHBoxLayout()
        title = QLabel("Command History")
        title.setObjectName("sectionHeader")
        header_row.addWidget(title)
        header_row.addStretch()

        prune_btn = ModernButton("Prune Old", variant="secondary")
        prune_btn.clicked.connect(lambda: self.prune_requested.emit(90))
        header_row.addWidget(prune_btn)

        refresh_btn = ModernButton("Refresh", variant="primary")
        refresh_btn.clicked.connect(self.refresh_requested)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # Filter bar
        filter_bar = QFrame()
        filter_bar.setObjectName("historyFilterBar")
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 8, 12, 8)
        filter_layout.setSpacing(10)

        # Source combo
        self._source_combo = QComboBox()
        self._source_combo.addItem("All Sources", "")
        for src in COMMAND_HISTORY_SOURCES:
            self._source_combo.addItem(SOURCE_LABELS.get(src, src.capitalize()), src)
        self._source_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._source_combo)

        # Agent combo
        self._agent_combo = QComboBox()
        self._agent_combo.addItem("All Agents", 0)
        self._agent_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._agent_combo)

        # Type combo
        self._type_combo = QComboBox()
        self._type_combo.addItem("All Types", "")
        for t in COMMAND_HISTORY_TYPES:
            self._type_combo.addItem(t.replace("_", " ").title(), t)
        self._type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._type_combo)

        # Status combo
        self._status_combo = QComboBox()
        self._status_combo.addItem("All Status", "")
        for st, label in STATUS_LABELS.items():
            self._status_combo.addItem(label, st)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._status_combo)

        # Search
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search commands...")
        self._search_input.setObjectName("chatInput")
        self._search_input.returnPressed.connect(self._on_filter_changed)
        filter_layout.addWidget(self._search_input)

        layout.addWidget(filter_bar)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_total = StatCard("0", "TOTAL", accent="blue")
        self._stat_today = StatCard("0", "TODAY", accent="purple")
        self._stat_success = StatCard("100%", "SUCCESS RATE", accent="green")
        self._stat_cost = StatCard("$0.00", "TOTAL COST", accent="orange")
        for card in [self._stat_total, self._stat_today, self._stat_success, self._stat_cost]:
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Scrollable history list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        self._list_layout = QVBoxLayout(scroll_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, stretch=1)

        # Empty state
        self._empty_state = EmptyState(
            icon_key="empty_history",
            title="No Command History",
            subtitle="Commands from chat, Telegram, and Discord will appear here.",
        )
        self._empty_state.hide()
        layout.addWidget(self._empty_state)

        # Pagination
        pagination = QFrame()
        pagination.setObjectName("historyPaginationBar")
        pag_layout = QHBoxLayout(pagination)
        pag_layout.setContentsMargins(0, 4, 0, 4)

        pag_layout.addStretch()
        self._prev_btn = ModernButton("Prev", variant="secondary")
        self._prev_btn.setIcon(get_icon("chevron_left", "dark"))
        self._prev_btn.setIconSize(QSize(14, 14))
        self._prev_btn.clicked.connect(lambda: self._change_page(-1))
        pag_layout.addWidget(self._prev_btn)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setObjectName("mutedText")
        pag_layout.addWidget(self._page_label)

        self._next_btn = ModernButton("Next", variant="secondary")
        self._next_btn.setIcon(get_icon("chevron_right", "dark"))
        self._next_btn.setIconSize(QSize(14, 14))
        self._next_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next_btn.clicked.connect(lambda: self._change_page(1))
        pag_layout.addWidget(self._next_btn)
        pag_layout.addStretch()

        layout.addWidget(pagination)

    def _on_filter_changed(self):
        filters = {
            "source": self._source_combo.currentData() or None,
            "agent_id": self._agent_combo.currentData() or None,
            "command_type": self._type_combo.currentData() or None,
            "status": self._status_combo.currentData() or None,
            "search_text": self._search_input.text().strip() or None,
        }
        self._current_page = 1
        self.filter_changed.emit(filters)

    def _change_page(self, delta: int):
        new_page = self._current_page + delta
        if 1 <= new_page <= self._total_pages:
            self._current_page = new_page
            self.page_changed.emit(new_page)

    # ─── Public slots ──────────────────────────────────────────────

    def set_agents_list(self, agents: list):
        """Populate the agent filter combo."""
        self._agents_list = agents
        self._agent_combo.blockSignals(True)
        self._agent_combo.clear()
        self._agent_combo.addItem("All Agents", 0)
        for a in agents:
            self._agent_combo.addItem(
                f"{a.get('emoji', '')} {a['name']}", a["id"]
            )
        self._agent_combo.blockSignals(False)

    def update_history(self, data: dict):
        """Update the history list from paginated data."""
        items = data.get("items", [])
        total = data.get("total", 0)
        page = data.get("page", 1)
        pages = data.get("pages", 1)

        self._current_page = page
        self._total_pages = pages
        self._page_label.setText(f"Page {page} of {pages}")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < pages)

        # Clear existing
        self._command_rows.clear()
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not items:
            self._empty_state.show()
            return

        self._empty_state.hide()
        for cmd_data in items:
            row = CommandRow(cmd_data)
            row.clicked.connect(self.command_selected.emit)
            row.expand_requested.connect(self.command_selected.emit)
            self._command_rows[cmd_data["id"]] = row
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def show_command_tree(self, tree_data: dict):
        """Show the command tree in a detail dialog."""
        if not self._detail_dialog:
            self._detail_dialog = CommandDetailDialog(self)
        self._detail_dialog.load_tree(tree_data)
        self._detail_dialog.show()
        self._detail_dialog.raise_()

        # Also update expanded children in the list
        cmd_id = tree_data.get("id")
        if cmd_id and cmd_id in self._command_rows:
            self._command_rows[cmd_id].set_children(tree_data.get("children", []))

    def update_stats(self, data: dict):
        """Update the stats row."""
        self._stat_total.set_value(str(data.get("root_total", data.get("total", 0))))
        self._stat_today.set_value(str(data.get("today", 0)))
        self._stat_success.set_value(f"{data.get('success_rate', 100)}%")
        total_cost = data.get("total_cost", 0)
        self._stat_cost.set_value(f"${total_cost:.2f}")

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
