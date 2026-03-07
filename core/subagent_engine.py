"""
Aura — Subagent Engine
Decomposes complex agent tasks into atomic subtasks, each with minimal context,
executed sequentially on cheaper models and composed into a final result.
Feature 2: Subagents System.
"""

import json
from datetime import datetime

from database.db_manager import DatabaseManager
from database.schema import SubagentTask, AgentTask
from config import (
    SUBAGENT_MAX_SUBTASKS,
    SUBAGENT_DEFAULT_TIER,
    SUBAGENT_DECOMPOSITION_MAP,
)
from utils.logger import get_logger

logger = get_logger("subagent_engine")

# Prompt templates for each subtask type
SUBTASK_PROMPTS = {
    "extract_lead_insights": (
        "Analyze the following lead information. Extract key business facts, "
        "potential pain points, and opportunities for outreach. Be concise.\n\n"
        "{lead_context}"
    ),
    "draft_email": (
        "{skill_prompt}\n\n"
        "LEAD INSIGHTS:\n{previous_output}\n\n"
        "SENDER: {sender_name} from {sender_company}\n\n"
        "Write a personalized cold outreach email for this lead. "
        "Output ONLY the email with Subject: line and Body."
    ),
    "review_tone": (
        "Review this email draft and improve its tone to be {tone}. "
        "Fix any awkward phrasing. Keep the same structure and facts. "
        "Output ONLY the improved email.\n\n{previous_output}"
    ),
    "check_website": (
        "Analyze this business information and assess their web presence:\n\n"
        "{lead_context}\n\n"
        "Provide a brief assessment of their digital maturity and potential needs."
    ),
    "assess_fit": (
        "Based on this website assessment:\n{previous_output}\n\n"
        "And these targeting criteria:\n"
        "Niche: {niche}\nCity: {city}\n\n"
        "Assess how well this lead fits our ideal customer profile. "
        "Score 1-10 and explain briefly."
    ),
    "score_lead": (
        "Based on this fit assessment:\n{previous_output}\n\n"
        "Provide a final lead qualification score (1-100) with a brief rationale. "
        "Output as JSON: {{\"score\": N, \"rationale\": \"...\", \"recommended_action\": \"...\"}}"
    ),
}


