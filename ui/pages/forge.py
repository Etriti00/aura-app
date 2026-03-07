"""
Aura — Forge Page (Enhanced with Full Skill Template)
Skill list, 3-tab editor (Identity, Behavior, Schema & Config),
import/export, built-in protection.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QListWidget, QListWidgetItem, QComboBox,
    QFileDialog, QSplitter, QScrollArea, QFrame, QTabWidget,
    QDoubleSpinBox, QSpinBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QFont

from ui.components.glass_card import GlassCard
from ui.components.modern_button import ModernButton
from ui.components.toast_notification import show_toast
from ui.icons import get_icon, get_pixmap

SKILL_CATEGORIES = [
    "general", "prospecting", "qualification", "outreach", "analysis",
    "enrichment", "research", "conversation", "management",
]

TONE_OPTIONS = [
    "professional", "casual", "friendly", "formal", "witty",
    "empathetic", "authoritative", "conversational", "confident",
    "direct", "persistent", "analytical", "precise", "strategic",
]

TIER_OPTIONS = ["haiku", "sonnet", "opus"]


class ForgePage(QWidget):
    """Skill Forge — create and manage AI skill templates for the agent fleet."""

    save_requested = Signal(int, object)       # skill_id, skill_data dict (id=0 for new)
    delete_requested = Signal(int)             # skill_id
    import_requested = Signal(str)             # file_path
    export_requested = Signal(int, str)        # skill_id, file_path
    rag_import_requested = Signal(str)         # file_path for RAG CSV import
    rag_clear_requested = Signal()             # clear all RAG memory

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_skill_id = None
        self._is_builtin = False
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("centralWidget")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("Skill Forge")
        title.setObjectName("sectionHeader")
        header_text.addWidget(title)
        subtitle = QLabel("Create and manage AI skill templates for the agent fleet")
        subtitle.setObjectName("sectionSubheader")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, stretch=1)

        # Import/Export buttons
        import_btn = ModernButton("Import", "secondary")
        import_btn.setFixedHeight(38)
        import_btn.clicked.connect(self._on_import)
        header.addWidget(import_btn)

        export_btn = ModernButton("Export", "secondary")
        export_btn.setFixedHeight(38)
        export_btn.clicked.connect(self._on_export)
        header.addWidget(export_btn)

        layout.addLayout(header)

        # Main content: skill list | editor
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ─── Left: Skill list ───────────────────────────────────────
        list_card = GlassCard()
        list_layout = list_card.get_layout()

        list_header = QHBoxLayout()
        list_label = QLabel("Skills")
        list_label.setObjectName("cardHeader")
        list_header.addWidget(list_label, stretch=1)

        new_btn = ModernButton("+ New", "primary")
        new_btn.setFixedHeight(36)
        new_btn.clicked.connect(self._on_new_skill)
        list_header.addWidget(new_btn)
        list_layout.addLayout(list_header)

        self.skill_list = QListWidget()
        self.skill_list.setObjectName("skillList")
        self.skill_list.currentRowChanged.connect(self._on_skill_selected)
        list_layout.addWidget(self.skill_list)

        splitter.addWidget(list_card)

        # ─── Right: Tabbed Editor ───────────────────────────────────
        editor_card = GlassCard()
        editor_layout = editor_card.get_layout()

        self.editor_header = QLabel("Select or create a skill")
        self.editor_header.setObjectName("cardHeader")
        editor_layout.addWidget(self.editor_header)

        # Tab widget
        self.editor_tabs = QTabWidget()
        self.editor_tabs.setObjectName("forgeEditorTabs")
        self.editor_tabs.setDocumentMode(True)

        # ── Tab 1: Identity ──
        identity_tab = QWidget()
        identity_layout = QVBoxLayout(identity_tab)
        identity_layout.setContentsMargins(0, 12, 0, 0)
        identity_layout.setSpacing(12)

        # Name
        identity_layout.addWidget(self._make_label("Skill Name"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., The Closer")
        identity_layout.addWidget(self.name_input)

        # Description
        identity_layout.addWidget(self._make_label("Description"))
        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Brief summary of what this skill does (1-2 sentences)"
        )
        self.description_input.setMaximumHeight(80)
        identity_layout.addWidget(self.description_input)

        # Category + Tone row
        cat_tone_row = QHBoxLayout()
        cat_group = QVBoxLayout()
        cat_group.addWidget(self._make_label("Category"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(SKILL_CATEGORIES)
        cat_group.addWidget(self.category_combo)
        cat_tone_row.addLayout(cat_group)

        tone_group = QVBoxLayout()
        tone_group.addWidget(self._make_label("Tone"))
        self.tone_combo = QComboBox()
        self.tone_combo.addItems(TONE_OPTIONS)
        tone_group.addWidget(self.tone_combo)
        cat_tone_row.addLayout(tone_group)
        identity_layout.addLayout(cat_tone_row)

        # Version + Tags row
        ver_tag_row = QHBoxLayout()
        ver_group = QVBoxLayout()
        ver_group.addWidget(self._make_label("Version"))
        self.version_input = QLineEdit()
        self.version_input.setPlaceholderText("1.0")
        self.version_input.setMaximumWidth(100)
        ver_group.addWidget(self.version_input)
        ver_tag_row.addLayout(ver_group)

        tag_group = QVBoxLayout()
        tag_group.addWidget(self._make_label("Tags (comma-separated)"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("email, sales, cold-outreach, b2b")
        tag_group.addWidget(self.tags_input)
        ver_tag_row.addLayout(tag_group, stretch=1)
        identity_layout.addLayout(ver_tag_row)

        identity_layout.addStretch()
        self.editor_tabs.addTab(identity_tab, "Identity")

        # ── Tab 2: Behavior ──
        behavior_tab = QWidget()
        behavior_layout = QVBoxLayout(behavior_tab)
        behavior_layout.setContentsMargins(0, 12, 0, 0)
        behavior_layout.setSpacing(12)

        # System Prompt
        behavior_layout.addWidget(self._make_label("System Prompt"))
        self.prompt_editor = QTextEdit()
        self.prompt_editor.setPlaceholderText(
            "Define the AI persona's behavior, style, and approach.\n\n"
            "Example:\nYou are a confident, results-driven sales professional who writes "
            "emails that convert. Your approach: lead with a specific observation..."
        )
        behavior_layout.addWidget(self.prompt_editor, stretch=2)

        # Instructions
        behavior_layout.addWidget(self._make_label("Instructions (step-by-step)"))
        self.instructions_editor = QTextEdit()
        self.instructions_editor.setPlaceholderText(
            "Step-by-step instructions the agent follows:\n\n"
            "1. RECEIVE lead profile with business data\n"
            "2. IDENTIFY a specific observation about the prospect\n"
            "3. CRAFT a hook sentence referencing the observation\n"
            "4. ..."
        )
        behavior_layout.addWidget(self.instructions_editor, stretch=2)

        # Examples
        behavior_layout.addWidget(self._make_label("Examples (JSON array)"))
        self.examples_editor = QTextEdit()
        self.examples_editor.setObjectName("forgeJsonEditor")
        self.examples_editor.setPlaceholderText(
            '[{"input": "Lead: Bella\'s Bakery, Sarah Chen", '
            '"output": "Subject: Quick question about Bella\'s..."}]'
        )
        mono_font = QFont("Consolas", 9)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.examples_editor.setFont(mono_font)
        self.examples_editor.setMaximumHeight(120)
        behavior_layout.addWidget(self.examples_editor)

        self.editor_tabs.addTab(behavior_tab, "Behavior")

        # ── Tab 3: Schema & Config ──
        schema_tab = QWidget()
        schema_layout = QVBoxLayout(schema_tab)
        schema_layout.setContentsMargins(0, 12, 0, 0)
        schema_layout.setSpacing(12)

        # Capabilities
        schema_layout.addWidget(self._make_label("Capabilities (JSON list)"))
        self.capabilities_editor = QTextEdit()
        self.capabilities_editor.setObjectName("forgeJsonEditor")
        self.capabilities_editor.setPlaceholderText(
            '["generate_email", "personalize_message", "roi_language"]'
        )
        self.capabilities_editor.setFont(mono_font)
        self.capabilities_editor.setMaximumHeight(80)
        schema_layout.addWidget(self.capabilities_editor)

        # Input Schema
        schema_layout.addWidget(self._make_label("Input Schema (JSON)"))
        self.input_schema_editor = QTextEdit()
        self.input_schema_editor.setObjectName("forgeJsonEditor")
        self.input_schema_editor.setPlaceholderText(
            '{"lead_profile": {"type": "object", "fields": ["business_name", "contact_name"]}}'
        )
        self.input_schema_editor.setFont(mono_font)
        self.input_schema_editor.setMaximumHeight(100)
        schema_layout.addWidget(self.input_schema_editor)

        # Output Schema
        schema_layout.addWidget(self._make_label("Output Schema (JSON)"))
        self.output_schema_editor = QTextEdit()
        self.output_schema_editor.setObjectName("forgeJsonEditor")
        self.output_schema_editor.setPlaceholderText(
            '{"subject_line": "string", "email_body": "string"}'
        )
        self.output_schema_editor.setFont(mono_font)
        self.output_schema_editor.setMaximumHeight(100)
        schema_layout.addWidget(self.output_schema_editor)

        # Config row: Tier + Temperature + Max Tokens
        config_row = QHBoxLayout()

        tier_group = QVBoxLayout()
        tier_group.addWidget(self._make_label("Preferred Tier"))
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(TIER_OPTIONS)
        tier_group.addWidget(self.tier_combo)
        config_row.addLayout(tier_group)

        temp_group = QVBoxLayout()
        temp_group.addWidget(self._make_label("Temperature"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        temp_group.addWidget(self.temperature_spin)
        config_row.addLayout(temp_group)

        tokens_group = QVBoxLayout()
        tokens_group.addWidget(self._make_label("Max Tokens"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 4096)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(1024)
        tokens_group.addWidget(self.max_tokens_spin)
        config_row.addLayout(tokens_group)

        schema_layout.addLayout(config_row)
        schema_layout.addStretch()

        self.editor_tabs.addTab(schema_tab, "Schema && Config")

        editor_layout.addWidget(self.editor_tabs, stretch=1)

        # Builtin warning with icon
        self.builtin_warning = QFrame()
        self.builtin_warning.setObjectName("warningText")
        self.builtin_warning.setVisible(False)
        warn_layout = QHBoxLayout(self.builtin_warning)
        warn_layout.setContentsMargins(0, 0, 0, 0)
        warn_layout.setSpacing(6)
        warn_icon = QLabel()
        warn_icon.setPixmap(get_pixmap("warning", "dark", "warning", 14))
        warn_icon.setFixedSize(18, 18)
        warn_layout.addWidget(warn_icon)
        warn_text = QLabel("Built-in skills are read-only")
        warn_text.setObjectName("warningText")
        warn_layout.addWidget(warn_text)
        warn_layout.addStretch()
        editor_layout.addWidget(self.builtin_warning)

        # Action buttons
        btn_row = QHBoxLayout()
        self.save_btn = ModernButton("Save Skill", "primary")
        self.save_btn.setFixedHeight(38)
        self.save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self.save_btn)

        self.delete_btn = ModernButton("Delete", "danger")
        self.delete_btn.setFixedHeight(38)
        self.delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self.delete_btn)
        editor_layout.addLayout(btn_row)

        splitter.addWidget(editor_card)
        splitter.setSizes([300, 500])

        splitter.setMinimumHeight(550)
        layout.addWidget(splitter)

        # ─── A/B Testing Stats Card ────────────────────────────────────
        ab_card = GlassCard()
        ab_layout = ab_card.get_layout()

        ab_header_row = QHBoxLayout()
        ab_h_icon = QLabel()
        ab_h_icon.setPixmap(get_pixmap("ab_test", "dark", "accent", 16))
        ab_h_icon.setFixedSize(20, 20)
        ab_header = QLabel("A/B Testing Performance")
        ab_header.setObjectName("cardHeader")
        ab_header_row.addWidget(ab_h_icon)
        ab_header_row.addWidget(ab_header, stretch=1)
        ab_layout.addLayout(ab_header_row)

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
        self.ab_table = QTableWidget()
        self.ab_table.setColumnCount(5)
        self.ab_table.setHorizontalHeaderLabels(["Variant", "Sends", "Opens", "Replies", "Win Rate"])
        self.ab_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ab_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ab_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ab_table.setMaximumHeight(120)
        self.ab_table.verticalHeader().setVisible(False)
        self.ab_table.setShowGrid(False)
        ab_layout.addWidget(self.ab_table)

        ab_note = QLabel("Stats update when A/B testing is enabled in Settings")
        ab_note.setObjectName("mutedText")
        ab_layout.addWidget(ab_note)

        layout.addWidget(ab_card)

        # ─── RAG Memory Card ────────────────────────────────────────
        rag_card = GlassCard()
        rag_layout = rag_card.get_layout()

        rag_header = QHBoxLayout()
        rag_title = QLabel("RAG Memory")
        rag_title.setObjectName("cardHeader")
        rag_header.addWidget(rag_title, stretch=1)

        self.rag_count_label = QLabel("0 emails stored · 0 replied")
        self.rag_count_label.setObjectName("mutedText")
        rag_header.addWidget(self.rag_count_label)
        rag_layout.addLayout(rag_header)

        rag_note = QLabel("Successful emails are stored automatically. Replied emails improve style matching.")
        rag_note.setObjectName("mutedText")
        rag_note.setWordWrap(True)
        rag_layout.addWidget(rag_note)

        rag_btn_row = QHBoxLayout()

        rag_import_btn = ModernButton("Import CSV", "secondary")
        rag_import_btn.setFixedHeight(36)
        rag_import_btn.clicked.connect(self._on_rag_import)
        rag_btn_row.addWidget(rag_import_btn)

        rag_clear_btn = ModernButton("Clear Memory", "danger")
        rag_clear_btn.setFixedHeight(36)
        rag_clear_btn.clicked.connect(self._on_rag_clear)
        rag_btn_row.addWidget(rag_clear_btn)

        rag_btn_row.addStretch()
        rag_layout.addLayout(rag_btn_row)

        layout.addWidget(rag_card)

        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _make_label(text: str) -> QLabel:
        """Create a form label with the standard objectName."""
        label = QLabel(text)
        label.setObjectName("formLabel")
        return label

    # ─── Public Methods (called by controller signals) ─────────────────

    def load_skills(self, skills: list):
        """Populate the skill list from controller data."""
        self.skill_list.clear()
        for skill in skills:
            icon_key = "skill_builtin" if skill["is_builtin"] else "skill_custom"
            item = QListWidgetItem(get_icon(icon_key, "dark"), skill['name'])
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self.skill_list.addItem(item)

    def clear_editor(self):
        """Reset the editor to empty state."""
        self._current_skill_id = None
        self._is_builtin = False
        self.editor_header.setText("New Skill")
        # Tab 1: Identity
        self.name_input.clear()
        self.description_input.clear()
        self.category_combo.setCurrentIndex(0)
        self.tone_combo.setCurrentIndex(0)
        self.version_input.setText("1.0")
        self.tags_input.clear()
        # Tab 2: Behavior
        self.prompt_editor.clear()
        self.instructions_editor.clear()
        self.examples_editor.clear()
        # Tab 3: Schema & Config
        self.capabilities_editor.clear()
        self.input_schema_editor.clear()
        self.output_schema_editor.clear()
        self.tier_combo.setCurrentIndex(0)
        self.temperature_spin.setValue(0.7)
        self.max_tokens_spin.setValue(1024)

        self.builtin_warning.setVisible(False)
        self._set_editor_editable(True)
        self.editor_tabs.setCurrentIndex(0)

    # ─── Internal ──────────────────────────────────────────────────────

    def _on_skill_selected(self, row: int):
        """Load selected skill into all editor tabs."""
        if row < 0:
            return
        item = self.skill_list.item(row)
        if not item:
            return

        skill = item.data(Qt.ItemDataRole.UserRole)
        self._current_skill_id = skill["id"]
        self._is_builtin = skill["is_builtin"]

        self.editor_header.setText(f"Editing: {skill['name']}")

        # Tab 1: Identity
        self.name_input.setText(skill.get("name", ""))
        self.description_input.setPlainText(skill.get("description", ""))
        self._set_combo(self.category_combo, skill.get("category", "general"))
        self._set_combo(self.tone_combo, skill.get("tone", "professional"))
        self.version_input.setText(skill.get("version", "1.0"))
        self.tags_input.setText(self._json_list_to_csv(skill.get("tags", "[]")))

        # Tab 2: Behavior
        self.prompt_editor.setPlainText(skill.get("system_prompt", ""))
        self.instructions_editor.setPlainText(skill.get("instructions", ""))
        self.examples_editor.setPlainText(self._format_json(skill.get("examples", "[]")))

        # Tab 3: Schema & Config
        self.capabilities_editor.setPlainText(self._format_json(skill.get("capabilities", "[]")))
        self.input_schema_editor.setPlainText(self._format_json(skill.get("input_schema", "{}")))
        self.output_schema_editor.setPlainText(self._format_json(skill.get("output_schema", "{}")))
        self._set_combo(self.tier_combo, skill.get("preferred_tier", "haiku"))
        self.temperature_spin.setValue(skill.get("temperature", 0.7) or 0.7)
        self.max_tokens_spin.setValue(skill.get("max_tokens", 1024) or 1024)

        self.builtin_warning.setVisible(self._is_builtin)
        self._set_editor_editable(not self._is_builtin)

    def _set_editor_editable(self, editable: bool):
        """Enable/disable all editor fields across all tabs."""
        # Tab 1
        self.name_input.setEnabled(editable)
        self.description_input.setReadOnly(not editable)
        self.category_combo.setEnabled(editable)
        self.tone_combo.setEnabled(editable)
        self.version_input.setEnabled(editable)
        self.tags_input.setEnabled(editable)
        # Tab 2
        self.prompt_editor.setReadOnly(not editable)
        self.instructions_editor.setReadOnly(not editable)
        self.examples_editor.setReadOnly(not editable)
        # Tab 3
        self.capabilities_editor.setReadOnly(not editable)
        self.input_schema_editor.setReadOnly(not editable)
        self.output_schema_editor.setReadOnly(not editable)
        self.tier_combo.setEnabled(editable)
        self.temperature_spin.setEnabled(editable)
        self.max_tokens_spin.setEnabled(editable)
        # Buttons
        self.save_btn.setEnabled(editable)
        self.delete_btn.setEnabled(editable and self._current_skill_id is not None)

    def _on_new_skill(self):
        """Create a new empty skill."""
        self.skill_list.clearSelection()
        self.clear_editor()

    def _on_save(self):
        """Gather all fields into a dict and emit save_requested."""
        name = self.name_input.text().strip()
        prompt = self.prompt_editor.toPlainText().strip()

        if not name or not prompt:
            show_toast(self.window(), "Name and system prompt are required.", "warning")
            return

        skill_data = {
            # Identity
            "name": name,
            "description": self.description_input.toPlainText().strip(),
            "category": self.category_combo.currentText(),
            "tone": self.tone_combo.currentText(),
            "version": self.version_input.text().strip() or "1.0",
            "tags": self._csv_to_json_list(self.tags_input.text()),
            # Behavior
            "system_prompt": prompt,
            "instructions": self.instructions_editor.toPlainText().strip(),
            "examples": self._compact_json(self.examples_editor.toPlainText().strip()) or "[]",
            # Schema & Config
            "capabilities": self._compact_json(self.capabilities_editor.toPlainText().strip()) or "[]",
            "input_schema": self._compact_json(self.input_schema_editor.toPlainText().strip()) or "{}",
            "output_schema": self._compact_json(self.output_schema_editor.toPlainText().strip()) or "{}",
            "preferred_tier": self.tier_combo.currentText(),
            "temperature": self.temperature_spin.value(),
            "max_tokens": self.max_tokens_spin.value(),
        }

        skill_id = self._current_skill_id or 0
        self.save_requested.emit(skill_id, skill_data)

    def _on_delete(self):
        """Emit delete request with confirmation."""
        if not self._current_skill_id:
            return
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Delete Skill",
            f"Are you sure you want to delete \"{self.name_input.text()}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(self._current_skill_id)

    def _on_import(self):
        """Open file dialog for skill import."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Skill", "", "JSON Files (*.json)"
        )
        if path:
            self.import_requested.emit(path)

    def _on_export(self):
        """Open file dialog for skill export."""
        if not self._current_skill_id:
            show_toast(self.window(), "Select a skill to export.", "warning")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Skill",
            f"{self.name_input.text()}.json",
            "JSON Files (*.json)"
        )
        if path:
            self.export_requested.emit(self._current_skill_id, path)

    def _on_rag_import(self):
        """Open file dialog for RAG CSV import."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Emails to RAG", "", "CSV Files (*.csv)"
        )
        if path:
            self.rag_import_requested.emit(path)

    def _on_rag_clear(self):
        """Emit signal to clear RAG memory."""
        self.rag_clear_requested.emit()

    def update_rag_stats(self, total: int, replied: int):
        """Update the RAG memory stats display."""
        self.rag_count_label.setText(f"{total} emails stored · {replied} replied")

    def receive_context(self, context: dict):
        """Handle incoming navigation context from other pages."""
        pass

    # ─── JSON helpers ─────────────────────────────────────────────────

    @staticmethod
    def _set_combo(combo: QComboBox, value: str):
        """Set combo box to value, defaulting to index 0 if not found."""
        idx = combo.findText(value)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    @staticmethod
    def _json_list_to_csv(json_str: str) -> str:
        """Convert a JSON list string like '["a","b"]' to comma-separated 'a, b'."""
        import json
        try:
            items = json.loads(json_str) if json_str else []
            if isinstance(items, list):
                return ", ".join(str(i) for i in items)
        except (json.JSONDecodeError, TypeError):
            pass
        return json_str if json_str else ""

    @staticmethod
    def _csv_to_json_list(csv_str: str) -> str:
        """Convert comma-separated 'a, b, c' to JSON list '["a","b","c"]'."""
        import json
        if not csv_str or not csv_str.strip():
            return "[]"
        items = [item.strip() for item in csv_str.split(",") if item.strip()]
        return json.dumps(items)

    @staticmethod
    def _format_json(json_str: str) -> str:
        """Pretty-print a JSON string for display in editors."""
        import json
        try:
            parsed = json.loads(json_str) if json_str else None
            if parsed is not None:
                return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            pass
        return json_str or ""

    @staticmethod
    def _compact_json(text: str) -> str:
        """Compact a JSON string (remove pretty formatting) for storage."""
        import json
        if not text:
            return ""
        try:
            parsed = json.loads(text)
            return json.dumps(parsed, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            return text
