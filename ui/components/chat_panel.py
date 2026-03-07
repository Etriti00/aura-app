"""
Aura — Chat Panel UI
Slide-in panel for natural language commands with premium message bubbles,
typing indicator, and context-sensitive action chips.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QPushButton, QGraphicsDropShadowEffect,
    QSizePolicy, QTextEdit, QProgressBar
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QFont, QColor

from config import CHAT_PANEL_WIDTH
from utils.logger import get_logger
from ui.icons import get_icon, get_pixmap

logger = get_logger("chat_panel")


class MessageBubble(QFrame):
    """A single chat message bubble — styled via QSS objectName."""

    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubbleUser" if is_user else "chatBubbleAI")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setFont(QFont("Inter", 11))
        layout.addWidget(label)


class ActionChip(QPushButton):
    """Small action suggestion chip."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("chipButton")
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class TypingIndicator(QFrame):
    """Animated typing dots indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("typingIndicator")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        self._dots = []
        for _ in range(3):
            dot = QLabel("●")
            dot.setObjectName("typingDot")
            dot.setFont(QFont("Inter", 10))
            layout.addWidget(dot)
            self._dots.append(dot)

        layout.addStretch()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_idx = 0

    def showEvent(self, event):
        super().showEvent(event)
        self._anim_timer.start(400)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._anim_timer.stop()

    def _animate(self):
        for i, dot in enumerate(self._dots):
            name = "typingDotActive" if i == self._anim_idx % 3 else "typingDot"
            dot.setObjectName(name)
            dot.style().unpolish(dot)
            dot.style().polish(dot)
        self._anim_idx += 1


class ConfirmationCard(QFrame):
    """Card for confirming destructive actions like sending emails."""

    confirmed = Signal(dict)
    cancelled = Signal()

    def __init__(self, action_text: str, detail: str, intent_dict: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("confirmCard")
        self.intent_dict = intent_dict

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        action_icon = QLabel()
        action_icon.setPixmap(get_pixmap("chat_action", "dark", "accent", 16))
        action_icon.setFixedSize(20, 20)

        action_text_label = QLabel(action_text)
        action_text_label.setObjectName("confirmCardTitle")
        action_text_label.setFont(QFont("Inter", 12, QFont.Weight.Bold))

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        action_row.addWidget(action_icon)
        action_row.addWidget(action_text_label)
        action_row.addStretch()
        layout.addLayout(action_row)

        # Keep reference for compatibility
        action_label = action_text_label
        action_label  # suppress unused warning
        # action_label already added via action_row above

        detail_label = QLabel(detail)
        detail_label.setObjectName("confirmCardDetail")
        detail_label.setWordWrap(True)
        layout.addWidget(detail_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        confirm_btn = QPushButton("Confirm")
        confirm_btn.setIcon(get_icon("chat_confirm", "dark", "success"))
        confirm_btn.setIconSize(QSize(14, 14))
        confirm_btn.setObjectName("primaryButton")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.clicked.connect(lambda: self.confirmed.emit(self.intent_dict))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setIcon(get_icon("chat_cancel", "dark", "danger"))
        cancel_btn.setIconSize(QSize(14, 14))
        cancel_btn.setObjectName("dangerButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.cancelled.emit)

        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)


class ProgressWidget(QFrame):
    """Shows progress for long-running chat operations."""

    def __init__(self, label: str = "Working...", parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubbleAI")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setFont(QFont("Inter", 11))
        layout.addWidget(self._label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setObjectName("mutedText")
        self._status.setFont(QFont("Inter", 9))
        layout.addWidget(self._status)

    def update_progress(self, pct: int, status: str = ""):
        self._progress.setValue(min(pct, 100))
        if status:
            self._status.setText(status)

    def set_label(self, text: str):
        self._label.setText(text)

    def mark_complete(self, text: str = "Done"):
        self._progress.setValue(100)
        self._status.setText(text)


class ActionBlock(QFrame):
    """Rich result card for displaying structured action outcomes in chat."""

    def __init__(self, title: str, data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubbleAI")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        layout.addWidget(title_lbl)

        # Display each key-value pair
        for key, value in data.items():
            if key.startswith("_"):
                continue
            row = QHBoxLayout()
            row.setSpacing(8)

            k_lbl = QLabel(f"{key.replace('_', ' ').title()}:")
            k_lbl.setObjectName("mutedText")
            k_lbl.setFixedWidth(120)
            row.addWidget(k_lbl)

            v_lbl = QLabel(str(value))
            v_lbl.setFont(QFont("Inter", 11))
            v_lbl.setWordWrap(True)
            row.addWidget(v_lbl, stretch=1)

            layout.addLayout(row)


class InlineEditor(QFrame):
    """Editable text block in chat for reviewing/editing email drafts."""

    edit_confirmed = Signal(str, str, str)  # subject, body, lead_email

    def __init__(self, subject: str, body: str, lead_email: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubbleAI")
        self._lead_email = lead_email

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QLabel("Draft Email")
        header.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        layout.addWidget(header)

        if lead_email:
            to_lbl = QLabel(f"To: {lead_email}")
            to_lbl.setObjectName("mutedText")
            layout.addWidget(to_lbl)

        subj_label = QLabel("Subject:")
        subj_label.setObjectName("formLabel")
        layout.addWidget(subj_label)

        self._subject = QLineEdit(subject)
        self._subject.setFont(QFont("Inter", 11))
        layout.addWidget(self._subject)

        body_label = QLabel("Body:")
        body_label.setObjectName("formLabel")
        layout.addWidget(body_label)

        self._body = QTextEdit()
        self._body.setPlainText(body)
        self._body.setFont(QFont("Inter", 11))
        self._body.setMaximumHeight(200)
        layout.addWidget(self._body)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        approve_btn = QPushButton("Approve & Send")
        approve_btn.setObjectName("primaryButton")
        approve_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        approve_btn.clicked.connect(self._on_approve)
        btn_row.addWidget(approve_btn)

        discard_btn = QPushButton("Discard")
        discard_btn.setObjectName("dangerButton")
        discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        discard_btn.clicked.connect(self.hide)
        btn_row.addWidget(discard_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _on_approve(self):
        self.edit_confirmed.emit(
            self._subject.text().strip(),
            self._body.toPlainText().strip(),
            self._lead_email,
        )


class ChatPanel(QWidget):
    """Slide-in chat panel for natural language commands."""

    message_sent = Signal(str)
    action_confirmed = Signal(dict)
    draft_approved = Signal(str, str, str)  # subject, body, lead_email

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(CHAT_PANEL_WIDTH)
        self.setObjectName("chatPanel")
        self._is_visible = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─── Header ───────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("chatHeader")
        header.setFixedHeight(56)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 0, 18, 0)

        title_icon = QLabel()
        title_icon.setPixmap(get_pixmap("chat_title", "dark", "accent", 18))
        title_icon.setFixedSize(22, 22)
        title = QLabel("Aura Chat")
        title.setObjectName("chatTitle")
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))

        close_btn = QPushButton()
        close_btn.setIcon(get_icon("chat_close", "dark"))
        close_btn.setIconSize(QSize(14, 14))
        close_btn.setObjectName("chatCloseButton")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip("Close chat (Esc)")
        close_btn.clicked.connect(self.toggle)

        header_layout.addWidget(title_icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        layout.addWidget(header)

        # ─── Messages Scroll Area ─────────────────────────────────
        self.scroll = QScrollArea()
        self.scroll.setObjectName("chatScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_widget = QWidget()
        self.messages_widget.setObjectName("chatMessagesWidget")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(12, 12, 12, 12)
        self.messages_layout.setSpacing(8)
        self.messages_layout.addStretch()

        self.scroll.setWidget(self.messages_widget)
        layout.addWidget(self.scroll)

        # ─── Typing Indicator ─────────────────────────────────────
        self.typing_indicator = TypingIndicator()
        self.typing_indicator.hide()

        # ─── Context Chips ────────────────────────────────────────
        chips_frame = QFrame()
        chips_frame.setObjectName("chatChipsBar")
        self.chips_layout = QHBoxLayout(chips_frame)
        self.chips_layout.setContentsMargins(12, 6, 12, 6)
        self.chips_layout.setSpacing(6)
        self._add_default_chips()
        layout.addWidget(chips_frame)

        # ─── Input Bar ────────────────────────────────────────────
        input_frame = QFrame()
        input_frame.setObjectName("chatInputBar")
        input_frame.setFixedHeight(56)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(10)

        self.input_field = QLineEdit()
        self.input_field.setObjectName("chatInput")
        self.input_field.setPlaceholderText("Ask Aura anything…")
        self.input_field.setFont(QFont("Inter", 12))
        self.input_field.returnPressed.connect(self._on_send)

        send_btn = QPushButton()
        send_btn.setIcon(get_icon("chat_send", "dark"))
        send_btn.setIconSize(QSize(16, 16))
        send_btn.setObjectName("chatSendButton")
        send_btn.setFixedSize(38, 38)
        send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        send_btn.setToolTip("Send message (Enter)")
        send_btn.clicked.connect(self._on_send)

        input_layout.addWidget(self.input_field)
        input_layout.addWidget(send_btn)
        layout.addWidget(input_frame)

    def _add_default_chips(self):
        """Add context-sensitive suggestion chips."""
        suggestions = ["Show stats", "Best skill?", "Export report"]
        for text in suggestions:
            chip = ActionChip(text)
            chip.clicked.connect(lambda checked, t=text: self._send_text(t))
            self.chips_layout.addWidget(chip)
        self.chips_layout.addStretch()

    def _send_text(self, text: str):
        self.input_field.setText(text)
        self._on_send()

    def _on_send(self):
        text = self.input_field.text().strip()
        if not text:
            return
        self.input_field.clear()
        self.add_message(text, is_user=True)
        self.message_sent.emit(text)

    # ─── Public API ───────────────────────────────────────────────

    def add_message(self, text: str, is_user: bool = True):
        """Add a message bubble to the chat."""
        bubble = MessageBubble(text, is_user)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, bubble)
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def add_confirmation_card(self, action: str, detail: str, intent_dict: dict):
        """Add a confirmation card for a destructive action."""
        card = ConfirmationCard(action, detail, intent_dict)
        card.confirmed.connect(self.action_confirmed.emit)
        card.cancelled.connect(lambda: card.hide())
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, card)

    def show_typing(self, show: bool):
        """Show or hide the typing indicator."""
        if show:
            count = self.messages_layout.count()
            self.messages_layout.insertWidget(count - 1, self.typing_indicator)
            self.typing_indicator.show()
        else:
            self.typing_indicator.hide()

    def toggle(self):
        """Toggle panel visibility."""
        if self._is_visible:
            self.hide()
            self._is_visible = False
        else:
            self.show()
            self._is_visible = True
            self.input_field.setFocus()

    @property
    def is_panel_visible(self) -> bool:
        return self._is_visible

    def add_progress(self, label: str = "Working...") -> ProgressWidget:
        """Add a progress widget to the chat and return it for updates."""
        widget = ProgressWidget(label)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, widget)
        self._scroll_to_bottom()
        return widget

    def add_action_block(self, title: str, data: dict):
        """Add a rich result card to the chat."""
        block = ActionBlock(title, data)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, block)
        self._scroll_to_bottom()

    def add_inline_editor(self, subject: str, body: str, lead_email: str = ""):
        """Add an editable email draft to the chat."""
        editor = InlineEditor(subject, body, lead_email)
        editor.edit_confirmed.connect(self.draft_approved.emit)
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, editor)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def handle_response(self, response: dict):
        """Process orchestrator response and update UI."""
        self.show_typing(False)

        if response.get("clarification_needed"):
            self.add_message(response.get("clarification_question", "Could you clarify?"), is_user=False)
            return

        execution = response.get("execution_result", {})
        if execution.get("requires_confirmation"):
            data = execution.get("data", {})
            action = response.get("intent", "Action")
            detail = response.get("response_text", "")
            if data.get("ready_count"):
                detail += f"\n{data['ready_count']} emails ready to send."
            self.add_confirmation_card(action, detail, response)
            return

        intent = response.get("intent", "")
        data = execution.get("data", {}) if execution else {}

        # Show structured ActionBlock for data-rich results
        action_intents = {
            "show_stats", "crm_sync", "enrich_list", "inbox_triage",
            "export_report", "start_campaign",
        }
        if intent in action_intents and data and execution.get("success"):
            response_text = response.get("response_text", "")
            if response_text:
                self.add_message(response_text, is_user=False)
            # Filter out internal keys and show useful data
            display_data = {k: v for k, v in data.items() if not k.startswith("_") and v is not None}
            if display_data:
                title_map = {
                    "show_stats": "Campaign Stats",
                    "crm_sync": "CRM Sync Results",
                    "enrich_list": "Enrichment Results",
                    "inbox_triage": "Inbox Triage",
                    "export_report": "Export Complete",
                    "start_campaign": "Campaign Created",
                }
                self.add_action_block(title_map.get(intent, "Result"), display_data)
            return

        # Show InlineEditor for draft generation results
        if intent == "generate_drafts" and data.get("draft"):
            draft = data["draft"]
            self.add_inline_editor(
                draft.get("subject", ""),
                draft.get("body", ""),
                draft.get("lead_email", ""),
            )
            return

        # Default: text message
        response_text = response.get("response_text", "")
        if not response_text and execution:
            answer = data.get("answer", "")
            if answer:
                response_text = answer
            else:
                response_text = "Done!" if execution.get("success") else f"Error: {execution.get('error', 'Unknown')}"

        self.add_message(response_text, is_user=False)
