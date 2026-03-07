"""
Tests for the codebase audit fixes (8 items).
Covers: per-task output tokens, hourly rate limits, model string constants,
dead queue dispatch, HubSpot rate, summarize_text chunking, subagent max_tokens.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from tests.conftest import InMemoryDatabaseManager
from database.schema import Agent, AgentTask, Settings


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    db_manager = InMemoryDatabaseManager()
    db_manager.init_db()
    return db_manager


@pytest.fixture
def db_with_agent(db):
    with db.session_scope() as session:
        agent = Agent(
            name="TestAgent", role="worker", identity_emoji="🧪",
            model_tier="haiku", rank=3, status="idle",
        )
        session.add(agent)
        session.flush()
    return db


@pytest.fixture
def db_with_settings(db_with_agent):
    with db_with_agent.session_scope() as session:
        session.add(Settings(id=1))
    return db_with_agent


# ═══════════════════════════════════════════════════════════════════════════
# Fix 1: Per-task output token map
# ═══════════════════════════════════════════════════════════════════════════


class TestTaskOutputTokens:
    """TASK_OUTPUT_TOKENS config + router wiring."""

    def test_task_output_tokens_defined(self):
        from config import TASK_OUTPUT_TOKENS
        assert isinstance(TASK_OUTPUT_TOKENS, dict)
        assert "_default" in TASK_OUTPUT_TOKENS
        assert TASK_OUTPUT_TOKENS["_default"] == 1024

    def test_generate_email_gets_1500(self):
        from config import TASK_OUTPUT_TOKENS
        assert TASK_OUTPUT_TOKENS["generate_email"] == 1500

    def test_synthesize_research_gets_2000(self):
        from config import TASK_OUTPUT_TOKENS
        assert TASK_OUTPUT_TOKENS["synthesize_research"] == 2000

    def test_qualify_lead_gets_512(self):
        from config import TASK_OUTPUT_TOKENS
        assert TASK_OUTPUT_TOKENS["qualify_lead"] == 512

    def test_summarize_gets_600(self):
        from config import TASK_OUTPUT_TOKENS
        assert TASK_OUTPUT_TOKENS["summarize"] == 600

    def test_router_uses_task_output_tokens(self, db_with_settings):
        """Router _run_llm should use TASK_OUTPUT_TOKENS for the task type."""
        from core.router_engine import RouterEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        router = RouterEngine(db_with_settings, kv)

        # Mock litellm so we can inspect the max_tokens passed
        mock_response = MagicMock()
        mock_response.get.return_value = {}
        mock_response.__getitem__ = lambda s, k: {
            "choices": [MagicMock(message=MagicMock(content="ok"))],
            "usage": {"total_tokens": 10},
        }[k] if k in ("choices", "usage") else {}

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            with patch("litellm.completion_cost", return_value=0.0):
                # Call _run_llm with task_type="generate_email" (budget=1500)
                # and no explicit max_tokens in context
                router._run_llm(
                    "anthropic/claude-haiku-4-5", "haiku",
                    "test prompt", {},
                    task_type="generate_email",
                )

                call_kwargs = mock_comp.call_args
                assert call_kwargs is not None
                # max_tokens should be 1500 from TASK_OUTPUT_TOKENS
                assert call_kwargs.kwargs.get("max_tokens") == 1500 or \
                       call_kwargs[1].get("max_tokens") == 1500

    def test_router_context_override_wins(self, db_with_settings):
        """Context max_tokens should override TASK_OUTPUT_TOKENS."""
        from core.router_engine import RouterEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        router = RouterEngine(db_with_settings, kv)

        mock_response = MagicMock()
        mock_response.get.return_value = {}
        mock_response.__getitem__ = lambda s, k: {
            "choices": [MagicMock(message=MagicMock(content="ok"))],
            "usage": {"total_tokens": 10},
        }[k] if k in ("choices", "usage") else {}

        with patch("litellm.completion", return_value=mock_response) as mock_comp:
            with patch("litellm.completion_cost", return_value=0.0):
                router._run_llm(
                    "anthropic/claude-haiku-4-5", "haiku",
                    "test prompt",
                    {"max_tokens": 999},
                    task_type="generate_email",
                )

                call_kwargs = mock_comp.call_args
                assert call_kwargs is not None
                assert call_kwargs.kwargs.get("max_tokens") == 999 or \
                       call_kwargs[1].get("max_tokens") == 999


# ═══════════════════════════════════════════════════════════════════════════
# Fix 2: Hourly rate limiting
# ═══════════════════════════════════════════════════════════════════════════


class TestHourlyRateLimit:
    """AGENT_MAX_MESSAGES_PER_HOUR enforcement in agent_engine."""

    def test_check_hourly_rate_allows_under_limit(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        engine = AgentEngine(db_with_settings, kv)
        assert engine._check_hourly_rate(1) is True

    def test_check_hourly_rate_blocks_over_limit(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        from config import AGENT_MAX_MESSAGES_PER_HOUR

        kv = KeyVault()
        engine = AgentEngine(db_with_settings, kv)

        # Fill up to limit
        for _ in range(AGENT_MAX_MESSAGES_PER_HOUR):
            engine._record_call(1)

        assert engine._check_hourly_rate(1) is False

    def test_old_calls_are_pruned(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        from config import AGENT_MAX_MESSAGES_PER_HOUR

        kv = KeyVault()
        engine = AgentEngine(db_with_settings, kv)

        # Add calls from 2 hours ago
        old_time = datetime.utcnow() - timedelta(hours=2)
        engine._hourly_calls[1] = [old_time] * AGENT_MAX_MESSAGES_PER_HOUR

        # Should still allow because old calls are pruned
        assert engine._check_hourly_rate(1) is True

    def test_run_task_returns_rate_limited(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        from config import AGENT_MAX_MESSAGES_PER_HOUR

        kv = KeyVault()
        engine = AgentEngine(db_with_settings, kv)

        # Fill up rate limit for agent_id=1
        for _ in range(AGENT_MAX_MESSAGES_PER_HOUR):
            engine._record_call(1)

        result = engine.run_task(1, "test_task", {"test": True})
        assert result["success"] is False
        assert result.get("rate_limited") is True

    def test_rate_limit_per_agent(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        from config import AGENT_MAX_MESSAGES_PER_HOUR

        kv = KeyVault()
        engine = AgentEngine(db_with_settings, kv)

        # Fill agent 1 to limit
        for _ in range(AGENT_MAX_MESSAGES_PER_HOUR):
            engine._record_call(1)

        # Agent 1 blocked, agent 2 still fine
        assert engine._check_hourly_rate(1) is False
        assert engine._check_hourly_rate(2) is True


# ═══════════════════════════════════════════════════════════════════════════
# Fix 3: Model string constants
# ═══════════════════════════════════════════════════════════════════════════


class TestModelStringConstants:
    """All engines use config.py model constants, not hardcoded strings."""

    def test_ai_engine_uses_config_models(self):
        from core.ai_engine import AIEngine
        from config import DEFAULT_TIER2_MODEL, DEFAULT_TIER3_MODEL

        engine = AIEngine()
        assert engine._models["tier2"] == DEFAULT_TIER2_MODEL
        assert engine._models["tier3"] == DEFAULT_TIER3_MODEL

    def test_router_uses_config_sonnet(self, db_with_settings):
        from core.router_engine import RouterEngine
        from core.key_vault import KeyVault
        from config import DEFAULT_TIER3_MODEL

        kv = KeyVault()
        router = RouterEngine(db_with_settings, kv)
        assert router._sonnet_model == DEFAULT_TIER3_MODEL

    def test_analyst_uses_config_model(self):
        from core.analyst_engine import AnalystEngine
        import inspect

        source = inspect.getsource(AnalystEngine.ask)
        assert "claude-sonnet-4-5" not in source
        assert "DEFAULT_TIER3_MODEL" in source

    def test_orchestrator_uses_config_model(self):
        from core.orchestrator_engine import OrchestratorEngine
        import inspect

        source = inspect.getsource(OrchestratorEngine.parse_intent)
        assert "claude-sonnet-4-5" not in source

    def test_settings_controller_uses_config_model(self):
        from controllers.settings_controller import SettingsController
        import inspect

        source = inspect.getsource(SettingsController.get_settings)
        assert "claude-sonnet-4-5" not in source


# ═══════════════════════════════════════════════════════════════════════════
# Fix 4: Dead queue dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestQueueDispatch:
    """dispatch_queued_tasks + agent_id=0 sentinel."""

    def test_queued_task_uses_sentinel_agent_id(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.key_vault import KeyVault

        kv = KeyVault()
        agent_engine = AgentEngine(db_with_settings, kv)
        fleet = FleetOrchestrator(db_with_settings, agent_engine)

        # Make all agents busy
        with db_with_settings.session_scope() as session:
            for agent in session.query(Agent).all():
                agent.status = "running"

        result = fleet.dispatch("generate_email", {"test": True})
        assert result.get("queued") is True

        # Verify agent_id is 0 (sentinel), not 1
        with db_with_settings.session_scope() as session:
            queued_task = session.query(AgentTask).filter_by(status="queued").first()
            assert queued_task is not None
            assert queued_task.agent_id == 0

    def test_dispatch_queued_empty(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.key_vault import KeyVault

        kv = KeyVault()
        agent_engine = AgentEngine(db_with_settings, kv)
        fleet = FleetOrchestrator(db_with_settings, agent_engine)

        result = fleet.dispatch_queued_tasks()
        assert result["success"] is True
        assert result["dispatched"] == 0

    def test_dispatch_queued_assigns_to_idle_agent(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.key_vault import KeyVault

        kv = KeyVault()
        agent_engine = AgentEngine(db_with_settings, kv)
        fleet = FleetOrchestrator(db_with_settings, agent_engine)

        # Create a queued task
        with db_with_settings.session_scope() as session:
            task = AgentTask(
                agent_id=0,
                task_type="enrich_lead",
                task_payload=json.dumps({"lead_id": 1}),
                status="queued",
                assigned_by="fleet_orchestrator",
            )
            session.add(task)

        # Agent is idle, so dispatch should pick it up
        result = fleet.dispatch_queued_tasks()
        assert result["success"] is True
        assert result["dispatched"] == 1

    def test_dispatch_queued_skips_when_all_busy(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.key_vault import KeyVault

        kv = KeyVault()
        agent_engine = AgentEngine(db_with_settings, kv)
        fleet = FleetOrchestrator(db_with_settings, agent_engine)

        # Make all agents busy
        with db_with_settings.session_scope() as session:
            for agent in session.query(Agent).all():
                agent.status = "running"
            task = AgentTask(
                agent_id=0,
                task_type="enrich_lead",
                task_payload=json.dumps({"lead_id": 1}),
                status="queued",
                assigned_by="fleet_orchestrator",
            )
            session.add(task)

        result = fleet.dispatch_queued_tasks()
        assert result["success"] is True
        assert result["dispatched"] == 0
        assert result["remaining"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Fix 5: HubSpot rate limit
# ═══════════════════════════════════════════════════════════════════════════


class TestHubSpotRate:
    """HUBSPOT_RATE_PER_MINUTE should be 600."""

    def test_hubspot_rate_is_600(self):
        from config import HUBSPOT_RATE_PER_MINUTE
        assert HUBSPOT_RATE_PER_MINUTE == 600


# ═══════════════════════════════════════════════════════════════════════════
# Fix 6: summarize_text chunking
# ═══════════════════════════════════════════════════════════════════════════


class TestSummarizeTextChunking:
    """summarize_text uses max_tokens=600 default + chunks long inputs."""

    def test_default_max_tokens_is_600(self, db):
        from core.token_manager import TokenManager

        tm = TokenManager(db)
        import inspect
        sig = inspect.signature(tm.summarize_text)
        assert sig.parameters["max_tokens"].default == 600

    def test_get_or_create_summary_default_is_600(self, db):
        from core.token_manager import TokenManager

        tm = TokenManager(db)
        import inspect
        sig = inspect.signature(tm.get_or_create_summary)
        assert sig.parameters["max_summary_tokens"].default == 600

    def test_short_text_no_chunking(self, db):
        from core.token_manager import TokenManager

        mock_router = MagicMock()
        mock_router.route.return_value = {"success": True, "data": "summary"}
        tm = TokenManager(db, router_engine=mock_router)

        result = tm.summarize_text("short text")
        assert result == "summary"
        assert mock_router.route.call_count == 1

    def test_long_text_triggers_chunking(self, db):
        from core.token_manager import TokenManager

        mock_router = MagicMock()
        mock_router.route.return_value = {"success": True, "data": "chunk summary"}
        tm = TokenManager(db, router_engine=mock_router)

        long_text = "A" * 5000  # >4000 chars
        result = tm.summarize_text(long_text)
        # Should make multiple calls (2 chunks)
        assert mock_router.route.call_count == 2
        assert "chunk summary" in result

    def test_fallback_truncation_without_router(self, db):
        from core.token_manager import TokenManager

        tm = TokenManager(db, router_engine=None)
        text = "A" * 3000
        result = tm.summarize_text(text, max_tokens=100)
        # Should truncate to 100 * 4 = 400 chars
        assert len(result) == 400

    def test_summarize_single_exists(self, db):
        from core.token_manager import TokenManager

        tm = TokenManager(db)
        assert hasattr(tm, "_summarize_single")


# ═══════════════════════════════════════════════════════════════════════════
# Fix 7: Subagent review_tone max_tokens
# ═══════════════════════════════════════════════════════════════════════════


class TestSubagentMaxTokens:
    """Subagent decomposition map has per-pattern max_tokens."""

    def test_review_tone_max_tokens_is_768(self):
        from config import SUBAGENT_DECOMPOSITION_MAP

        email_patterns = SUBAGENT_DECOMPOSITION_MAP["generate_email"]
        review_tone = [p for p in email_patterns if p["type"] == "review_tone"]
        assert len(review_tone) == 1
        assert review_tone[0]["max_tokens"] == 768

    def test_draft_email_max_tokens_is_768(self):
        from config import SUBAGENT_DECOMPOSITION_MAP

        email_patterns = SUBAGENT_DECOMPOSITION_MAP["generate_email"]
        draft = [p for p in email_patterns if p["type"] == "draft_email"]
        assert len(draft) == 1
        assert draft[0]["max_tokens"] == 768

    def test_run_subtask_accepts_max_tokens(self, db):
        from core.subagent_engine import SubagentEngine

        engine = SubagentEngine(db)
        import inspect
        sig = inspect.signature(engine.run_subtask)
        assert "max_tokens" in sig.parameters

    def test_run_subtask_passes_max_tokens_to_router(self, db):
        from core.subagent_engine import SubagentEngine
        from database.schema import SubagentTask

        mock_router = MagicMock()
        mock_router.route.return_value = {
            "success": True, "data": "result", "tokens": 10, "cost_usd": 0.001
        }

        engine = SubagentEngine(db, router_engine=mock_router)

        # Create a parent task + subtask record
        with db.session_scope() as session:
            session.add(Agent(
                name="Test", role="worker", identity_emoji="🧪",
                model_tier="haiku", rank=3, status="idle",
            ))
            session.flush()
            parent = AgentTask(
                agent_id=1, task_type="generate_email",
                task_payload="{}", status="running",
            )
            session.add(parent)
            session.flush()
            sub = SubagentTask(
                parent_task_id=parent.id, subtask_type="review_tone",
                status="running", tier="haiku",
            )
            session.add(sub)
            session.flush()
            sub_id = sub.id

        engine.run_subtask(sub_id, "test prompt", "haiku", max_tokens=768)

        # Verify router was called with max_tokens=768
        call_args = mock_router.route.call_args
        context = call_args.kwargs.get("context") or call_args[0][2] if len(call_args[0]) > 2 else call_args.kwargs.get("context")
        if context is None:
            # It might be passed positionally
            context = call_args[1].get("context", {})
        assert context.get("max_tokens") == 768


# ═══════════════════════════════════════════════════════════════════════════
# Integration: fleet_controller wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestFleetControllerQueueTimer:
    """Fleet controller has queue dispatch timer."""

    def test_fleet_controller_has_queue_timer(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from controllers.fleet_controller import FleetController
        from core.key_vault import KeyVault

        kv = KeyVault()
        ae = AgentEngine(db_with_settings, kv)
        fo = FleetOrchestrator(db_with_settings, ae)
        obs = ObserverEngine(db_with_settings, ae)
        fc = FleetController(db_with_settings, ae, fo, obs)

        assert hasattr(fc, "_queue_timer")

    def test_fleet_controller_has_dispatch_queued_method(self, db_with_settings):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from controllers.fleet_controller import FleetController
        from core.key_vault import KeyVault

        kv = KeyVault()
        ae = AgentEngine(db_with_settings, kv)
        fo = FleetOrchestrator(db_with_settings, ae)
        obs = ObserverEngine(db_with_settings, ae)
        fc = FleetController(db_with_settings, ae, fo, obs)

        assert hasattr(fc, "_dispatch_queued")
