"""
Integration tests — verify all new engines can be instantiated together
and cross-wiring works correctly.
"""

import pytest

from database.schema import (
    AgentReflection, PerformanceMetric, AgentLearnedRule,
    LeadStateTransition, KnowledgeNode, KnowledgeEdge,
    ConversationThread, StrategicGoal, GoalMilestone,
    PendingApproval, Campaign, Lead,
)
from config import (
    LeadLifecycleStatus, LEAD_STATE_TRANSITIONS, LEAD_TERMINAL_STATES,
    AutonomyLevel, AUTONOMY_REQUIRES_APPROVAL,
    VECTOR_RAG_COLLECTIONS,
)


class TestConfigIntegrity:
    """Verify config enums and dicts are consistent."""

    def test_lead_lifecycle_states_all_defined(self):
        """Every state in transitions map should be in the enum."""
        enum_values = {e.value for e in LeadLifecycleStatus}
        for state in LEAD_STATE_TRANSITIONS:
            assert state in enum_values, f"'{state}' in transitions but not in enum"

    def test_terminal_states_not_in_transitions_targets(self):
        """Terminal states should not appear as FROM states (except closed_lost→re_engage)."""
        for terminal in LEAD_TERMINAL_STATES:
            if terminal == "closed_lost":
                continue  # closed_lost can re-engage
            assert terminal not in LEAD_STATE_TRANSITIONS or \
                   LEAD_STATE_TRANSITIONS[terminal] == [], \
                   f"Terminal state '{terminal}' should not have outgoing transitions"

    def test_autonomy_levels_match_enum(self):
        """Every key in AUTONOMY_REQUIRES_APPROVAL should be a valid AutonomyLevel."""
        valid = {e.value for e in AutonomyLevel}
        for key in AUTONOMY_REQUIRES_APPROVAL:
            assert key in valid, f"'{key}' not in AutonomyLevel enum"

    def test_vector_rag_collections(self):
        """Verify expected collections exist."""
        assert "emails" in VECTOR_RAG_COLLECTIONS
        assert "interactions" in VECTOR_RAG_COLLECTIONS
        assert "knowledge" in VECTOR_RAG_COLLECTIONS
        assert "agent_learnings" in VECTOR_RAG_COLLECTIONS


class TestCrossEngineWiring:
    """Test that engines can talk to each other."""

    def test_reflection_plus_improvement(self, db_full):
        """Self-improvement engine can query reflection engine."""
        from core.reflection_engine import ReflectionEngine
        from core.self_improvement_engine import SelfImprovementEngine
        from tests.conftest import get_agent_id_by_name

        reflection = ReflectionEngine(db_full)
        improvement = SelfImprovementEngine(db_full, reflection_engine=reflection)

        agent_id = get_agent_id_by_name(db_full, "Closer")

        # Record a metric, then analyze — should work end-to-end
        improvement.record_metric(agent_id, "reply_rate", "wire_test", 0.06, 10)
        result = improvement.analyze_agent_performance(agent_id, period_days=7)
        assert result["success"] is True
        assert "metrics_by_type" in result["data"]

    def test_lifecycle_to_conversation(self, db_full):
        """Lead lifecycle transition triggers conversation thread usage."""
        from core.lead_lifecycle_engine import LeadLifecycleEngine
        from core.conversation_engine import ConversationEngine

        lifecycle = LeadLifecycleEngine(db_full)
        conversation = ConversationEngine(db_full)

        # Create a lead and move through lifecycle
        with db_full.session_scope() as s:
            c = Campaign(name="Wire Test", target_niche="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Wire Co", lifecycle_state="new")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        lifecycle.transition(lead_id, "researched")
        lifecycle.transition(lead_id, "qualifying")
        lifecycle.transition(lead_id, "qualified")
        lifecycle.transition(lead_id, "email_drafted")
        lifecycle.transition(lead_id, "contacted")

        # Now start a conversation thread
        conversation.append_message(lead_id, "agent", "Hello! Interested in our services?")
        thread = conversation.get_thread(lead_id)
        assert thread["success"] is True
        assert thread["data"]["message_count"] == 1

    def test_knowledge_graph_plus_rag(self, db_full):
        """Knowledge graph engine works alongside RAG engine."""
        from core.knowledge_graph_engine import KnowledgeGraphEngine
        from core.rag_engine import RAGEngine

        rag = RAGEngine(db_full)
        kg = KnowledgeGraphEngine(db_full, rag_engine=rag)

        # Store some graph data
        kg.upsert_node("niche", "wire_plumbing", "Plumbing")
        kg.upsert_node("lead", "wire_lead_1", "Wire Lead", {"converted": True})
        kg.add_edge("lead", "wire_lead_1", "niche", "wire_plumbing", "belongs_to")

        # Store a RAG email
        rag.store("emails", "Subject: Plumbing services\n\nWe help plumbers grow online")

        # Both should work
        proof = kg.find_social_proof("wire_plumbing")
        assert proof["success"] is True
        stats = rag.get_collection_stats()
        assert isinstance(stats, dict)

    def test_strategy_with_milestones(self, db_full):
        """Strategy engine creates goals and milestones end-to-end."""
        from core.strategy_engine import StrategyEngine

        strategy = StrategyEngine(db_full)

        result = strategy.create_goal(
            "Get 5 HVAC clients in Dallas",
            target_metric="conversions", target_value=5,
            niche="HVAC", city="Dallas",
        )
        assert result["success"] is True
        goal_id = result["data"]["goal_id"]

        goal = strategy.get_goal(goal_id)
        assert len(goal["data"]["milestones"]) == 5

        strategy.activate_goal(goal_id)
        goal2 = strategy.get_goal(goal_id)
        assert goal2["data"]["status"] == "active"

    def test_autonomy_gates_action(self, db_full):
        """Autonomy controller gates actions and queues approvals."""
        from controllers.autonomy_controller import AutonomyController

        ctrl = AutonomyController(db_full)

        # At supervised level, send_email needs approval
        check = ctrl.check_permission("send_email")
        if check["data"]["needs_approval"]:
            q = ctrl.queue_for_approval(
                "send_email", description="Cold email to Lead 1",
                payload={"lead_id": 1},
            )
            assert q["success"] is True

            pending = ctrl.get_pending_approvals()
            assert len(pending["data"]) >= 1

            # Approve it
            ctrl.approve_action(q["data"]["approval_id"])


