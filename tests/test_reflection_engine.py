"""
Tests for the Reflection Engine — post-action critique loop.
"""

import pytest
from datetime import datetime, timedelta

from database.schema import (
    AgentReflection, PerformanceMetric, AgentLearnedRule,
    Agent, AgentTask,
)
from tests.conftest import get_agent_id_by_name


# ─── Schema Tests ─────────────────────────────────────────────


class TestSchemaModels:
    """Verify new ORM models create and persist correctly."""

    def test_agent_reflection_creation(self, db_with_agents):
        agent_id = get_agent_id_by_name(db_with_agents, "Scout")
        with db_with_agents.session_scope() as s:
            task = AgentTask(
                agent_id=agent_id, task_type="generate_email",
                status="completed", task_payload="{}"
            )
            s.add(task)
            s.flush()

            reflection = AgentReflection(
                agent_id=agent_id, task_id=task.id,
                task_type="generate_email", output_text="Hello world",
                reflection_text="Good email", score=8,
                improvement_notes="Add more personalization",
                revision_count=0, was_revised=False,
            )
            s.add(reflection)
            s.flush()
            assert reflection.id is not None
            assert reflection.score == 8

    def test_performance_metric_creation(self, db_with_agents):
        agent_id = get_agent_id_by_name(db_with_agents, "Closer")
        with db_with_agents.session_scope() as s:
            metric = PerformanceMetric(
                agent_id=agent_id, metric_type="reply_rate",
                metric_key="plumber", value=0.12, sample_count=50,
                period="weekly", period_date="2026-02-28",
            )
            s.add(metric)
            s.flush()
            assert metric.id is not None
            assert metric.value == 0.12

    def test_learned_rule_creation(self, db_with_agents):
        agent_id = get_agent_id_by_name(db_with_agents, "Analyst")
        with db_with_agents.session_scope() as s:
            rule = AgentLearnedRule(
                agent_id=agent_id, rule_type="timing",
                rule_text="Emails sent at 9am get 2x replies",
                confidence=0.85, evidence_count=42,
                is_active=True, source="auto",
            )
            s.add(rule)
            s.flush()
            assert rule.id is not None
            assert rule.confidence == 0.85


# ─── Reflection Engine Tests ──────────────────────────────────


def _create_task(db, agent_id, task_type="generate_email"):
    """Helper to create a completed task for reflection testing."""
    with db.session_scope() as s:
        task = AgentTask(
            agent_id=agent_id, task_type=task_type,
            status="completed", task_payload="{}", result="test output"
        )
        s.add(task)
        s.flush()
        return task.id


