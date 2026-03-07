"""
Tests for Skill Registry — capability-based skill matching + built-in skills.
"""
import json
import pytest
from unittest.mock import MagicMock

from core.skill_registry import (
    SkillRegistry,
    get_builtin_skills,
    find_best_skill_for_task,
    build_skill_context,
    SKILL_CATEGORIES,
    CAPABILITY_TASK_MAP,
)


@pytest.fixture
def skill_registry(db):
    """Fresh SkillRegistry with in-memory DB."""
    return SkillRegistry(db)


class TestBuiltinSkills:
    """Test built-in skill definitions."""

    def test_builtin_skills_list(self):
        """Should return a list of built-in skill definitions."""
        skills = get_builtin_skills()
        assert isinstance(skills, list)
        assert len(skills) >= 8

    def test_builtin_skill_structure(self):
        """Each skill should have required fields."""
        skills = get_builtin_skills()
        required_fields = [
            "name", "system_prompt", "tone", "category",
            "capabilities", "description", "instructions",
        ]
        for skill in skills:
            for field in required_fields:
                assert field in skill, f"Skill {skill.get('name')} missing '{field}'"

    def test_builtin_skill_names_unique(self):
        """All built-in skill names should be unique."""
        skills = get_builtin_skills()
        names = [s["name"] for s in skills]
        assert len(names) == len(set(names))

    def test_builtin_skills_have_capabilities(self):
        """Each skill should have at least one capability."""
        skills = get_builtin_skills()
        for skill in skills:
            caps_str = skill.get("capabilities", "[]")
            caps = json.loads(caps_str)
            assert len(caps) > 0, f"Skill {skill['name']} has no capabilities"

    def test_builtin_skill_categories_valid(self):
        """Each skill's category should be in SKILL_CATEGORIES."""
        skills = get_builtin_skills()
        for skill in skills:
            assert skill["category"] in SKILL_CATEGORIES, (
                f"Skill {skill['name']} has invalid category '{skill['category']}'"
            )

    def test_prospector_skill_exists(self):
        """The Prospector skill should be in built-ins."""
        skills = get_builtin_skills()
        names = [s["name"] for s in skills]
        assert any("Prospector" in n for n in names)

    def test_closer_skill_exists(self):
        """The Closer skill should be in built-ins."""
        skills = get_builtin_skills()
        names = [s["name"] for s in skills]
        assert any("Closer" in n for n in names)

    def test_fleet_commander_skill_exists(self):
        """The Fleet Commander skill should be in built-ins."""
        skills = get_builtin_skills()
        names = [s["name"] for s in skills]
        assert any("commander" in n.lower() or "fleet" in n.lower() for n in names)


class TestFindBestSkill:
    """Test capability-based skill matching."""

    def test_find_skill_for_search_leads(self):
        """Should match a search_leads task to the prospector skill."""
        skills = get_builtin_skills()
        result = find_best_skill_for_task(skills, "search_leads")
        assert result is not None
        assert isinstance(result, dict)
        assert "name" in result

    def test_find_skill_for_generate_email(self):
        """Should match a generate_email task."""
        skills = get_builtin_skills()
        result = find_best_skill_for_task(skills, "generate_email")
        assert result is not None

    def test_find_skill_for_qualify_lead(self):
        """Should match a qualify_lead task."""
        skills = get_builtin_skills()
        result = find_best_skill_for_task(skills, "qualify_lead")
        assert result is not None

    def test_find_skill_no_match(self):
        """Should return None when no skill matches."""
        result = find_best_skill_for_task([], "cook_pasta")
        assert result is None

    def test_find_skill_with_empty_skills(self):
        """Empty skills list should return None."""
        result = find_best_skill_for_task([], "search_leads")
        assert result is None

    def test_find_skill_for_enrich_lead(self):
        """Should match enrich_lead to enrichment skill."""
        skills = get_builtin_skills()
        result = find_best_skill_for_task(skills, "enrich_lead")
        assert result is not None

    def test_find_skill_for_research(self):
        """Should match research task."""
        skills = get_builtin_skills()
        result = find_best_skill_for_task(skills, "research")
        assert result is not None


