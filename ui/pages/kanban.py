"""
Aura -- Kanban Board Page
5-column Kanban board with ticket cards, filter bar, and detail/create dialogs.
"""

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QComboBox, QLineEdit, QSizePolicy, QDialog, QTextEdit,
    QDateTimeEdit, QMenu, QGridLayout,
)
from PySide6.QtCore import Qt, Signal

from ui.components.glass_card import GlassCard, StatCard
from ui.components.modern_button import ModernButton
from ui.components.empty_state import EmptyState
from ui.icons import get_pixmap
from config import TICKET_STATUSES, TICKET_PRIORITIES


# ─── Ticket Card ────────────────────────────────────────────────────

class TicketCard(QFrame):
    """Compact card representing a single ticket in a Kanban column."""

    clicked = Signal(int)
    move_requested = Signal(int, str)

    def __init__(self, ticket_data: dict, parent=None):
        super().__init__(parent)
        self._ticket_id = ticket_data.get("id", 0)
        self._data = ticket_data
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(80)
        # Mark overdue
        is_overdue = False
        due = ticket_data.get("due_date")
        if due and ticket_data.get("status") != "done":
            try:
                due_dt = datetime.fromisoformat(due)
                is_overdue = due_dt < datetime.utcnow()
            except (ValueError, TypeError):
                pass
        self.setObjectName("ticketCardOverdue" if is_overdue else "ticketCard")
        self._setup_ui(ticket_data)

    def _setup_ui(self, data: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Top row: priority dot + title
        top = QHBoxLayout()
        top.setSpacing(8)

        priority = data.get("priority", "medium")
        priority_dot = QLabel("\u25cf")
        priority_dot.setObjectName(f"priorityDot{priority.capitalize()}")
        priority_dot.setFixedWidth(14)
        top.addWidget(priority_dot)

        title = QLabel(data.get("title", "Untitled"))
        title.setObjectName("ticketTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(40)
        top.addWidget(title, stretch=1)
        layout.addLayout(top)

        # Bottom row: assignee emoji + due date + labels
        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        assignee_emoji = data.get("assignee_emoji", "")
        if assignee_emoji:
            assignee = QLabel(assignee_emoji)
            assignee.setObjectName("ticketAssignee")
            assignee.setFixedWidth(20)
            assignee.setToolTip(data.get("assignee_name", ""))
            bottom.addWidget(assignee)

        due_display = data.get("due_date_display", "")
        if due_display:
            due_label = QLabel(due_display)
            due_label.setObjectName("ticketDueDate")
            bottom.addWidget(due_label)

        labels_str = data.get("labels", "")
        if labels_str:
            for label_text in labels_str.split(",")[:2]:
                text = label_text.strip()
                if text:
                    chip = QLabel(text)
                    chip.setObjectName("ticketLabel")
                    bottom.addWidget(chip)

        bottom.addStretch()

        sub_count = data.get("sub_ticket_count", 0)
        if sub_count > 0:
            sub_label = QLabel(f"[{sub_count}]")
            sub_label.setObjectName("mutedText")
            bottom.addWidget(sub_label)

        layout.addLayout(bottom)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._ticket_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setObjectName("ticketContextMenu")
        for status in TICKET_STATUSES:
            display = status.replace("_", " ").title()
            action = menu.addAction(f"Move to {display}")
            action.triggered.connect(
                lambda checked, s=status: self.move_requested.emit(self._ticket_id, s)
            )
        menu.exec(event.globalPos())


# ─── Kanban Column ────────────────────────────────────────────────

class KanbanColumn(QFrame):
    """A single Kanban column containing stacked ticket cards."""

    ticket_clicked = Signal(int)
    ticket_move_requested = Signal(int, str)

    DISPLAY_NAMES = {
        "backlog": "Backlog",
        "todo": "To Do",
        "in_progress": "In Progress",
        "review": "Review",
        "done": "Done",
    }

    def __init__(self, status: str, parent=None):
        super().__init__(parent)
        self.setObjectName("kanbanColumn")
        self._status = status
        self._cards = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)

        # Column header
        header_row = QHBoxLayout()
        header = QLabel(self.DISPLAY_NAMES.get(self._status, self._status))
        header.setObjectName("kanbanColumnHeader")
        header_row.addWidget(header)

        self._count_label = QLabel("0")
        self._count_label.setObjectName("kanbanColumnCount")
        header_row.addWidget(self._count_label)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch()

        scroll.setWidget(self._card_container)
        layout.addWidget(scroll, stretch=1)

    def load_tickets(self, tickets: list):
        """Clear and repopulate with ticket cards."""
        self._cards.clear()
        while self._card_layout.count() > 1:
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._count_label.setText(str(len(tickets)))

        for t in tickets:
            card = TicketCard(t)
            card.clicked.connect(self.ticket_clicked.emit)
            card.move_requested.connect(self.ticket_move_requested.emit)
            self._card_layout.insertWidget(self._card_layout.count() - 1, card)
            self._cards.append(card)


# ─── Ticket Detail Dialog ─────────────────────────────────────────

class TicketDetailDialog(QDialog):
    """Full ticket detail with editable fields and comment thread."""

    ticket_updated = Signal(int, dict)
    comment_added = Signal(int, str)
    ticket_deleted = Signal(int)
    move_requested = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ticket Detail")
        self.setObjectName("ticketDetailDialog")
        self.setMinimumSize(560, 640)
        self.resize(620, 720)
        self._ticket_id = None
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Header
        header_frame = QFrame()
        header_frame.setObjectName("ticketDetailHeader")
        header_frame.setFixedHeight(60)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 12, 20, 12)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Ticket title...")
        header_layout.addWidget(self._title_edit, stretch=1)

        self._status_combo = QComboBox()
        for s in TICKET_STATUSES:
            self._status_combo.addItem(s.replace("_", " ").title(), s)
        header_layout.addWidget(self._status_combo)

        main.addWidget(header_frame)

        # Body scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(12)

        # Description
        desc_label = QLabel("Description")
        desc_label.setObjectName("formLabel")
        body_layout.addWidget(desc_label)
        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(120)
        self._desc_edit.setPlaceholderText("Describe the ticket...")
        body_layout.addWidget(self._desc_edit)

        # Fields row
        fields_grid = QGridLayout()
        fields_grid.setSpacing(10)

        fields_grid.addWidget(self._make_label("Priority"), 0, 0)
        self._priority_combo = QComboBox()
        for p in TICKET_PRIORITIES:
            self._priority_combo.addItem(p.capitalize(), p)
        fields_grid.addWidget(self._priority_combo, 0, 1)

        fields_grid.addWidget(self._make_label("Assignee"), 0, 2)
        self._assignee_combo = QComboBox()
        self._assignee_combo.addItem("Unassigned", None)
        fields_grid.addWidget(self._assignee_combo, 0, 3)

        fields_grid.addWidget(self._make_label("Due Date"), 1, 0)
        self._due_edit = QDateTimeEdit()
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._due_edit.setSpecialValueText("No due date")
        fields_grid.addWidget(self._due_edit, 1, 1)

        fields_grid.addWidget(self._make_label("Labels"), 1, 2)
        self._labels_edit = QLineEdit()
        self._labels_edit.setPlaceholderText("bug, urgent, ...")
        fields_grid.addWidget(self._labels_edit, 1, 3)

        body_layout.addLayout(fields_grid)

        # Comments section
        comments_label = QLabel("Comments")
        comments_label.setObjectName("cardHeader")
        body_layout.addWidget(comments_label)

        self._comments_container = QVBoxLayout()
        self._comments_container.setSpacing(8)
        body_layout.addLayout(self._comments_container)

        # New comment input
        comment_row = QHBoxLayout()
        self._comment_input = QLineEdit()
        self._comment_input.setPlaceholderText("Add a comment...")
        self._comment_input.returnPressed.connect(self._on_add_comment)
        comment_row.addWidget(self._comment_input, stretch=1)
        send_btn = ModernButton("Send", "primary")
        send_btn.setFixedHeight(36)
        send_btn.clicked.connect(self._on_add_comment)
        comment_row.addWidget(send_btn)
        body_layout.addLayout(comment_row)

        body_layout.addStretch()
        scroll.setWidget(body)
        main.addWidget(scroll, stretch=1)

        # Footer buttons
        footer = QHBoxLayout()
        footer.setContentsMargins(20, 12, 20, 12)

        save_btn = ModernButton("Save Changes", "primary")
        save_btn.clicked.connect(self._on_save)
        footer.addWidget(save_btn)

        delete_btn = ModernButton("Delete", "danger")
        delete_btn.clicked.connect(self._on_delete)
        footer.addWidget(delete_btn)

        footer.addStretch()
        main.addLayout(footer)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("formLabel")
        return lbl

    def load_ticket(self, data: dict):
        """Populate dialog with full ticket data and comments."""
        self._ticket_id = data.get("id")
        self._title_edit.setText(data.get("title", ""))
        self._desc_edit.setPlainText(data.get("description", ""))

        # Status
        idx = self._status_combo.findData(data.get("status", "backlog"))
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)

        # Priority
        idx = self._priority_combo.findData(data.get("priority", "medium"))
        if idx >= 0:
            self._priority_combo.setCurrentIndex(idx)

        # Assignee
        assignee_id = data.get("assignee_id")
        for i in range(self._assignee_combo.count()):
            if self._assignee_combo.itemData(i) == assignee_id:
                self._assignee_combo.setCurrentIndex(i)
                break

        # Due date
        due = data.get("due_date")
        if due:
            try:
                self._due_edit.setDateTime(datetime.fromisoformat(due))
            except (ValueError, TypeError):
                pass

        # Labels
        self._labels_edit.setText(data.get("labels", ""))

        # Comments
        self._clear_comments()
        for c in data.get("comments", []):
            self._add_comment_bubble(c)

    def set_agents(self, agents: list):
        """Populate assignee combo."""
        self._assignee_combo.clear()
        self._assignee_combo.addItem("Unassigned", None)
        for a in agents:
            display = f"{a.get('emoji', '')} {a.get('name', '')}".strip()
            self._assignee_combo.addItem(display, a.get("id"))

    def _clear_comments(self):
        while self._comments_container.count():
            item = self._comments_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_comment_bubble(self, comment: dict):
        bubble = QFrame()
        bubble.setObjectName("ticketCommentBubble")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.setSpacing(4)

        # Author + time
        meta_row = QHBoxLayout()
        author_name = comment.get("author_name") or comment.get("author_type", "User")
        author_emoji = comment.get("author_emoji", "")
        author_label = QLabel(f"{author_emoji} {author_name}".strip())
        author_label.setObjectName("ticketCommentAuthor")
        meta_row.addWidget(author_label)

        time_str = comment.get("created_at", "")
        if time_str:
            try:
                dt = datetime.fromisoformat(time_str)
                time_str = dt.strftime("%b %d, %H:%M")
            except (ValueError, TypeError):
                pass
        time_label = QLabel(time_str)
        time_label.setObjectName("ticketCommentTime")
        meta_row.addWidget(time_label)
        meta_row.addStretch()
        bl.addLayout(meta_row)

        content = QLabel(comment.get("content", ""))
        content.setWordWrap(True)
        content.setObjectName("mutedText")
        bl.addWidget(content)

        self._comments_container.addWidget(bubble)

    def _on_save(self):
        if not self._ticket_id:
            return
        fields = {
            "title": self._title_edit.text(),
            "description": self._desc_edit.toPlainText(),
            "priority": self._priority_combo.currentData(),
            "assignee_id": self._assignee_combo.currentData(),
            "labels": self._labels_edit.text(),
        }
        new_status = self._status_combo.currentData()
        self.ticket_updated.emit(self._ticket_id, fields)
        self.move_requested.emit(self._ticket_id, new_status)
        self.accept()

    def _on_delete(self):
        if self._ticket_id:
            self.ticket_deleted.emit(self._ticket_id)
            self.accept()

    def _on_add_comment(self):
        text = self._comment_input.text().strip()
        if text and self._ticket_id:
            self.comment_added.emit(self._ticket_id, text)
            self._comment_input.clear()


