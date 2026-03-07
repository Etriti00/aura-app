"""
Aura — Forge Controller
CRUD operations for Skills (AI personas), JSON import/export.
Full-field dict-based API supporting all enhanced skill template fields.
"""

import json
from typing import Optional, List

from PySide6.QtCore import QObject, Signal

from database.db_manager import DatabaseManager
from database.schema import Skill
from utils.logger import get_logger

logger = get_logger("forge_controller")

# Fields that map directly from dict keys to Skill column names
_SKILL_FIELDS = [
    "name", "system_prompt", "tone", "example_output",
    "preferred_tier", "temperature", "max_tokens",
    "description", "instructions", "category", "version",
    "capabilities", "tags", "input_schema", "output_schema", "examples",
]


def _skill_to_dict(s: Skill) -> dict:
    """Convert a Skill ORM object to a full dict with all fields."""
    return {
        "id": s.id,
        "name": s.name,
        "system_prompt": s.system_prompt or "",
        "tone": s.tone or "professional",
        "is_builtin": s.is_builtin,
        "is_default": s.is_default,
        "example_output": s.example_output or "",
        "preferred_tier": s.preferred_tier or "haiku",
        "temperature": s.temperature if s.temperature is not None else 0.7,
        "max_tokens": s.max_tokens or 1024,
        "description": s.description or "",
        "instructions": s.instructions or "",
        "category": s.category or "general",
        "version": s.version or "1.0",
        "capabilities": s.capabilities or "[]",
        "tags": s.tags or "[]",
        "input_schema": s.input_schema or "{}",
        "output_schema": s.output_schema or "{}",
        "examples": s.examples or "[]",
    }


class ForgeController(QObject):
    """Manages Skill (AI persona) lifecycle: create, read, update, delete, import, export."""

    skills_changed = Signal()       # Emitted when skill list changes
    skill_saved = Signal(str)       # Emitted with skill name on save
    skill_error = Signal(str)       # Error message

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def get_all_skills(self) -> list:
        """Retrieve all skills as dicts with all fields."""
        with self.db_manager.session_scope() as session:
            skills = session.query(Skill).order_by(Skill.is_builtin.desc(), Skill.name).all()
            return [_skill_to_dict(s) for s in skills]

    def get_skill(self, skill_id: int) -> Optional[dict]:
        """Get a single skill by ID with all fields."""
        with self.db_manager.session_scope() as session:
            s = session.query(Skill).filter_by(id=skill_id).first()
            if s:
                return _skill_to_dict(s)
        return None

    def create_skill(self, skill_data: dict) -> bool:
        """Create a new custom skill from a dict of fields."""
        name = skill_data.get("name", "").strip()
        system_prompt = skill_data.get("system_prompt", "").strip()

        if not name or not system_prompt:
            self.skill_error.emit("Name and system prompt are required.")
            return False

        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(Skill).filter_by(name=name).first()
                if existing:
                    self.skill_error.emit(f"A skill named '{name}' already exists.")
                    return False

                skill = Skill(is_builtin=False)
                _apply_dict_to_skill(skill, skill_data)
                session.add(skill)

            self.skill_saved.emit(name)
            self.skills_changed.emit()
            logger.info(f"Created skill: {name}")
            return True
        except Exception as e:
            self.skill_error.emit(f"Failed to create skill: {e}")
            return False

    def update_skill(self, skill_id: int, skill_data: dict) -> bool:
        """Update an existing skill with all fields from dict. Built-in skills cannot be modified."""
        try:
            with self.db_manager.session_scope() as session:
                skill = session.query(Skill).filter_by(id=skill_id).first()
                if not skill:
                    self.skill_error.emit("Skill not found.")
                    return False
                if skill.is_builtin:
                    self.skill_error.emit("Built-in skills cannot be modified.")
                    return False

                _apply_dict_to_skill(skill, skill_data)

            name = skill_data.get("name", "")
            self.skill_saved.emit(name)
            self.skills_changed.emit()
            logger.info(f"Updated skill: {name}")
            return True
        except Exception as e:
            self.skill_error.emit(f"Failed to update skill: {e}")
            return False

    def delete_skill(self, skill_id: int) -> bool:
        """Delete a custom skill. Built-in skills cannot be deleted."""
        try:
            with self.db_manager.session_scope() as session:
                skill = session.query(Skill).filter_by(id=skill_id).first()
                if not skill:
                    self.skill_error.emit("Skill not found.")
                    return False
                if skill.is_builtin:
                    self.skill_error.emit("Built-in skills cannot be deleted.")
                    return False

                name = skill.name
                session.delete(skill)

            self.skills_changed.emit()
            logger.info(f"Deleted skill: {name}")
            return True
        except Exception as e:
            self.skill_error.emit(f"Failed to delete skill: {e}")
            return False

    def create_skill_from_agent(self, name: str, system_prompt: str,
                               tone: str = "professional",
                               preferred_tier: str = "haiku") -> dict:
        """Programmatically create a skill (called by agent engine).

        Returns dict with success flag and skill_id, or existing skill if duplicate.
        """
        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(Skill).filter_by(name=name).first()
                if existing:
                    return {"success": True, "skill_id": existing.id, "existing": True}

                skill = Skill(
                    name=name,
                    system_prompt=system_prompt,
                    tone=tone,
                    preferred_tier=preferred_tier,
                    is_builtin=False,
                )
                session.add(skill)
                session.flush()
                skill_id = skill.id

            self.skills_changed.emit()
            logger.info(f"Agent-created skill: '{name}' (#{skill_id})")
            return {"success": True, "skill_id": skill_id, "existing": False}
        except Exception as e:
            logger.error(f"Failed to create skill from agent: {e}")
            return {"success": False, "error": str(e)}

    def export_skill(self, skill_id: int, file_path: str) -> bool:
        """Export a skill to a JSON file with all enhanced fields."""
        try:
            skill = self.get_skill(skill_id)
            if not skill:
                self.skill_error.emit("Skill not found.")
                return False

            export_data = {
                "name": skill["name"],
                "system_prompt": skill["system_prompt"],
                "tone": skill["tone"],
                "description": skill["description"],
                "instructions": skill["instructions"],
                "category": skill["category"],
                "version": skill["version"],
                "capabilities": skill["capabilities"],
                "tags": skill["tags"],
                "input_schema": skill["input_schema"],
                "output_schema": skill["output_schema"],
                "examples": skill["examples"],
                "example_output": skill["example_output"],
                "preferred_tier": skill["preferred_tier"],
                "temperature": skill["temperature"],
                "max_tokens": skill["max_tokens"],
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported skill '{skill['name']}' to {file_path}")
            return True
        except Exception as e:
            self.skill_error.emit(f"Export failed: {e}")
            return False

    def import_skill(self, file_path: str) -> bool:
        """Import a skill from a JSON file with all enhanced fields."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            name = data.get("name", "")
            system_prompt = data.get("system_prompt", "")

            if not name or not system_prompt:
                self.skill_error.emit("Invalid skill file: missing name or prompt.")
                return False

            return self.create_skill(data)
        except json.JSONDecodeError:
            self.skill_error.emit("Invalid JSON file.")
            return False
        except Exception as e:
            self.skill_error.emit(f"Import failed: {e}")
            return False


def _apply_dict_to_skill(skill: Skill, data: dict):
    """Apply all fields from a dict to a Skill ORM object."""
    for field in _SKILL_FIELDS:
        if field in data:
            value = data[field]
            # Coerce numeric fields
            if field == "temperature":
                value = float(value) if value else 0.7
            elif field == "max_tokens":
                value = int(value) if value else 1024
            setattr(skill, field, value)
