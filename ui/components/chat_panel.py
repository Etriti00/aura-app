"""
Aura — Advanced Chat Panel UI
Claude Code-style chat with streaming text, fun thinking animations,
stop generation, file upload/download, and multiline input.
"""

import os
import random

from PySide6.QtWidgets import (
    QComboBox, QGridLayout,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QScrollArea, QFrame, QPushButton, QGraphicsDropShadowEffect,
    QSizePolicy, QTextEdit, QProgressBar, QFileDialog, QApplication,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QSize, QMimeData, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import QFont, QColor, QKeyEvent, QDragEnterEvent, QDropEvent

from config import CHAT_PANEL_WIDTH
from utils.logger import get_logger
from ui.icons import get_icon, get_pixmap

logger = get_logger("chat_panel")

# ─── Fun thinking phrases ──────────────────────────────────────────────
THINKING_PHRASES = [
    "Discombobulating the flibbergibbets…",
    "Recalibrating the quantum flux…",
    "Consulting the oracle of sales wisdom…",
    "Untangling the spaghetti of data…",
    "Polishing the crystal ball…",
    "Herding digital cats…",
    "Reticulating splines…",
    "Brewing a fresh pot of insights…",
    "Negotiating with the algorithms…",
    "Deciphering the ancient scrolls…",
    "Warming up the neural pathways…",
    "Summoning the spirit of productivity…",
    "Calibrating the persuasion matrix…",
    "Folding space-time for faster results…",
    "Charging the creativity capacitors…",
    "Asking the magic 8-ball for backup…",
    "Running the numbers through the vibe check…",
    "Feeding the hamsters that power the AI…",
    "Consulting the spreadsheet gods…",
    "Aligning the sales chakras…",
    "Defragmenting the inspiration drive…",
    "Downloading more RAM for this task…",
    "Teaching the AI to be humble…",
    "Converting caffeine to code…",
    "Checking if Mercury is in retrograde…",
    "Synchronizing the buzzword generators…",
    "Deploying the charm offensive…",
    "Compiling the witty response module…",
    "Mining the depths of knowledge…",
    "Performing advanced rocket surgery…",
]

# Streaming speed (ms between words)
STREAM_WORD_DELAY_MS = 30


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
        bubble_font = QFont(label.font())  # inherit the platform system font
        bubble_font.setPointSize(11)
        label.setFont(bubble_font)
        layout.addWidget(label)


class StreamingBubble(QFrame):
    """AI message bubble that reveals text word-by-word like streaming."""

    stream_finished = Signal()

    def __init__(self, full_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("chatBubbleAI")
        self._full_text = full_text
        self._words = full_text.split()
        self._current_idx = 0
        self._is_stopped = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setFont(QFont("Inter", 11))
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._reveal_next)

    def start_streaming(self):
        """Begin the word-by-word reveal."""
        if not self._words:
            self._label.setText(self._full_text)
            self.stream_finished.emit()
            return
        self._timer.start(STREAM_WORD_DELAY_MS)

    def stop_streaming(self):
        """Immediately reveal all remaining text."""
        self._timer.stop()
        self._label.setText(self._full_text)
        self._is_stopped = True
        self.stream_finished.emit()

    def _reveal_next(self):
        if self._current_idx < len(self._words):
            self._current_idx += 1
            self._label.setText(" ".join(self._words[:self._current_idx]))
        else:
            self._timer.stop()
            self.stream_finished.emit()


class ActionChip(QPushButton):
    """Small action suggestion chip."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setObjectName("chipButton")
        self.setFixedHeight(30)
        fm = self.fontMetrics()
        self.setMinimumWidth(fm.horizontalAdvance(text) + 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class ThinkingWidget(QFrame):
    """Fun animated thinking indicator with rotating silly phrases and spinner."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("thinkingWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        # Spinner dots
        self._spinner_label = QLabel("◐")
        self._spinner_label.setObjectName("thinkingSpinner")
        self._spinner_label.setFont(QFont("Inter", 14))
        self._spinner_label.setFixedWidth(20)
        layout.addWidget(self._spinner_label)

        # Fun phrase
        self._phrase_label = QLabel("")
        self._phrase_label.setObjectName("thinkingPhrase")
        self._phrase_label.setFont(QFont("Inter", 11))
        self._phrase_label.setWordWrap(True)
        layout.addWidget(self._phrase_label, stretch=1)

        # Spinner animation (rotate through ◐ ◓ ◑ ◒)
        self._spinner_chars = ["◐", "◓", "◑", "◒"]
        self._spinner_idx = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._spin)

        # Phrase rotation
        self._phrase_timer = QTimer(self)
        self._phrase_timer.timeout.connect(self._next_phrase)
        self._used_phrases = []

    def showEvent(self, event):
        super().showEvent(event)
        self._next_phrase()
        self._spin_timer.start(150)
        self._phrase_timer.start(3000)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._spin_timer.stop()
        self._phrase_timer.stop()

    def _spin(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_chars)
        self._spinner_label.setText(self._spinner_chars[self._spinner_idx])

    def _next_phrase(self):
        if len(self._used_phrases) >= len(THINKING_PHRASES):
            self._used_phrases.clear()
        available = [p for p in THINKING_PHRASES if p not in self._used_phrases]
        phrase = random.choice(available)
        self._used_phrases.append(phrase)
        self._phrase_label.setText(phrase)


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


