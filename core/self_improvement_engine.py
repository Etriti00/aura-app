"""
Aura — Self-Improvement Engine
Monitors agent performance, identifies underperformers, auto-generates
revised skills, learns rules from patterns, and orchestrates improvement cycles.
"""

import json
from datetime import datetime, timedelta

from database.db_manager import DatabaseManager
from database.schema import (
    PerformanceMetric, AgentLearnedRule, AgentReflection,
    Agent, Skill,
)
from config import (
    IMPROVEMENT_MIN_SAMPLES,
    IMPROVEMENT_REPLY_RATE_THRESHOLD,
    IMPROVEMENT_QUALITY_THRESHOLD,
)
from utils.logger import get_logger

logger = get_logger("self_improvement_engine")


class SelfImprovementEngine:
    """Monitors, analyzes, and improves agent and skill performance."""

    def __init__(self, db_manager: DatabaseManager, reflection_engine=None,
                 rag_engine=None, fleet_orchestrator=None, forge_controller=None):
        self.db_manager = db_manager
        self.reflection_engine = reflection_engine
        self.rag_engine = rag_engine
        self.fleet_orchestrator = fleet_orchestrator
        self.forge_controller = forge_controller

    # ─── Metric Recording ──────────────────────────────────────

    def record_metric(self, agent_id: int, metric_type: str,
                      metric_key: str, value: float,
                      sample_count: int = 1, period: str = "daily") -> dict:
        """Record a performance metric for an agent."""
        try:
            with self.db_manager.session_scope() as session:
                today = datetime.utcnow().strftime("%Y-%m-%d")

                # Upsert: update if same agent/type/key/period/date exists
                existing = session.query(PerformanceMetric).filter_by(
                    agent_id=agent_id,
                    metric_type=metric_type,
                    metric_key=metric_key,
                    period=period,
                    period_date=today,
                ).first()

                if existing:
                    # Weighted average update
                    total = existing.sample_count + sample_count
                    existing.value = (
                        (existing.value * existing.sample_count + value * sample_count)
                        / total
                    )
                    existing.sample_count = total
                    metric_id = existing.id
                else:
                    metric = PerformanceMetric(
                        agent_id=agent_id,
                        metric_type=metric_type,
                        metric_key=metric_key,
                        value=value,
                        sample_count=sample_count,
                        period=period,
                        period_date=today,
                    )
                    session.add(metric)
                    session.flush()
                    metric_id = metric.id

            return {"success": True, "data": {"metric_id": metric_id}}

        except Exception as e:
            logger.error(f"record_metric failed: {e}")
            return {"success": False, "error": str(e)}

    # ─── Performance Analysis ──────────────────────────────────

    def analyze_agent_performance(self, agent_id: int, period_days: int = 7) -> dict:
        """Analyze an agent's performance over a period."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).strftime("%Y-%m-%d")

            with self.db_manager.session_scope() as session:
                metrics = (
                    session.query(PerformanceMetric)
                    .filter(
                        PerformanceMetric.agent_id == agent_id,
                        PerformanceMetric.period_date >= cutoff,
                    )
                    .all()
                )

                by_type = {}
                for m in metrics:
                    if m.metric_type not in by_type:
                        by_type[m.metric_type] = []
                    by_type[m.metric_type].append({
                        "key": m.metric_key,
                        "value": m.value,
                        "samples": m.sample_count,
                        "date": m.period_date,
                    })

                # Get reflection average if available
                avg_score = 0.0
                if self.reflection_engine:
                    score_result = self.reflection_engine.get_average_score(
                        agent_id=agent_id, days=period_days
                    )
                    if score_result.get("success"):
                        avg_score = score_result["data"]["average_score"]

            return {
                "success": True,
                "data": {
                    "agent_id": agent_id,
                    "period_days": period_days,
                    "metrics_by_type": by_type,
                    "avg_reflection_score": avg_score,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_skill_performance(self, skill_id: int, period_days: int = 7) -> dict:
        """Analyze how a specific skill is performing (via reflections on tasks using it)."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=period_days)
            from sqlalchemy import func

            with self.db_manager.session_scope() as session:
                avg = (
                    session.query(func.avg(AgentReflection.score))
                    .filter(AgentReflection.created_at >= cutoff)
                    .scalar()
                )
                count = (
                    session.query(func.count(AgentReflection.id))
                    .filter(AgentReflection.created_at >= cutoff)
                    .scalar()
                )

            return {
                "success": True,
                "data": {
                    "skill_id": skill_id,
                    "avg_score": round(float(avg), 2) if avg else 0.0,
                    "total_reflections": count or 0,
                    "period_days": period_days,
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_niche_performance(self, niche: str, period_days: int = 30) -> dict:
        """Analyze performance metrics for a specific niche."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).strftime("%Y-%m-%d")

            with self.db_manager.session_scope() as session:
                metrics = (
                    session.query(PerformanceMetric)
                    .filter(
                        PerformanceMetric.metric_key == niche,
                        PerformanceMetric.period_date >= cutoff,
                    )
                    .all()
                )

                by_type = {}
                for m in metrics:
                    if m.metric_type not in by_type:
                        by_type[m.metric_type] = {"total_value": 0, "total_samples": 0}
                    by_type[m.metric_type]["total_value"] += m.value * m.sample_count
                    by_type[m.metric_type]["total_samples"] += m.sample_count

                averages = {}
                for mt, data in by_type.items():
                    if data["total_samples"] > 0:
                        averages[mt] = round(data["total_value"] / data["total_samples"], 4)

            return {
                "success": True,
                "data": {"niche": niche, "averages": averages, "period_days": period_days},
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Underperformer Detection ──────────────────────────────

    def identify_underperformers(self, metric_type: str = "reply_rate",
                                  threshold: float = None) -> dict:
        """Find agents whose metrics fall below the threshold."""
        threshold = threshold or IMPROVEMENT_REPLY_RATE_THRESHOLD

        try:
            with self.db_manager.session_scope() as session:
                from sqlalchemy import func

                subq = (
                    session.query(
                        PerformanceMetric.agent_id,
                        func.avg(PerformanceMetric.value).label("avg_val"),
                        func.sum(PerformanceMetric.sample_count).label("total_samples"),
                    )
                    .filter(PerformanceMetric.metric_type == metric_type)
                    .group_by(PerformanceMetric.agent_id)
                    .all()
                )

                underperformers = []
                for agent_id, avg_val, total_samples in subq:
                    if total_samples >= IMPROVEMENT_MIN_SAMPLES and avg_val < threshold:
                        underperformers.append({
                            "agent_id": agent_id,
                            "metric_type": metric_type,
                            "avg_value": round(float(avg_val), 4),
                            "total_samples": int(total_samples),
                        })

            return {"success": True, "data": underperformers}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Learned Rules ─────────────────────────────────────────

    def store_learned_rule(self, rule_type: str, rule_text: str,
                           confidence: float = 0.5,
                           evidence_count: int = 1,
                           agent_id: int = None) -> dict:
        """Store a learned rule/pattern."""
        try:
            with self.db_manager.session_scope() as session:
                rule = AgentLearnedRule(
                    agent_id=agent_id,
                    rule_type=rule_type,
                    rule_text=rule_text,
                    confidence=confidence,
                    evidence_count=evidence_count,
                    is_active=True,
                    source="auto",
                )
                session.add(rule)
                session.flush()
                rule_id = rule.id

            return {"success": True, "data": {"rule_id": rule_id}}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_active_rules(self, rule_type: str = None) -> dict:
        """Get all active learned rules, optionally filtered by type."""
        try:
            with self.db_manager.session_scope() as session:
                query = session.query(AgentLearnedRule).filter_by(is_active=True)
                if rule_type:
                    query = query.filter_by(rule_type=rule_type)

                rules = query.order_by(AgentLearnedRule.confidence.desc()).all()
                items = [
                    {
                        "id": r.id,
                        "rule_type": r.rule_type,
                        "rule_text": r.rule_text,
                        "confidence": r.confidence,
                        "evidence_count": r.evidence_count,
                        "agent_id": r.agent_id,
                        "source": r.source,
                    }
                    for r in rules
                ]

            return {"success": True, "data": items}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_learned_rules(self, min_evidence: int = 5) -> dict:
        """Extract new rules from performance patterns (placeholder for LLM analysis)."""
        try:
            with self.db_manager.session_scope() as session:
                from sqlalchemy import func

                # Find metric keys with enough samples and high variance
                candidates = (
                    session.query(
                        PerformanceMetric.metric_type,
                        PerformanceMetric.metric_key,
                        func.avg(PerformanceMetric.value).label("avg_val"),
                        func.sum(PerformanceMetric.sample_count).label("samples"),
                    )
                    .group_by(PerformanceMetric.metric_type, PerformanceMetric.metric_key)
                    .having(func.sum(PerformanceMetric.sample_count) >= min_evidence)
                    .all()
                )

                rules = []
                for metric_type, metric_key, avg_val, samples in candidates:
                    rule_text = (
                        f"For '{metric_key}', the average {metric_type} is "
                        f"{round(float(avg_val), 4)} across {int(samples)} samples."
                    )
                    rules.append({
                        "rule_type": metric_type,
                        "rule_text": rule_text,
                        "confidence": min(0.9, float(samples) / 100),
                        "evidence_count": int(samples),
                    })

            return {"success": True, "data": rules}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Improvement Cycle ─────────────────────────────────────

    def run_improvement_cycle(self) -> dict:
        """
        Orchestrate a full improvement cycle:
        1. Analyze performance across agents
        2. Identify underperformers
        3. Extract patterns into rules
        Returns summary of actions taken.
        """
        try:
            actions = []

            # Step 1: Identify underperformers
            under_result = self.identify_underperformers()
            if under_result["success"]:
                actions.append({
                    "step": "identify_underperformers",
                    "count": len(under_result["data"]),
                })

            # Step 2: Extract rules
            rules_result = self.extract_learned_rules()
            if rules_result["success"]:
                new_rules = 0
                for rule_data in rules_result["data"]:
                    store_result = self.store_learned_rule(
                        rule_type=rule_data["rule_type"],
                        rule_text=rule_data["rule_text"],
                        confidence=rule_data["confidence"],
                        evidence_count=rule_data["evidence_count"],
                    )
                    if store_result["success"]:
                        new_rules += 1
                actions.append({"step": "extract_rules", "new_rules": new_rules})

            logger.info(f"Improvement cycle complete: {actions}")
            return {"success": True, "data": {"actions": actions}}

        except Exception as e:
            logger.error(f"Improvement cycle failed: {e}")
            return {"success": False, "error": str(e)}
