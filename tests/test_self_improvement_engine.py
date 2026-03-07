"""
Tests for the Self-Improvement Engine — metrics, performance analysis,
underperformer detection, learned rules, improvement cycles.
"""

import pytest

from database.schema import PerformanceMetric, AgentLearnedRule, AgentReflection, AgentTask
from tests.conftest import get_agent_id_by_name


# ─── Metric Recording ─────────────────────────────────────────


class TestMetricRecording:

    def test_record_metric(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        result = engine.record_metric(
            agent_id=agent_id, metric_type="reply_rate",
            metric_key="plumbing", value=0.08, sample_count=25,
        )
        assert result["success"] is True
        assert "metric_id" in result["data"]

    def test_record_metric_upserts(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        engine.record_metric(agent_id, "quality_score", "email", 7.0, 10)
        engine.record_metric(agent_id, "quality_score", "email", 9.0, 10)

        # Should be weighted average: (7*10 + 9*10) / 20 = 8.0
        with db.session_scope() as s:
            m = s.query(PerformanceMetric).filter_by(
                agent_id=agent_id, metric_type="quality_score", metric_key="email"
            ).first()
            assert m is not None
            assert m.sample_count == 20
            assert abs(m.value - 8.0) < 0.01


# ─── Performance Analysis ─────────────────────────────────────


class TestPerformanceAnalysis:

    def test_analyze_agent_performance(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        engine.record_metric(agent_id, "reply_rate", "hvac", 0.06, 30)
        engine.record_metric(agent_id, "open_rate", "hvac", 0.25, 30)

        result = engine.analyze_agent_performance(agent_id, period_days=7)
        assert result["success"] is True
        assert "reply_rate" in result["data"]["metrics_by_type"]

    def test_analyze_skill_performance(self, self_improvement_engine):
        engine, db = self_improvement_engine
        # Seed some reflections
        agent_id = get_agent_id_by_name(db, "Closer")
        with db.session_scope() as s:
            task = AgentTask(agent_id=agent_id, task_type="generate_email", status="completed")
            s.add(task)
            s.flush()
            s.add(AgentReflection(
                agent_id=agent_id, task_id=task.id,
                task_type="generate_email", score=7,
            ))

        result = engine.analyze_skill_performance(skill_id=1, period_days=7)
        assert result["success"] is True
        assert result["data"]["total_reflections"] >= 1

    def test_analyze_niche_performance(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Scout")

        engine.record_metric(agent_id, "reply_rate", "plumbing_niche", 0.04, 50)

        result = engine.analyze_niche_performance("plumbing_niche", period_days=30)
        assert result["success"] is True
        assert "averages" in result["data"]


# ─── Underperformer Detection ──────────────────────────────────


class TestUnderperformers:

    def test_identify_underperformers(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        # Record enough low-performing metrics
        engine.record_metric(agent_id, "reply_rate", "test_under", 0.02, 15)

        result = engine.identify_underperformers(metric_type="reply_rate", threshold=0.05)
        assert result["success"] is True
        # Should find at least one underperformer
        agent_ids = [u["agent_id"] for u in result["data"]]
        assert agent_id in agent_ids

    def test_no_underperformers_when_above_threshold(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Scout")

        engine.record_metric(agent_id, "open_rate", "high_perf", 0.50, 20)

        result = engine.identify_underperformers(metric_type="open_rate", threshold=0.10)
        assert result["success"] is True
        agent_ids = [u["agent_id"] for u in result["data"]]
        assert agent_id not in agent_ids


# ─── Learned Rules ─────────────────────────────────────────────


class TestLearnedRules:

    def test_store_and_get_rules(self, self_improvement_engine):
        engine, db = self_improvement_engine

        engine.store_learned_rule("timing", "Send emails at 9am for best results", 0.85, 42)
        engine.store_learned_rule("content", "Mention local competitors for higher engagement", 0.70, 20)

        result = engine.get_active_rules()
        assert result["success"] is True
        assert len(result["data"]) >= 2

    def test_filter_rules_by_type(self, self_improvement_engine):
        engine, db = self_improvement_engine

        engine.store_learned_rule("timing", "Tuesday mornings work best", 0.80, 30)

        result = engine.get_active_rules(rule_type="timing")
        assert result["success"] is True
        assert all(r["rule_type"] == "timing" for r in result["data"])

    def test_extract_learned_rules(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        # Seed enough metrics
        engine.record_metric(agent_id, "reply_rate", "extraction_test", 0.08, 20)

        result = engine.extract_learned_rules(min_evidence=5)
        assert result["success"] is True
        assert isinstance(result["data"], list)


# ─── Improvement Cycle ─────────────────────────────────────────


class TestImprovementCycle:

    def test_run_improvement_cycle(self, self_improvement_engine):
        engine, db = self_improvement_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        engine.record_metric(agent_id, "reply_rate", "cycle_test", 0.03, 15)

        result = engine.run_improvement_cycle()
        assert result["success"] is True
        assert "actions" in result["data"]
        step_names = [a["step"] for a in result["data"]["actions"]]
        assert "identify_underperformers" in step_names
        assert "extract_rules" in step_names