class TestReflectOnTask:
    """Test the core reflect_on_task method."""

    def test_stores_reflection(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        task_id = _create_task(db, agent_id)

        result = engine.reflect_on_task(
            agent_id=agent_id, task_id=task_id,
            task_type="generate_email",
            output_text="Dear business owner, we can help you grow.",
        )

        assert result["success"] is True
        assert "score" in result["data"]
        assert isinstance(result["data"]["score"], int)

    def test_default_score_without_router(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        task_id = _create_task(db, agent_id)

        result = engine.reflect_on_task(
            agent_id=agent_id, task_id=task_id,
            task_type="generate_email", output_text="Test output",
        )

        # Without router, defaults to score=5
        assert result["data"]["score"] == 5
        assert result["data"]["needs_revision"] is False

    def test_respects_max_revisions(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Scout")
        task_id = _create_task(db, agent_id, "qualify_lead")

        # Manually insert a reflection with revision_count = 2
        with db.session_scope() as s:
            existing = AgentReflection(
                agent_id=agent_id, task_id=task_id,
                task_type="qualify_lead", output_text="old",
                score=2, revision_count=2, was_revised=True,
            )
            s.add(existing)

        result = engine.reflect_on_task(
            agent_id=agent_id, task_id=task_id,
            task_type="qualify_lead", output_text="New attempt",
        )

        assert result["success"] is True
        assert result["data"]["needs_revision"] is False
        assert "Max revisions" in result["data"]["reflection"]

    def test_persists_to_database(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Qualifier")
        task_id = _create_task(db, agent_id, "qualify_lead")

        engine.reflect_on_task(
            agent_id=agent_id, task_id=task_id,
            task_type="qualify_lead", output_text="Lead score: 7/10",
        )

        with db.session_scope() as s:
            stored = s.query(AgentReflection).filter_by(task_id=task_id).first()
            assert stored is not None
            assert stored.agent_id == agent_id
            assert stored.task_type == "qualify_lead"
            assert stored.score == 5  # default without router


class TestGetReflections:
    """Test querying stored reflections."""

    def _seed_reflections(self, db, agent_id, count=5, task_type="generate_email"):
        """Seed N reflections for testing."""
        task_ids = []
        for i in range(count):
            tid = _create_task(db, agent_id, task_type)
            task_ids.append(tid)
        with db.session_scope() as s:
            for i, tid in enumerate(task_ids):
                s.add(AgentReflection(
                    agent_id=agent_id, task_id=tid,
                    task_type=task_type, output_text=f"output {i}",
                    score=i + 3, reflection_text=f"reflection {i}",
                    improvement_notes=f"improve {i}" if i < 3 else "",
                ))

    def test_get_all_reflections(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        self._seed_reflections(db, agent_id, 5)

        result = engine.get_reflections()
        assert result["success"] is True
        assert len(result["data"]) == 5

    def test_filter_by_agent(self, reflection_engine):
        engine, db = reflection_engine
        closer_id = get_agent_id_by_name(db, "Closer")
        scout_id = get_agent_id_by_name(db, "Scout")
        self._seed_reflections(db, closer_id, 3)
        self._seed_reflections(db, scout_id, 2, "qualify_lead")

        result = engine.get_reflections(agent_id=closer_id)
        assert len(result["data"]) == 3
        assert all(r["agent_id"] == closer_id for r in result["data"])

    def test_filter_by_task_type(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        self._seed_reflections(db, agent_id, 3, "generate_email")
        self._seed_reflections(db, agent_id, 2, "qualify_lead")

        result = engine.get_reflections(task_type="qualify_lead")
        assert len(result["data"]) == 2

    def test_filter_by_min_score(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        self._seed_reflections(db, agent_id, 5)  # scores: 3, 4, 5, 6, 7

        result = engine.get_reflections(min_score=6)
        assert len(result["data"]) == 2
        assert all(r["score"] >= 6 for r in result["data"])


class TestAverageScore:
    """Test average score calculation."""

    def test_average_score(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")
        for i in range(4):
            tid = _create_task(db, agent_id)
            with db.session_scope() as s:
                s.add(AgentReflection(
                    agent_id=agent_id, task_id=tid,
                    task_type="generate_email", score=(i + 1) * 2,
                ))
        # Scores: 2, 4, 6, 8 → avg = 5.0
        result = engine.get_average_score(agent_id=agent_id)
        assert result["success"] is True
        assert result["data"]["average_score"] == 5.0

    def test_average_score_respects_days_filter(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        # Recent reflection
        tid1 = _create_task(db, agent_id)
        with db.session_scope() as s:
            s.add(AgentReflection(
                agent_id=agent_id, task_id=tid1,
                task_type="generate_email", score=8,
                created_at=datetime.utcnow(),
            ))

        # Old reflection (30 days ago)
        tid2 = _create_task(db, agent_id)
        with db.session_scope() as s:
            s.add(AgentReflection(
                agent_id=agent_id, task_id=tid2,
                task_type="generate_email", score=2,
                created_at=datetime.utcnow() - timedelta(days=30),
            ))

        # 7-day window should only include the recent one
        result = engine.get_average_score(agent_id=agent_id, days=7)
        assert result["data"]["average_score"] == 8.0

    def test_average_score_no_data(self, reflection_engine):
        engine, db = reflection_engine
        result = engine.get_average_score(agent_id=99999)
        assert result["data"]["average_score"] == 0.0


class TestImprovementInsights:
    """Test improvement insights from low-score reflections."""

    def test_returns_low_score_notes(self, reflection_engine):
        engine, db = reflection_engine
        agent_id = get_agent_id_by_name(db, "Closer")

        for score, notes in [(2, "Fix greeting"), (3, "Add CTA"), (7, "")]:
            tid = _create_task(db, agent_id)
            with db.session_scope() as s:
                s.add(AgentReflection(
                    agent_id=agent_id, task_id=tid,
                    task_type="generate_email", score=score,
                    improvement_notes=notes,
                ))

        result = engine.get_improvement_insights()
        assert result["success"] is True
        # Only score < 4 with non-empty notes
        assert len(result["data"]) == 2
        notes_texts = [i["improvement_notes"] for i in result["data"]]
        assert "Fix greeting" in notes_texts
        assert "Add CTA" in notes_texts
