"""
Aura — Reflection Engine
Post-action critique loop: evaluates agent task outputs, scores quality,
identifies improvements, and flags low-quality outputs for revision.
"""

import json
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import Agent, AgentReflection, PerformanceMetric, AgentLearnedRule, AgentTask
from config import REFLECTION_SCORE_THRESHOLD, REFLECTION_MAX_REVISIONS
from utils.logger import get_logger

logger = get_logger("reflection_engine")

# Critique prompt used when a router is available
REFLECTION_PROMPT = """You are a quality reviewer for an AI sales agent system.
Review the following agent output and provide a critique.

Task type: {task_type}
Agent output:
{output_text}

{context_section}

Score the output from 1-10 where:
1-3: Poor quality, major issues
4-5: Below average, notable problems
6-7: Acceptable, minor improvements possible
8-9: Good quality, well done
10: Excellent, no improvements needed

Respond ONLY with valid JSON (no other text):
{{"score": <int 1-10>, "reflection": "<what went well and what didn't>", "improvements": "<specific actionable improvements>"}}"""


class ReflectionEngine:
    """Evaluates agent task outputs, scores quality, and flags for revision."""

    def __init__(self, db_manager: DatabaseManager, router_engine=None):
        self.db_manager = db_manager
        self.router_engine = router_engine
        self.command_history = None  # Injected from main_window
        self.case_engine = None  # Injected from main_window
        self.self_improvement_engine = None  # Injected from main_window

    def reflect_on_task(self, agent_id: int, task_id: int, task_type: str,
                        output_text: str, context: str = "") -> dict:
        """
        Score output quality, store reflection, return whether revision is needed.

        Returns: {"success": bool, "data": {"score": int, "needs_revision": bool,
                  "reflection": str, "revision_count": int}, "error": str}
        """
        try:
            # Check existing revision count for this task
            existing_count = self._get_revision_count(task_id)
            if existing_count >= REFLECTION_MAX_REVISIONS:
                return {
                    "success": True,
                    "data": {
                        "score": 5,
                        "needs_revision": False,
                        "reflection": "Max revisions reached, accepting output as-is.",
                        "revision_count": existing_count,
                    },
                }

            # Get critique from LLM if router available, otherwise use default
            score, reflection_text, improvement_notes = self._evaluate(
                task_type, output_text, context
            )

            needs_revision = score < REFLECTION_SCORE_THRESHOLD

            # Store reflection
            with self.db_manager.session_scope() as session:
                reflection = AgentReflection(
                    agent_id=agent_id,
                    task_id=task_id,
                    task_type=task_type,
                    output_text=output_text[:5000],
                    reflection_text=reflection_text,
                    score=score,
                    improvement_notes=improvement_notes,
                    revision_count=existing_count + (1 if needs_revision else 0),
                    was_revised=needs_revision,
                )
                session.add(reflection)

            logger.info(
                f"Reflection: agent={agent_id} task={task_id} type={task_type} "
                f"score={score} needs_revision={needs_revision}"
            )

            if self.command_history:
                try:
                    self.command_history.log_command(
                        source="system",
                        command_type="reflection",
                        command_text=f"Task {task_id} scored {score}/10",
                        actor_type="system",
                        agent_id=agent_id,
                        linked_task_id=task_id,
                        status="completed",
                        parameters={
                            "task_type": task_type,
                            "score": score,
                            "needs_revision": needs_revision,
                        },
                    )
                except Exception:
                    pass

            # Log case note if this task involved a lead
            if self.case_engine:
                try:
                    with self.db_manager.session_scope() as s2:
                        task_row = s2.query(AgentTask).filter_by(id=task_id).first()
                        if task_row:
                            pl = json.loads(task_row.task_payload or "{}")
                            if pl.get("lead_id"):
                                self.case_engine.add_note(
                                    lead_id=pl["lead_id"],
                                    note_type="reflection",
                                    content=f"Score {score}/10 — {reflection_text[:200]}",
                                    agent_id=agent_id,
                                    metadata={"task_id": task_id, "score": score},
                                )
                except Exception:
                    pass

            # Auto-learn from low-score reflections
            if self.self_improvement_engine and improvement_notes:
                try:
                    with self.db_manager.session_scope() as s3:
                        agent_row = s3.query(Agent).filter_by(id=agent_id).first()
                        agent_name = agent_row.name if agent_row else None
                    if agent_name:
                        self.auto_learn_from_reflection(
                            agent_id, agent_name, score,
                            improvement_notes, task_type,
                        )
                except Exception:
                    pass

            return {
                "success": True,
                "data": {
                    "score": score,
                    "needs_revision": needs_revision,
                    "reflection": reflection_text,
                    "improvements": improvement_notes,
                    "revision_count": existing_count + (1 if needs_revision else 0),
                },
            }

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return {"success": False, "error": str(e)}

    def get_reflections(self, agent_id: int = None, task_type: str = None,
                        min_score: int = None, limit: int = 50) -> dict:
        """Query stored reflections with optional filters."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentReflection)
                if agent_id is not None:
                    query = query.filter(AgentReflection.agent_id == agent_id)
                if task_type is not None:
                    query = query.filter(AgentReflection.task_type == task_type)
                if min_score is not None:
                    query = query.filter(AgentReflection.score >= min_score)

                reflections = query.order_by(
                    AgentReflection.created_at.desc()
                ).limit(limit).all()

                items = [
                    {
                        "id": r.id,
                        "agent_id": r.agent_id,
                        "task_id": r.task_id,
                        "task_type": r.task_type,
                        "score": r.score,
                        "reflection_text": r.reflection_text,
                        "improvement_notes": r.improvement_notes,
                        "revision_count": r.revision_count,
                        "was_revised": r.was_revised,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in reflections
                ]

            return {"success": True, "data": items}

        except Exception as e:
            logger.error(f"get_reflections failed: {e}")
            return {"success": False, "error": str(e)}

    def get_average_score(self, agent_id: int = None, task_type: str = None,
                          days: int = 7) -> dict:
        """Calculate average reflection score over a period."""
        try:
            with self.db_manager.session_scope() as session:
                from sqlalchemy import func
                query = session.query(func.avg(AgentReflection.score))

                if agent_id is not None:
                    query = query.filter(AgentReflection.agent_id == agent_id)
                if task_type is not None:
                    query = query.filter(AgentReflection.task_type == task_type)

                cutoff = datetime.utcnow() - timedelta(days=days)
                query = query.filter(AgentReflection.created_at >= cutoff)

                avg_score = query.scalar()

            return {
                "success": True,
                "data": {
                    "average_score": round(float(avg_score), 2) if avg_score else 0.0,
                    "days": days,
                    "agent_id": agent_id,
                    "task_type": task_type,
                },
            }

        except Exception as e:
            logger.error(f"get_average_score failed: {e}")
            return {"success": False, "error": str(e)}

    def get_improvement_insights(self, agent_id: int = None, limit: int = 10) -> dict:
        """Return top improvement notes aggregated from low-score reflections."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentReflection).filter(
                    AgentReflection.score < REFLECTION_SCORE_THRESHOLD,
                    AgentReflection.improvement_notes != "",
                )
                if agent_id is not None:
                    query = query.filter(AgentReflection.agent_id == agent_id)

                low_reflections = query.order_by(
                    AgentReflection.created_at.desc()
                ).limit(limit).all()

                insights = [
                    {
                        "task_type": r.task_type,
                        "score": r.score,
                        "improvement_notes": r.improvement_notes,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in low_reflections
                ]

            return {"success": True, "data": insights}

        except Exception as e:
            logger.error(f"get_improvement_insights failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Private ──────────────────────────────────────────────

    def _evaluate(self, task_type: str, output_text: str,
                  context: str = "") -> tuple:
        """
        Evaluate output quality. Uses router if available, otherwise returns defaults.
        Returns: (score, reflection_text, improvement_notes)
        """
        if not self.router_engine:
            return 5, "No router available for evaluation.", ""

        try:
            context_section = f"Additional context:\n{context}" if context else ""
            prompt = REFLECTION_PROMPT.format(
                task_type=task_type,
                output_text=output_text[:3000],
                context_section=context_section,
            )

            result = self.router_engine.route("qualify_lead_basic", prompt)
            if not result.get("success"):
                return 5, "Router evaluation failed.", ""

            raw_text = result.get("data", "")
            parsed = json.loads(raw_text)

            score = max(1, min(10, int(parsed.get("score", 5))))
            reflection = parsed.get("reflection", "")
            improvements = parsed.get("improvements", "")

            return score, reflection, improvements

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse reflection response: {e}")
            return 5, "Could not parse evaluation response.", ""

    def _get_revision_count(self, task_id: int) -> int:
        """Get the current revision count for a task."""
        try:
            with self.db_manager.session_scope() as session:
                existing = session.query(AgentReflection).filter_by(
                    task_id=task_id
                ).order_by(AgentReflection.created_at.desc()).first()
                return existing.revision_count if existing else 0
        except Exception:
            return 0

    def auto_learn_from_reflection(self, agent_id: int, agent_name: str,
                                   score: int, improvement_notes: str,
                                   task_type: str) -> dict:
        """
        After a reflection, auto-extract a learned rule from improvement notes
        and store it scoped to the agent. Only triggers on low scores (<= 5)
        with non-empty improvement notes.
        """
        if score > 5 or not improvement_notes or not improvement_notes.strip():
            return {"success": True, "data": {"action": "skipped"}}

        if not self.self_improvement_engine:
            return {"success": False, "error": "No self_improvement_engine available"}

        try:
            # Extract a concise rule from improvement notes
            rule_text = improvement_notes.strip()
            if len(rule_text) > 200:
                rule_text = rule_text[:200]

            # Use LLM to extract a better rule if router available
            if self.router_engine:
                try:
                    prompt = (
                        f"Extract one concise imperative rule from this feedback "
                        f"for a '{task_type}' task:\n\n{improvement_notes[:500]}\n\n"
                        f"Respond with ONLY the rule as a single sentence, e.g. "
                        f"'Always include a specific CTA in outreach emails'."
                    )
                    result = self.router_engine.route("qualify_lead_basic", prompt)
                    if result.get("success") and result.get("data"):
                        extracted = result["data"].strip().strip('"').strip("'")
                        if 10 < len(extracted) < 200:
                            rule_text = extracted
                except Exception:
                    pass  # Fall back to raw improvement_notes

            # Check for duplicate before storing
            with self.db_manager.session_scope() as session:
                existing = session.query(AgentLearnedRule).filter_by(
                    rule_text=rule_text, is_active=True,
                ).first()
                if existing:
                    existing.evidence_count += 1
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                    return {"success": True, "data": {"action": "reinforced", "rule_id": existing.id}}

            result = self.self_improvement_engine.store_learned_rule(
                rule_type=task_type,
                rule_text=rule_text,
                confidence=max(0.3, (10 - score) / 10),
                evidence_count=1,
                agent_id=agent_id,
            )

            # Set agent_name on the rule
            if result.get("success") and result.get("data", {}).get("rule_id"):
                try:
                    with self.db_manager.session_scope() as session:
                        rule = session.query(AgentLearnedRule).filter_by(
                            id=result["data"]["rule_id"]
                        ).first()
                        if rule:
                            rule.agent_name = agent_name
                            rule.source = "auto_reflection"
                except Exception:
                    pass

            logger.info(
                f"Auto-learned rule for agent '{agent_name}': {rule_text[:60]}"
            )
            return result

        except Exception as e:
            logger.error(f"auto_learn_from_reflection failed: {e}")
            return {"success": False, "error": str(e)}