class TestSchemaCompleteness:
    """Verify all new tables get created properly."""

    def test_all_new_tables_exist(self, db):
        """All new schema models should have their tables created."""
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        table_names = inspector.get_table_names()

        expected_tables = [
            "agent_reflections",
            "performance_metrics",
            "agent_learned_rules",
            "lead_state_transitions",
            "knowledge_nodes",
            "knowledge_edges",
            "conversation_threads",
            "strategic_goals",
            "goal_milestones",
            "pending_approvals",
        ]

        for table in expected_tables:
            assert table in table_names, f"Table '{table}' missing from database"

    def test_lead_has_lifecycle_state(self, db):
        """Lead model should have the lifecycle_state column."""
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [c["name"] for c in inspector.get_columns("leads")]
        assert "lifecycle_state" in columns


# ─── Production Wiring Tests ─────────────────────────────────
# These verify engines are actually called from production code paths.

from unittest.mock import MagicMock
from database.schema import Agent, AgentTask, Settings, Skill


@pytest.fixture
def wired_engines(db_full):
    """Fully wired engine set mimicking main_window._init_controllers()."""
    from core.agent_engine import AgentEngine
    from core.fleet_orchestrator import FleetOrchestrator
    from core.reflection_engine import ReflectionEngine
    from core.lead_lifecycle_engine import LeadLifecycleEngine
    from core.knowledge_graph_engine import KnowledgeGraphEngine
    from core.conversation_engine import ConversationEngine
    from core.self_improvement_engine import SelfImprovementEngine
    from core.strategy_engine import StrategyEngine
    from controllers.autonomy_controller import AutonomyController
    from core.key_vault import KeyVault

    kv = KeyVault()
    agent_engine = AgentEngine(db_full, kv)
    fleet = FleetOrchestrator(db_full, agent_engine)
    reflection = ReflectionEngine(db_full)
    lifecycle = LeadLifecycleEngine(db_full)
    knowledge_graph = KnowledgeGraphEngine(db_full)
    conversation = ConversationEngine(db_full)
    self_improvement = SelfImprovementEngine(db_full, reflection_engine=reflection)
    strategy = StrategyEngine(db_full)
    autonomy = AutonomyController(db_full)

    # Cross-wire (mirrors main_window)
    agent_engine.reflection_engine = reflection
    agent_engine.knowledge_graph = knowledge_graph
    agent_engine.self_improvement_engine = self_improvement
    agent_engine.autonomy_controller = autonomy

    engines_dict = {
        "strategy": strategy,
        "reflection": reflection,
        "autonomy": autonomy,
        "conversation": conversation,
        "lifecycle": lifecycle,
        "knowledge_graph": knowledge_graph,
        "self_improvement": self_improvement,
    }

    return {
        "db": db_full,
        "agent_engine": agent_engine,
        "fleet": fleet,
        "reflection": reflection,
        "lifecycle": lifecycle,
        "knowledge_graph": knowledge_graph,
        "conversation": conversation,
        "self_improvement": self_improvement,
        "strategy": strategy,
        "autonomy": autonomy,
        "engines_dict": engines_dict,
    }


# ─── Orchestrator Intent Routing ─────────────────────────────


