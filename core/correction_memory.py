"""
Aura — Correction Memory Engine
Detects user corrections in chat, extracts rules via LLM, persists to
AgentLearnedRule, and injects them into future agent prompts.

Inspired by Claude Code's MEMORY.md pattern.
"""

import json
import os
from typing import Optional

from database.db_manager import DatabaseManager
from database.schema import AgentLearnedRule
from utils.logger import get_logger

logger = get_logger("correction_memory")

# Phrases that signal a correction
CORRECTION_SIGNALS = [
    "no, ", "not like that", "wrong", "incorrect", "don't ",
    "stop ", "never ", "always ", "instead ", "actually ",
    "i told you", "i said", "remember to", "make sure",
    "you should", "please don't", "that's not", "fix this",
]

EXTRACTION_PROMPT = """Analyze this user message for correction intent.
If the user is correcting the AI's behavior, extract a concise rule.

User message: "{message}"
Previous AI response summary: "{prev_response}"

Respond with JSON only:
{{
  "is_correction": true/false,
  "rule": "<concise imperative rule, e.g. 'Always use formal tone in emails'>",
  "rule_type": "<one of: tone, format, content, workflow, persona>",
  "confidence": <0.0-1.0>
}}"""

MAX_RULES_PER_AGENT = 10
MAX_MEMORY_TOKENS = 500