# ─── Create Ticket Dialog ──────────────────────────────────────────

class CreateTicketDialog(QDialog):
    """Dialog for creating a new ticket."""

    ticket_submitted = Signal(dict)

    def __init__(self, agents_list: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Ticket")
        self.setObjectName("createTicketDialog")
        self.setMinimumSize(480, 480)
        self._agents = agents_list
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title
        title_label = QLabel("Title")
        title_label.setObjectName("formLabel")
        layout.addWidget(title_label)
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Ticket title...")
        layout.addWidget(self._title_input)

        # Description
        desc_label = QLabel("Description")
        desc_label.setObjectName("formLabel")
        layout.addWidget(desc_label)
        self._desc_input = QTextEdit()
        self._desc_input.setMaximumHeight(100)
        self._desc_input.setPlaceholderText("Describe the task...")
        layout.addWidget(self._desc_input)

        # Row: Priority + Assignee
        row = QHBoxLayout()
        row.setSpacing(12)

        p_col = QVBoxLayout()
        p_label = QLabel("Priority")
        p_label.setObjectName("formLabel")
        p_col.addWidget(p_label)
        self._priority_combo = QComboBox()
        for p in TICKET_PRIORITIES:
            self._priority_combo.addItem(p.capitalize(), p)
        self._priority_combo.setCurrentIndex(2)  # medium
        p_col.addWidget(self._priority_combo)
        row.addLayout(p_col)

        a_col = QVBoxLayout()
        a_label = QLabel("Assignee")
        a_label.setObjectName("formLabel")
        a_col.addWidget(a_label)
        self._assignee_combo = QComboBox()
        self._assignee_combo.addItem("Unassigned", None)
        for a in self._agents:
            display = f"{a.get('emoji', '')} {a.get('name', '')}".strip()
            self._assignee_combo.addItem(display, a.get("id"))
        a_col.addWidget(self._assignee_combo)
        row.addLayout(a_col)

        layout.addLayout(row)

        # Row: Due Date + Labels
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        d_col = QVBoxLayout()
        d_label = QLabel("Due Date")
        d_label.setObjectName("formLabel")
        d_col.addWidget(d_label)
        self._due_edit = QDateTimeEdit()
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._due_edit.setDateTime(datetime.now())
        self._due_edit.setSpecialValueText("No due date")
        d_col.addWidget(self._due_edit)
        row2.addLayout(d_col)

        l_col = QVBoxLayout()
        l_label = QLabel("Labels")
        l_label.setObjectName("formLabel")
        l_col.addWidget(l_label)
        self._labels_input = QLineEdit()
        self._labels_input.setPlaceholderText("bug, urgent, ...")
        l_col.addWidget(self._labels_input)
        row2.addLayout(l_col)

        layout.addLayout(row2)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = ModernButton("Cancel", "secondary")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        create_btn = ModernButton("Create Ticket", "primary")
        create_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(create_btn)
        layout.addLayout(btn_row)

    def _on_submit(self):
        title = self._title_input.text().strip()
        if not title:
            return
        data = {
            "title": title,
            "description": self._desc_input.toPlainText(),
            "priority": self._priority_combo.currentData(),
            "assignee_id": self._assignee_combo.currentData(),
            "labels": self._labels_input.text(),
        }
        # Only include due_date if user changed it from default
        due = self._due_edit.dateTime().toPython()
        if due:
            data["due_date"] = due
        self.ticket_submitted.emit(data)
        self.accept()


# ─── Kanban Board Page ─────────────────────────────────────────────

class KanbanPage(QWidget):
    """Full Kanban board page with 5 columns, filter bar, and create button."""

    create_ticket_requested = Signal(dict)
    move_ticket_requested = Signal(int, str)
    ticket_selected = Signal(int)
    update_ticket_requested = Signal(int, dict)
    delete_ticket_requested = Signal(int)
    add_comment_requested = Signal(int, str)
    filter_changed = Signal(dict)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._columns = {}
        self._agents_list = []
        self._setup_ui()
        self.detail_dialog = TicketDetailDialog(self)

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(0)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        content = QWidget()
        content.setObjectName("centralWidget")
        content.setMinimumWidth(0)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(32, 28, 32, 28)
        self._content_layout.setSpacing(16)

        # Header row
        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        title = QLabel("Kanban")
        title.setObjectName("sectionHeader")
        header_col.addWidget(title)
        subtitle = QLabel("Track and manage agent tickets across your pipeline")
        subtitle.setObjectName("sectionSubheader")
        header_col.addWidget(subtitle)
        header_row.addLayout(header_col)
        header_row.addStretch()

        self._create_btn = ModernButton("+ Create Ticket", "primary")
        self._create_btn.setFixedHeight(40)
        self._create_btn.clicked.connect(self._on_create_ticket)
        header_row.addWidget(self._create_btn)

        refresh_btn = ModernButton("Refresh", "secondary")
        refresh_btn.setFixedHeight(40)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        header_row.addWidget(refresh_btn)

        self._content_layout.addLayout(header_row)

        # Stat cards row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self._total_card = StatCard("0", "TOTAL", accent="blue", variant="default")
        self._progress_card = StatCard("0", "IN PROGRESS", accent="purple", variant="solid")
        self._overdue_card = StatCard("0", "OVERDUE", accent="red", variant="default")
        self._done_card = StatCard("0", "DONE", accent="green", variant="solid")
        stats_row.addWidget(self._total_card)
        stats_row.addWidget(self._progress_card)
        stats_row.addWidget(self._overdue_card)
        stats_row.addWidget(self._done_card)
        self._content_layout.addLayout(stats_row)

        # Filter bar
        filter_card = GlassCard()
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        filter_layout.addWidget(self._make_label("Priority:"))
        self._filter_priority = QComboBox()
        self._filter_priority.addItem("All", None)
        for p in TICKET_PRIORITIES:
            self._filter_priority.addItem(p.capitalize(), p)
        self._filter_priority.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_priority)

        filter_layout.addWidget(self._make_label("Assignee:"))
        self._filter_assignee = QComboBox()
        self._filter_assignee.addItem("All", None)
        self._filter_assignee.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_assignee)

        filter_layout.addWidget(self._make_label("Label:"))
        self._filter_label = QLineEdit()
        self._filter_label.setPlaceholderText("Filter by label...")
        self._filter_label.setMaximumWidth(160)
        self._filter_label.returnPressed.connect(self._on_filter_changed)
        filter_layout.addWidget(self._filter_label)

        filter_layout.addStretch()
        filter_card.get_layout().addLayout(filter_layout)
        self._content_layout.addWidget(filter_card)

        # Kanban columns
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)
        for status in TICKET_STATUSES:
            col = KanbanColumn(status)
            col.ticket_clicked.connect(self.ticket_selected.emit)
            col.ticket_move_requested.connect(self.move_ticket_requested.emit)
            columns_layout.addWidget(col, stretch=1)
            self._columns[status] = col
        self._content_layout.addLayout(columns_layout, stretch=1)

        # Empty state (hidden initially)
        self._empty_state = EmptyState(
            icon_key="empty_kanban",
            title="No tickets yet",
            subtitle="Create your first ticket to start tracking agent work",
        )
        self._empty_state.setVisible(False)
        self._content_layout.addWidget(self._empty_state)

        scroll.setWidget(content)
        main.addWidget(scroll)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("formLabel")
        return lbl

    def update_board(self, data: dict):
        """Receive grouped ticket data {status: [tickets]} and populate columns."""
        total = 0
        in_progress = 0
        done = 0
        overdue = 0
        now = datetime.utcnow()

        for status, tickets in data.items():
            col = self._columns.get(status)
            if col:
                col.load_tickets(tickets)
            total += len(tickets)
            if status == "in_progress":
                in_progress = len(tickets)
            elif status == "done":
                done = len(tickets)
            for t in tickets:
                due = t.get("due_date")
                if due and t.get("status") != "done":
                    try:
                        due_dt = datetime.fromisoformat(due)
                        if due_dt < now:
                            overdue += 1
                    except (ValueError, TypeError):
                        pass

        self._total_card.set_value(str(total))
        self._progress_card.set_value(str(in_progress))
        self._overdue_card.set_value(str(overdue))
        self._done_card.set_value(str(done))

        self._empty_state.setVisible(total == 0)

    def show_ticket_detail(self, data: dict):
        """Show the detail dialog for a ticket."""
        self.detail_dialog.set_agents(self._agents_list)
        self.detail_dialog.load_ticket(data)
        self.detail_dialog.show()

    def set_agents_list(self, agents: list):
        """Store agents list for create dialog and filter combo."""
        self._agents_list = agents
        self._filter_assignee.clear()
        self._filter_assignee.addItem("All", None)
        for a in agents:
            display = f"{a.get('emoji', '')} {a.get('name', '')}".strip()
            self._filter_assignee.addItem(display, a.get("id"))

    def _on_create_ticket(self):
        dialog = CreateTicketDialog(self._agents_list, self)
        dialog.ticket_submitted.connect(self.create_ticket_requested.emit)
        dialog.exec()

    def _on_filter_changed(self):
        self.filter_changed.emit({
            "priority": self._filter_priority.currentData(),
            "assignee_id": self._filter_assignee.currentData(),
            "label": self._filter_label.text().strip() or None,
        })

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
