"""
Tests for enhanced ForgePage with 3-tab editor and full skill template fields.
"""

import json
import pytest

from PySide6.QtWidgets import QTabWidget


@pytest.fixture
def forge_page(qapp):
    from ui.pages.forge import ForgePage
    page = ForgePage()
    return page


class TestForgePageStructure:
    def test_has_tab_widget(self, forge_page):
        assert hasattr(forge_page, "editor_tabs")
        assert isinstance(forge_page.editor_tabs, QTabWidget)

    def test_has_three_tabs(self, forge_page):
        assert forge_page.editor_tabs.count() == 3

    def test_tab_names(self, forge_page):
        tabs = forge_page.editor_tabs
        assert tabs.tabText(0) == "Identity"
        assert tabs.tabText(1) == "Behavior"
        assert tabs.tabText(2) == "Schema && Config"

    def test_identity_tab_fields(self, forge_page):
        assert hasattr(forge_page, "name_input")
        assert hasattr(forge_page, "description_input")
        assert hasattr(forge_page, "category_combo")
        assert hasattr(forge_page, "tone_combo")
        assert hasattr(forge_page, "version_input")
        assert hasattr(forge_page, "tags_input")

    def test_behavior_tab_fields(self, forge_page):
        assert hasattr(forge_page, "prompt_editor")
        assert hasattr(forge_page, "instructions_editor")
        assert hasattr(forge_page, "examples_editor")

    def test_schema_tab_fields(self, forge_page):
        assert hasattr(forge_page, "capabilities_editor")
        assert hasattr(forge_page, "input_schema_editor")
        assert hasattr(forge_page, "output_schema_editor")
        assert hasattr(forge_page, "tier_combo")
        assert hasattr(forge_page, "temperature_spin")
        assert hasattr(forge_page, "max_tokens_spin")


class TestForgePageLoadSkill:
    def _make_skill(self, **overrides):
        base = {
            "id": 1, "name": "Test Skill", "system_prompt": "You are a test.",
            "tone": "professional", "is_builtin": False, "is_default": False,
            "description": "Test description", "instructions": "Step 1\nStep 2",
            "category": "analysis", "version": "2.0",
            "capabilities": '["cap1", "cap2"]', "tags": '["tag1", "tag2"]',
            "input_schema": '{"field": "value"}', "output_schema": '{"out": "put"}',
            "examples": '[{"input": "x", "output": "y"}]',
            "example_output": "", "preferred_tier": "sonnet",
            "temperature": 0.5, "max_tokens": 800,
        }
        base.update(overrides)
        return base

    def test_load_populates_all_fields(self, forge_page):
        skill = self._make_skill()
        forge_page.load_skills([skill])
        forge_page.skill_list.setCurrentRow(0)

        assert forge_page.name_input.text() == "Test Skill"
        assert forge_page.description_input.toPlainText() == "Test description"
        assert forge_page.category_combo.currentText() == "analysis"
        assert forge_page.tone_combo.currentText() == "professional"
        assert forge_page.version_input.text() == "2.0"
        assert "tag1" in forge_page.tags_input.text()
        assert "tag2" in forge_page.tags_input.text()
        assert forge_page.prompt_editor.toPlainText() == "You are a test."
        assert "Step 1" in forge_page.instructions_editor.toPlainText()
        assert "cap1" in forge_page.capabilities_editor.toPlainText()
        assert forge_page.tier_combo.currentText() == "sonnet"
        assert forge_page.temperature_spin.value() == 0.5
        assert forge_page.max_tokens_spin.value() == 800

    def test_load_builtin_sets_readonly(self, forge_page):
        skill = self._make_skill(is_builtin=True)
        forge_page.load_skills([skill])
        forge_page.skill_list.setCurrentRow(0)

        assert not forge_page.name_input.isEnabled()
        assert forge_page.prompt_editor.isReadOnly()
        assert forge_page.instructions_editor.isReadOnly()
        assert not forge_page.save_btn.isEnabled()

    def test_load_custom_sets_editable(self, forge_page):
        skill = self._make_skill(is_builtin=False)
        forge_page.load_skills([skill])
        forge_page.skill_list.setCurrentRow(0)

        assert forge_page.name_input.isEnabled()
        assert not forge_page.prompt_editor.isReadOnly()
        assert forge_page.save_btn.isEnabled()


