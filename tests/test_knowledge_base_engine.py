"""Tests for core.knowledge_base_engine — KnowledgeBaseEngine."""

import pytest
from database.schema import KnowledgeBase


class TestSetEntry:
    """Creating and updating KB entries."""

    def test_create_entry(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.set_entry("product", "name", "Aura CRM")
        assert result["success"]
        assert result["data"]["action"] == "created"

    def test_update_existing_entry(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "name", "Old Name")
        result = kb.set_entry("product", "name", "New Name")
        assert result["data"]["action"] == "updated"

        entries = kb.get_entries("product")
        assert len(entries["data"]) == 1
        assert entries["data"][0]["value"] == "New Name"

    def test_invalid_category(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.set_entry("invalid_cat", "key", "value")
        assert not result["success"]
        assert "Invalid category" in result["error"]

    def test_empty_key_rejected(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.set_entry("product", "", "value")
        assert not result["success"]

    def test_empty_value_rejected(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.set_entry("product", "key", "")
        assert not result["success"]

    def test_set_with_priority(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.set_entry("icp", "industry", "SaaS", priority=10)
        assert result["success"]


class TestGetEntries:
    """Querying KB entries."""

    def test_get_all_entries(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "name", "Aura")
        kb.set_entry("icp", "industry", "SaaS")
        kb.set_entry("approach", "tone", "professional")

        result = kb.get_entries()
        assert result["success"]
        assert len(result["data"]) == 3

    def test_get_filtered_by_category(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "name", "Aura")
        kb.set_entry("product", "price", "$500/mo")
        kb.set_entry("icp", "industry", "SaaS")

        result = kb.get_entries("product")
        assert len(result["data"]) == 2

    def test_get_empty(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.get_entries()
        assert result["success"]
        assert len(result["data"]) == 0

    def test_priority_ordering(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "low_priority", "val", priority=1)
        kb.set_entry("product", "high_priority", "val", priority=10)

        result = kb.get_entries("product")
        assert result["data"][0]["key"] == "high_priority"


class TestDeleteEntry:
    """Soft-delete operations."""

    def test_delete_by_id(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        created = kb.set_entry("product", "name", "Aura")
        entry_id = created["data"]["id"]

        result = kb.delete_entry(entry_id=entry_id)
        assert result["success"]
        assert result["data"]["deleted"] == 1

        # Verify it's gone from active entries
        entries = kb.get_entries()
        assert len(entries["data"]) == 0

    def test_delete_by_category_key(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("icp", "industry", "SaaS")

        result = kb.delete_entry(category="icp", key="industry")
        assert result["success"]

    def test_delete_nonexistent(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.delete_entry(entry_id=999)
        assert not result["success"]

    def test_delete_no_params(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        result = kb.delete_entry()
        assert not result["success"]


class TestBuildContext:
    """Context string building for agent injection."""

    def test_empty_returns_empty(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        assert kb.build_context() == ""

    def test_context_has_header(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "name", "Aura CRM")
        context = kb.build_context()
        assert "KNOWLEDGE_BASE" in context
        assert "Aura CRM" in context

    def test_context_sections(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("product", "name", "Aura")
        kb.set_entry("icp", "industry", "SaaS")
        kb.set_entry("approach", "tone", "professional")

        context = kb.build_context()
        assert "[PRODUCT]" in context
        assert "[ICP]" in context
        assert "[APPROACH]" in context

    def test_context_truncation(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        # Add a very long entry
        kb.set_entry("product", "description", "x" * 5000)
        context = kb.build_context(max_chars=200)
        assert len(context) <= 200


class TestGetIcpCriteria:
    """ICP criteria extraction for scoring."""

    def test_empty_icp(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        assert kb.get_icp_criteria() == {}

    def test_returns_icp_dict(self, db):
        from core.knowledge_base_engine import KnowledgeBaseEngine
        kb = KnowledgeBaseEngine(db)
        kb.set_entry("icp", "industry", "SaaS")
        kb.set_entry("icp", "company_size", "10-200")
        kb.set_entry("product", "name", "Aura")  # Not ICP

        criteria = kb.get_icp_criteria()
        assert criteria == {"industry": "SaaS", "company_size": "10-200"}