class TestBuildSkillContext:
    """Test context building for agent prompts."""

    def test_build_context_basic(self):
        """Should build a context string from a skill dict."""
        skill = {
            "name": "Test Skill",
            "system_prompt": "You are a test skill.",
            "tone": "confident",
            "description": "A skill for testing.",
            "instructions": "Follow the test protocol.",
            "capabilities": json.dumps(["testing", "validation"]),
            "input_schema": '{"query": "string"}',
            "output_schema": '{"result": "string"}',
            "examples": '[{"input": "test", "output": "pass"}]',
        }
        context = build_skill_context(skill)
        assert isinstance(context, str)
        assert "Test Skill" in context
        assert "test skill" in context.lower()

    def test_build_context_minimal(self):
        """Should handle skill with minimal fields."""
        skill = {
            "name": "Minimal",
            "system_prompt": "You are minimal.",
        }
        context = build_skill_context(skill)
        assert isinstance(context, str)
        assert "Minimal" in context

    def test_build_context_includes_instructions(self):
        """Should include instructions when present."""
        skill = {
            "name": "Instructor",
            "system_prompt": "You instruct.",
            "instructions": "Step 1: Do this. Step 2: Do that.",
        }
        context = build_skill_context(skill)
        assert "Step 1" in context

    def test_build_context_includes_examples(self):
        """Should include examples when present."""
        skill = {
            "name": "Example Skill",
            "system_prompt": "You example.",
            "examples": '[{"input": "hello", "output": "world"}]',
        }
        context = build_skill_context(skill)
        assert "hello" in context or "example" in context.lower()

    def test_build_context_from_builtin(self):
        """Should work with actual built-in skill definitions."""
        skills = get_builtin_skills()
        context = build_skill_context(skills[0])
        assert isinstance(context, str)
        assert len(context) > 50  # Should be substantive


class TestSkillRegistry:
    """Test the SkillRegistry class."""

    def test_registry_init(self, skill_registry):
        assert skill_registry is not None
        assert skill_registry.db_manager is not None

    def test_seed_builtin_skills(self, skill_registry):
        """Should seed built-in skills into the database."""
        result = skill_registry.seed_builtin_skills()
        assert result["created"] >= 8
        assert isinstance(result["errors"], list)
        assert len(result["errors"]) == 0

    def test_seed_builtin_skills_idempotent(self, skill_registry):
        """Seeding twice should not duplicate skills."""
        skill_registry.seed_builtin_skills()
        result = skill_registry.seed_builtin_skills()
        # Second seeding should update, not create new
        assert result["created"] == 0
        assert result["updated"] >= 8

    def test_get_all_skills(self, skill_registry):
        """Should return all skills after seeding."""
        skill_registry.seed_builtin_skills()
        skills = skill_registry.get_all_skills()
        assert isinstance(skills, list)
        assert len(skills) >= 8

    def test_find_skill_for_task(self, skill_registry):
        """Should find a skill matching a task type."""
        skill_registry.seed_builtin_skills()
        result = skill_registry.find_skill_for_task("search_leads")
        assert result is not None

    def test_get_skills_by_category(self, skill_registry):
        """Should filter skills by category."""
        skill_registry.seed_builtin_skills()
        skills = skill_registry.get_skills_by_category("outreach")
        assert isinstance(skills, list)

    def test_get_skills_by_capability(self, skill_registry):
        """Should filter skills by capability."""
        skill_registry.seed_builtin_skills()
        skills = skill_registry.get_skills_by_capability("search_leads")
        assert isinstance(skills, list)
        assert len(skills) >= 1


class TestCapabilityTaskMap:
    """Test the CAPABILITY_TASK_MAP constants."""

    def test_capability_map_not_empty(self):
        assert len(CAPABILITY_TASK_MAP) > 0

    def test_capability_map_values_are_lists(self):
        for cap, keywords in CAPABILITY_TASK_MAP.items():
            assert isinstance(keywords, (list, tuple)), (
                f"CAPABILITY_TASK_MAP['{cap}'] should be a list"
            )

    def test_skill_categories_not_empty(self):
        assert len(SKILL_CATEGORIES) > 0
        assert "general" in SKILL_CATEGORIES

    def test_skill_categories_has_core_categories(self):
        expected = ["prospecting", "outreach", "analysis", "management"]
        for cat in expected:
            assert cat in SKILL_CATEGORIES