class CorrectionMemory:
    """Detects corrections and stores them as learned rules."""

    def __init__(self, db_manager: DatabaseManager, key_vault=None):
        self.db_manager = db_manager
        self.key_vault = key_vault

    def looks_like_correction(self, message: str) -> bool:
        """Quick heuristic check — does this message look like a correction?"""
        lower = message.lower().strip()
        return any(lower.startswith(s) or f" {s}" in f" {lower}" for s in CORRECTION_SIGNALS)

    def extract_and_store(self, message: str, prev_response: str = "",
                          agent_name: str = None) -> Optional[dict]:
        """
        Use LLM to extract a rule from a correction, then persist it.
        Returns the stored rule dict or None.
        """
        try:
            settings = self.db_manager.get_settings()
            if not settings:
                return None

            # Build API keys
            api_keys = {}
            if self.key_vault:
                for attr, provider in [
                    ("gemini_key_enc", "gemini"),
                    ("anthropic_key_enc", "anthropic"),
                    ("openai_key_enc", "openai"),
                    ("openrouter_key_enc", "openrouter"),
                ]:
                    enc = getattr(settings, attr, None)
                    if enc:
                        val = self.key_vault.decrypt(enc)
                        if val:
                            api_keys[provider] = val

            _sub_available = any(
                getattr(settings, m, "none") == "subscription"
                for m in ("anthropic_auth_mode", "gemini_auth_mode", "openai_auth_mode")
            )
            if not api_keys and not _sub_available:
                return self._store_raw_rule(message, agent_name)

            # Set env vars for litellm
            for provider, key in api_keys.items():
                env_map = {
                    "gemini": "GEMINI_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "openrouter": "OPENROUTER_API_KEY",
                }
                if provider in env_map:
                    os.environ[env_map[provider]] = key

            # Use cheapest model
            model = getattr(settings, "tier2_model", None) or "gemini/gemini-2.0-flash"

            prompt = EXTRACTION_PROMPT.format(
                message=message[:500],
                prev_response=(prev_response or "")[:300],
            )

            # Subscription modes route through provider CLIs (no API key)
            from core.cli_llm import strip_code_fences, try_subscription_route
            _messages = [{"role": "user", "content": prompt}]
            handled, raw = try_subscription_route(settings, model, _messages)
            if handled:
                if not raw:
                    return self._store_raw_rule(message, agent_name)
                raw = strip_code_fences(raw)
            else:
                import litellm
                response = litellm.completion(
                    model=model,
                    messages=_messages,
                    max_tokens=200,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )

                raw = response.choices[0].message.content.strip()
            data = json.loads(raw)

            if not data.get("is_correction"):
                return None

            rule_text = data.get("rule", "").strip()
            if not rule_text:
                return None

            return self._store_rule(
                rule_text=rule_text,
                rule_type=data.get("rule_type", "general"),
                confidence=data.get("confidence", 0.7),
                agent_name=agent_name,
                source="user_correction",
            )

        except Exception as e:
            logger.error(f"Correction extraction failed: {e}")
            return self._store_raw_rule(message, agent_name)

    def _store_raw_rule(self, message: str, agent_name: str = None) -> Optional[dict]:
        """Fallback: store the raw message as a rule when LLM is unavailable."""
        cleaned = message.strip()[:200]
        if len(cleaned) < 5:
            return None
        return self._store_rule(
            rule_text=cleaned,
            rule_type="general",
            confidence=0.5,
            agent_name=agent_name,
            source="user_correction",
        )

    def _store_rule(self, rule_text: str, rule_type: str,
                    confidence: float, agent_name: str = None,
                    source: str = "user_correction") -> Optional[dict]:
        """Persist a learned rule to the database."""
        try:
            with self.db_manager.session_scope() as session:
                # Check for duplicate
                existing = session.query(AgentLearnedRule).filter_by(
                    rule_text=rule_text, is_active=True,
                ).first()
                if existing:
                    existing.evidence_count += 1
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                    return {"rule_id": existing.id, "action": "reinforced"}

                rule = AgentLearnedRule(
                    rule_type=rule_type,
                    rule_text=rule_text,
                    confidence=confidence,
                    evidence_count=1,
                    is_active=True,
                    source=source,
                    agent_name=agent_name,
                )
                session.add(rule)
                session.flush()
                rule_id = rule.id

            logger.info(f"Stored correction rule #{rule_id}: {rule_text[:60]}")
            return {"rule_id": rule_id, "action": "created"}

        except Exception as e:
            logger.error(f"Failed to store correction rule: {e}")
            return None

    def get_rules_for_context(self, agent_name: str = None,
                              max_rules: int = MAX_RULES_PER_AGENT) -> str:
        """
        Build a memory context string for injection into agent prompts.
        Returns empty string if no rules.
        """
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentLearnedRule).filter_by(is_active=True)

                # Get agent-specific + global rules
                if agent_name:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            AgentLearnedRule.agent_name == agent_name,
                            AgentLearnedRule.agent_name.is_(None),
                        )
                    )

                rules = query.order_by(
                    AgentLearnedRule.confidence.desc()
                ).limit(max_rules).all()

                if not rules:
                    return ""

                lines = ["LEARNED_RULES (follow these strictly):"]
                for r in rules:
                    lines.append(f"- [{r.rule_type}] {r.rule_text}")

                result = "\n".join(lines)
                # Cap at MAX_MEMORY_TOKENS (~4 chars per token)
                if len(result) > MAX_MEMORY_TOKENS * 4:
                    result = result[:MAX_MEMORY_TOKENS * 4]

                return result

        except Exception as e:
            logger.error(f"Failed to get correction rules: {e}")
            return ""

    def clear_rules(self, agent_name: str = None) -> dict:
        """Deactivate all rules, optionally scoped to an agent."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentLearnedRule).filter_by(
                    is_active=True, source="user_correction",
                )
                if agent_name:
                    query = query.filter_by(agent_name=agent_name)

                count = query.update({"is_active": False})

            return {"success": True, "data": {"cleared": count}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_rules(self, agent_name: str = None) -> dict:
        """List all active learned rules."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentLearnedRule).filter_by(is_active=True)
                if agent_name:
                    from sqlalchemy import or_
                    query = query.filter(
                        or_(
                            AgentLearnedRule.agent_name == agent_name,
                            AgentLearnedRule.agent_name.is_(None),
                        )
                    )

                rules = query.order_by(AgentLearnedRule.confidence.desc()).all()

                return {
                    "success": True,
                    "data": [
                        {
                            "id": r.id,
                            "type": r.rule_type,
                            "text": r.rule_text,
                            "confidence": r.confidence,
                            "source": r.source,
                            "agent_name": r.agent_name,
                        }
                        for r in rules
                    ],
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
