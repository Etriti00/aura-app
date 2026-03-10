"""
Aura — Knowledge Base Engine
CRUD for the KnowledgeBase table. Stores ICP definitions, product info,
and sales approach as user-defined ground truth injected into agent contexts.

Categories: "product", "icp", "approach", "general"
"""

import json
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import KnowledgeBase
from utils.logger import get_logger

logger = get_logger("knowledge_base_engine")

VALID_CATEGORIES = ("product", "icp", "approach", "general")
MAX_CONTEXT_TOKENS = 1000


class KnowledgeBaseEngine:
    """CRUD engine for knowledge base entries."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    def set_entry(self, category: str, key: str, value: str,
                  priority: int = 0) -> dict:
        """Create or update a knowledge base entry."""
        if category not in VALID_CATEGORIES:
            return {"success": False, "error": f"Invalid category: {category}. Use: {VALID_CATEGORIES}"}
        if not key or not value:
            return {"success": False, "error": "Key and value are required"}

        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(KnowledgeBase).filter_by(
                    category=category, key=key, is_active=True,
                ).first()

                if existing:
                    existing.value = value
                    existing.priority = priority
                    entry_id = existing.id
                    action = "updated"
                else:
                    entry = KnowledgeBase(
                        category=category,
                        key=key,
                        value=value,
                        priority=priority,
                        is_active=True,
                    )
                    session.add(entry)
                    session.flush()
                    entry_id = entry.id
                    action = "created"

            return {"success": True, "data": {"id": entry_id, "action": action}}

        except Exception as e:
            logger.error(f"Failed to set KB entry: {e}")
            return {"success": False, "error": str(e)}

    def get_entries(self, category: str = None) -> dict:
        """List active entries, optionally filtered by category."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(KnowledgeBase).filter_by(is_active=True)
                if category:
                    query = query.filter_by(category=category)

                entries = query.order_by(
                    KnowledgeBase.priority.desc(),
                    KnowledgeBase.category,
                    KnowledgeBase.key,
                ).all()

                return {
                    "success": True,
                    "data": [
                        {
                            "id": e.id,
                            "category": e.category,
                            "key": e.key,
                            "value": e.value,
                            "priority": e.priority,
                        }
                        for e in entries
                    ],
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_entry(self, entry_id: int = None, category: str = None,
                     key: str = None) -> dict:
        """Soft-delete an entry by ID or by category+key."""
        try:
            with self.db_manager.session_scope() as session:
                if entry_id:
                    entry = session.query(KnowledgeBase).filter_by(
                        id=entry_id, is_active=True,
                    ).first()
                    if entry:
                        entry.is_active = False
                        return {"success": True, "data": {"deleted": 1}}
                    return {"success": False, "error": "Entry not found"}

                if category and key:
                    count = session.query(KnowledgeBase).filter_by(
                        category=category, key=key, is_active=True,
                    ).update({"is_active": False})
                    return {"success": True, "data": {"deleted": count}}

                return {"success": False, "error": "Provide entry_id or category+key"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def build_context(self, max_chars: int = MAX_CONTEXT_TOKENS * 4) -> str:
        """
        Build a structured context string from all active KB entries
        for injection into agent prompts.
        Returns empty string if no entries.
        """
        try:
            result = self.get_entries()
            if not result.get("success") or not result.get("data"):
                return ""

            entries = result["data"]

            sections = {}
            for e in entries:
                cat = e["category"].upper()
                if cat not in sections:
                    sections[cat] = []
                sections[cat].append(f"  {e['key']}: {e['value']}")

            lines = ["KNOWLEDGE_BASE (ground truth — use this to personalize outreach):"]
            for cat in ["PRODUCT", "ICP", "APPROACH", "GENERAL"]:
                if cat in sections:
                    lines.append(f"[{cat}]")
                    lines.extend(sections[cat])

            context = "\n".join(lines)
            if len(context) > max_chars:
                context = context[:max_chars]

            return context

        except Exception as e:
            logger.error(f"Failed to build KB context: {e}")
            return ""

    def get_icp_criteria(self) -> dict:
        """Extract ICP entries as a dict for scoring purposes."""
        try:
            result = self.get_entries(category="icp")
            if not result.get("success"):
                return {}
            return {e["key"]: e["value"] for e in result.get("data", [])}
        except Exception:
            return {}