class TestForgePageSave:
    def test_save_emits_dict(self, forge_page):
        received = []
        forge_page.save_requested.connect(lambda sid, data: received.append((sid, data)))

        forge_page.clear_editor()
        forge_page.name_input.setText("New Skill")
        forge_page.prompt_editor.setPlainText("System prompt here")
        forge_page.description_input.setPlainText("A description")
        forge_page.category_combo.setCurrentIndex(
            forge_page.category_combo.findText("outreach")
        )
        forge_page.instructions_editor.setPlainText("Step 1")
        forge_page.capabilities_editor.setPlainText('["cap1"]')
        forge_page.temperature_spin.setValue(0.8)
        forge_page.max_tokens_spin.setValue(512)

        forge_page._on_save()

        assert len(received) == 1
        skill_id, data = received[0]
        assert skill_id == 0  # new skill
        assert isinstance(data, dict)
        assert data["name"] == "New Skill"
        assert data["system_prompt"] == "System prompt here"
        assert data["description"] == "A description"
        assert data["category"] == "outreach"
        assert data["instructions"] == "Step 1"
        assert data["capabilities"] == '["cap1"]'
        assert data["temperature"] == 0.8
        assert data["max_tokens"] == 512

    def test_save_rejects_empty_name(self, forge_page):
        received = []
        forge_page.save_requested.connect(lambda sid, data: received.append(1))

        forge_page.clear_editor()
        forge_page.prompt_editor.setPlainText("Some prompt")
        # name_input is empty
        forge_page._on_save()
        assert len(received) == 0

    def test_save_rejects_empty_prompt(self, forge_page):
        received = []
        forge_page.save_requested.connect(lambda sid, data: received.append(1))

        forge_page.clear_editor()
        forge_page.name_input.setText("Some Name")
        # prompt_editor is empty
        forge_page._on_save()
        assert len(received) == 0


class TestForgePageClear:
    def test_clear_resets_all_fields(self, forge_page):
        forge_page.name_input.setText("Test")
        forge_page.description_input.setPlainText("desc")
        forge_page.instructions_editor.setPlainText("inst")
        forge_page.capabilities_editor.setPlainText("caps")
        forge_page.temperature_spin.setValue(1.5)
        forge_page.max_tokens_spin.setValue(2048)

        forge_page.clear_editor()

        assert forge_page.name_input.text() == ""
        assert forge_page.description_input.toPlainText() == ""
        assert forge_page.instructions_editor.toPlainText() == ""
        assert forge_page.capabilities_editor.toPlainText() == ""
        assert forge_page.version_input.text() == "1.0"
        assert forge_page.temperature_spin.value() == 0.7
        assert forge_page.max_tokens_spin.value() == 1024
        assert forge_page.editor_tabs.currentIndex() == 0


class TestJsonHelpers:
    def test_json_list_to_csv(self, forge_page):
        assert forge_page._json_list_to_csv('["a", "b", "c"]') == "a, b, c"
        assert forge_page._json_list_to_csv("[]") == ""
        assert forge_page._json_list_to_csv("") == ""

    def test_csv_to_json_list(self, forge_page):
        result = forge_page._csv_to_json_list("a, b, c")
        parsed = json.loads(result)
        assert parsed == ["a", "b", "c"]
        assert forge_page._csv_to_json_list("") == "[]"

    def test_format_json(self, forge_page):
        result = forge_page._format_json('{"a":1}')
        assert '"a": 1' in result  # pretty printed

    def test_compact_json(self, forge_page):
        result = forge_page._compact_json('{\n  "a": 1\n}')
        assert result == '{"a": 1}'