class FileAttachmentChip(QFrame):
    """Small chip showing an attached file with a remove button."""

    removed = Signal(str)  # file_path

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.setObjectName("fileChip")
        self.file_path = file_path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(6)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap("batch_import", "dark", "accent", 14))
        icon_lbl.setFixedSize(16, 16)
        layout.addWidget(icon_lbl)

        name = os.path.basename(file_path)
        if len(name) > 25:
            name = name[:22] + "…"
        name_lbl = QLabel(name)
        name_lbl.setObjectName("fileChipName")
        name_lbl.setFont(QFont("Inter", 10))
        name_lbl.setToolTip(file_path)
        layout.addWidget(name_lbl)

        remove_btn = QPushButton("×")
        remove_btn.setObjectName("fileChipRemove")
        remove_btn.setFixedSize(18, 18)
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.clicked.connect(lambda: self.removed.emit(self.file_path))
        layout.addWidget(remove_btn)


class FileDownloadCard(QFrame):
    """Card in chat for a file the AI is providing — click to save."""

    def __init__(self, filename: str, content: str, parent=None):
        super().__init__(parent)
        self.setObjectName("fileDownloadCard")
        self._filename = filename
        self._content = content

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_pixmap("export_csv", "dark", "accent", 20))
        icon_lbl.setFixedSize(24, 24)
        layout.addWidget(icon_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_lbl = QLabel(filename)
        name_lbl.setObjectName("fileCardName")
        name_lbl.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        info_layout.addWidget(name_lbl)

        size_text = f"{len(content):,} chars"
        size_lbl = QLabel(size_text)
        size_lbl.setObjectName("mutedText")
        size_lbl.setFont(QFont("Inter", 9))
        info_layout.addWidget(size_lbl)

        layout.addLayout(info_layout, stretch=1)

        save_btn = QPushButton("Save")
        save_btn.setIcon(get_icon("export_csv", "dark", "success"))
        save_btn.setIconSize(QSize(14, 14))
        save_btn.setObjectName("primaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFixedHeight(30)
        save_btn.clicked.connect(self._save_file)
        layout.addWidget(save_btn)

    def _save_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File", self._filename,
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._content)
                logger.info(f"File saved: {path}")
            except Exception as e:
                logger.error(f"File save error: {e}")


class ChatInput(QTextEdit):
    """Multiline input that sends on Enter (Shift+Enter for newline)."""

    submit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatInput")
        self.setPlaceholderText("Ask Aura anything…")
        self.setToolTip("Enter to send · Shift+Enter for a new line")
        self.setFont(QFont("Inter", 12))
        self.setAcceptRichText(False)
        self.setMaximumHeight(120)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.document().contentsChanged.connect(self._auto_resize)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit.emit()
        else:
            super().keyPressEvent(event)

    def _auto_resize(self):
        doc_height = int(self.document().size().height()) + 12
        new_height = max(40, min(120, doc_height))
        self.setFixedHeight(new_height)


class ChatPanel(QWidget):
    """Advanced slide-in chat panel with streaming, stop, files, and fun animations."""

    model_changed = Signal(str)
    panel_toggled = Signal(bool)  # panel opened/closed  # chat model picked in the header
    message_sent = Signal(str)
    message_sent_with_files = Signal(str, list)  # text, [file_paths]
    stop_requested = Signal()
    action_confirmed = Signal(dict)
    draft_approved = Signal(str, str, str)  # subject, body, lead_email

    def __init__(self, parent=None):
        super().__init__(parent)
        # Width is animated by toggle(): closed = 0, open = CHAT_PANEL_WIDTH
        self.setMinimumWidth(0)
        self.setMaximumWidth(0)
        self._width_anim = None
        self._greeting = None
        self.setObjectName("chatPanel")
        self._is_visible = False
        self._is_thinking = False
        self._attached_files: list[str] = []
        self._current_streaming_bubble = None
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Hard 1px dividing line on the panel left edge
        divider = QWidget()
        divider.setObjectName("chatDivider")
        divider.setFixedWidth(1)
        outer.addWidget(divider)

        body = QWidget()
        body.setObjectName("chatPanelBody")
        outer.addWidget(body, stretch=1)

        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ─── Header ───────────────────────────────────────────────
        header = QFrame()
        header.setObjectName("chatHeader")
        header.setFixedHeight(56)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 12, 0)
        header_layout.setSpacing(8)

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

        # Model selector — full fleet plus free-typed custom IDs
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("chatModelCombo")
        self.model_combo.setEditable(True)
        try:
            from core.model_fleet import all_models
            self.model_combo.addItems(all_models())
        except Exception:
            pass
        self.model_combo.setMinimumWidth(170)
        self.model_combo.setMaximumWidth(235)
        self.model_combo.setToolTip(
            "Chat model — pick from the fleet or type any model ID"
        )
        self.model_combo.activated.connect(
            lambda _i: self.model_changed.emit(self.model_combo.currentText())
        )
        self.model_combo.lineEdit().returnPressed.connect(
            lambda: self.model_changed.emit(self.model_combo.currentText())
        )
        # Long model IDs: keep the provider prefix visible, not the tail
        self.model_combo.lineEdit().editingFinished.connect(
            lambda: self.model_combo.lineEdit().setCursorPosition(0)
        )
        header_layout.addWidget(self.model_combo)
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

        # Empty-state greeting, hidden once the first message arrives
        self._greeting = QWidget()
        g_lay = QVBoxLayout(self._greeting)
        g_lay.setContentsMargins(24, 48, 24, 24)
        g_lay.setSpacing(10)
        g_icon = QLabel()
        g_icon.setPixmap(get_pixmap("chat_title", "dark", "accent", 28))
        g_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g_lay.addWidget(g_icon)
        g_title = QLabel("Aura Assistant")
        g_title.setObjectName("chatTitle")
        g_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g_lay.addWidget(g_title)
        g_sub = QLabel(
            "Ask about your leads, campaigns, and outreach.\n"
            "Try one of the suggestions below."
        )
        g_sub.setObjectName("mutedText")
        g_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g_sub.setWordWrap(True)
        g_lay.addWidget(g_sub)
        self.messages_layout.insertWidget(0, self._greeting)

        # ─── Thinking Widget ─────────────────────────────────────
        self.thinking_widget = ThinkingWidget()
        self.thinking_widget.hide()

        # ─── File Attachment Bar (hidden by default) ──────────────
        self._file_bar = QFrame()
        self._file_bar.setObjectName("chatFileBar")
        self._file_bar_layout = QHBoxLayout(self._file_bar)
        self._file_bar_layout.setContentsMargins(12, 4, 12, 4)
        self._file_bar_layout.setSpacing(6)
        self._file_bar_layout.addStretch()
        self._file_bar.hide()
        layout.addWidget(self._file_bar)

        # ─── Context Chips ────────────────────────────────────────
        chips_frame = QFrame()
        chips_frame.setObjectName("chatChipsBar")
        self.chips_layout = QGridLayout(chips_frame)
        self.chips_layout.setContentsMargins(12, 6, 12, 6)
        self.chips_layout.setHorizontalSpacing(8)
        self.chips_layout.setVerticalSpacing(6)
        self._add_default_chips()
        layout.addWidget(chips_frame)

        # ─── Input Bar ────────────────────────────────────────────
        input_frame = QFrame()
        input_frame.setObjectName("chatInputBar")
        input_frame.setMinimumHeight(56)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)
        input_layout.setSpacing(8)

        # Attach file button
        attach_btn = QPushButton()
        attach_btn.setIcon(get_icon("batch_import", "dark", "muted"))
        attach_btn.setIconSize(QSize(16, 16))
        attach_btn.setObjectName("chatAttachButton")
        attach_btn.setFixedSize(34, 34)
        attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attach_btn.setToolTip("Attach file")
        attach_btn.clicked.connect(self._pick_file)
        input_layout.addWidget(attach_btn)

        # Multiline input
        self.input_field = ChatInput()
        input_layout.addWidget(self.input_field)
        self.input_field.submit.connect(self._on_send)

        # Send button (swaps to Stop when thinking)
        self._send_btn = QPushButton()
        self._send_btn.setIcon(get_icon("chat_send", "dark"))
        self._send_btn.setIconSize(QSize(16, 16))
        self._send_btn.setObjectName("chatSendButton")
        self._send_btn.setFixedSize(38, 38)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setToolTip("Send message (Enter)")
        self._send_btn.clicked.connect(self._on_send_or_stop)
        input_layout.addWidget(self._send_btn)

        layout.addWidget(input_frame)

    def _add_default_chips(self):
        suggestions = ["Show stats", "Enrich leads", "Export report", "Best skill?"]
        for i, text in enumerate(suggestions):
            chip = ActionChip(text)
            chip.clicked.connect(lambda checked, t=text: self._send_text(t))
            self.chips_layout.addWidget(chip, i // 2, i % 2)
        self.chips_layout.setColumnStretch(2, 1)

    # ─── Input Handling ──────────────────────────────────────────

    def _send_text(self, text: str):
        self.input_field.setPlainText(text)
        self._on_send()

    def _on_send(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return
        self.input_field.clear()
        self.add_message(text, is_user=True)

        if self._attached_files:
            self.message_sent_with_files.emit(text, list(self._attached_files))
            self._clear_attachments()
        else:
            self.message_sent.emit(text)

    def _on_send_or_stop(self):
        if self._is_thinking:
            self._on_stop()
        else:
            self._on_send()

    def _on_stop(self):
        """User clicked stop — cancel generation."""
        self.stop_requested.emit()
        self.show_thinking(False)
        # If there's a streaming bubble in progress, finish it
        if self._current_streaming_bubble:
            self._current_streaming_bubble.stop_streaming()
            self._current_streaming_bubble = None
        self.add_message("Generation stopped.", is_user=False)

    # ─── File Attachment ─────────────────────────────────────────

    def _pick_file(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", "",
            "All Files (*);;Text (*.txt *.csv *.json *.md);;Images (*.png *.jpg *.jpeg)",
        )
        for p in paths:
            self._add_attachment(p)

    def _add_attachment(self, file_path: str):
        if file_path in self._attached_files:
            return
        self._attached_files.append(file_path)

        chip = FileAttachmentChip(file_path)
        chip.removed.connect(self._remove_attachment)
        # Insert before the stretch
        count = self._file_bar_layout.count()
        self._file_bar_layout.insertWidget(count - 1, chip)
        self._file_bar.show()

    def _remove_attachment(self, file_path: str):
        if file_path in self._attached_files:
            self._attached_files.remove(file_path)
        # Remove the chip widget
        for i in range(self._file_bar_layout.count()):
            item = self._file_bar_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), FileAttachmentChip):
                if item.widget().file_path == file_path:
                    w = item.widget()
                    self._file_bar_layout.removeWidget(w)
                    w.deleteLater()
                    break
        if not self._attached_files:
            self._file_bar.hide()

    def _clear_attachments(self):
        self._attached_files.clear()
        while self._file_bar_layout.count() > 1:
            item = self._file_bar_layout.itemAt(0)
            if item and item.widget():
                w = item.widget()
                self._file_bar_layout.removeWidget(w)
                w.deleteLater()
            else:
                break
        self._file_bar.hide()

    # ─── Drag and Drop ───────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and os.path.isfile(path):
                self._add_attachment(path)

    # ─── Public API ───────────────────────────────────────────────

    def add_message(self, text: str, is_user: bool = True):
        """Add a message bubble to the chat."""
        bubble = MessageBubble(text, is_user)
        self._insert_widget(bubble)
        self._scroll_to_bottom()

    def add_streaming_message(self, text: str):
        """Add an AI message that streams in word-by-word."""
        bubble = StreamingBubble(text)
        self._current_streaming_bubble = bubble
        bubble.stream_finished.connect(self._on_stream_done)
        self._insert_widget(bubble)
        bubble.start_streaming()
        self._scroll_to_bottom()

    def _on_stream_done(self):
        self._current_streaming_bubble = None

    def add_confirmation_card(self, action: str, detail: str, intent_dict: dict):
        card = ConfirmationCard(action, detail, intent_dict)
        card.confirmed.connect(self.action_confirmed.emit)
        card.cancelled.connect(lambda: card.hide())
        self._insert_widget(card)
        self._scroll_to_bottom()

    def add_file_download(self, filename: str, content: str):
        """Add a downloadable file card to the chat."""
        card = FileDownloadCard(filename, content)
        self._insert_widget(card)
        self._scroll_to_bottom()

    def show_thinking(self, show: bool):
        """Show or hide the fun thinking indicator."""
        self._is_thinking = show
        if show:
            self._insert_widget(self.thinking_widget)
            self.thinking_widget.show()
            # Swap send button to stop
            self._send_btn.setIcon(get_icon("chat_cancel", "dark", "danger"))
            self._send_btn.setObjectName("chatStopButton")
            self._send_btn.style().unpolish(self._send_btn)
            self._send_btn.style().polish(self._send_btn)
            self._send_btn.setToolTip("Stop generation")
            self.input_field.setEnabled(False)
        else:
            self.thinking_widget.hide()
            # Swap stop button back to send
            self._send_btn.setIcon(get_icon("chat_send", "dark"))
            self._send_btn.setObjectName("chatSendButton")
            self._send_btn.style().unpolish(self._send_btn)
            self._send_btn.style().polish(self._send_btn)
            self._send_btn.setToolTip("Send message (Enter)")
            self.input_field.setEnabled(True)
            self.input_field.setFocus()
        self._scroll_to_bottom()

    # Legacy alias
    def show_typing(self, show: bool):
        self.show_thinking(show)

    def set_current_model(self, model_id: str):
        """Reflect the configured chat model in the header selector."""
        if model_id:
            self.model_combo.setEditText(model_id)
        self.model_combo.lineEdit().setCursorPosition(0)

    def toggle(self):
        if self._is_visible:
            self._is_visible = False
            self._animate_width(0)
        else:
            self._is_visible = True
            self.show()
            self._animate_width(CHAT_PANEL_WIDTH)
            self.input_field.setFocus()
        self.panel_toggled.emit(self._is_visible)

    def _animate_width(self, target: int):
        """Slide the panel open or closed; interruptible mid-flight."""
        if self._width_anim is not None:
            self._width_anim.stop()
        anim = QPropertyAnimation(self, b"maximumWidth", self)
        anim.setStartValue(self.width())
        anim.setEndValue(target)
        anim.setDuration(300)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if target == 0:
            self.setMinimumWidth(0)
            anim.finished.connect(self._finish_close)
        else:
            anim.valueChanged.connect(lambda v: self.setMinimumWidth(int(v)))
        anim.start()
        self._width_anim = anim

    def _finish_close(self):
        if not self._is_visible:
            self.hide()

    @property
    def is_panel_visible(self) -> bool:
        return self._is_visible

    def add_progress(self, label: str = "Working...") -> ProgressWidget:
        widget = ProgressWidget(label)
        self._insert_widget(widget)
        self._scroll_to_bottom()
        return widget

    def add_action_block(self, title: str, data: dict):
        block = ActionBlock(title, data)
        self._insert_widget(block)
        self._scroll_to_bottom()

    def add_inline_editor(self, subject: str, body: str, lead_email: str = ""):
        editor = InlineEditor(subject, body, lead_email)
        editor.edit_confirmed.connect(self.draft_approved.emit)
        self._insert_widget(editor)
        self._scroll_to_bottom()

    # ─── Helpers ──────────────────────────────────────────────────

    def _insert_widget(self, widget):
        if self._greeting is not None and self._greeting.isVisible():
            self._greeting.hide()
        count = self.messages_layout.count()
        self.messages_layout.insertWidget(count - 1, widget)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()
        ))

    def handle_response(self, response: dict):
        """Process orchestrator response and update UI."""
        self.show_thinking(False)

        if response.get("clarification_needed"):
            self.add_streaming_message(
                response.get("clarification_question", "Could you clarify?")
            )
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
                self.add_streaming_message(response_text)
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

        # Show lead list as streamed text
        if intent == "list_leads" and execution.get("success"):
            total = data.get("total", 0)
            text_summary = data.get("_text_summary", "")
            response_text = response.get("response_text", "")
            if total == 0:
                self.add_streaming_message(
                    response_text or "No leads found matching your criteria."
                )
                return
            header = response_text or f"Found {total} leads:"
            full_text = f"{header}\n\n{text_summary}"
            self.add_streaming_message(full_text)
            return

        # Show lead detail as action block
        if intent == "show_lead_detail" and execution.get("success"):
            response_text = response.get("response_text", "")
            if response_text:
                self.add_streaming_message(response_text)
            display_data = {k: v for k, v in data.items() if not k.startswith("_") and v is not None}
            if display_data:
                name = display_data.get("business_name", "Lead")
                self.add_action_block(f"Lead: {name}", display_data)
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

        # Check for file content in response
        if data.get("_file_content") and data.get("_file_name"):
            self.add_file_download(data["_file_name"], data["_file_content"])

        # Default: streaming text message
        response_text = response.get("response_text", "")
        if not response_text and execution:
            answer = data.get("answer", "")
            if answer:
                response_text = answer
            else:
                response_text = "Done!" if execution.get("success") else f"Error: {execution.get('error', 'Unknown')}"

        self.add_streaming_message(response_text)
