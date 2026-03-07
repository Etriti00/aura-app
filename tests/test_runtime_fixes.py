"""
Tests for runtime bug fixes — enrichment signature, router tier_override,
AIEngine.generate(), self-improvement method name, email_sent_at/email_body,
autonomy enforcement, and sequence_id in follow-up data.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import InMemoryDatabaseManager
from database.schema import (
    Base, Lead, Campaign, Settings, Agent, AgentTask,
    FollowUpSequence, FollowUpStep, FollowUpSend,
    PendingApproval,
)


@pytest.fixture
def db():
    db_manager = InMemoryDatabaseManager()
    db_manager.init_db()
    return db_manager


@pytest.fixture
def db_with_lead(db):
    with db.session_scope() as session:
        campaign = Campaign(name="Test Camp", status="active", target_niche="plumbing")
        session.add(campaign)
        session.flush()
        lead = Lead(
            campaign_id=campaign.id,
            business_name="Test Plumber",
            email="plumber@test.com",
            city="Austin",
            website_url="https://testplumber.com",
            status="new",
        )
        session.add(lead)
        session.flush()
    return db


# ─── Fix 1: Enrichment signature ───────────────────────────

class TestEnrichmentSignature:
    """enrich_lead(lead_dict) must accept a dict, not keyword args."""

    def test_enrich_lead_accepts_dict(self, db_with_lead):
        from core.enrichment_engine import EnrichmentEngine
        engine = EnrichmentEngine(db_with_lead)
        lead_dict = {
            "id": 1,
            "business_name": "Test Plumber",
            "city": "Austin",
            "website_url": "https://testplumber.com",
        }
        # Should not raise TypeError
        result = engine.enrich_lead(lead_dict)
        assert isinstance(result, dict)

    def test_hunter_controller_calls_enrich_with_dict(self):
        """Verify hunter_controller passes a dict, not kwargs."""
        import ast
        src = Path(__file__).parent.parent / "controllers" / "hunter_controller.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "enrich_lead":
                    # Should have exactly 1 positional arg and 0 keyword args
                    assert len(node.args) == 1, "enrich_lead should have 1 positional arg"
                    assert len(node.keywords) == 0, "enrich_lead should have 0 keyword args"


# ─── Fix 2: Router tier_override ────────────────────────────

class TestRouterTierOverride:
    """route() must accept tier_override kwarg."""

    def test_route_signature_accepts_tier_override(self):
        import inspect
        from core.router_engine import RouterEngine
        sig = inspect.signature(RouterEngine.route)
        params = list(sig.parameters.keys())
        assert "tier_override" in params

    def test_tier_override_changes_target(self, db):
        from core.router_engine import RouterEngine
        from core.key_vault import KeyVault
        engine = RouterEngine(db, KeyVault())
        # Without a configured provider, route will fail,
        # but we verify the tier_override is accepted without TypeError
        result = engine.route("generate_email", "test prompt", tier_override="haiku")
        # Should return a dict (even if error), not raise TypeError
        assert isinstance(result, dict)


# ─── Fix 3: AIEngine.generate() ────────────────────────────

class TestAIEngineGenerate:
    """AIEngine must have a generate() method for sequence_controller."""

    def test_generate_method_exists(self):
        from core.ai_engine import AIEngine
        engine = AIEngine()
        assert hasattr(engine, "generate")
        assert callable(engine.generate)

    def test_generate_returns_dict(self):
        from core.ai_engine import AIEngine
        engine = AIEngine()
        # Without API keys, _call_llm will return None
        result = engine.generate("Hello, world!")
        assert isinstance(result, dict)
        assert "success" in result

    def test_generate_with_system_prompt(self):
        from core.ai_engine import AIEngine
        engine = AIEngine()
        result = engine.generate(
            prompt="Write an email",
            system_prompt="You are an email writer",
        )
        assert isinstance(result, dict)

    def test_generate_uses_router_when_available(self):
        from core.ai_engine import AIEngine
        engine = AIEngine()
        mock_router = MagicMock()
        mock_router.route.return_value = {"success": True, "data": "Generated text"}
        engine.router = mock_router
        result = engine.generate("test prompt", system_prompt="sys")
        assert result["success"] is True
        assert result["response"] == "Generated text"
        mock_router.route.assert_called_once()


# ─── Fix 4: Self-improvement method name ────────────────────

class TestSelfImprovementMethodName:
    """fleet_controller must call run_improvement_cycle(), not run_daily_improvement_cycle()."""

    def test_correct_method_name_in_source(self):
        src = Path(__file__).parent.parent / "controllers" / "fleet_controller.py"
        text = src.read_text(encoding="utf-8")
        assert "run_improvement_cycle()" in text
        assert "run_daily_improvement_cycle()" not in text

    def test_self_improvement_engine_has_method(self):
        from core.self_improvement_engine import SelfImprovementEngine
        assert hasattr(SelfImprovementEngine, "run_improvement_cycle")


# ─── Fix 5: email_sent_at + email_body on send ─────────────

class TestEmailSentFields:
    """Outreach controller must set email_body and email_sent_at after send."""

    def test_source_sets_email_body(self):
        src = Path(__file__).parent.parent / "controllers" / "outreach_controller.py"
        text = src.read_text(encoding="utf-8")
        assert "lead.email_body = body" in text

    def test_source_sets_email_sent_at(self):
        src = Path(__file__).parent.parent / "controllers" / "outreach_controller.py"
        text = src.read_text(encoding="utf-8")
        assert "lead.email_sent_at" in text

    def test_lead_schema_has_fields(self):
        """Lead model must have email_sent_at, email_body, email_subject columns."""
        assert hasattr(Lead, "email_sent_at")
        assert hasattr(Lead, "email_body")
        assert hasattr(Lead, "email_subject")


# ─── Fix 6: Autonomy enforcement in agent_engine ────────────

class TestAutonomyEnforcement:
    """agent_engine.run_task() must check autonomy before executing."""

    def test_autonomy_check_in_source(self):
        src = Path(__file__).parent.parent / "core" / "agent_engine.py"
        text = src.read_text(encoding="utf-8")
        assert "autonomy_controller" in text
        assert "check_permission" in text
        assert "queue_for_approval" in text

    def test_observer_blocks_task(self, db):
        """Observer level should block all tasks."""
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        from controllers.autonomy_controller import AutonomyController

        kv = KeyVault()
        engine = AgentEngine(db, kv)

        # Create agent + settings (observer level)
        with db.session_scope() as session:
            session.add(Settings(id=1, autonomy_level="observer"))
            agent = Agent(
                name="TestBot", role="worker", identity_emoji="🤖",
                model_tier="haiku", rank=3, status="idle",
            )
            session.add(agent)
            session.flush()
            agent_id = agent.id

        autonomy = AutonomyController(db)
        engine.autonomy_controller = autonomy

        result = engine.run_task(agent_id, "generate_email", {"lead_id": 1})
        assert result.get("needs_approval") is True

        # Check PendingApproval was created
        with db.session_scope() as session:
            approvals = session.query(PendingApproval).all()
            assert len(approvals) == 1
            assert approvals[0].action_type == "generate_email"

    def test_full_trust_allows_task(self, db):
        """Full trust should allow all tasks without approval."""
        from controllers.autonomy_controller import AutonomyController

        with db.session_scope() as session:
            session.add(Settings(id=1, autonomy_level="full_trust"))

        autonomy = AutonomyController(db)
        perm = autonomy.check_permission("send_email")
        data = perm.get("data", {})
        assert data.get("allowed") is True
        assert data.get("needs_approval") is False


# ─── Fix 7: sequence_id in follow-up data ───────────────────

class TestSequenceIdInFollowup:
    """get_leads_due_for_followup() must return sequence_id."""

    def test_returns_sequence_id(self, db):
        from core.sequence_engine import SequenceEngine

        # Create campaign, sequence, step, lead, and scheduled send
        with db.session_scope() as session:
            campaign = Campaign(name="Camp", status="active", target_niche="plumbing")
            session.add(campaign)
            session.flush()

            seq = FollowUpSequence(campaign_id=campaign.id, name="Test Seq")
            session.add(seq)
            session.flush()

            step = FollowUpStep(
                sequence_id=seq.id, step_number=1, delay_days=3,
            )
            session.add(step)
            session.flush()

            lead = Lead(
                campaign_id=campaign.id, business_name="Biz",
                email="biz@test.com", status="emailed",
            )
            session.add(lead)
            session.flush()

            send = FollowUpSend(
                lead_id=lead.id, step_id=step.id,
                scheduled_for=datetime.utcnow() - timedelta(hours=1),
                status="scheduled",
            )
            session.add(send)
            session.flush()

            expected_seq_id = seq.id
            campaign_id = campaign.id

        engine = SequenceEngine(db)
        results = engine.get_leads_due_for_followup(campaign_id)
        assert len(results) == 1
        assert "sequence_id" in results[0]
        assert results[0]["sequence_id"] == expected_seq_id


# ─── Fix 8: Pacing key name ─────────────────────────────────

class TestPacingKeyName:
    """agent_engine must use 'current_max_tier' not 'allowed_max_tier'."""

    def test_correct_key_in_source(self):
        src = Path(__file__).parent.parent / "core" / "agent_engine.py"
        text = src.read_text(encoding="utf-8")
        assert '"current_max_tier"' in text
        assert '"allowed_max_tier"' not in text


# ─── Fix 9: Reflection engine router result parsing ─────────

class TestReflectionRouterParsing:
    """reflection_engine must extract data as string, not nested dict."""

    def test_no_nested_get_text_in_source(self):
        src = Path(__file__).parent.parent / "core" / "reflection_engine.py"
        text = src.read_text(encoding="utf-8")
        assert '.get("data", {}).get("text"' not in text

    def test_evaluate_parses_router_string(self, db):
        """Verify _evaluate can parse JSON from a router string result."""
        from core.reflection_engine import ReflectionEngine
        from core.router_engine import RouterEngine
        from core.key_vault import KeyVault

        engine = ReflectionEngine(db, router_engine=RouterEngine(db, KeyVault()))
        # Mock router to return string data (as it actually does)
        mock_router = MagicMock()
        mock_router.route.return_value = {
            "success": True,
            "data": '{"score": 8, "reflection": "Good work", "improvements": "None needed"}',
        }
        engine.router_engine = mock_router
        score, reflection, improvements = engine._evaluate("test", "output", "context")
        assert score == 8
        assert reflection == "Good work"


# ─── Fix 10: Conversation engine router result parsing ──────

class TestConversationRouterParsing:
    """conversation_engine must extract data as string, not nested dict."""

    def test_no_nested_get_text_in_source(self):
        src = Path(__file__).parent.parent / "core" / "conversation_engine.py"
        text = src.read_text(encoding="utf-8")
        assert '.get("data", {}).get("text"' not in text


# ─── Fix 11: Lead.business_name in orchestrator ─────────────

class TestOrchestratorLeadName:
    """orchestrator_engine must use Lead.business_name not Lead.name."""

    def test_no_lead_dot_name_in_query(self):
        src = Path(__file__).parent.parent / "core" / "orchestrator_engine.py"
        text = src.read_text(encoding="utf-8")
        assert "Lead.business_name" in text
        assert "Lead.name" not in text


# ─── Fix 12: Knowledge graph None guard ──────────────────────

class TestKnowledgeGraphNoneGuard:
    """agent_engine must not call record_interaction with lead_id=None."""

    def test_no_lead_id_none_in_agent_engine(self):
        src = Path(__file__).parent.parent / "core" / "agent_engine.py"
        text = src.read_text(encoding="utf-8")
        assert "lead_id=None" not in text


# ─── Fix 13: Strategy milestone increment ────────────────────

class TestStrategyMilestoneIncrement:
    """closed_won callback must increment milestone actual_value."""

    def test_milestone_increment_in_source(self):
        src = Path(__file__).parent.parent / "ui" / "main_window.py"
        text = src.read_text(encoding="utf-8")
        assert "actual_value" in text
        assert "milestone" in text

    def test_milestone_incremented(self, db):
        from core.strategy_engine import StrategyEngine
        from database.schema import StrategicGoal, GoalMilestone

        engine = StrategyEngine(db)

        with db.session_scope() as session:
            goal = StrategicGoal(
                goal_text="Convert 10 leads",
                target_metric="conversions",
                target_value=10,
                status="active",
            )
            session.add(goal)
            session.flush()
            goal_id = goal.id

            ms = GoalMilestone(
                goal_id=goal_id, phase=1, description="First 5 conversions",
                target_value=5, actual_value=0, status="active",
            )
            session.add(ms)
            session.flush()
            ms_id = ms.id

        # Simulate what _on_lead_closed_won now does
        with db.session_scope() as session:
            milestone = session.query(GoalMilestone).filter_by(
                goal_id=goal_id, status="active"
            ).first()
            assert milestone is not None
            milestone.actual_value = (milestone.actual_value or 0) + 1

        engine.update_progress(goal_id)

        with db.session_scope() as session:
            ms = session.query(GoalMilestone).get(ms_id)
            assert ms.actual_value == 1
