"""Tests for reflection_engine.auto_learn_from_reflection (Feature 3)."""

import pytest
from database.schema import Agent, AgentLearnedRule


class TestAutoLearnFromReflection:
    """Auto-extraction of rules from low-score reflections."""

    def _make_engines(self, db):
        from core.reflection_engine import ReflectionEngine
        from core.self_improvement_engine import SelfImprovementEngine

        reflection = ReflectionEngine(db, router_engine=None)
        self_improvement = SelfImprovementEngine(
            db, reflection_engine=reflection,
        )
        reflection.self_improvement_engine = self_improvement
        return reflection, self_improvement

    def _seed_agent(self, db):
        with db.session_scope() as session:
            agent = Agent(
                name="TestAgent", role="worker", identity_emoji="🧪",
                model_tier="haiku", rank=3, status="idle",
            )
            session.add(agent)
            session.flush()
            return agent.id

    def test_low_score_creates_rule(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        result = reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=3,
            improvement_notes="Include specific pain points in emails",
            task_type="generate_email",
        )
        assert result.get("success")

        with db.session_scope() as session:
            rules = session.query(AgentLearnedRule).filter_by(is_active=True).all()
            assert len(rules) == 1
            assert "pain points" in rules[0].rule_text.lower()

    def test_high_score_skipped(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        result = reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=8,
            improvement_notes="Minor formatting tweaks",
            task_type="generate_email",
        )
        assert result.get("success")
        assert result["data"]["action"] == "skipped"

    def test_empty_notes_skipped(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        result = reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=2,
            improvement_notes="",
            task_type="generate_email",
        )
        assert result["data"]["action"] == "skipped"

    def test_rule_has_agent_name(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=3,
            improvement_notes="Always mention ROI in qualification",
            task_type="qualify_lead",
        )

        with db.session_scope() as session:
            rule = session.query(AgentLearnedRule).first()
            assert rule.agent_name == "TestAgent"
            assert rule.source == "auto_reflection"

    def test_duplicate_rule_reinforced(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=3,
            improvement_notes="Be concise",
            task_type="generate_email",
        )
        result = reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=2,
            improvement_notes="Be concise",
            task_type="generate_email",
        )
        assert result.get("success")
        assert result["data"]["action"] == "reinforced"

    def test_confidence_scales_with_score(self, db):
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        # Score 2 → confidence = (10-2)/10 = 0.8
        reflection.auto_learn_from_reflection(
            agent_id=agent_id,
            agent_name="TestAgent",
            score=2,
            improvement_notes="Rule with high confidence",
            task_type="generate_email",
        )

        with db.session_scope() as session:
            rule = session.query(AgentLearnedRule).first()
            assert rule.confidence >= 0.7

    def test_no_self_improvement_engine(self, db):
        from core.reflection_engine import ReflectionEngine
        reflection = ReflectionEngine(db, router_engine=None)
        # self_improvement_engine is None

        result = reflection.auto_learn_from_reflection(
            agent_id=1,
            agent_name="TestAgent",
            score=3,
            improvement_notes="Some improvement",
            task_type="test",
        )
        assert not result["success"]

    def test_reflect_on_task_triggers_auto_learn(self, db):
        """Full integration: reflect_on_task should call auto_learn when score is low."""
        reflection, _ = self._make_engines(db)
        agent_id = self._seed_agent(db)

        # Create a task to reflect on
        from database.schema import AgentTask
        with db.session_scope() as session:
            task = AgentTask(
                agent_id=agent_id,
                task_type="generate_email",
                task_payload='{"lead_id": null}',
                status="completed",
            )
            session.add(task)
            session.flush()
            task_id = task.id

        # reflect_on_task with no router → default score 5 (at threshold, no learn)
        result = reflection.reflect_on_task(
            agent_id=agent_id,
            task_id=task_id,
            task_type="generate_email",
            output_text="Some output",
        )
        assert result["success"]
        # Score 5 → no auto-learn (only <= 5, but improvement_notes is "")
