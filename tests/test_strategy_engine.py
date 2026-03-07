"""
Tests for the Strategy Engine — goal CRUD, backward math, milestones, progress, cost.
"""

import pytest

from database.schema import StrategicGoal, GoalMilestone


# ─── Schema Tests ──────────────────────────────────────────────


class TestSchemaModels:

    def test_goal_creation(self, strategy_engine):
        engine, db = strategy_engine
        with db.session_scope() as s:
            goal = StrategicGoal(
                goal_text="Get 10 plumbing clients in Austin",
                target_metric="conversions", target_value=10,
                niche="plumbing", city="Austin",
            )
            s.add(goal)
            s.flush()
            assert goal.id is not None

    def test_milestone_creation(self, strategy_engine):
        engine, db = strategy_engine
        with db.session_scope() as s:
            goal = StrategicGoal(goal_text="Test", target_value=5)
            s.add(goal)
            s.flush()
            ms = GoalMilestone(
                goal_id=goal.id, phase=1,
                description="Scrape 100 leads", target_value=100,
            )
            s.add(ms)
            s.flush()
            assert ms.id is not None


# ─── Backward Math ────────────────────────────────────────────


class TestCalculatePlan:

    def test_conversions_plan(self, strategy_engine):
        engine, _ = strategy_engine
        result = engine.calculate_plan(10, "conversions")
        assert result["success"] is True
        d = result["data"]
        assert d["contacts_needed"] > d["emails_needed"] > d["replies_needed"]
        assert d["estimated_cost"] > 0

    def test_meetings_plan(self, strategy_engine):
        engine, _ = strategy_engine
        result = engine.calculate_plan(5, "meetings")
        assert result["success"] is True
        assert result["data"]["meetings_needed"] == 5

    def test_replies_plan(self, strategy_engine):
        engine, _ = strategy_engine
        result = engine.calculate_plan(20, "replies")
        assert result["success"] is True
        assert result["data"]["replies_needed"] == 20
        assert result["data"]["emails_needed"] >= 20

    def test_unknown_metric_fails(self, strategy_engine):
        engine, _ = strategy_engine
        result = engine.calculate_plan(10, "unknown_metric")
        assert result["success"] is False


# ─── Goal CRUD ─────────────────────────────────────────────────


class TestGoalCRUD:

    def test_create_goal(self, strategy_engine):
        engine, db = strategy_engine
        result = engine.create_goal(
            "Get 10 plumbing clients", target_metric="conversions",
            target_value=10, budget=50.0, niche="plumbing", city="Austin",
        )
        assert result["success"] is True
        assert "goal_id" in result["data"]
        assert "plan" in result["data"]

    def test_get_goal(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Test goal", target_value=5)
        goal_id = create["data"]["goal_id"]

        result = engine.get_goal(goal_id)
        assert result["success"] is True
        assert result["data"]["goal_text"] == "Test goal"
        assert len(result["data"]["milestones"]) == 5  # 5 phases

    def test_get_all_goals(self, strategy_engine):
        engine, db = strategy_engine
        engine.create_goal("Goal A", target_value=3)
        engine.create_goal("Goal B", target_value=7)

        result = engine.get_all_goals()
        assert result["success"] is True
        assert len(result["data"]) >= 2

    def test_get_goals_by_status(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Active goal", target_value=2)
        goal_id = create["data"]["goal_id"]
        engine.activate_goal(goal_id)

        result = engine.get_all_goals(status="active")
        assert any(g["goal_id"] == goal_id if "goal_id" in g else g["id"] == goal_id
                    for g in result["data"])


# ─── Goal Lifecycle ────────────────────────────────────────────


class TestGoalLifecycle:

    def test_activate_goal(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Activate me", target_value=5)
        goal_id = create["data"]["goal_id"]

        result = engine.activate_goal(goal_id)
        assert result["success"] is True
        assert result["data"]["status"] == "active"

        # First milestone should be active
        goal = engine.get_goal(goal_id)
        assert goal["data"]["milestones"][0]["status"] == "active"

    def test_update_progress(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Progress test", target_value=3)
        goal_id = create["data"]["goal_id"]

        # Complete 2 of 5 milestones
        with db.session_scope() as s:
            milestones = s.query(GoalMilestone).filter_by(goal_id=goal_id).order_by(GoalMilestone.phase).all()
            milestones[0].status = "completed"
            milestones[1].status = "completed"

        result = engine.update_progress(goal_id)
        assert result["success"] is True
        assert result["data"]["progress_pct"] == 40.0

    def test_complete_all_milestones(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Complete me", target_value=1)
        goal_id = create["data"]["goal_id"]

        # Complete all milestones
        with db.session_scope() as s:
            for ms in s.query(GoalMilestone).filter_by(goal_id=goal_id).all():
                ms.status = "completed"

        result = engine.update_progress(goal_id)
        assert result["data"]["progress_pct"] == 100.0

        goal = engine.get_goal(goal_id)
        assert goal["data"]["status"] == "completed"

    def test_execute_next_milestone(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Execute test", target_value=2)
        goal_id = create["data"]["goal_id"]

        result = engine.execute_next_milestone(goal_id)
        assert result["success"] is True
        assert result["data"]["phase"] == 1


# ─── Cost Summary ──────────────────────────────────────────────


class TestCostSummary:

    def test_cost_summary(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("Cost test", target_value=5, budget=100.0)
        goal_id = create["data"]["goal_id"]

        result = engine.get_goal_cost_summary(goal_id)
        assert result["success"] is True
        assert result["data"]["under_budget"] is True
        assert result["data"]["budget_usd"] == 100.0

    def test_cost_summary_no_budget(self, strategy_engine):
        engine, db = strategy_engine
        create = engine.create_goal("No budget", target_value=3)
        goal_id = create["data"]["goal_id"]

        result = engine.get_goal_cost_summary(goal_id)
        assert result["data"]["under_budget"] is True  # no budget = always under
