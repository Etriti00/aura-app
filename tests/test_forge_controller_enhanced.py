"""
Tests for enhanced ForgeController with full-field dict-based CRUD.
"""

import json
import os
import tempfile
import pytest

from tests.conftest import InMemoryDatabaseManager
from database.schema import Skill
from controllers.forge_controller import ForgeController


@pytest.fixture
def db():
    db_manager = InMemoryDatabaseManager()
    db_manager.init_db()
    return db_manager


@pytest.fixture
def ctrl(db):
    return ForgeController(db)


@pytest.fixture
def sample_skill_data():
    return {
        "name": "Test Skill",
        "system_prompt": "You are a test skill.",
        "tone": "professional",
        "description": "A skill for testing purposes.",
        "instructions": "1. RECEIVE input\n2. PROCESS data\n3. OUTPUT result",
        "category": "analysis",
        "version": "1.0",
        "capabilities": '["analyze", "summarize"]',
        "tags": '["test", "analysis"]',
        "input_schema": '{"data": "object"}',
        "output_schema": '{"result": "string"}',
        "examples": '[{"input": "test data", "output": "test result"}]',
        "preferred_tier": "haiku",
        "temperature": 0.5,
        "max_tokens": 800,
    }


class TestGetAllSkills:
    def test_returns_all_enhanced_fields(self, db, ctrl):
        with db.session_scope() as session:
            session.add(Skill(
                name="Enhanced Skill",
                system_prompt="prompt",
                tone="casual",
                is_builtin=True,
                description="A description",
                instructions="Step 1\nStep 2",
                category="outreach",
                capabilities='["generate_email"]',
                tags='["email"]',
                input_schema='{"lead": "object"}',
                output_schema='{"email": "string"}',
                examples='[{"input": "x", "output": "y"}]',
                version="2.0",
            ))

        skills = ctrl.get_all_skills()
        assert len(skills) == 1
        s = skills[0]
        assert s["description"] == "A description"
        assert s["instructions"] == "Step 1\nStep 2"
        assert s["category"] == "outreach"
        assert s["capabilities"] == '["generate_email"]'
        assert s["tags"] == '["email"]'
        assert s["input_schema"] == '{"lead": "object"}'
        assert s["output_schema"] == '{"email": "string"}'
        assert s["examples"] == '[{"input": "x", "output": "y"}]'
        assert s["version"] == "2.0"

    def test_returns_defaults_for_empty_fields(self, db, ctrl):
        with db.session_scope() as session:
            session.add(Skill(name="Bare Skill", system_prompt="prompt"))

        skills = ctrl.get_all_skills()
        s = skills[0]
        assert s["description"] == ""
        assert s["category"] == "general"
        assert s["capabilities"] == "[]"
        assert s["version"] == "1.0"
        assert s["temperature"] == 0.7
        assert s["max_tokens"] == 1024


class TestGetSkill:
    def test_returns_full_dict(self, db, ctrl):
        with db.session_scope() as session:
            session.add(Skill(
                name="Single", system_prompt="sp", description="desc",
                category="research", version="3.0",
            ))

        with db.session_scope() as session:
            skill_id = session.query(Skill).first().id

        result = ctrl.get_skill(skill_id)
        assert result is not None
        assert result["name"] == "Single"
        assert result["description"] == "desc"
        assert result["category"] == "research"
        assert result["version"] == "3.0"

    def test_returns_none_for_missing(self, ctrl):
        assert ctrl.get_skill(9999) is None


class TestCreateSkill:
    def test_creates_with_all_fields(self, db, ctrl, sample_skill_data):
        result = ctrl.create_skill(sample_skill_data)
        assert result is True

        skills = ctrl.get_all_skills()
        assert len(skills) == 1
        s = skills[0]
        assert s["name"] == "Test Skill"
        assert s["description"] == "A skill for testing purposes."
        assert s["instructions"] == "1. RECEIVE input\n2. PROCESS data\n3. OUTPUT result"
        assert s["category"] == "analysis"
        assert s["capabilities"] == '["analyze", "summarize"]'
        assert s["temperature"] == 0.5
        assert s["max_tokens"] == 800

    def test_rejects_missing_name(self, ctrl):
        result = ctrl.create_skill({"system_prompt": "test"})
        assert result is False

    def test_rejects_missing_prompt(self, ctrl):
        result = ctrl.create_skill({"name": "Test"})
        assert result is False

    def test_rejects_duplicate_name(self, db, ctrl, sample_skill_data):
        ctrl.create_skill(sample_skill_data)
        result = ctrl.create_skill(sample_skill_data)
        assert result is False

    def test_emits_signals(self, ctrl, sample_skill_data):
        saved_names = []
        changed_count = [0]
        ctrl.skill_saved.connect(lambda name: saved_names.append(name))
        ctrl.skills_changed.connect(lambda: changed_count.__setitem__(0, changed_count[0] + 1))

        ctrl.create_skill(sample_skill_data)
        assert saved_names == ["Test Skill"]
        assert changed_count[0] == 1


