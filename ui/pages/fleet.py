"""
Aura — Fleet Page (Multi-Agent Command Center)
Agent grid with popup detail dialog for viewing/editing agents.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QFrame, QScrollArea, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QComboBox, QSpinBox, QTextEdit,
    QSizePolicy, QTabWidget, QDialog,
)
from PySide6.QtCore import Qt, Signal, QSize

from ui.components.glass_card import GlassCard, StatCard
from ui.components.empty_state import EmptyState
from ui.icons import get_icon, get_pixmap


# ─── Agent Detail Dialog ───────────────────────────────────────────────────

class AgentDetailDialog(QDialog):
    """Popup dialog showing full agent info when an AgentCard is clicked."""

    boot_requested = Signal(int)          # agent_id
    shutdown_requested = Signal(int)      # agent_id
    edit_field = Signal(int, str, str)    # agent_id, field_name, new_value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agent Detail")
        self.setObjectName("agentDetailDialog")
        self.setMinimumSize(520, 600)
        self.resize(560, 720)
        self._agent_id = None
        self._edit_widgets = {}   # field_name -> (label, text_edit, save_btn)
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header (fixed, not scrollable) ──────────────────────
        header_frame = QFrame()
        header_frame.setObjectName("agentDetailHeader")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(24, 20, 24, 16)
        header_layout.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        self._emoji_label = QLabel("")
        self._emoji_label.setObjectName("agentDetailEmoji")
        self._emoji_label.setFixedSize(56, 56)
        self._emoji_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self._emoji_label)

        header_info = QVBoxLayout()
        header_info.setSpacing(4)

        self._name_label = QLabel("Agent Name")
        self._name_label.setObjectName("sectionHeader")
        header_info.addWidget(self._name_label)

        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)
        self._status_badge = QLabel("IDLE")
        self._status_badge.setObjectName("badgeInfo")
        badge_row.addWidget(self._status_badge)

        self._role_badge = QLabel("Worker")
        self._role_badge.setObjectName("badgeInfo")
        badge_row.addWidget(self._role_badge)

        self._tier_badge = QLabel("HAIKU")
        self._tier_badge.setObjectName("badgeInfo")
        badge_row.addWidget(self._tier_badge)

        badge_row.addStretch()
        header_info.addLayout(badge_row)
        top_row.addLayout(header_info, stretch=1)

        header_layout.addLayout(top_row)

        # Current task line
        self._task_label = QLabel("")
        self._task_label.setObjectName("mutedText")
        self._task_label.setWordWrap(True)
        header_layout.addWidget(self._task_label)

        outer.addWidget(header_frame)

        # ── Tabbed Content ──────────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setObjectName("agentTabs")
        self._tabs.setDocumentMode(True)
        self._tabs.tabBar().setObjectName("agentTabBar")

        # --- Tab 1: Persona ---
        self._persona_tab = self._build_persona_tab()
        self._tabs.addTab(self._persona_tab, "Persona")

        # --- Tab 2: Config & Skills ---
        self._config_tab = self._build_config_tab()
        self._tabs.addTab(self._config_tab, "Config")

        # --- Tab 3: Activity ---
        self._activity_tab = self._build_activity_tab()
        self._tabs.addTab(self._activity_tab, "Activity")

        outer.addWidget(self._tabs, stretch=1)

        # ── Controls (fixed bottom) ────────────────────────────
        ctrl_frame = QFrame()
        ctrl_frame.setObjectName("agentDetailFooter")
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setContentsMargins(24, 14, 24, 16)
        ctrl_layout.setSpacing(12)

        self._boot_btn = QPushButton("Boot Agent")
        self._boot_btn.setObjectName("primaryButton")
        self._boot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._boot_btn.clicked.connect(lambda: self.boot_requested.emit(self._agent_id))
        ctrl_layout.addWidget(self._boot_btn)

        self._shutdown_btn = QPushButton("Shutdown")
        self._shutdown_btn.setObjectName("dangerButton")
        self._shutdown_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._shutdown_btn.clicked.connect(lambda: self.shutdown_requested.emit(self._agent_id))
        ctrl_layout.addWidget(self._shutdown_btn)

        ctrl_layout.addStretch()

        # Stats summary
        self._stat_tasks = QLabel("Tasks: 0")
        self._stat_tasks.setObjectName("agentBodyText")
        ctrl_layout.addWidget(self._stat_tasks)

        self._stat_cost = QLabel("Cost: $0.0000")
        self._stat_cost.setObjectName("agentBodyText")
        ctrl_layout.addWidget(self._stat_cost)

        outer.addWidget(ctrl_frame)

    # ── Tab Builders ───────────────────────────────────────────────

    def _build_persona_tab(self) -> QScrollArea:
        """Persona tab: Soul, Mission, Playbook, Boundaries."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Soul
        soul_card = GlassCard()
        sl = soul_card.get_layout()
        sl.addWidget(self._card_header("Soul"))
        sl.addWidget(self._card_subtitle("Personality, values, and behavioral traits"))
        self._soul_display, self._soul_edit, self._soul_save = self._editable_field("soul", sl, height=160)
        layout.addWidget(soul_card)

        # Mission
        mission_card = GlassCard()
        ml = mission_card.get_layout()
        ml.addWidget(self._card_header("Mission"))
        ml.addWidget(self._card_subtitle("Objectives, KPIs, and success criteria"))
        self._mission_display, self._mission_edit, self._mission_save = self._editable_field("mission", ml, height=120)
        layout.addWidget(mission_card)

        # Playbook
        pb_card = GlassCard()
        pbl = pb_card.get_layout()
        pbl.addWidget(self._card_header("Playbook"))
        pbl.addWidget(self._card_subtitle("Step-by-step standard operating procedures"))
        self._playbook_display, self._playbook_edit, self._playbook_save = self._editable_field("playbook", pbl, height=200)
        layout.addWidget(pb_card)

        # Boundaries
        bound_card = GlassCard()
        bl = bound_card.get_layout()
        bl.addWidget(self._card_header("Boundaries"))
        bl.addWidget(self._card_subtitle("Hard limits and compliance requirements"))
        self._boundaries_display, self._boundaries_edit, self._boundaries_save = self._editable_field("boundaries", bl, height=140)
        layout.addWidget(bound_card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_config_tab(self) -> QScrollArea:
        """Config tab: Model tier, heartbeat, skills."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Configuration
        config_card = GlassCard()
        cl = config_card.get_layout()
        cl.addWidget(self._card_header("Model Configuration"))

        config_row = QHBoxLayout()
        config_row.setSpacing(16)

        tier_col = QVBoxLayout()
        tier_col.setSpacing(4)
        tier_lbl = QLabel("Model Tier")
        tier_lbl.setObjectName("formLabel")
        tier_col.addWidget(tier_lbl)
        self._tier_combo = QComboBox()
        self._tier_combo.addItems(["local", "ollama", "haiku", "sonnet"])
        self._tier_combo.setMinimumHeight(34)
        tier_col.addWidget(self._tier_combo)
        config_row.addLayout(tier_col)

        override_col = QVBoxLayout()
        override_col.setSpacing(4)
        override_lbl = QLabel("Model Override")
        override_lbl.setObjectName("formLabel")
        override_col.addWidget(override_lbl)
        self._override_combo = QComboBox()
        self._override_combo.setEditable(True)
        from core.model_fleet import all_models
        self._override_combo.addItem("(tier default)")
        self._override_combo.addItems(all_models())
        self._override_combo.setMinimumHeight(34)
        self._override_combo.setMinimumWidth(230)
        self._override_combo.setToolTip(
            "Pin this agent to one exact model (verified before saving), "
            "or type any custom model ID"
        )
        override_col.addWidget(self._override_combo)
        config_row.addLayout(override_col)

        hb_col = QVBoxLayout()
        hb_col.setSpacing(4)
        hb_lbl = QLabel("Heartbeat (min)")
        hb_lbl.setObjectName("formLabel")
        hb_col.addWidget(hb_lbl)
        self._hb_spin = QSpinBox()
        self._hb_spin.setRange(1, 120)
        self._hb_spin.setValue(30)
        self._hb_spin.setMinimumHeight(34)
        hb_col.addWidget(self._hb_spin)
        config_row.addLayout(hb_col)

        config_row.addStretch()

        save_config_btn = QPushButton("Save Config")
        save_config_btn.setObjectName("primaryButton")
        save_config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_config_btn.setMinimumHeight(34)
        save_config_btn.clicked.connect(self._on_save_config)
        config_row.addWidget(save_config_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        cl.addLayout(config_row)
        layout.addWidget(config_card)

        # Skills
        skills_card = GlassCard()
        skl = skills_card.get_layout()
        skl.addWidget(self._card_header("Skills"))
        skl.addWidget(self._card_subtitle("Skills used in recent tasks"))

        self._skills_label = QLabel("No skills associated yet.")
        self._skills_label.setObjectName("agentBodyText")
        self._skills_label.setWordWrap(True)
        skl.addWidget(self._skills_label)
        layout.addWidget(skills_card)

        # Memory
        mem_card = GlassCard()
        meml = mem_card.get_layout()
        meml.addWidget(self._card_header("Memory"))

        meml.addWidget(self._card_subtitle("Today's working notes"))
        self._memory_today_label = QLabel("No notes today.")
        self._memory_today_label.setObjectName("agentBodyText")
        self._memory_today_label.setWordWrap(True)
        self._memory_today_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meml.addWidget(self._memory_today_label)

        # Visual divider
        mem_divider = QFrame()
        mem_divider.setObjectName("separator")
        mem_divider.setFixedHeight(1)
        meml.addSpacing(8)
        meml.addWidget(mem_divider)
        meml.addSpacing(8)

        meml.addWidget(self._card_subtitle("Long-term memory"))
        self._memory_lt_label = QLabel("No long-term memory.")
        self._memory_lt_label.setObjectName("agentBodyText")
        self._memory_lt_label.setWordWrap(True)
        self._memory_lt_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meml.addWidget(self._memory_lt_label)
        layout.addWidget(mem_card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_activity_tab(self) -> QScrollArea:
        """Activity tab: Recent tasks table."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        tasks_card = GlassCard()
        tl = tasks_card.get_layout()
        tl.addWidget(self._card_header("Recent Tasks"))

        self._tasks_table = QTableWidget()
        self._tasks_table.setColumnCount(5)
        self._tasks_table.setHorizontalHeaderLabels(["Type", "Status", "Skill", "Cost", "Time"])
        self._tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tasks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tasks_table.setMinimumHeight(300)
        tl.addWidget(self._tasks_table)
        layout.addWidget(tasks_card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _card_header(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("cardHeader")
        return lbl

    @staticmethod
    def _card_subtitle(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("mutedText")
        return lbl

    def _editable_field(self, field_name: str, parent_layout, height: int = 140):
        """Create a display label + hidden text editor + edit/save buttons."""
        display = QLabel("")
        display.setObjectName("agentBodyText")
        display.setWordWrap(True)
        display.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        parent_layout.addWidget(display)

        editor = QTextEdit()
        editor.setObjectName("chatInput")
        editor.setMinimumHeight(height)
        editor.setMaximumHeight(height + 80)
        editor.hide()
        parent_layout.addWidget(editor)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("secondaryButton")
        edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        edit_btn.setFixedHeight(30)
        btn_row.addWidget(edit_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setFixedHeight(30)
        save_btn.hide()
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryButton")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFixedHeight(30)
        cancel_btn.hide()
        btn_row.addWidget(cancel_btn)

        parent_layout.addLayout(btn_row)

        # Wire edit mode toggle
        def enter_edit():
            editor.setPlainText(display.text())
            display.hide()
            editor.show()
            edit_btn.hide()
            save_btn.show()
            cancel_btn.show()

        def exit_edit():
            editor.hide()
            display.show()
            edit_btn.show()
            save_btn.hide()
            cancel_btn.hide()

        def do_save():
            new_val = editor.toPlainText().strip()
            if self._agent_id and new_val != display.text():
                self.edit_field.emit(self._agent_id, field_name, new_val)
                display.setText(new_val)
            exit_edit()

        edit_btn.clicked.connect(enter_edit)
        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(exit_edit)

        self._edit_widgets[field_name] = (display, editor, save_btn)
        return display, editor, save_btn

    def _on_save_config(self):
        if not self._agent_id:
            return
        self.edit_field.emit(self._agent_id, "model_tier", self._tier_combo.currentText())
        self.edit_field.emit(
            self._agent_id, "model_override", self._override_combo.currentText()
        )
        self.edit_field.emit(
            self._agent_id, "heartbeat_interval_mins", str(self._hb_spin.value())
        )

    # ── Public API ─────────────────────────────────────────────

    def load_agent(self, data: dict):
        """Populate the dialog with full agent status data."""
        if not data.get("success"):
            return

        info = data.get("data", {})
        self._agent_id = info.get("id")

        # Header
        self._emoji_label.setText(info.get("identity_emoji", ""))
        self._name_label.setText(info.get("name", "Unknown"))
        self.setWindowTitle(f"{info.get('identity_emoji', '')} {info.get('name', 'Agent')}")

        status = info.get("status", "idle")
        self._status_badge.setText(status.upper())
        badge_map = {
            "idle": "badgeInfo", "running": "badgeSuccess",
            "error": "badgeDanger", "paused": "badgeWarning",
        }
        self._status_badge.setObjectName(badge_map.get(status, "badgeInfo"))
        self._status_badge.style().unpolish(self._status_badge)
        self._status_badge.style().polish(self._status_badge)

        role = info.get("role", "worker")
        self._role_badge.setText(role.upper())
        role_badge_map = {
            "orchestrator": "badgeWarning", "worker": "badgeInfo",
            "canary": "badgeSuccess", "observer": "badgeDanger",
        }
        self._role_badge.setObjectName(role_badge_map.get(role, "badgeInfo"))
        self._role_badge.style().unpolish(self._role_badge)
        self._role_badge.style().polish(self._role_badge)

        tier = info.get("model_tier", "haiku")
        tier_colors = {
            "local": "badgeSuccess", "ollama": "badgeInfo",
            "haiku": "badgeWarning", "sonnet": "badgeDanger",
        }
        self._tier_badge.setText(tier.upper())
        self._tier_badge.setObjectName(tier_colors.get(tier, "badgeInfo"))
        self._tier_badge.style().unpolish(self._tier_badge)
        self._tier_badge.style().polish(self._tier_badge)

        current = info.get("current_task")
        self._task_label.setText(f"Current: {current}" if current else "Currently idle")

        # Persona tab
        self._soul_display.setText(info.get("soul", "") or "No soul defined.")
        self._mission_display.setText(info.get("mission", "") or "No mission defined.")
        self._playbook_display.setText(info.get("playbook", "") or "No playbook defined.")
        self._boundaries_display.setText(info.get("boundaries", "") or "No boundaries defined.")

        # Config tab
        idx = self._tier_combo.findText(tier)
        if idx >= 0:
            self._tier_combo.setCurrentIndex(idx)
        self._hb_spin.setValue(info.get("heartbeat_interval_mins", 30))
        self._override_combo.setEditText(
            info.get("model_override") or "(tier default)"
        )

        # Skills
        skills = info.get("skills", [])
        if skills:
            skill_chips = []
            for s in skills:
                name = s.get("name", "")
                if name:
                    skill_chips.append(name)
            self._skills_label.setText(" · ".join(skill_chips) if skill_chips else "No skills associated yet.")
        else:
            # Check recent tasks for skill names
            recent_skills = set()
            for t in info.get("recent_tasks", []):
                sn = t.get("skill_name", "")
                if sn:
                    recent_skills.add(sn)
            if recent_skills:
                self._skills_label.setText("Recent: " + " · ".join(sorted(recent_skills)))
            else:
                self._skills_label.setText("No skills associated yet.")

        # Memory
        mem_today = info.get("memory_today") or "No notes today."
        self._memory_today_label.setText(mem_today)
        mem_lt = info.get("long_term_memory") or "No long-term memory."
        self._memory_lt_label.setText(mem_lt)

        # Recent tasks
        tasks = info.get("recent_tasks", [])
        self._tasks_table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            self._tasks_table.setItem(i, 0, QTableWidgetItem(t.get("task_type", "")))
            self._tasks_table.setItem(i, 1, QTableWidgetItem(t.get("status", "")))
            self._tasks_table.setItem(i, 2, QTableWidgetItem(t.get("skill_name", "")))
            self._tasks_table.setItem(i, 3, QTableWidgetItem(f"${t.get('cost_usd', 0):.4f}"))
            ts = t.get("completed_at") or t.get("started_at") or ""
            self._tasks_table.setItem(i, 4, QTableWidgetItem(str(ts)[:16] if ts else ""))

        # Stats
        self._stat_tasks.setText(f"Tasks: {info.get('tasks_completed', 0)}")
        self._stat_cost.setText(f"Cost: ${info.get('total_cost_usd', 0):.4f}")

        # Switch to persona tab
        self._tabs.setCurrentIndex(0)


# ─── Agent Card ────────────────────────────────────────────────────────────

class AgentCard(QFrame):
    """Compact card for a single agent in the fleet grid."""

    clicked = Signal(int)  # agent_id

    def __init__(self, agent_data: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("glassCard")
        self.setMinimumHeight(110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._agent_id = agent_data.get("id", 0)
        self._selected = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Top row: emoji + name + status badge
        top = QHBoxLayout()
        top.setSpacing(10)

        emoji = QLabel(agent_data.get("identity_emoji", ""))
        emoji.setObjectName("agentCardEmoji")
        emoji.setFixedWidth(36)
        top.addWidget(emoji)

        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        name = QLabel(agent_data.get("name", "Unknown"))
        name.setObjectName("cardHeader")
        name_col.addWidget(name)

        role = QLabel(agent_data.get("role", "").capitalize())
        role.setObjectName("mutedText")
        name_col.addWidget(role)

        top.addLayout(name_col, stretch=1)

        status = agent_data.get("status", "idle")
        badge = QLabel(status.upper())
        badge_name = {
            "idle": "badgeInfo",
            "running": "badgeSuccess",
            "error": "badgeDanger",
            "paused": "badgeWarning",
        }.get(status, "badgeInfo")
        badge.setObjectName(badge_name)
        top.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        layout.addLayout(top)

        # Bottom row: tier + tasks + cost
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        tier = agent_data.get("model_tier", "haiku")
        tier_label = QLabel(tier.upper())
        tier_label.setObjectName("mutedText")
        bottom.addWidget(tier_label)

        tasks = QLabel(f"{agent_data.get('tasks_completed', 0)} tasks")
        tasks.setObjectName("mutedText")
        bottom.addWidget(tasks)

        cost = agent_data.get("total_cost_usd", 0.0)
        cost_label = QLabel(f"${cost:.4f}")
        cost_label.setObjectName("mutedText")
        bottom.addWidget(cost_label)

        # Current task indicator
        current = agent_data.get("current_task")
        if current:
            task_indicator = QLabel()
            task_indicator.setPixmap(get_pixmap("current_task", "dark", "accent", 14))
            task_indicator.setFixedSize(18, 18)
            task_indicator.setToolTip(current)
            bottom.addWidget(task_indicator)

        bottom.addStretch()
        layout.addLayout(bottom)

    def set_selected(self, selected: bool):
        """Toggle selected visual state."""
        self._selected = selected
        if selected:
            self.setObjectName("agentCardSelected")
        else:
            self.setObjectName("glassCard")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self._agent_id)
        super().mousePressEvent(event)


# ─── Fleet Page ────────────────────────────────────────────────────────────

class FleetPage(QWidget):
    """Fleet command center — agent grid with popup detail dialog."""

    boot_fleet_requested = Signal()
    shutdown_fleet_requested = Signal()
    boot_agent_requested = Signal(int)
    shutdown_agent_requested = Signal(int)
    dispatch_requested = Signal(str, dict)  # task_type, payload
    agent_selected = Signal(int)
    health_check_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._agent_cards = {}  # agent_id -> AgentCard
        self._selected_agent_id = None
        self._setup_ui()

        # Detail dialog (created once, reused)
        self.detail_dialog = AgentDetailDialog(self)

    def _setup_ui(self):
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scrollable fleet content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(0)
        scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)

        content = QWidget()
        content.setObjectName("centralWidget")
        content.setMinimumWidth(0)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # ─── Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        title = QLabel("Fleet Command")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)

        subtitle = QLabel("Multi-agent system overview and controls")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)

        header.addLayout(header_text, stretch=1)

        self.boot_btn = QPushButton("Boot Fleet")
        self.boot_btn.setObjectName("primaryButton")
        self.boot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boot_btn.clicked.connect(self.boot_fleet_requested.emit)
        header.addWidget(self.boot_btn)

        self.shutdown_btn = QPushButton("Shutdown")
        self.shutdown_btn.setObjectName("dangerButton")
        self.shutdown_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.shutdown_btn.clicked.connect(self.shutdown_fleet_requested.emit)
        header.addWidget(self.shutdown_btn)

        self.health_btn = QPushButton("Health Check")
        self.health_btn.setObjectName("secondaryButton")
        self.health_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.health_btn.clicked.connect(self.health_check_requested.emit)
        header.addWidget(self.health_btn)

        layout.addLayout(header)

        # ─── Fleet Stats ─────────────────────────────────────────
        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.health_card = StatCard("100%", "FLEET HEALTH", accent="green", variant="solid")
        stats_grid.addWidget(self.health_card, 0, 0)

        self.agents_card = StatCard("0", "TOTAL AGENTS", accent="blue")
        stats_grid.addWidget(self.agents_card, 0, 1)

        self.running_card = StatCard("0", "RUNNING", accent="purple")
        stats_grid.addWidget(self.running_card, 0, 2)

        self.tasks_card = StatCard("0", "TASKS TODAY", accent="cyan")
        stats_grid.addWidget(self.tasks_card, 0, 3)

        self.cost_card = StatCard("$0.00", "COST TODAY", accent="orange")
        stats_grid.addWidget(self.cost_card, 1, 0)

        self.errors_card = StatCard("0", "ERRORS", accent="red")
        stats_grid.addWidget(self.errors_card, 1, 1)

        self.idle_card = StatCard("0", "IDLE", accent="blue")
        stats_grid.addWidget(self.idle_card, 1, 2)

        self.queued_card = StatCard("0", "QUEUED", accent="pink")
        stats_grid.addWidget(self.queued_card, 1, 3)

        layout.addLayout(stats_grid)

        # ─── Agent Grid ──────────────────────────────────────────
        agents_header_row = QHBoxLayout()
        agents_header_row.setSpacing(8)
        agents_header = QLabel("Agent Fleet")
        agents_header.setObjectName("cardHeader")
        agents_header_row.addWidget(agents_header)

        self._agent_count_label = QLabel("")
        self._agent_count_label.setObjectName("mutedText")
        agents_header_row.addWidget(self._agent_count_label)
        agents_header_row.addStretch()
        layout.addLayout(agents_header_row)

        self.agent_grid = QGridLayout()
        self.agent_grid.setSpacing(12)
        self._agent_grid_widget = QWidget()
        self._agent_grid_widget.setLayout(self.agent_grid)
        layout.addWidget(self._agent_grid_widget)

        # Empty state (shown when no agents)
        self.empty_state = EmptyState(
            icon_key="empty_fleet",
            title="No agents yet",
            subtitle="Boot the fleet to activate your AI agents.",
            action_text="Boot Fleet",
        )
        self.empty_state.action_clicked.connect(self.boot_fleet_requested.emit)
        layout.addWidget(self.empty_state)

        # ─── Observer Panel ───────────────────────────────────────
        observer_card = GlassCard()
        obs_layout = observer_card.get_layout()

        obs_header = QLabel("Observer Report")
        obs_header.setObjectName("cardHeader")
        obs_layout.addWidget(obs_header)

        self.observer_text = QLabel("Run a health check to see the observer report.")
        self.observer_text.setObjectName("mutedText")
        self.observer_text.setWordWrap(True)
        obs_layout.addWidget(self.observer_text)

        self.anomaly_label = QLabel("")
        self.anomaly_label.setObjectName("warningText")
        self.anomaly_label.setWordWrap(True)
        self.anomaly_label.hide()
        obs_layout.addWidget(self.anomaly_label)

        layout.addWidget(observer_card)

        layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── Detail dialog control ──────────────────────────────────────────

    def show_agent_detail(self, data: dict):
        """Called when agent status data arrives — populate and show dialog."""
        self.detail_dialog.load_agent(data)
        self.detail_dialog.show()
        self.detail_dialog.raise_()
        self.detail_dialog.activateWindow()

    def _close_detail(self):
        """Hide the detail dialog and clear selection."""
        self.detail_dialog.hide()
        self._clear_selection()

    def _clear_selection(self):
        """Deselect all agent cards."""
        if self._selected_agent_id and self._selected_agent_id in self._agent_cards:
            self._agent_cards[self._selected_agent_id].set_selected(False)
        self._selected_agent_id = None

    def _on_agent_card_clicked(self, agent_id: int):
        """Handle agent card click — select card and emit signal."""
        # Deselect previous
        if self._selected_agent_id and self._selected_agent_id in self._agent_cards:
            self._agent_cards[self._selected_agent_id].set_selected(False)

        # Select new
        self._selected_agent_id = agent_id
        if agent_id in self._agent_cards:
            self._agent_cards[agent_id].set_selected(True)

        self.agent_selected.emit(agent_id)

    # ─── Data update methods ──────────────────────────────────────────

    def update_fleet_status(self, data: dict):
        """Update the fleet stat cards and agent grid from fleet status data."""
        if not data.get("success"):
            return

        info = data.get("data", {})
        self.health_card.set_value(f"{info.get('health_pct', 0)}%")
        self.agents_card.set_value(str(info.get("total_agents", 0)))
        self.running_card.set_value(str(info.get("running", 0)))
        self.tasks_card.set_value(str(info.get("total_tasks_today", 0)))
        self.cost_card.set_value(f"${info.get('total_cost_today', 0):.2f}")
        self.errors_card.set_value(str(info.get("error", 0)))
        self.idle_card.set_value(str(info.get("idle", 0)))
        self.queued_card.set_value(str(info.get("paused", 0)))

        # Rebuild agent grid
        agents = info.get("agents", [])
        self._rebuild_agent_grid(agents)

    def _rebuild_agent_grid(self, agents: list):
        """Clear and rebuild the agent card grid."""
        # Clear existing
        self._agent_cards.clear()
        while self.agent_grid.count():
            item = self.agent_grid.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        if not agents:
            self.empty_state.show()
            self._agent_grid_widget.hide()
            self._agent_count_label.setText("")
            return

        self.empty_state.hide()
        self._agent_grid_widget.show()
        self._agent_count_label.setText(f"({len(agents)})")

        cols = 4
        for i, agent in enumerate(agents):
            card = AgentCard(agent)
            card.clicked.connect(self._on_agent_card_clicked)
            agent_id = agent.get("id", 0)
            self._agent_cards[agent_id] = card

            # Restore selection state
            if agent_id == self._selected_agent_id:
                card.set_selected(True)

            self.agent_grid.addWidget(card, i // cols, i % cols)

    def update_health_check(self, data: dict):
        """Update the observer panel with health check results."""
        if not data.get("success"):
            return

        info = data.get("data", {})
        healthy = info.get("healthy_count", 0)
        warning = info.get("warning_count", 0)
        critical = info.get("critical_count", 0)
        total = info.get("total", 0)

        self.observer_text.setText(
            f"Fleet Health: {info.get('health_pct', 0)}% — "
            f"{healthy} healthy, {warning} warning, {critical} critical "
            f"(of {total} agents)"
        )

        # Show critical/warning details
        issues = []
        for a in info.get("critical", []):
            issues.append(f"CRITICAL: {a['identity_emoji']} {a['name']} — {', '.join(a['issues'])}")
        for a in info.get("warning", []):
            issues.append(f"WARNING: {a['identity_emoji']} {a['name']} — {', '.join(a['issues'])}")

        if issues:
            self.anomaly_label.setText("\n".join(issues))
            self.anomaly_label.show()
        else:
            self.anomaly_label.hide()

    def set_fleet_running(self, running: bool):
        """Toggle button states based on fleet status."""
        self.boot_btn.setEnabled(not running)
        self.shutdown_btn.setEnabled(running)

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass
