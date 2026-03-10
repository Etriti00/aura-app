"""Tests for core.correction_memory — CorrectionMemory engine."""

import pytest
from database.schema import AgentLearnedRule


class TestLooksLikeCorrection:
    """Heuristic detection of correction-like messages."""

    def test_starts_with_no(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("No, use a different tone")

    def test_contains_wrong(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("That's wrong, fix it")

    def test_contains_always(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("Always use formal language")

    def test_contains_never(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("Never mention pricing in first email")

    def test_normal_message_not_correction(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert not cm.looks_like_correction("Send 10 emails to campaign X")

    def test_empty_message(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert not cm.looks_like_correction("")

    def test_contains_dont(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("Don't include phone numbers")

    def test_contains_instead(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.looks_like_correction("Instead of formal, use casual tone")


class TestStoreRule:
    """Direct rule storage and retrieval."""

    def test_store_new_rule(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm._store_rule("Use formal tone", "tone", 0.8)
        assert result is not None
        assert result["action"] == "created"
        assert "rule_id" in result

    def test_duplicate_rule_reinforces(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Use formal tone", "tone", 0.8)
        result = cm._store_rule("Use formal tone", "tone", 0.8)
        assert result["action"] == "reinforced"

    def test_store_with_agent_name(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm._store_rule("Be brief", "format", 0.7, agent_name="Closer")
        assert result["action"] == "created"

        with db.session_scope() as session:
            rule = session.query(AgentLearnedRule).filter_by(
                id=result["rule_id"]
            ).first()
            assert rule.agent_name == "Closer"

    def test_store_raw_rule_fallback(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm._store_raw_rule("Always use bullet points")
        assert result is not None
        assert result["action"] == "created"

    def test_store_raw_rule_too_short(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm._store_raw_rule("hi")
        assert result is None


class TestGetRulesForContext:
    """Context string building for agent injection."""

    def test_empty_returns_empty_string(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        assert cm.get_rules_for_context() == ""

    def test_returns_rules_header(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Be concise", "format", 0.9)
        context = cm.get_rules_for_context()
        assert "LEARNED_RULES" in context
        assert "Be concise" in context

    def test_agent_scoped_rules(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Rule for Closer", "tone", 0.8, agent_name="Closer")
        cm._store_rule("Global rule", "format", 0.9)

        # Closer sees both
        closer_ctx = cm.get_rules_for_context(agent_name="Closer")
        assert "Rule for Closer" in closer_ctx
        assert "Global rule" in closer_ctx

    def test_max_rules_limit(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        for i in range(20):
            cm._store_rule(f"Rule number {i}", "general", 0.5 + i * 0.02)

        context = cm.get_rules_for_context(max_rules=5)
        # Should contain at most 5 rules
        assert context.count("- [") <= 5


class TestClearAndListRules:
    """Clear and list operations."""

    def test_clear_all_rules(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Rule 1", "tone", 0.8, source="user_correction")
        cm._store_rule("Rule 2", "format", 0.7, source="user_correction")

        result = cm.clear_rules()
        assert result["success"]
        assert result["data"]["cleared"] == 2
        assert cm.get_rules_for_context() == ""

    def test_clear_agent_scoped(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Global", "tone", 0.8, source="user_correction")
        cm._store_rule("Agent rule", "format", 0.7, agent_name="Closer",
                       source="user_correction")

        result = cm.clear_rules(agent_name="Closer")
        assert result["data"]["cleared"] == 1

    def test_list_rules(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        cm._store_rule("Be formal", "tone", 0.8)
        cm._store_rule("Include CTA", "content", 0.9)

        result = cm.list_rules()
        assert result["success"]
        assert len(result["data"]) == 2

    def test_list_rules_empty(self, db):
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm.list_rules()
        assert result["success"]
        assert len(result["data"]) == 0

    def test_extract_and_store_no_api_keys(self, db):
        """Without API keys, falls back to raw rule storage."""
        from database.schema import Settings
        with db.session_scope() as session:
            session.add(Settings())
        from core.correction_memory import CorrectionMemory
        cm = CorrectionMemory(db)
        result = cm.extract_and_store("Always use formal language")
        assert result is not None
        assert result["action"] == "created"