class TestUpdateSkill:
    def test_updates_all_fields(self, db, ctrl, sample_skill_data):
        ctrl.create_skill(sample_skill_data)
        skill = ctrl.get_all_skills()[0]

        updated = {
            "name": "Updated Skill",
            "system_prompt": "Updated prompt",
            "tone": "casual",
            "description": "Updated desc",
            "instructions": "New instructions",
            "category": "outreach",
            "capabilities": '["new_cap"]',
            "tags": '["updated"]',
            "input_schema": '{"new": "schema"}',
            "output_schema": '{"out": "put"}',
            "examples": '[]',
            "version": "2.0",
            "temperature": 0.9,
            "max_tokens": 2048,
        }
        result = ctrl.update_skill(skill["id"], updated)
        assert result is True

        s = ctrl.get_skill(skill["id"])
        assert s["name"] == "Updated Skill"
        assert s["description"] == "Updated desc"
        assert s["category"] == "outreach"
        assert s["temperature"] == 0.9
        assert s["max_tokens"] == 2048

    def test_rejects_builtin(self, db, ctrl):
        with db.session_scope() as session:
            session.add(Skill(name="Builtin", system_prompt="sp", is_builtin=True))
        skill = ctrl.get_all_skills()[0]
        result = ctrl.update_skill(skill["id"], {"name": "Changed"})
        assert result is False

    def test_rejects_missing_id(self, ctrl):
        result = ctrl.update_skill(9999, {"name": "X"})
        assert result is False


class TestExportImport:
    def test_export_includes_enhanced_fields(self, db, ctrl, sample_skill_data):
        ctrl.create_skill(sample_skill_data)
        skill = ctrl.get_all_skills()[0]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        try:
            result = ctrl.export_skill(skill["id"], path)
            assert result is True

            with open(path, "r") as f:
                exported = json.load(f)

            assert exported["name"] == "Test Skill"
            assert exported["description"] == "A skill for testing purposes."
            assert exported["instructions"] == "1. RECEIVE input\n2. PROCESS data\n3. OUTPUT result"
            assert exported["category"] == "analysis"
            assert exported["capabilities"] == '["analyze", "summarize"]'
            assert exported["input_schema"] == '{"data": "object"}'
            assert exported["output_schema"] == '{"result": "string"}'
            assert exported["temperature"] == 0.5
        finally:
            os.unlink(path)

    def test_import_with_enhanced_fields(self, ctrl):
        import_data = {
            "name": "Imported Skill",
            "system_prompt": "Imported prompt",
            "tone": "formal",
            "description": "Imported description",
            "instructions": "Imported instructions",
            "category": "research",
            "capabilities": '["research"]',
            "tags": '["imported"]',
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(import_data, f)
            path = f.name

        try:
            result = ctrl.import_skill(path)
            assert result is True

            skills = ctrl.get_all_skills()
            assert len(skills) == 1
            s = skills[0]
            assert s["name"] == "Imported Skill"
            assert s["description"] == "Imported description"
            assert s["category"] == "research"
        finally:
            os.unlink(path)


class TestSeedSkillsEnhanced:
    def test_seed_skills_have_enhanced_fields(self, db):
        db.seed_defaults()
        with db.session_scope() as session:
            skills = session.query(Skill).filter_by(is_builtin=True).all()
            assert len(skills) >= 15

            for skill in skills:
                assert skill.category, f"Skill '{skill.name}' missing category"
                assert skill.category != "general" or skill.name in ("CRM Data Mapper",), \
                    f"Skill '{skill.name}' has default category 'general'"
                assert skill.description, f"Skill '{skill.name}' missing description"
                assert skill.instructions, f"Skill '{skill.name}' missing instructions"
                assert skill.capabilities and skill.capabilities != "[]", \
                    f"Skill '{skill.name}' missing capabilities"

    def test_seed_upsert_updates_enhanced_fields(self, db):
        # First seed
        db.seed_defaults()
        # Second seed should update, not duplicate
        db.seed_defaults()
        with db.session_scope() as session:
            skills = session.query(Skill).filter_by(is_builtin=True).all()
            names = [s.name for s in skills]
            assert len(names) == len(set(names)), "Duplicate skill names after re-seed"

            closer = session.query(Skill).filter_by(name="The Closer").first()
            assert closer.category == "outreach"
            assert closer.description != ""
            assert "generate_email" in closer.capabilities