class SubagentEngine:
    """Decomposes complex tasks into atomic subtasks on cheaper models."""

    def __init__(self, db_manager: DatabaseManager, router_engine=None):
        self.db_manager = db_manager
        self.router_engine = router_engine

    def should_decompose(self, task_type: str) -> bool:
        """Return True if this task_type has a decomposition pattern defined."""
        return task_type in SUBAGENT_DECOMPOSITION_MAP

    def decompose_and_run(self, parent_task_id: int, task_type: str,
                          payload: dict, lead_context: str = "",
                          skill_data: dict = None) -> dict:
        """
        Decompose task into subtasks and execute sequentially.
        Returns {"success": bool, "result": str, "subtask_ids": [],
                 "total_cost_usd": float, "total_tokens": int, "decomposed": bool}.
        """
        patterns = SUBAGENT_DECOMPOSITION_MAP.get(task_type)
        if not patterns:
            return {"success": True, "decomposed": False}

        if not self.router_engine:
            return {
                "success": False, "decomposed": False,
                "error": "No router engine available",
            }

        subtask_ids = []
        total_cost = 0.0
        total_tokens = 0
        previous_output = ""
        final_output = ""

        try:
            for pattern in patterns[:SUBAGENT_MAX_SUBTASKS]:
                subtask_type = pattern["type"]
                tier = pattern.get("tier", SUBAGENT_DEFAULT_TIER)

                # Build minimal prompt for this subtask
                prompt = self._build_subtask_prompt(
                    subtask_type, lead_context, previous_output,
                    payload, skill_data,
                )

                # Create DB record
                with self.db_manager.session_scope() as session:
                    record = SubagentTask(
                        parent_task_id=parent_task_id,
                        subtask_type=subtask_type,
                        input_json=json.dumps({
                            "prompt_length": len(prompt),
                            "tier": tier,
                        }),
                        status="running",
                        tier=tier,
                        started_at=datetime.utcnow(),
                    )
                    session.add(record)
                    session.flush()
                    record_id = record.id

                # Execute via router
                subtask_max_tokens = pattern.get("max_tokens", 512)
                result = self.run_subtask(record_id, prompt, tier, max_tokens=subtask_max_tokens)

                if result.get("success"):
                    previous_output = result["output"]
                    final_output = previous_output
                    total_cost += result.get("cost_usd", 0.0)
                    total_tokens += result.get("tokens", 0)
                    subtask_ids.append(record_id)
                else:
                    # Subtask failed — mark and bail
                    logger.warning(
                        f"Subtask '{subtask_type}' failed for parent {parent_task_id}: "
                        f"{result.get('error', 'unknown')}"
                    )
                    return {
                        "success": False,
                        "decomposed": True,
                        "result": previous_output,
                        "subtask_ids": subtask_ids,
                        "total_cost_usd": total_cost,
                        "total_tokens": total_tokens,
                        "error": f"Subtask '{subtask_type}' failed",
                    }

            return {
                "success": True,
                "decomposed": True,
                "result": final_output,
                "subtask_ids": subtask_ids,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens,
            }
        except Exception as e:
            logger.error(f"Decompose and run failed for parent {parent_task_id}: {e}")
            return {
                "success": False,
                "decomposed": True,
                "error": str(e),
                "subtask_ids": subtask_ids,
                "total_cost_usd": total_cost,
                "total_tokens": total_tokens,
            }

    def run_subtask(self, subtask_record_id: int, prompt: str,
                    tier: str = SUBAGENT_DEFAULT_TIER,
                    max_tokens: int = 512) -> dict:
        """Execute a single subtask via router_engine. Updates SubagentTask row."""
        try:
            result = self.router_engine.route(
                "agent_triage", prompt,
                context={"max_tokens": max_tokens, "temperature": 0.5},
            )

            tokens = result.get("tokens", 0)
            cost = result.get("cost_usd", 0.0)
            output = result.get("data", "") if result.get("success") else ""
            status = "completed" if result.get("success") else "failed"

            # Update DB record
            with self.db_manager.session_scope() as session:
                record = (
                    session.query(SubagentTask)
                    .filter_by(id=subtask_record_id)
                    .first()
                )
                if record:
                    record.status = status
                    record.output_json = json.dumps({"output": output[:5000]})
                    record.tokens_used = tokens
                    record.cost_usd = cost
                    record.completed_at = datetime.utcnow()

            return {
                "success": result.get("success", False),
                "output": output,
                "tokens": tokens,
                "cost_usd": cost,
            }
        except Exception as e:
            logger.error(f"Subtask {subtask_record_id} execution failed: {e}")
            # Mark as failed
            try:
                with self.db_manager.session_scope() as session:
                    record = (
                        session.query(SubagentTask)
                        .filter_by(id=subtask_record_id)
                        .first()
                    )
                    if record:
                        record.status = "failed"
                        record.completed_at = datetime.utcnow()
            except Exception:
                pass
            return {"success": False, "error": str(e), "output": "", "tokens": 0}

    def get_subtasks_for_parent(self, parent_task_id: int) -> dict:
        """Query all SubagentTask rows for a parent task."""
        try:
            with self.db_manager.session_scope() as session:
                subtasks = (
                    session.query(SubagentTask)
                    .filter_by(parent_task_id=parent_task_id)
                    .order_by(SubagentTask.created_at.asc())
                    .all()
                )
                data = [
                    {
                        "id": s.id,
                        "parent_task_id": s.parent_task_id,
                        "subtask_type": s.subtask_type,
                        "status": s.status,
                        "tier": s.tier,
                        "tokens_used": s.tokens_used,
                        "cost_usd": s.cost_usd,
                        "output": json.loads(s.output_json or "{}").get("output", ""),
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    }
                    for s in subtasks
                ]
            return {"success": True, "data": data}
        except Exception as e:
            logger.error(f"Failed to get subtasks for parent {parent_task_id}: {e}")
            return {"success": False, "data": [], "error": str(e)}

    def _build_subtask_prompt(self, subtask_type: str, lead_context: str,
                              previous_output: str, payload: dict,
                              skill_data: dict = None) -> str:
        """Build a minimal prompt for a specific subtask type."""
        template = SUBTASK_PROMPTS.get(subtask_type, "{lead_context}\n\nTask: {subtask_type}")

        return template.format(
            lead_context=lead_context or "(no lead context)",
            previous_output=previous_output or "(no prior output)",
            skill_prompt=(skill_data or {}).get("system_prompt", ""),
            sender_name=payload.get("sender_name", ""),
            sender_company=payload.get("sender_company", ""),
            tone=(skill_data or {}).get("tone", "professional"),
            niche=payload.get("niche", payload.get("category", "")),
            city=payload.get("city", ""),
            subtask_type=subtask_type,
        )
