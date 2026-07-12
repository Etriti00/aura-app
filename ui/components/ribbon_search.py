"""
Aura -- Ribbon Search
An inline search that lives in the top ribbon. Collapsed it is a compact
search pill on the right; clicking it expands horizontally to the centre of
the ribbon (a "water droplet" glide) with a liquid-glass field, and shows a
results dropdown. Supports fuzzy command matching and a natural-language
route to the assistant. Esc or a click outside collapses it and clears it.
"""

from PySide6.QtCore import (
    Qt, Signal, QTimer, QEvent, QRect, QPoint,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtWidgets import (
    QWidget, QFrame, QLineEdit, QListWidget, QListWidgetItem,
    QHBoxLayout, QVBoxLayout, QLabel, QApplication,
)
from ui.icons import get_icon
from ui.components.command_palette import _fuzzy_match


class RibbonSearch(QWidget):
    """Inline expanding search for the top ribbon."""

    command_selected = Signal(dict)

    COLLAPSED_W = 132
    EXPANDED_W = 480
    HEIGHT = 40
    RIGHT_INSET = 96   # chat button + right margin + gap

    def __init__(self, ribbon: QWidget, dropdown_host: QWidget, theme: str = "dark"):
        super().__init__(ribbon)
        self._ribbon = ribbon
        self._host = dropdown_host
        self._theme = theme
        self._commands: list = []
        self._filtered: list = []
        self._expanded = False
        self._app_filter_on = False

        self.setObjectName("ribbonSearchWrap")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.input = QLineEdit()
        self.input.setObjectName("ribbonSearchInput")
        self.input.setPlaceholderText("Search")
        self.input.addAction(
            get_icon("sidebar_hunter", theme, "muted"),
            QLineEdit.LeadingPosition,
        )
        self.input.textChanged.connect(self._on_text_changed)
        self.input.returnPressed.connect(self._on_enter)
        self.input.installEventFilter(self)
        lay.addWidget(self.input)

        self.dropdown = QFrame(dropdown_host)
        self.dropdown.setObjectName("ribbonSearchDropdown")
        dl = QVBoxLayout(self.dropdown)
        dl.setContentsMargins(8, 8, 8, 8)
        dl.setSpacing(6)
        self.list = QListWidget()
        self.list.setObjectName("ribbonSearchList")
        self.list.itemClicked.connect(self._on_item_clicked)
        dl.addWidget(self.list)
        self._hint = QLabel("↑↓ to navigate   ↵ to run   esc to close")
        self._hint.setObjectName("ribbonSearchHint")
        self._hint.setAlignment(Qt.AlignCenter)
        dl.addWidget(self._hint)
        self.dropdown.hide()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(360)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._do_filter)

        self._ribbon.installEventFilter(self)
        QTimer.singleShot(0, self.reposition)

    # ── State ───────────────────────────────────────────────────
    @property
    def is_expanded(self) -> bool:
        return self._expanded

    # ── Geometry ────────────────────────────────────────────────
    def _y(self) -> int:
        return max((self._ribbon.height() - self.HEIGHT) // 2, 0)

    def _collapsed_rect(self) -> QRect:
        x = self._ribbon.width() - self.RIGHT_INSET - self.COLLAPSED_W
        return QRect(max(x, 0), self._y(), self.COLLAPSED_W, self.HEIGHT)

    def _expanded_rect(self) -> QRect:
        x = (self._ribbon.width() - self.EXPANDED_W) // 2
        return QRect(max(x, 0), self._y(), self.EXPANDED_W, self.HEIGHT)

    def reposition(self):
        if self._anim.state() == QPropertyAnimation.Running:
            return
        self.setGeometry(self._expanded_rect() if self._expanded else self._collapsed_rect())
        if self._expanded:
            self._place_dropdown()

    # ── Commands ────────────────────────────────────────────────
    def set_commands(self, commands: list):
        self._commands = commands or []

    # ── Expand / collapse ───────────────────────────────────────
    def expand(self):
        if self._expanded:
            self.input.setFocus()
            return
        self._expanded = True
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(self._expanded_rect())
        self._anim.start()
        self.input.setFocus()
        if not self._app_filter_on:
            QApplication.instance().installEventFilter(self)
            self._app_filter_on = True

    def collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        if self._app_filter_on:
            QApplication.instance().removeEventFilter(self)
            self._app_filter_on = False
        self.dropdown.hide()
        self.input.blockSignals(True)
        self.input.clear()
        self.input.blockSignals(False)
        self.input.clearFocus()
        self._anim.stop()
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(self._collapsed_rect())
        self._anim.start()

    def toggle(self):
        self.collapse() if self._expanded else self.expand()

    def _on_anim_finished(self):
        if self._expanded:
            self._filtered = []
            self._do_filter()
        else:
            self.setGeometry(self._collapsed_rect())

    # ── Dropdown ────────────────────────────────────────────────
    def _place_dropdown(self):
        top_left = self.mapTo(self._host, QPoint(0, self.height() + 6))
        rows = min(self.list.count(), 8)
        h = 16 + rows * 40 + 26 if rows else 70
        self.dropdown.setGeometry(top_left.x(), top_left.y(), self.EXPANDED_W, h)
        self.dropdown.raise_()

    # ── Search logic ────────────────────────────────────────────
    def _on_text_changed(self, _t: str):
        self._debounce.start()

    def _do_filter(self):
        if not self._expanded:
            return
        query = self.input.text().strip()
        if not query:
            self._filtered = self._commands[:12]
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
            self._filtered = [c for _, c in scored[:16]]
            ask = {"type": "ask", "label": f'Ask Aura: "{query}"', "query": query}
            if not self._filtered or " " in query:
                self._filtered.insert(0, ask)
            else:
                self._filtered.append(ask)
        self._populate()

    def _populate(self):
        self.list.clear()
        for cmd in self._filtered:
            label = cmd.get("label", "")
            t = cmd.get("type", "")
            prefix = {"navigate": "→", "action": "⚡", "agent": "🤖",
                      "campaign": "📋", "ask": "✨"}.get(t, "")
            item = QListWidgetItem(f"{prefix}   {label}" if prefix else label)
            item.setData(Qt.UserRole, cmd)
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)
        if self._expanded:
            self._place_dropdown()
            self.dropdown.show()
            self.dropdown.raise_()

    def _select(self, cmd: dict):
        if cmd:
            self.command_selected.emit(cmd)
        self.collapse()

    def _on_item_clicked(self, item: QListWidgetItem):
        self._select(item.data(Qt.UserRole))

    def _on_enter(self):
        current = self.list.currentItem()
        if current:
            self._select(current.data(Qt.UserRole))

    def _move_selection(self, delta: int):
        new = self.list.currentRow() + delta
        if 0 <= new < self.list.count():
            self.list.setCurrentRow(new)

    # ── Point-in-search test for click-outside ─────────────────
    def _point_in_search(self, gp: QPoint) -> bool:
        for w in (self.input, self.dropdown):
            if w.isVisible():
                tl = w.mapToGlobal(QPoint(0, 0))
                if QRect(tl, w.size()).contains(gp):
                    return True
        return False

    # ── Events ──────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        et = event.type()
        if obj is self._ribbon:
            if et == QEvent.Resize:
                self.reposition()
            return False
        if obj is self.input:
            if et == QEvent.FocusIn:
                self.expand()
            elif et == QEvent.KeyPress:
                k = event.key()
                if k == Qt.Key_Escape:
                    self.collapse()
                    return True
                if k == Qt.Key_Down:
                    self._move_selection(1)
                    return True
                if k == Qt.Key_Up:
                    self._move_selection(-1)
                    return True
            return False
        # Application-level while expanded: outside-click + Escape collapse.
        if self._expanded:
            if et == QEvent.MouseButtonPress:
                try:
                    gp = event.globalPosition().toPoint()
                except AttributeError:
                    gp = event.globalPos()
                if not self._point_in_search(gp):
                    self.collapse()
            elif et == QEvent.KeyPress and event.key() == Qt.Key_Escape:
                self.collapse()
                return True
        return False