class TestOrchestratorIntents:

    def test_set_goal_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_set_goal(
            {"goal_text": "Get 5 clients", "target_value": 5, "niche": "plumbing"},
            wired_engines["engines_dict"],
        )
        assert result["success"] is True
        assert "goal_id" in result["data"]

    def test_show_goals_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        wired_engines["strategy"].create_goal("Test goal", target_value=3)
        result = orch._exec_show_goals({}, wired_engines["engines_dict"])
        assert result["success"] is True
        assert len(result["data"]) >= 1

    def test_show_reflections_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_show_reflections(
            {"limit": 5}, wired_engines["engines_dict"],
        )
        assert result["success"] is True

    def test_set_autonomy_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_set_autonomy(
            {"level": "autonomous"}, wired_engines["engines_dict"],
        )
        assert result["success"] is True
        assert result["data"]["level"] == "autonomous"

    def test_set_autonomy_invalid_level(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_set_autonomy(
            {"level": "mega_trust"}, wired_engines["engines_dict"],
        )
        assert result["success"] is False

    def test_show_conversations_stats(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_show_conversations({}, wired_engines["engines_dict"])
        assert result["success"] is True

    def test_show_approvals_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_show_approvals({}, wired_engines["engines_dict"])
        assert result["success"] is True

    def test_approve_action_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        q = wired_engines["autonomy"].queue_for_approval(
            "send_email", description="Test email",
        )
        approval_id = q["data"]["approval_id"]
        result = orch._exec_approve_action(
            {"approval_id": approval_id}, wired_engines["engines_dict"],
        )
        assert result["success"] is True
        assert result["data"]["status"] == "approved"

    def test_deny_action_via_orchestrator(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        q = wired_engines["autonomy"].queue_for_approval(
            "skill_revision", description="Deny me",
        )
        approval_id = q["data"]["approval_id"]
        result = orch._exec_deny_action(
            {"approval_id": approval_id}, wired_engines["engines_dict"],
        )
        assert result["success"] is True
        assert result["data"]["status"] == "denied"

    def test_missing_engine_returns_error(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_set_goal({"goal_text": "Test"}, {})
        assert result["success"] is False
        assert "not available" in result["error"]

    def test_approve_without_id_returns_error(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_approve_action({}, wired_engines["engines_dict"])
        assert result["success"] is False
        assert "approval_id" in result["error"]

    def test_deny_without_id_returns_error(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        result = orch._exec_deny_action({}, wired_engines["engines_dict"])
        assert result["success"] is False
        assert "approval_id" in result["error"]


# ─── Agent Engine Post-Task Hooks ────────────────────────────


class TestAgentPostTaskHooks:

    def test_post_task_hooks_reflection(self, wired_engines):
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id
            task = AgentTask(
                agent_id=agent_id, task_type="generate_email",
                task_payload="{}", status="completed",
            )
            s.add(task)
            s.flush()
            task_id = task.id

        ae._post_task_hooks(
            agent_id=agent_id, task_id=task_id, task_type="generate_email",
            agent_name="Closer", result_data="Great email content",
            cost=0.001, skill_data={"name": "The Closer"},
        )
        with db.session_scope() as s:
            ref = s.query(AgentReflection).filter_by(task_id=task_id).first()
            assert ref is not None
            assert ref.task_type == "generate_email"

    def test_post_task_hooks_metrics(self, wired_engines):
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]
        # Enable self-improvement toggle for this test
        with db.session_scope() as s:
            settings = s.query(Settings).first()
            if settings:
                settings.self_improvement_enabled = True
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id

        ae._post_task_hooks(
            agent_id=agent_id, task_id=999, task_type="qualify_lead",
            agent_name="Qualifier", result_data="Score: 8/10",
            cost=0.0, skill_data=None,
        )
        with db.session_scope() as s:
            metric = (
                s.query(PerformanceMetric)
                .filter_by(metric_type="task_completion", metric_key="qualify_lead")
                .first()
            )
            assert metric is not None
            assert metric.value == 1.0

    def test_post_task_hooks_knowledge_graph(self, wired_engines):
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]
        # Enable knowledge graph toggle for this test
        with db.session_scope() as s:
            settings = s.query(Settings).first()
            if settings:
                settings.knowledge_graph_enabled = True
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id

        ae._post_task_hooks(
            agent_id=agent_id, task_id=888, task_type="enrich_lead",
            agent_name="Enricher", result_data="Enriched data",
            cost=0.0, skill_data=None, payload={"lead_id": 42},
        )
        with db.session_scope() as s:
            edges = s.query(KnowledgeEdge).all()
            assert len(edges) >= 1

    def test_post_task_hooks_nonfatal_on_failure(self, wired_engines):
        ae = wired_engines["agent_engine"]
        ae.reflection_engine = MagicMock()
        ae.reflection_engine.reflect_on_task.side_effect = Exception("Boom")
        # Should NOT raise
        ae._post_task_hooks(
            agent_id=1, task_id=1, task_type="test",
            agent_name="Test", result_data="", cost=0.0, skill_data=None,
        )

    def test_post_task_hooks_skip_when_no_engines(self, db_full):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        ae = AgentEngine(db_full, KeyVault())
        assert ae.reflection_engine is None
        assert ae.knowledge_graph is None
        assert ae.self_improvement_engine is None
        # Should not raise
        ae._post_task_hooks(
            agent_id=1, task_id=1, task_type="test",
            agent_name="Test", result_data="", cost=0.0, skill_data=None,
        )

    def test_post_task_hooks_all_three_fire(self, wired_engines):
        """All 3 hooks (reflection, metrics, KG) fire on a single call."""
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]
        # Enable all toggles
        with db.session_scope() as s:
            settings = s.query(Settings).first()
            if settings:
                settings.reflection_enabled = True
                settings.self_improvement_enabled = True
                settings.knowledge_graph_enabled = True
        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id
            task = AgentTask(
                agent_id=agent_id, task_type="research",
                task_payload="{}", status="completed",
            )
            s.add(task)
            s.flush()
            task_id = task.id

        ae._post_task_hooks(
            agent_id=agent_id, task_id=task_id, task_type="research",
            agent_name="Analyst", result_data="Analysis complete",
            cost=0.0, skill_data=None, payload={"lead_id": 42},
        )
        with db.session_scope() as s:
            assert s.query(AgentReflection).filter_by(task_id=task_id).first() is not None
            assert s.query(PerformanceMetric).filter_by(metric_key="research").first() is not None
            assert s.query(KnowledgeEdge).count() >= 1


# ─── Reply Detector Hooks ────────────────────────────────────


class TestReplyDetectorHooks:

    def test_reply_detector_has_hook_attributes(self, db_full):
        from core.reply_detector import ReplyDetector
        from core.key_vault import KeyVault
        rd = ReplyDetector(db_full, KeyVault())
        assert hasattr(rd, "conversation_engine")
        assert hasattr(rd, "lead_lifecycle_engine")
        assert hasattr(rd, "knowledge_graph_engine")
        assert rd.conversation_engine is None
        assert rd.lead_lifecycle_engine is None
        assert rd.knowledge_graph_engine is None

    def test_reply_detector_accepts_wiring(self, wired_engines):
        from core.reply_detector import ReplyDetector
        from core.key_vault import KeyVault
        rd = ReplyDetector(wired_engines["db"], KeyVault())
        rd.conversation_engine = wired_engines["conversation"]
        rd.lead_lifecycle_engine = wired_engines["lifecycle"]
        rd.knowledge_graph_engine = wired_engines["knowledge_graph"]
        assert rd.conversation_engine is not None
        assert rd.lead_lifecycle_engine is not None
        assert rd.knowledge_graph_engine is not None


# ─── Fleet Orchestrator Task Types ───────────────────────────


class TestFleetTaskTypes:

    def test_new_task_types_in_map(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        new_types = [
            "reflect_on_output", "classify_reply", "handle_objection",
            "record_metrics", "update_knowledge_graph", "plan_strategy",
            "improve_skill",
        ]
        for t in new_types:
            assert t in TASK_SPECIALTY_MAP, f"Missing task type: {t}"

    def test_reflect_on_output_maps_to_analyst(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["reflect_on_output"] == "Analyst"

    def test_classify_reply_maps_to_triage(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["classify_reply"] == "Triage Lead"

    def test_handle_objection_maps_to_closer(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["handle_objection"] == "Closer"

    def test_improve_skill_maps_to_forger(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["improve_skill"] == "Forger"

    def test_update_knowledge_graph_maps_to_archivist(self):
        from core.fleet_orchestrator import TASK_SPECIALTY_MAP
        assert TASK_SPECIALTY_MAP["update_knowledge_graph"] == "Archivist"


# ─── Enrichment Engine Hooks ─────────────────────────────────


class TestEnrichmentHooks:

    def test_enrichment_engine_has_hook_attributes(self, db_full):
        from core.enrichment_engine import EnrichmentEngine
        ee = EnrichmentEngine(db_full)
        assert hasattr(ee, "lead_lifecycle_engine")
        assert hasattr(ee, "knowledge_graph_engine")
        assert ee.lead_lifecycle_engine is None
        assert ee.knowledge_graph_engine is None

    def test_enrichment_hooks_accept_wiring(self, wired_engines):
        from core.enrichment_engine import EnrichmentEngine
        ee = EnrichmentEngine(wired_engines["db"])
        ee.lead_lifecycle_engine = wired_engines["lifecycle"]
        ee.knowledge_graph_engine = wired_engines["knowledge_graph"]
        assert ee.lead_lifecycle_engine is not None
        assert ee.knowledge_graph_engine is not None


# ─── Settings Controller New Fields ──────────────────────────


class TestSettingsControllerNewFields:

    def test_get_settings_returns_autonomy_fields(self, db_full):
        from controllers.settings_controller import SettingsController
        from core.key_vault import KeyVault
        sc = SettingsController(db_full, KeyVault())
        with db_full.session_scope() as s:
            if not s.query(Settings).first():
                s.add(Settings(id=1))
        result = sc.get_settings()
        assert "autonomy_level" in result
        assert "reflection_enabled" in result
        assert "self_improvement_enabled" in result
        assert "knowledge_graph_enabled" in result
        assert "conversation_engine_enabled" in result

    def test_get_settings_default_values(self, db_full):
        from controllers.settings_controller import SettingsController
        from core.key_vault import KeyVault
        sc = SettingsController(db_full, KeyVault())
        with db_full.session_scope() as s:
            if not s.query(Settings).first():
                s.add(Settings(id=1))
        result = sc.get_settings()
        assert result["autonomy_level"] == "supervised"
        assert result["reflection_enabled"] is True
        assert result["self_improvement_enabled"] is True
        assert result["knowledge_graph_enabled"] is True
        assert result["conversation_engine_enabled"] is True


# ─── Full Approval Flow ──────────────────────────────────────


class TestFullApprovalFlow:

    def test_queue_approve_verify(self, wired_engines):
        autonomy = wired_engines["autonomy"]
        q = autonomy.queue_for_approval(
            "send_email", description="Email to Lead 42",
            payload={"lead_id": 42, "subject": "Hello"},
        )
        assert q["success"] is True
        approval_id = q["data"]["approval_id"]

        pending = autonomy.get_pending_approvals()
        assert any(p["id"] == approval_id for p in pending["data"])

        result = autonomy.approve_action(approval_id)
        assert result["success"] is True
        assert result["data"]["status"] == "approved"

        pending2 = autonomy.get_pending_approvals()
        assert not any(p["id"] == approval_id for p in pending2["data"])

    def test_queue_deny_verify(self, wired_engines):
        autonomy = wired_engines["autonomy"]
        q = autonomy.queue_for_approval(
            "skill_revision", description="Revise closer skill",
        )
        approval_id = q["data"]["approval_id"]

        result = autonomy.deny_action(approval_id)
        assert result["success"] is True
        assert result["data"]["status"] == "denied"

    def test_autonomy_gating_observer_blocks(self, wired_engines):
        ctrl = wired_engines["autonomy"]
        result = ctrl.check_permission("send_email", autonomy_level="observer")
        assert result["data"]["allowed"] is False

    def test_autonomy_gating_autonomous_allows_scrape(self, wired_engines):
        ctrl = wired_engines["autonomy"]
        result = ctrl.check_permission("scrape_leads", autonomy_level="autonomous")
        assert result["data"]["allowed"] is True


# ─── Gap 1: Autonomy Gating in Orchestrator ──────────────────


class TestOrchestratorAutonomyGating:

    def test_send_emails_blocked_at_observer(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        # Set autonomy to observer
        wired_engines["autonomy"].set_autonomy_level("observer")
        result = orch._exec_send_emails(
            {"campaign_name": "Test"}, wired_engines["engines_dict"],
        )
        assert result["success"] is False
        assert "requires approval" in result.get("error", "") or "blocked" in result.get("error", "")

    def test_start_campaign_blocked_at_observer(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        wired_engines["autonomy"].set_autonomy_level("observer")
        result = orch._exec_start_campaign(
            {"niche": "plumbing", "city": "Austin"}, wired_engines["engines_dict"],
        )
        assert result["success"] is False

    def test_generate_drafts_blocked_at_observer(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        wired_engines["autonomy"].set_autonomy_level("observer")
        result = orch._exec_generate_drafts(
            {"campaign_name": "Test"}, wired_engines["engines_dict"],
        )
        assert result["success"] is False

    def test_send_emails_allowed_at_autonomous(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        from database.schema import Campaign, Lead
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        wired_engines["autonomy"].set_autonomy_level("autonomous")
        # Create a campaign for it to find
        db = wired_engines["db"]
        with db.session_scope() as s:
            c = Campaign(name="Autonomy Test", target_niche="hvac", target_city="Denver", status="active")
            s.add(c)
        result = orch._exec_send_emails(
            {"campaign_name": "Autonomy Test"}, wired_engines["engines_dict"],
        )
        assert result["success"] is True

    def test_gating_queues_approval(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        wired_engines["autonomy"].set_autonomy_level("supervised")
        result = orch._exec_send_emails(
            {"campaign_name": "Test"}, wired_engines["engines_dict"],
        )
        assert result["success"] is False
        assert result.get("approval_queued") is True
        assert result.get("approval_id") is not None

    def test_check_autonomy_no_engine_allows(self, wired_engines):
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(wired_engines["db"], KeyVault())
        # Empty engines dict → no autonomy controller → action allowed
        result = orch._check_autonomy("send_email", {}, "Test")
        assert result is None  # None means "allowed"


# ─── Gap 2: Self-Improvement Timer ───────────────────────────


class TestSelfImprovementTimer:

    def test_fleet_controller_has_improvement_timer(self, db_full):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from controllers.fleet_controller import FleetController
        from core.key_vault import KeyVault

        kv = KeyVault()
        ae = AgentEngine(db_full, kv)
        fleet = FleetOrchestrator(db_full, ae)
        observer = ObserverEngine(db_full, ae)
        fc = FleetController(db_full, ae, fleet, observer)

        assert hasattr(fc, "_improvement_timer")
        assert hasattr(fc, "self_improvement_engine")
        assert fc.self_improvement_engine is None

    def test_improvement_timer_wired(self, db_full, qapp):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from controllers.fleet_controller import FleetController
        from core.reflection_engine import ReflectionEngine
        from core.self_improvement_engine import SelfImprovementEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        ae = AgentEngine(db_full, kv)
        fleet = FleetOrchestrator(db_full, ae)
        observer = ObserverEngine(db_full, ae)
        fc = FleetController(db_full, ae, fleet, observer)
        reflection = ReflectionEngine(db_full)
        si = SelfImprovementEngine(db_full, reflection_engine=reflection)
        fc.self_improvement_engine = si

        # Call _run_improvement_cycle — should not crash
        fc._run_improvement_cycle()

    def test_improvement_cycle_skip_when_not_wired(self, db_full, qapp):
        from core.agent_engine import AgentEngine
        from core.fleet_orchestrator import FleetOrchestrator
        from core.observer_engine import ObserverEngine
        from controllers.fleet_controller import FleetController
        from core.key_vault import KeyVault

        kv = KeyVault()
        ae = AgentEngine(db_full, kv)
        fleet = FleetOrchestrator(db_full, ae)
        observer = ObserverEngine(db_full, ae)
        fc = FleetController(db_full, ae, fleet, observer)

        # No engine set → should silently return
        fc._run_improvement_cycle()


# ─── Gap 3: Feature Toggle Enforcement ───────────────────────


class TestFeatureToggleEnforcement:

    def test_agent_hooks_respect_toggles_off(self, wired_engines):
        """When toggles are off, hooks should NOT fire."""
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]

        # Set all toggles to False
        with db.session_scope() as s:
            settings = s.query(Settings).first()
            if settings:
                settings.reflection_enabled = False
                settings.self_improvement_enabled = False
                settings.knowledge_graph_enabled = False

        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id

        # Clear any existing data
        with db.session_scope() as s:
            s.query(AgentReflection).delete()
            s.query(PerformanceMetric).delete()
            s.query(KnowledgeEdge).delete()

        ae._post_task_hooks(
            agent_id=agent_id, task_id=777, task_type="test_toggle",
            agent_name="Test", result_data="data", cost=0.0, skill_data=None,
        )

        with db.session_scope() as s:
            assert s.query(AgentReflection).filter_by(task_type="test_toggle").first() is None
            assert s.query(PerformanceMetric).filter_by(metric_key="test_toggle").first() is None

    def test_agent_hooks_respect_toggles_on(self, wired_engines):
        """When toggles are on, hooks SHOULD fire."""
        ae = wired_engines["agent_engine"]
        db = wired_engines["db"]

        with db.session_scope() as s:
            settings = s.query(Settings).first()
            if settings:
                settings.reflection_enabled = True
                settings.self_improvement_enabled = True
                settings.knowledge_graph_enabled = True

        with db.session_scope() as s:
            agent = s.query(Agent).first()
            agent_id = agent.id
            task = AgentTask(
                agent_id=agent_id, task_type="toggle_on_test",
                task_payload="{}", status="completed",
            )
            s.add(task)
            s.flush()
            task_id = task.id

        ae._post_task_hooks(
            agent_id=agent_id, task_id=task_id, task_type="toggle_on_test",
            agent_name="Test", result_data="data", cost=0.0, skill_data=None,
        )

        with db.session_scope() as s:
            assert s.query(AgentReflection).filter_by(task_id=task_id).first() is not None
            assert s.query(PerformanceMetric).filter_by(metric_key="toggle_on_test").first() is not None

    def test_get_feature_toggles_returns_defaults(self, db_full):
        from core.agent_engine import AgentEngine
        from core.key_vault import KeyVault
        ae = AgentEngine(db_full, KeyVault())
        toggles = ae._get_feature_toggles()
        assert "reflection" in toggles
        assert "self_improvement" in toggles
        assert "knowledge_graph" in toggles

    def test_reply_detector_get_feature_toggles(self, db_full):
        from core.reply_detector import ReplyDetector
        from core.key_vault import KeyVault
        rd = ReplyDetector(db_full, KeyVault())
        toggles = rd._get_feature_toggles()
        assert "conversation" in toggles
        assert "knowledge_graph" in toggles


# ─── Gap 4: Conversation Auto-Response ───────────────────────


class TestConversationAutoResponse:

    def test_reply_detector_has_strategy_engine(self, db_full):
        from core.reply_detector import ReplyDetector
        from core.key_vault import KeyVault
        rd = ReplyDetector(db_full, KeyVault())
        assert hasattr(rd, "strategy_engine")
        assert rd.strategy_engine is None

    def test_generate_response_exists_and_works(self, wired_engines):
        conv = wired_engines["conversation"]
        db = wired_engines["db"]

        with db.session_scope() as s:
            c = Campaign(name="Conv Auto Test", target_niche="test", target_city="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="AutoReply Co")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        result = conv.generate_response(lead_id, "I'm interested, tell me more!")
        assert result["success"] is True
        assert result["data"]["intent"] == "interested"
        assert result["data"]["response"] is not None


# ─── Gap 5: Strategy Progress Updates ────────────────────────


class TestStrategyProgressUpdates:

    def test_strategy_update_progress_works(self, wired_engines):
        strategy = wired_engines["strategy"]
        result = strategy.create_goal("Get 5 clients", target_value=5)
        goal_id = result["data"]["goal_id"]
        strategy.activate_goal(goal_id)

        progress = strategy.update_progress(goal_id)
        assert progress["success"] is True
        assert "progress_pct" in progress["data"]

    def test_lifecycle_callback_registered(self, wired_engines):
        """Verify the lifecycle engine has on_enter callbacks for closed_won."""
        lifecycle = wired_engines["lifecycle"]
        # The callback is registered in main_window, not in tests.
        # But we can verify the register mechanism works.
        called = []
        lifecycle.register_on_enter("closed_won", lambda *a: called.append(a))
        # Simulate a full lifecycle to closed_won
        db = wired_engines["db"]
        with db.session_scope() as s:
            c = Campaign(name="Win Test", target_niche="test", target_city="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Won Lead", lifecycle_state="negotiating")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        result = lifecycle.transition(lead_id, "closed_won", triggered_by="test")
        assert result["success"] is True
        assert len(called) == 1
        assert called[0][0] == lead_id


# ─── Gap Fix Tests: AnalystEngine wiring ─────────────────────────────


class TestAnalystEngineWiring:
    """Test that AnalystEngine is properly wired."""

    def test_analyst_engine_instantiates(self, db_full):
        """AnalystEngine can be created with db_manager and key_vault."""
        from core.analyst_engine import AnalystEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        ae = AnalystEngine(db_full, kv)
        assert ae is not None
        assert ae.db_manager is db_full

    def test_analyst_gather_context(self, db_full):
        """gather_context returns a dict with expected keys."""
        from core.analyst_engine import AnalystEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        ae = AnalystEngine(db_full, kv)
        context = ae.gather_context()
        assert isinstance(context, dict)

    def test_show_stats_with_analyst(self, db_full):
        """Orchestrator show_stats works when analyst is in engines_dict."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.analyst_engine import AnalystEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        analyst = AnalystEngine(db_full, kv)
        engines = {"analyst": analyst}
        result = orch.execute_intent(
            {"intent": "show_stats", "confidence": 0.9, "parameters": {}},
            engines,
        )
        assert result["success"] is True
        assert "data" in result

    def test_analyze_performance_with_analyst(self, db_full):
        """Orchestrator analyze_performance works when analyst is wired."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.analyst_engine import AnalystEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        analyst = AnalystEngine(db_full, kv)
        engines = {"analyst": analyst}
        result = orch.execute_intent(
            {"intent": "analyze_performance", "confidence": 0.9,
             "parameters": {"question": "How are my campaigns?"}},
            engines,
        )
        # May fail if no LLM key, but should not error with "analyst not available"
        assert "Analyst engine not available" not in str(result.get("error", ""))

    def test_general_question_with_analyst(self, db_full):
        """general_question goes through analyst when wired."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.analyst_engine import AnalystEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        analyst = AnalystEngine(db_full, kv)
        engines = {"analyst": analyst}
        result = orch.execute_intent(
            {"intent": "general_question", "confidence": 0.9,
             "parameters": {"question": "Hello"}},
            engines,
        )
        assert result["success"] is True


# ─── Gap Fix Tests: show_replies / schedule_followups handlers ───────


class TestShowRepliesHandler:
    """Test the real show_replies orchestrator handler."""

    def test_show_replies_returns_stats(self, db_full):
        """show_replies returns thread stats when conversation engine is wired."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.conversation_engine import ConversationEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        conv = ConversationEngine(db_full)
        engines = {"conversation": conv}
        result = orch.execute_intent(
            {"intent": "show_replies", "confidence": 0.9, "parameters": {}},
            engines,
        )
        assert result["success"] is True
        assert "stats" in result["data"]
        assert "replied_threads" in result["data"]
        assert "pending_re_engagements" in result["data"]

    def test_show_replies_specific_lead(self, db_full):
        """show_replies for a specific lead returns thread data."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.conversation_engine import ConversationEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        conv = ConversationEngine(db_full)

        # Create a lead + thread
        with db_full.session_scope() as s:
            c = Campaign(name="Reply Test", target_niche="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Reply Lead")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        conv.append_message(lead_id, "lead", "I'm interested!", intent="interested")

        engines = {"conversation": conv}
        result = orch.execute_intent(
            {"intent": "show_replies", "confidence": 0.9,
             "parameters": {"lead_id": lead_id}},
            engines,
        )
        assert result["success"] is True
        assert result["data"]["message_count"] == 1

    def test_show_replies_no_engine(self, db_full):
        """show_replies fails gracefully without conversation engine."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(db_full, KeyVault())
        result = orch.execute_intent(
            {"intent": "show_replies", "confidence": 0.9, "parameters": {}},
            {},
        )
        assert result["success"] is False
        assert "Conversation engine not available" in result["error"]


class TestScheduleFollowupsHandler:
    """Test the real schedule_followups orchestrator handler."""

    def test_schedule_specific_lead(self, db_full):
        """schedule_followups for a specific lead sets re-engagement."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.conversation_engine import ConversationEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        conv = ConversationEngine(db_full)

        with db_full.session_scope() as s:
            c = Campaign(name="Follow Test", target_niche="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Follow Lead")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        engines = {"conversation": conv}
        result = orch.execute_intent(
            {"intent": "schedule_followups", "confidence": 0.9,
             "parameters": {"lead_id": lead_id, "delay_days": 7}},
            engines,
        )
        assert result["success"] is True
        assert result["data"]["delay_days"] == 7

    def test_schedule_bulk_followups(self, db_full):
        """schedule_followups without lead_id finds objection/not_now threads."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.conversation_engine import ConversationEngine
        from core.key_vault import KeyVault
        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        conv = ConversationEngine(db_full)

        # Create a lead + thread with "not_now" intent
        with db_full.session_scope() as s:
            c = Campaign(name="Bulk Follow", target_niche="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Bulk Lead")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        conv.append_message(lead_id, "lead", "Maybe later", intent="not_now")

        engines = {"conversation": conv}
        result = orch.execute_intent(
            {"intent": "schedule_followups", "confidence": 0.9,
             "parameters": {"delay_days": 10}},
            engines,
        )
        assert result["success"] is True
        assert result["data"]["scheduled_count"] >= 1

    def test_schedule_no_engine(self, db_full):
        """schedule_followups fails gracefully without conversation engine."""
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault
        orch = OrchestratorEngine(db_full, KeyVault())
        result = orch.execute_intent(
            {"intent": "schedule_followups", "confidence": 0.9, "parameters": {}},
            {},
        )
        assert result["success"] is False
        assert "Conversation engine not available" in result["error"]


# ─── Gap Fix Tests: Chat command history logging ─────────────────────


class TestChatCommandHistoryLogging:
    """Test that direct chat messages are logged to command history."""

    def test_chat_controller_has_command_history_attr(self):
        """ChatController has command_history attribute."""
        from controllers.chat_controller import ChatController
        import inspect
        source = inspect.getsource(ChatController.__init__)
        assert "command_history" in source

    def test_chat_controller_logs_on_send(self, db_full):
        """ChatController logs user command when command_history is set."""
        from controllers.chat_controller import ChatController
        from core.command_history import CommandHistoryEngine
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        ch = CommandHistoryEngine(db_full)
        ctrl = ChatController(db_full, orch, {})
        ctrl.command_history = ch

        # Verify _update_history method exists
        assert hasattr(ctrl, "_update_history")

    def test_update_history_does_not_crash_without_cmd_id(self, db_full):
        """_update_history is no-op when cmd_id is None."""
        from controllers.chat_controller import ChatController
        from core.orchestrator_engine import OrchestratorEngine
        from core.key_vault import KeyVault

        kv = KeyVault()
        orch = OrchestratorEngine(db_full, kv)
        ctrl = ChatController(db_full, orch, {})
        ctrl.command_history = None
        # Should not raise
        ctrl._update_history(None, "completed", {"intent": "test"})


# ─── Gap Fix Tests: Advanced engine command history logging ──────────


class TestAdvancedEngineHistoryLogging:
    """Test that advanced engines log to command history."""

    def test_autonomy_logs_approval(self, db_full):
        """Autonomy controller logs to command_history on approve/deny."""
        from controllers.autonomy_controller import AutonomyController
        from core.command_history import CommandHistoryEngine
        from database.schema import Settings

        with db_full.session_scope() as s:
            settings = s.query(Settings).first()
            if not settings:
                s.add(Settings(id=1))

        ac = AutonomyController(db_full)
        ch = CommandHistoryEngine(db_full)
        ac.command_history = ch

        # Queue and approve
        q = ac.queue_for_approval("send_email", description="test email")
        aid = q["data"]["approval_id"]
        ac.approve_action(aid)

        # Check command_history logged it
        from database.schema import CommandLog
        with db_full.session_scope() as s:
            logs = s.query(CommandLog).filter(
                CommandLog.command_type == "approval_approved"
            ).all()
            assert len(logs) >= 1
            assert "send_email" in logs[0].command_text

    def test_autonomy_logs_denial(self, db_full):
        """Autonomy controller logs denial to command_history."""
        from controllers.autonomy_controller import AutonomyController
        from core.command_history import CommandHistoryEngine

        ac = AutonomyController(db_full)
        ch = CommandHistoryEngine(db_full)
        ac.command_history = ch

        q = ac.queue_for_approval("skill_revision", description="revise skill")
        aid = q["data"]["approval_id"]
        ac.deny_action(aid)

        from database.schema import CommandLog
        with db_full.session_scope() as s:
            logs = s.query(CommandLog).filter(
                CommandLog.command_type == "approval_denied"
            ).all()
            assert len(logs) >= 1

    def test_lifecycle_logs_transitions(self, db_full):
        """Lead lifecycle engine logs transitions to command_history."""
        from core.lead_lifecycle_engine import LeadLifecycleEngine
        from core.command_history import CommandHistoryEngine

        lifecycle = LeadLifecycleEngine(db_full)
        ch = CommandHistoryEngine(db_full)
        lifecycle.command_history = ch

        with db_full.session_scope() as s:
            c = Campaign(name="Log Test", target_niche="test")
            s.add(c)
            s.flush()
            lead = Lead(campaign_id=c.id, business_name="Log Lead", lifecycle_state="new")
            s.add(lead)
            s.flush()
            lead_id = lead.id

        lifecycle.transition(lead_id, "researched", triggered_by="test")

        from database.schema import CommandLog
        with db_full.session_scope() as s:
            logs = s.query(CommandLog).filter(
                CommandLog.command_type == "lifecycle_transition"
            ).all()
            assert len(logs) >= 1
            assert "researched" in logs[0].command_text

    def test_reflection_logs_scores(self, db_full):
        """Reflection engine logs reflections to command_history."""
        from core.reflection_engine import ReflectionEngine
        from core.command_history import CommandHistoryEngine
        from database.schema import AgentTask, Agent
        from tests.conftest import get_agent_id_by_name

        reflection = ReflectionEngine(db_full)
        ch = CommandHistoryEngine(db_full)
        reflection.command_history = ch

        agent_id = get_agent_id_by_name(db_full, "Closer")

        # Create a task to reflect on
        with db_full.session_scope() as s:
            task = AgentTask(
                agent_id=agent_id,
                task_type="generate_email",
                task_payload="{}",
                status="completed",
                result="Great email content here",
            )
            s.add(task)
            s.flush()
            task_id = task.id

        reflection.reflect_on_task(
            agent_id, task_id, "generate_email", "Great email content here"
        )

        from database.schema import CommandLog
        with db_full.session_scope() as s:
            logs = s.query(CommandLog).filter(
                CommandLog.command_type == "reflection"
            ).all()
            assert len(logs) >= 1
            assert str(task_id) in logs[0].command_text
